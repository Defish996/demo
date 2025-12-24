from main import *
import json
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import pymysql
from pymysql.cursors import DictCursor
from datetime import date, datetime  # 需要 datetime 来处理时间戳或日期
import time  # wait_get 和 simulate_alphas 中用到了 time.sleep，确保导入

# 同样的这里要修改数据库配置和你自己的一样
MYSQL_CONFIG = {
    'user': 'root',
    'password': 'hgz9580k.',
    'host': '117.72.46.139',
    'database': 'wq',
    'charset': 'utf8mb4'
}

# --- 全局变量和配置 (从原代码中保留) ---
# selections, combo, REGIONS, neutralizations, delay 已不再直接用于生成 sim_data_list
# 它们现在被认为是已存在于数据库 alpha_json 中的配置

sess = login()  # 初始化会话，simulate_alphas 会用到
alpha_fail_attempt_tolerance = 5  # 每个 alpha 允许的最大失败尝试次数
MAX_WORKERS = 3  # 同时处理的最大alpha数量
failure_count = 0  # simulate_alphas 中用到的全局变量


# --- API 调用函数 (基本保持不变) ---
def wait_get(url: str, max_retries: int = 10) -> "Response":  # type: ignore
    """
    发送带有重试机制的 GET 请求，直到成功或达到最大重试次数。
    此函数会根据服务器返回的 `Retry-After` 头信息进行等待，并在遇到 401 状态码时重新初始化配置。

    Args:
        url (str): 目标 URL。
        max_retries (int, optional): 最大重试次数，默认为 10。

    Returns:
        Response: 请求的响应对象。
    """
    retries = 0
    global sess  # 确保 sess 是可访问的
    while retries < max_retries:
        while True:
            try:
                simulation_progress = sess.get(url)
                if simulation_progress.headers.get("Retry-After", "0") == "0":  # Retry-After 是字符串
                    break
                time.sleep(float(simulation_progress.headers["Retry-After"]))
            except requests.exceptions.RequestException as e:  # 更具体的异常捕获
                print(f"请求 {url} 时发生网络错误: {e}, 等待后重试...")
                time.sleep(5)  # 发生连接错误等，稍等后重试内部循环
                continue  # 继续内部while True循环
            except Exception as e:
                print(f"wait_get 内部发生未知错误: {e}, url: {url}")
                time.sleep(5)
                continue

        if simulation_progress.status_code < 400:
            try:
                # 尝试解析JSON，如果文本不是有效的JSON，split会出问题
                content_type = simulation_progress.headers.get('Content-Type', '')
                if 'application/json' in content_type:
                    # 只有当内容是JSON时才尝试解析
                    sim_data = simulation_progress.json()
                    if isinstance(sim_data,
                                  dict) and "message" in sim_data and "ERROR" in simulation_progress.text:  # 检查message字段和原始文本
                        print(f"回测API返回错误信息 {url}：{sim_data.get('message')}")
                elif "ERROR" in simulation_progress.text:  # 非JSON但包含ERROR
                    print(f"回测API返回非JSON错误文本 {url}：{simulation_progress.text[:200]}")  # 打印部分文本
            except json.JSONDecodeError:
                if "ERROR" in simulation_progress.text:  # 如果JSON解析失败但文本中包含ERROR
                    print(f"回测API返回错误文本 (JSON解析失败) {url}：{simulation_progress.text[:200]}")
            break  # 成功或有message的错误，都跳出重试
        elif simulation_progress.status_code == 401:  # 未授权
            print(f"请求 {url} 遇到401未授权错误，尝试重新登录...")
            sess = login()  # 重新登录
            # 不需要增加 retries，因为这是会话问题，而不是请求本身的问题
            # 但为了避免死循环，如果login持续失败，外部逻辑需要处理
        else:
            print(f"请求 {url} 失败，状态码: {simulation_progress.status_code}, 内容: {simulation_progress.text[:200]}")
            time.sleep(2 ** retries)
            retries += 1
    if retries >= max_retries:
        print(f"达到最大重试次数 {max_retries} 仍然失败: {url}")
    return simulation_progress


def simulate_alphas(db_id,data_for_simulation):  # 参数名修改以示区分
    """
    data_for_simulation: simulation data dictionary
    return alpha list or False on critical failure
    """
    print(
        f"线程 {threading.get_ident()} 开始处理任务: ",db_id)  # 打印当前线程ID和部分信息
    keep_trying = True
    global failure_count  # simulate_alphas内部的失败计数器
    global sess  # simulate_alphas内部使用的会话

    local_failure_count = 0  # 此函数调用的失败计数

    while keep_trying:
        try:
            simulation_response = sess.post('https://api.worldquantbrain.com/simulations', json=data_for_simulation)
            simulation_response.raise_for_status()  # 如果POST请求失败（4xx, 5xx），则抛出异常

            simulation_progress_url = simulation_response.headers['Location']
            children_ids_str = simulation_progress_url.split('/')[-1]
            children_ids = [children_ids_str]  # 假设总是单个child

            alphas_results = []
            for child_id in children_ids:
                child_url = f'https://api.worldquantbrain.com/simulations/{child_id}'
                child_progress_response = wait_get(child_url)

                if child_progress_response.status_code >= 400:
                    print(f"获取子任务 {child_id} 进度失败。状态码: {child_progress_response.status_code}")
                    alphas_results.append(None)  # 标记此子任务失败
                    continue

                try:
                    child_progress = child_progress_response.json()
                except json.JSONDecodeError:
                    print(f"解析子任务 {child_id} 响应失败。响应文本: {child_progress_response.text[:200]}")
                    alphas_results.append(None)
                    continue

                print(f"子任务 {child_id} 状态: {child_progress.get('status')}")
                if child_progress.get('status') in ['CANCELLED', 'ERROR']:  # 增加 'ERROR' 状态
                    print(
                        f"错误：模拟任务 {db_id} 的子任务 {child_id} 状态为 {child_progress.get('status')}, 详情: {child_progress}")
                    alphas_results.append(None)
                elif child_progress.get('status') in ['COMPLETE', 'WARNING']:
                    alphas_results.append(child_progress.get('alpha'))  # 获取alpha ID
                else:  # 其他未完成或未知状态
                    print(f"子任务 {child_id} 状态未完成或未知: {child_progress.get('status')}")
                    alphas_results.append(None)  # 视为未成功获取alpha

            print(f"线程 {threading.get_ident()} 模拟结果: {alphas_results}")
            return alphas_results  # 返回包含alpha ID或None的列表

        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP错误发生在 simulate_alphas (POST): {http_err}, data: {str(data_for_simulation)[:100]}")
            if http_err.response.status_code == 401:
                print("会话可能已过期，尝试重新登录...")
                sess = login()
                # 不立即重试，让外部循环或重试机制处理
            local_failure_count += 1

        except requests.exceptions.RequestException as req_err:  # 其他网络错误，如DNS、连接超时
            print(f"网络请求错误发生在 simulate_alphas: {req_err}, data: {str(data_for_simulation)[:100]}")
            local_failure_count += 1

        except KeyError as ke:  # 比如 'Location' 不在 headers 里
            print(f"关键信息缺失 (KeyError: {ke})，可能POST请求未成功。data: {str(data_for_simulation)[:100]}")
            local_failure_count += 1

        except Exception as e:
            print(f"simulate_alphas中发生未知异常: {e}, data: {str(data_for_simulation)[:100]}")
            local_failure_count += 1

        # 重试逻辑
        if local_failure_count > 0:  # 只有发生错误才进入重试判断
            print(f"尝试次数 {local_failure_count}/{alpha_fail_attempt_tolerance}。等待15秒后重试...")
            time.sleep(15)
            failure_count += 1  # 更新全局的failure_count，用于判断是否需要重新login

            if failure_count >= alpha_fail_attempt_tolerance:  # 此处用全局的failure_count判断是否需要重新login
                print("全局失败次数达到阈值，尝试重新登录...")
                sess = login()
                failure_count = 0  # 重置全局失败计数器

            if local_failure_count >= alpha_fail_attempt_tolerance:  # 如果此函数内的尝试次数达到上限
                print(f"此任务失败次数已达上限 {alpha_fail_attempt_tolerance}，放弃处理。")
                return False  # 表示此任务彻底失败
        else:  # 如果没有错误，说明成功了
            keep_trying = False  # 退出while循环

    return False  # 如果循环因其他原因退出（理论上不应该）


# --- 数据库交互函数 ---
def get_db_connection():
    """建立并返回一个新的数据库连接"""
    return pymysql.connect(**MYSQL_CONFIG, cursorclass=DictCursor)


def fetch_sim_configs_from_db(target_add_date_str: str):
    """从数据库获取待处理的模拟配置"""
    conn = get_db_connection()
    sim_configs = []
    try:
        with conn.cursor() as cursor:
            # 选择id和alpha_json，条件是alpha_id为空且add_date匹配
            sql = "SELECT id, alpha_json FROM sa_alpha WHERE up_date IS NULL AND add_date = %s"
            cursor.execute(sql, (target_add_date_str,))
            sim_configs = cursor.fetchall()  # [{'id': X, 'alpha_json': 'json_string'}, ...]
    except pymysql.Error as e:
        print(f"从数据库读取数据失败: {e}")
    finally:
        if conn:
            conn.close()

    print(f"为日期 {target_add_date_str} 从数据库获取到 {len(sim_configs)} 条待处理记录。")
    return sim_configs


def update_alpha_in_db(db_id: int, new_alpha_id: str = None):
    """更新数据库中的alpha_id和up_date"""
    conn = get_db_connection()
    success = False
    try:
        with conn.cursor() as cursor:
            current_date_str = date.today().isoformat()
            if new_alpha_id:
                sql = "UPDATE sa_alpha SET alpha_id = %s, up_date = %s WHERE id = %s"
                cursor.execute(sql, (new_alpha_id, current_date_str, db_id))
            else:
                # 如果 new_alpha_id 为 None 或空字符串，只更新 up_date
                sql = "UPDATE sa_alpha SET up_date = %s WHERE id = %s"
                cursor.execute(sql, (current_date_str, db_id))
            conn.commit()
            success = True
            action = f"已更新 alpha_id 为 {new_alpha_id}" if new_alpha_id else "仅更新 up_date"
            print(f"数据库记录 ID {db_id}: {action}。")
    except pymysql.Error as e:
        print(f"更新数据库记录 ID {db_id} 失败: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
    return success


# --- 任务处理函数 (用于线程池) ---
import threading  # 用于获取线程ID，方便日志追踪


def process_simulation_task(db_record):
    """
    处理单个数据库记录：解析json，调用API，更新数据库
    db_record: {'id': int, 'alpha_json': str}
    """
    db_id = db_record['id']
    alpha_json_str = db_record['alpha_json']

    if not alpha_json_str:
        print(f"记录 ID {db_id}: alpha_json 为空，跳过处理并更新up_date。")
        update_alpha_in_db(db_id, None)
        return

    try:
        # 解析JSON字符串为字典
        simulation_params = json.loads(alpha_json_str)
    except json.JSONDecodeError as e:
        print(f"记录 ID {db_id}: JSON解析失败 - {e}。alpha_json: {alpha_json_str[:100]}... 跳过处理并更新up_date。")
        update_alpha_in_db(db_id, None)  # 标记为已尝试
        return

    # 调用 simulate_alphas 函数
    # simulate_alphas 返回一个列表，通常包含一个alpha ID或None，或返回False表示严重失败
    api_results = simulate_alphas(db_id,simulation_params)

    returned_alpha_id = None
    if isinstance(api_results, list) and len(api_results) > 0:
        # 取第一个结果，如果它是有效的alpha ID字符串
        if api_results[0] and isinstance(api_results[0], str) and api_results[0].strip():
            returned_alpha_id = api_results[0].strip()
    elif api_results is False:
        print(f"记录 ID {db_id}: simulate_alphas 返回 False，表示任务处理严重失败。")
        # 这种情况也只更新up_date，不更新alpha_id

    # 根据API结果更新数据库
    update_alpha_in_db(db_id, returned_alpha_id)


# --- 主程序逻辑 ---
if __name__ == "__main__":
    # 用户指定要处理的 add_date
    target_add_date_input = "2025-10-13"
    try:
        # 验证日期格式
        datetime.strptime(target_add_date_input, '%Y-%m-%d')
    except ValueError:
        print("日期格式无效，请输入 YYYY-MM-DD 格式的日期。")
        exit()

    # 1. 从数据库获取待处理的配置
    tasks_to_process = fetch_sim_configs_from_db(target_add_date_input)

    if not tasks_to_process:
        print(f"日期 {target_add_date_input} 没有需要处理的记录，或数据库连接失败。")
    else:

        print(f"准备使用 {MAX_WORKERS} 个线程处理 {len(tasks_to_process)} 个任务...")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # 为每个任务提交到线程池
            future_to_task = {executor.submit(process_simulation_task, task): task for task in tasks_to_process}

            for future in concurrent.futures.as_completed(future_to_task):
                task_info = future_to_task[future]
                try:
                    future.result()  # 获取结果，主要是为了捕获在 process_simulation_task 中未捕获的异常
                    # print(f"任务 (DB ID: {task_info['id']}) 完成。") # 可以在 process_simulation_task 内部打印
                except Exception as exc:
                    print(f"任务 (DB ID: {task_info['id']}) 执行时产生异常: {exc}")

        print("所有任务处理完毕。")