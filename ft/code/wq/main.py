import requests
from os import environ
from time import sleep
import time
import json
import pandas as pd
import random
import pickle
from itertools import product
from itertools import combinations
from collections import defaultdict
import pickle
import pytz
import datetime
import sys


def get_alpha_performance_comparison(s, alpha_id, type="stats"):
    """获取单个 Alpha 因子的性能对比数据"""
    while True:
        result = s.get(
            f"https://api.worldquantbrain.com/users/self/alphas/{alpha_id}/before-and-after-performance"
        )
        
        # 处理速率限制
        if "retry-after" in result.headers:
            time.sleep(float(result.headers["Retry-After"]))
        else:
            break
    
    res = result.json()
    return res['stats'] if type == "stats" else res

def get_alpha_performance_comparisons(s, alpha_ids):
    """批量获取多个 Alpha 因子的性能对比数据"""
    alpha_performances = []
    
    for id in alpha_ids:
        stats = get_alpha_performance_comparison(s, id)
        alpha_performances.append({
            "id": id, 
            "before": stats['before'], 
            "after": stats['after']
        })
    
    return alpha_performances

def calculate_alpha_importance(alpha_performances):
    """计算 Alpha 因子重要性评分并排序"""
    alpha_importance = []
    
    for ap in alpha_performances:
        # 权重配置（可根据需求调整）
        weights = {
            'fitness': 10,
            'sharpe': 8,
            'returns': 6,
            'margin': 5,
            'turnover': -4,
            'drawdown': -3
        }
        
        # 计算归一化重要性评分
        importance = round(
            sum([
                (ap['after'][metric] - ap['before'][metric]) / 
                abs(ap['before'][metric]) * weights[metric]
                for metric in weights
            ]),
            4  # 保留4位小数
        )
        
        alpha_importance.append({"id": ap['id'], "importance": importance})
    
    # 按重要性降序排序
    return sorted(alpha_importance, key=lambda x: x["importance"], reverse=True)


 
basic_ops = ["kth_element","jump_decay","hump","hump_decay","days_from_last_change","arc_cos","arc_sin","ceiling","floor","sign","to_nan", 
"log_diff", 
"sqrt", "reverse", "inverse", "rank", "zscore",
"log", 
"s_log_1p",
             #'fraction', 
             'quantile', "normalize", "scale_down", "power"]
 
ts_ops = ["last_diff_value","ts_rank" , "ts_zscore", "ts_delta",  "ts_sum", "ts_product",
          #"ts_ir", 
          "ts_std_dev", "ts_mean",  "ts_arg_min", "ts_arg_max","ts_av_diff","ts_count_nans",
            #"ts_min_diff","ts_max_diff",
              #"ts_returns", 
              "ts_scale", #"ts_skewness",
               # "ts_kurtosis",  
          "ts_quantile"]

ts_use = ["ts_min", "ts_max", "ts_delay", "ts_median",]
 
arsenal = [#咱不可用"ts_moment", "ts_entropy", "ts_min_max_cps", "ts_min_max_diff",  'sigmoid',"ts_percentage","ts_co_skewness",,  "ts_theilsen"
            #暂未设置 ,
            "inst_tvr", 
           "ts_decay_exp_window",  "vector_neut", 
           "signed_power"]
 
twin_field_ops = [
    #3参数 暂未设置"vector_proj","ts_corr", "ts_covariance", "ts_co_kurtosis"
    ]
 
group_ops = ["group_vector_neut", "group_rank","group_max", "group_median", "group_min", "group_zscore","group_scale","group_neutralize",
             "group_neutralize", "group_normalize","group_mean"]
              
                
 
group_ac_ops = [#暂无权限"group_sum", , "group_std_dev"
         ]

special_list = ["convert"]

ops_set = basic_ops + ts_ops + arsenal + group_ops + ts_use + twin_field_ops + special_list

def login():
    
    username = "3133866171@qq.com"
    password = "wyq20021113."
 
    # Create a session to persistently store the headers
    s = requests.Session()
 
    # Save credentials into session
    s.auth = (username, password)
 
    # Send a POST request to the /authentication API
    response = s.post('https://api.worldquantbrain.com/authentication')
    print(response.content)
    return s  
 
def locate_alpha(s, alpha_id):
    alpha = s.get("https://api.worldquantbrain.com/alphas/" + alpha_id)
    string = alpha.content.decode('utf-8')
    metrics = json.loads(string)
    #print(metrics["regular"]["code"])
    
    dateCreated = metrics["dateCreated"]
    sharpe = metrics["is"]["sharpe"]
    fitness = metrics["is"]["fitness"]
    turnover = metrics["is"]["turnover"]
    margin = metrics["is"]["margin"]
    
    triple = [sharpe, fitness, turnover, margin, dateCreated]
 
    return triple
 
def set_alpha_properties(
    s,
    alpha_id,
    name: str = None,
    color: str = None,
    selection_desc: str = "None",
    combo_desc: str = "None",
    tags: str = ["ace_tag"],
):
    """
    Function changes alpha's description parameters
    """
 
    params = {
        "color": color,
        "name": name,
        "tags": tags,
        "category": None,
        "regular": {"description": None},
        "combo": {"description": combo_desc},
        "selection": {"description": selection_desc},
    }
    response = s.patch(
        "https://api.worldquantbrain.com/alphas/" + alpha_id, json=params
    )
 
def check_submission(alpha_bag, gold_bag, start):
    depot = []
    s = login()
    for idx, g in enumerate(alpha_bag):
        if idx < start:
            continue
        if idx % 5 == 0:
            print(idx)
        if idx % 200 == 0:
            s = login()
        #print(idx)
        pc = get_check_submission(s, g)
        if pc == "sleep":
            sleep(100)
            s = login()
            alpha_bag.append(g)
        elif pc != pc:
            # pc is nan
            print("check self-corrlation error")
            sleep(100)
            alpha_bag.append(g)
        elif pc == "fail":
            continue
        elif pc == "error":
            depot.append(g)
        else:
            print(g)
            gold_bag.append((g, pc))
    print(depot)
    return gold_bag

def get_check_submission(s, alpha_id):
    while True:
        result = s.get("https://api.worldquantbrain.com/alphas/" + alpha_id + "/check")
        if "retry-after" in result.headers:
            time.sleep(float(result.headers["Retry-After"]))
        else:
            break
    try:
        if result.json().get("is", 0) == 0:
            print("logged out")
            return "sleep"
        checks_df = pd.DataFrame(
                result.json()["is"]["checks"]
        )
        pc = checks_df[checks_df.name == "PROD_CORRELATION"]["value"].values[0]
        if not any(checks_df["result"] == "FAIL"):
            return pc
        else:
            return "fail"
    except:
        print("catch: %s"%(alpha_id))
        return "error"
            
def get_vec_fields(fields):

    vec_ops = ["vec_avg", "vec_sum", #"vec_ir", 
               "vec_max", "vec_min","vec_count", "vec_choose","vec_percentage",
               #"vec_skewness","vec_stddev",
               ]
    vec_fields = []
 
    for field in fields:
        for vec_op in vec_ops:
            if vec_op == "vec_choose":
                vec_fields.append("%s(%s, nth=-1)"%(vec_op, field))
                vec_fields.append("%s(%s, nth=0)"%(vec_op, field))
            else:
                vec_fields.append("%s(%s)"%(vec_op, field))
 
    return(vec_fields)

def multi_simulate(alpha_pools, neut, region, universe, start):

    s = login()

    brain_api_url = 'https://api.worldquantbrain.com'

    for x, pool in enumerate(alpha_pools):
        if x < start: continue
        progress_urls = []
        for y, task in enumerate(pool):
            # 10 tasks, 10 alpha in each task
            sim_data_list = generate_sim_data(task, region, universe, neut)
            try:
                simulation_response = s.post('https://api.worldquantbrain.com/simulations', json=sim_data_list)
                simulation_progress_url = simulation_response.headers['Location']
                progress_urls.append(simulation_progress_url)
            except:
                print(" loc key error")# 参数设置有问题
                # sleep(600)
                s = login()

        print("pool %d task %d post done"%(x,y))

        for j, progress in enumerate(progress_urls):
            try:
                while True:
                    simulation_progress = s.get(progress)
                    if simulation_progress.headers.get("Retry-After", 0) == 0:
                        break
                    #print("Sleeping for " + simulation_progress.headers["Retry-After"] + " seconds")
                    sleep(float(simulation_progress.headers["Retry-After"]))

                status = simulation_progress.json().get("status", 0)
                if status != "COMPLETE": # 回测失败, 株连九族(缺点), alpha表达式错误
                    print(f"Not complete: {progress}, task: {pool[j]}")

                """
                #alpha_id = simulation_progress.json()["alpha"]
                children = simulation_progress.json().get("children", 0)
                children_list = []
                for child in children:
                    child_progress = s.get(brain_api_url + "/simulations/" + child)
                    alpha_id = child_progress.json()["alpha"]

                    set_alpha_properties(s, # 给每个alpha加颜色 耗时, 所以暂时不考虑
                            # 可以考虑开一个新的进程, 然后数据库进行在本地取名的操作后的保存, 减少该进程的耗时
                            alpha_id,
                            name = "%s"%name,
                            color = None,)
                """
            except KeyError:
                print("look into: %s"%progress)
            except:
                print("other")


        print("pool %d task %d simulate done"%(x, y))
    
    print("Simulate done")

#task
def generate_sim_data(alpha_list, region, uni, neut):
    sim_data_list = []
    for alpha, decay in alpha_list:
        simulation_data = {
            'type': 'REGULAR',
            'settings': {
                'instrumentType': 'EQUITY',
                'region': region,
                'universe': uni,
                'delay': 1,
                'decay': decay,
                'neutralization': neut,
                'truncation': 0.08,
                'pasteurization': 'ON',
                'unitHandling': 'VERIFY',
                'nanHandling': 'ON',
                'language': 'FASTEXPR',
                'visualization': False,
            },
            'regular': alpha}

        sim_data_list.append(simulation_data)
    return sim_data_list

def load_task_pool(alpha_list, limit_of_children_simulations, limit_of_multi_simulations):
    '''
    Input:
        alpha_list : list of (alpha, decay) tuples
        limit_of_multi_simulations : number of children simulation in a multi-simulation
        limit_of_multi_simulations : number of simultaneous multi-simulations
    Output:
        task : [10 * (alpha, decay)] for a multi-simulation
        pool : [10 * [10 * (alpha, decay)]] for simultaneous multi-simulations # pool是总的
        pools : [[10 * [10 * (alpha, decay)]]]

    '''
    tasks = [alpha_list[i:i + limit_of_children_simulations] for i in range(0, len(alpha_list), limit_of_children_simulations)]
    # 一个task是一个总的
    pools = [tasks[i:i + limit_of_multi_simulations] for i in range(0, len(tasks), limit_of_multi_simulations)] # 10个一起
    return pools

def get_datasets(
    s,
    instrument_type: str = 'EQUITY',
    region: str = 'USA',
    delay: int = 1,
    universe: str = 'TOP3000'
):
    url = "https://api.worldquantbrain.com/data-sets?" +\
        f"instrumentType={instrument_type}&region={region}&delay={str(delay)}&universe={universe}"
    result = s.get(url)
    datasets_df = pd.DataFrame(result.json()['results'])
    return datasets_df
 
def get_datafields(
    s,
    instrument_type: str = 'EQUITY',
    region: str = 'USA',
    delay: int = 1,
    universe: str = 'TOP3000',
    dataset_id: str = '',
    search: str = ''
):
    if len(search) == 0:
        url_template = "https://api.worldquantbrain.com/data-fields?" +\
            f"&instrumentType={instrument_type}" +\
            f"&region={region}&delay={str(delay)}&universe={universe}&dataset.id={dataset_id}&limit=50" +\
            "&offset={x}"
        count = s.get(url_template.format(x=0)).json()['count'] 
        
    else:
        url_template = "https://api.worldquantbrain.com/data-fields?" +\
            f"&instrumentType={instrument_type}" +\
            f"&region={region}&delay={str(delay)}&universe={universe}&limit=50" +\
            f"&search={search}" +\
            "&offset={x}"
        count = 100
    
    datafields_list = []
    for x in range(0, count, 50):
        datafields = s.get(url_template.format(x=x))
        datafields_list.append(datafields.json()['results'])
 
    datafields_list_flat = [item for sublist in datafields_list for item in sublist]
 
    datafields_df = pd.DataFrame(datafields_list_flat)
    return datafields_df

def process_datafields(df, data_type):

    if data_type == "matrix":
        datafields = df[df['type'] == "MATRIX"]["id"].tolist()
    elif data_type == "vector":
        datafields = get_vec_fields(df[df['type'] == "VECTOR"]["id"].tolist())

    tb_fields = []
    for field in datafields:
        tb_fields.append("winsorize(ts_backfill(%s, 120), std=4)"%field)
    return tb_fields
 
def view_alphas(gold_bag):
    s = login()
    sharp_list = []
    for gold, pc in gold_bag:

        triple = locate_alpha(s, gold)
        info = [triple[0], triple[2], triple[3], triple[4], triple[5], triple[6], triple[1]]
        info.append(pc)
        sharp_list.append(info)

    sharp_list.sort(reverse=True, key = lambda x : x[1])
    for i in sharp_list:
        print(i)
        
    with open("sharp_list.txt", "w") as f:
        for t in sharp_list:
            f.write(str(t) + "\n")
 
def locate_alpha(s, alpha_id):
    while True:
        alpha = s.get("https://api.worldquantbrain.com/alphas/" + alpha_id)
        if "retry-after" in alpha.headers:
            time.sleep(float(alpha.headers["Retry-After"]))
        else:
            break
    string = alpha.content.decode('utf-8')
    metrics = json.loads(string)
    #print(metrics["regular"]["code"])
    
    dateCreated = metrics["dateCreated"]
    sharpe = metrics["is"]["sharpe"]
    fitness = metrics["is"]["fitness"]
    turnover = metrics["is"]["turnover"]
    margin = metrics["is"]["margin"]
    decay = metrics["settings"]["decay"]
    exp = metrics['regular']['code']
    
    triple = [alpha_id, exp, sharpe, turnover, fitness, margin, dateCreated, decay]
    return triple
 
 
def convert_to_est(china_time_str):
    # 将中国时间字符串转换为datetime对象
    china_time = datetime.datetime.strptime(china_time_str, "%m-%d %H:%M:%S")
    # 假设年份是当前年份
    china_time = china_time.replace(year=datetime.datetime.now().year)

    # 定义中国时区和美国东部时区
    china_tz = pytz.timezone('Asia/Shanghai')
    est_tz = pytz.timezone('US/Eastern')

    # 将中国时间转换为UTC时间
    china_time = china_tz.localize(china_time)
    utc_time = china_time.astimezone(pytz.utc)

    # 将UTC时间转换为美国东部时间
    est_time = utc_time.astimezone(est_tz)   
    return est_time.strftime("%Y-%m-%dT%H:%M:%S-05:00")

def get_alphas(start_date, end_date, sharpe_th, fitness_th, region, alpha_num, usage):
    s = login()
    output = []
    count = 0
   
    # 转换时间格式
    start_date_est = convert_to_est(start_date)
    end_date_est = convert_to_est(end_date)
   
    for i in range(0, alpha_num, 100):
        print(i)
        url_e = "https://api.worldquantbrain.com/users/self/alphas?limit=100&offset=%d"%(i) \
                + "&status=UNSUBMITTED%1FIS_FAIL&dateCreated%3E=" + start_date_est  \
                + "&dateCreated%3C=" + end_date_est \
                + "&is.fitness%3E" + str(fitness_th) + "&is.sharpe%3E" \
                + str(sharpe_th) + "&settings.region=" + region + "&order=-is.sharpe&hidden=false&type!=SUPER"
        url_c = "https://api.worldquantbrain.com/users/self/alphas?limit=100&offset=%d"%(i) \
                + "&status=UNSUBMITTED%1FIS_FAIL&dateCreated%3E=" + start_date_est  \
                + "&dateCreated%3C=" + end_date_est \
                + "&is.fitness%3C-" + str(fitness_th) + "&is.sharpe%3C-" \
                + str(sharpe_th) + "&settings.region=" + region + "&order=is.sharpe&hidden=false&type!=SUPER"
        urls = [url_e]
        if usage != "submit":
            urls.append(url_c)
        for url in urls:
            response = s.get(url)
            try:
                alpha_list = response.json()["results"]
                print(response.json())
                for j in range(len(alpha_list)):
                    alpha_id = alpha_list[j]["id"]
                    name = alpha_list[j]["name"]
                    dateCreated = alpha_list[j]["dateCreated"]
                    sharpe = alpha_list[j]["is"]["sharpe"]
                    fitness = alpha_list[j]["is"]["fitness"]
                    turnover = alpha_list[j]["is"]["turnover"]
                    margin = alpha_list[j]["is"]["margin"]
                    returns = alpha_list[j]["is"]["returns"]
                    drawdown = alpha_list[j]["is"]["drawdown"]
                    longCount = alpha_list[j]["is"]["longCount"]
                    shortCount = alpha_list[j]["is"]["shortCount"]
                    decay = alpha_list[j]["settings"]["decay"]
                    exp = alpha_list[j]['regular']['code']
                    count += 1
                    if (longCount + shortCount) > 1200:
                        if sharpe < -sharpe_th:
                            exp = "-%s"%exp
                        rec = [alpha_id, exp, sharpe, turnover, fitness, margin, returns, drawdown, dateCreated, decay]
                        print(rec)
                        if turnover > 0.7:
                            rec.append(decay*4)
                        elif turnover > 0.6:
                            rec.append(decay*3+3)
                        elif turnover > 0.5:
                            rec.append(decay*3)
                        elif turnover > 0.4:
                            rec.append(decay*2)
                        elif turnover > 0.35:
                            rec.append(decay+4)
                        elif turnover > 0.3:
                            rec.append(decay+2)
                        output.append(rec)
            except:
                print("%d finished re-login"%i)
                s = login()
    print("count: %d"%count)
    return output

# def get_alphas(start_date, end_date, sharpe_th, fitness_th, region, alpha_num, usage):
#     s = login()
#     output = []
#     # 3E large 3C less
#     count = 0
#     start_year = 2025
#     end_year = 2026
#     for i in range(0, alpha_num, 100):
#         print(i)
#         url_e = "https://api.worldquantbrain.com/users/self/alphas?limit=100&offset=%d"%(i) \
#         + "&status=UNSUBMITTED%1FIS_FAIL&dateCreated%3E=" + str(start_year) + "-" + start_date  \
#         + "T00:00:00-04:00&dateCreated%3C" + str(end_year) + "-" + end_date \
#         + "T00:00:00-04:00&is.fitness%3E" + str(fitness_th) + "&is.sharpe%3E" \
#         + str(sharpe_th) + "&settings.region=" + region + "&order=-is.sharpe&hidden=false&type!=SUPER"

#         url_c = "https://api.worldquantbrain.com/users/self/alphas?limit=100&offset=%d"%(i) \
#         + "&status=UNSUBMITTED%1FIS_FAIL&dateCreated%3E=" + str(start_year) + "-" + start_date  \
#         + "T00:00:00-04:00&dateCreated%3C" + str(end_year) + "-" + end_date \
#         + "T00:00:00-04:00&is.fitness%3C-" + str(fitness_th) + "&is.sharpe%3C-" \
#         + str(sharpe_th) + "&settings.region=" + region + "&order=is.sharpe&hidden=false&type!=SUPER"
#         urls = [url_e]
#         if usage != "submit":
#             urls.append(url_c)
#         for url in urls:
#             response = s.get(url)
#             #print(response.json())
#             try:
#                 alpha_list = response.json()["results"]
#                 #print(response.json())
#                 for j in range(len(alpha_list)):
#                     alpha_id = alpha_list[j]["id"]
#                     name = alpha_list[j]["name"]
#                     dateCreated = alpha_list[j]["dateCreated"]
#                     sharpe = alpha_list[j]["is"]["sharpe"]
#                     fitness = alpha_list[j]["is"]["fitness"]
#                     turnover = alpha_list[j]["is"]["turnover"]
#                     margin = alpha_list[j]["is"]["margin"]
#                     longCount = alpha_list[j]["is"]["longCount"]
#                     shortCount = alpha_list[j]["is"]["shortCount"]
#                     decay = alpha_list[j]["settings"]["decay"]
#                     exp = alpha_list[j]['regular']['code']
#                     count += 1
#                     #if (sharpe > 1.2 and sharpe < 1.6) or (sharpe < -1.2 and sharpe > -1.6):
#                     if (longCount + shortCount) > 100:
#                         if sharpe < -sharpe_th:
#                             exp = "-%s"%exp
#                         rec = [alpha_id, exp, sharpe, turnover, fitness, margin, dateCreated, decay]
#                         print(rec)
#                         if turnover > 0.7:# turnover是手续费 return是回报
#                             rec.append(decay*4)
#                         elif turnover > 0.6:
#                             rec.append(decay*3+3)
#                         elif turnover > 0.5:
#                             rec.append(decay*3)
#                         elif turnover > 0.4:
#                             rec.append(decay*2)
#                         elif turnover > 0.35:
#                             rec.append(decay+4)
#                         elif turnover > 0.3:
#                             rec.append(decay+2)
#                         output.append(rec)
#             except:
#                 print("%d finished re-login"%i)
#                 s = login()

#     print("count: %d"%count)
#     return output
 
def transform(next_alpha_recs, region):
    output = []
    for rec in next_alpha_recs:
        
        decay = rec[-1]
        exp = rec[1]
        output.append([exp,decay])
    output_dict = {region : output}
    return output_dict



# 字段索引常量（提高可读性和维护性）
ALPHA_ID, EXP, SHARPE, TURNOVER, FITNESS, MARGIN, RETURNS, DRAWDOWN, DATE_CREATED, DECAY = range(10)

def extract_field_from_exp(exp: str) -> str:
    """从表达式中提取第一个参数作为 field，失败返回 'unknown'"""
    try:
        last_open = exp.rfind('(')
        if last_open == -1 or last_open >= len(exp) - 1:
            return "unknown"
        rest = exp[last_open + 1:].strip()
        for i, ch in enumerate(rest):
            if ch in ',)':
                return rest[:i].strip() or "unknown"
        return rest.strip() or "unknown"
    except Exception:
        return "unknown"

def prune(next_alpha_recs, prefix: str = "", keep_num: int = 5):
    """
    剪枝逻辑：
    - Sharpe >= 0: 需满足 returns > drawdown，按多目标排序
    - Sharpe < 0: 不检查 returns/drawdown，按 fitness 越小越好排序
    - 合并后按 |fitness| 降序取 top-k
    """
    # Step 1: 可选前缀过滤
    # if prefix:
    #     filtered_recs = [rec for rec in next_alpha_recs if prefix in rec[EXP]]
    # else:
    filtered_recs = next_alpha_recs

    groups = defaultdict(list)

    for rec in filtered_recs:
        try:
            sharpe = float(rec[SHARPE])
            returns = float(rec[RETURNS])
            drawdown = float(rec[DRAWDOWN])
            fitness = float(rec[FITNESS])
        except (ValueError, TypeError, IndexError):
            continue  # 跳过非法记录

        # === 新规则：returns > drawdown 仅对 sharpe >= 0 生效 ===
        if sharpe >= 0 and returns <= drawdown:
            continue  # Sharpe ≥ 0 但收益未跑赢回撤，剔除

        # Sharpe < 0 的策略无此限制，直接通过

        field = extract_field_from_exp(rec[EXP])
        groups[field].append(rec)

    output = []
    for field, recs in groups.items():
        pos_sharpe = []   # sharpe >= 0
        neg_sharpe = []   # sharpe < 0

        for rec in recs:
            s = float(rec[SHARPE])
            if s >= 0:
                pos_sharpe.append(rec)
            else:
                neg_sharpe.append(rec)

        # 正 Sharpe：常规多目标排序（sharpe 主导）
        pos_sorted = sorted(
            pos_sharpe,
            key=lambda r: (
                -float(r[SHARPE]),      # 高 sharpe 优先
                -float(r[FITNESS]),
                -float(r[MARGIN]),
                -float(r[RETURNS]),
                float(r[DRAWDOWN])      # drawdown 越小越好
            )
        )

        # 负 Sharpe：fitness 越小越好（主键），其他次要
        neg_sorted = sorted(
            neg_sharpe,
            key=lambda r: (
                float(r[FITNESS]),      # fitness 升序：-5 < -1 → -5 更好
                -float(r[MARGIN]),      # 次要：margin 越高越好
                -float(r[RETURNS]),
                float(r[DRAWDOWN])
            )
        )

        # 合并：按 |fitness| 降序（即 -abs(fitness) 升序）
        merged = []
        for rec in pos_sorted:
            fit = float(rec[FITNESS])
            merged.append((-abs(fit), 0, rec))
        for rec in neg_sorted:
            fit = float(rec[FITNESS])
            merged.append((-abs(fit), 1, rec))

        merged.sort(key=lambda x: (x[0], x[1]))  # 先按 |fitness| 大到小，再稳定排序

        top_recs = [item[2] for item in merged[:keep_num]]
        output.extend([rec[EXP], rec[DECAY]] for rec in top_recs)

    return output

def first_order_factory(fields, ops_set, region):
    alpha_set = []
    #for field in fields:
    for field in fields:
        #reverse op does the work
        alpha_set.append(field)
        #alpha_set.append("-%s"%field)
        for op in ops_set:
            if op == "quantile":
                #quantile(x, driver = gaussian, sigma = 1.0)
                sigma_list = [0.2, 0.5, 0.8, 1.0]
                for s in sigma_list:
                    alpha = f'{op}({field}, driver=gaussian, sigma={s})'
                    alpha_set.append(alpha)

            elif op == "ts_percentage":
 
                alpha_set += ts_comp_factory(op, field, "percentage", [ 0.5])#,0.2, 0.8])
                #alpha_set += ts_comp_factory(op, field, "percentage", [0.5])
 
            elif op == "ts_decay_exp_window":
 
                alpha_set += ts_comp_factory(op, field, "factor", [0.5 ])#0.2, 0.8])
                #alpha_set += ts_comp_factory(op, field, "factor", [0.5])
 
 
            elif op == "ts_moment":
 
                # alpha_set += ts_comp_factory(op, field, "k", [2, 3, 4])
                alpha_set += ts_comp_factory(op, field, "k", [3])
 
            elif op == "ts_entropy":
 
                # alpha_set += ts_comp_factory(op, field, "buckets", [5, 10, 15, 20])
                alpha_set += ts_comp_factory(op, field, "buckets", [10])
 
            elif op.startswith("ts_") or op == "inst_tvr" or op == "jump_decay" or op == "kth_element" or op == "last_diff_value":
 
                alpha_set += ts_factory(op, field)
 
            elif op.startswith("group_"):
 
                alpha_set += group_factory(op, field, region)
 
            elif op.startswith("vector"):
 
                alpha_set += vector_factory(op, field)
 
            elif op == "signed_power":
 
                alpha = "%s(%s, 2)"%(op, field)
                alpha_set.append(alpha)
            elif op == "replace":
                #replace (returns, target=0.1, dest=0)
                for t in (0.1, 0.2):
                    alpha_set.append(f"{op}({field},target={t},dest=0)")

            elif op == "power":
                alpha = "%s(2.7132, %s)"%(op, field)
                alpha_set.append(alpha)
                
            elif op == "hump_decay":
                alpha = "%s(%s, p=0.1, relative=True)"%(op, field)
                alpha_set.append(alpha)
                
            elif op == "hump":
                #hump(-ts_delta(close, 5), hump = 0.00001)
                alpha = "%s(%s, hump = 0.00001)"%(op, field)
                alpha_set.append(alpha)


            elif op == "to_nan":
                #to_nan(alpha, value=0, reverse=false)
                alpha = "%s(%s, value=0, reverse=false)"%(op, field)
                alpha_set.append(alpha)
                alpha = "%s(%s, value=0, reverse=true)"%(op, field)
                alpha_set.append(alpha)

            elif op == "rank":
                #rank(x, rate=2)
                alpha = "%s(%s, rate=2)"%(op,field)
                alpha_set.append(alpha)

            elif op == "normalize":
                #normalize(x, useStd = false, limit = 0.0)
                alpha = "%s(%s, useStd = false, limit = 0.0)"%(op,field)
                alpha_set.append(alpha)
                alpha = "%s(%s, useStd = true, limit = 0.0)"%(op,field)
                alpha_set.append(alpha)

            elif op == "scale_down":
                #scale_down(x,constant=0)
                alpha = "%s(%s, constant=0)"%(op,field)
                alpha_set.append(alpha)
            
            elif op == "convert":
                #convert(x, mode = "dollar2share")
                alpha = "%s(%s, mode = 'dollar2share')"%(op,field)
                alpha_set.append(alpha)

            else:
                alpha = "%s(%s)"%(op, field)
                alpha_set.append(alpha)
 
    return alpha_set
    
def get_group_second_order_factory(first_order, group_ops, region):
    second_order = []
    for fo in first_order:
        for group_op in group_ops:
            second_order += group_factory(group_op, fo, region)
    return second_order
 
def get_ts_second_order_factory(first_order, ts_ops):
    second_order = []
    for fo in first_order:
        for ts_op in ts_ops:
            second_order += ts_factory(ts_op, fo)
    return second_order
 
 
def get_data_fields_csv(filename, prefix):
    '''
    inputs: 
    CSV file with header 'field' 
    outputs:
    A list of string
    '''
    df = pd.read_csv(filename,header=0,encoding = 'unicode_escape')
    collection = []
    for _, row in df.iterrows():
        if row['field'].startswith(prefix):
            collection.append(row['field'])
 
    return collection
 
def ts_arith_factory(ts_op, arith_op, field):
    first_order = "%s(%s)"%(arith_op, field)
    second_order = ts_factory(ts_op, first_order)
    return second_order
 
def arith_ts_factory(arith_op, ts_op, field):
    second_order = []
    first_order = ts_factory(ts_op, field)
    for fo in first_order:
        second_order.append("%s(%s)"%(arith_op, fo))
    return second_order
 
def ts_group_factory(ts_op, group_op, field, region):
    second_order = []
    first_order = group_factory(group_op, field, region)
    for fo in first_order:
        second_order += ts_factory(ts_op, fo)
    return second_order
 
def group_ts_factory(group_op, ts_op, field, region):
    second_order = []
    first_order = ts_factory(ts_op, field)
    for fo in first_order:
        second_order += group_factory(group_op, fo, region)
    return second_order
 
def vector_factory(op, field):
    output = []
    vectors = ["cap"]
    
    for vector in vectors:
    
        alpha = "%s(%s, %s)"%(op, field, vector)
        output.append(alpha)
    
    return output
 
def trade_when_factory(op,field,region):

    output = []
    events = []
    open_events = ["ts_arg_max(volume, 5) == 0", "ts_corr(close, volume, 20) < 0",
                   "ts_corr(close, volume, 5) < 0", "ts_mean(volume,10)>ts_mean(volume,60)",
                   "group_rank(ts_std_dev(returns,60), sector) > 0.7", "ts_zscore(returns,60) > 2",
                   #"ts_skewness(returns,120)> 0.7",
                    "ts_arg_min(volume, 5) > 3",
                   "ts_std_dev(returns, 5) > ts_std_dev(returns, 20)",
                   "ts_arg_max(close, 5) == 0", "ts_arg_max(close, 20) == 0",
                   "ts_corr(close, volume, 5) > 0", "ts_corr(close, volume, 5) > 0.3", "ts_corr(close, volume, 5) > 0.5",
                   "ts_corr(close, volume, 20) > 0", "ts_corr(close, volume, 20) > 0.3", "ts_corr(close, volume, 20) > 0.5",
                   "ts_regression(returns, %s, 5, lag = 0, rettype = 2) > 0"%field,
                   "ts_regression(returns, %s, 20, lag = 0, rettype = 2) > 0"%field,
                   "ts_regression(returns, ts_step(20), 20, lag = 0, rettype = 2) > 0",
                   "ts_regression(returns, ts_step(5), 5, lag = 0, rettype = 2) > 0"]

    exit_events = ["abs(returns) > 0.1", "-1", "days_from_last_change(ern3_pre_reptime) > 20"
                   ]

    usa_events = ["rank(rp_css_business) > 0.8", "ts_rank(rp_css_business, 22) > 0.8", "rank(vec_avg(mws82_sentiment)) > 0.8",
                  "ts_rank(vec_avg(mws82_sentiment),22) > 0.8", "rank(vec_avg(nws48_ssc)) > 0.8",
                  "ts_rank(vec_avg(nws48_ssc),22) > 0.8", "rank(vec_avg(mws50_ssc)) > 0.8", "ts_rank(vec_avg(mws50_ssc),22) > 0.8",
                  "ts_rank(vec_sum(scl12_alltype_buzzvec),22) > 0.9", "pcr_oi_270 < 1", "pcr_oi_270 > 1",]

    asi_events = ["rank(vec_avg(mws38_score)) > 0.8", "ts_rank(vec_avg(mws38_score),22) > 0.8"]

    eur_events = ["rank(rp_css_business) > 0.8", "ts_rank(rp_css_business, 22) > 0.8",
                  "rank(vec_avg(oth429_research_reports_fundamental_keywords_4_method_2_pos)) > 0.8",
                  "ts_rank(vec_avg(oth429_research_reports_fundamental_keywords_4_method_2_pos),22) > 0.8",
                  "rank(vec_avg(mws84_sentiment)) > 0.8", "ts_rank(vec_avg(mws84_sentiment),22) > 0.8",
                  "rank(vec_avg(mws85_sentiment)) > 0.8", "ts_rank(vec_avg(mws85_sentiment),22) > 0.8",
                  "rank(mdl110_analyst_sentiment) > 0.8", "ts_rank(mdl110_analyst_sentiment, 22) > 0.8",
                  "rank(vec_avg(nws3_scores_posnormscr)) > 0.8",
                  "ts_rank(vec_avg(nws3_scores_posnormscr),22) > 0.8",
                  "rank(vec_avg(mws36_sentiment_words_positive)) > 0.8",
                  "ts_rank(vec_avg(mws36_sentiment_words_positive),22) > 0.8"]

    glb_events = ["rank(vec_avg(mdl109_news_sent_1m)) > 0.8",
                  "ts_rank(vec_avg(mdl109_news_sent_1m),22) > 0.8",
                  "rank(vec_avg(nws20_ssc)) > 0.8",
                  "ts_rank(vec_avg(nws20_ssc),22) > 0.8",
                  "vec_avg(nws20_ssc) > 0",
                  "rank(vec_avg(nws20_bee)) > 0.8",
                  "ts_rank(vec_avg(nws20_bee),22) > 0.8",
                  "rank(vec_avg(nws20_qmb)) > 0.8",
                  "ts_rank(vec_avg(nws20_qmb),22) > 0.8"]

    chn_events = ["rank(vec_avg(oth111_xueqiunaturaldaybasicdivisionstat_senti_conform)) > 0.8",
                  "ts_rank(vec_avg(oth111_xueqiunaturaldaybasicdivisionstat_senti_conform),22) > 0.8",
                  "rank(vec_avg(oth111_gubanaturaldaydevicedivisionstat_senti_conform)) > 0.8",
                  "ts_rank(vec_avg(oth111_gubanaturaldaydevicedivisionstat_senti_conform),22) > 0.8",
                  "rank(vec_avg(oth111_baragedivisionstat_regi_senti_conform)) > 0.8",
                  "ts_rank(vec_avg(oth111_baragedivisionstat_regi_senti_conform),22) > 0.8"]

    kor_events = ["rank(vec_avg(mdl110_analyst_sentiment)) > 0.8",
                  "ts_rank(vec_avg(mdl110_analyst_sentiment),22) > 0.8",
                  "rank(vec_avg(mws38_score)) > 0.8",
                  "ts_rank(vec_avg(mws38_score),22) > 0.8"]

    twn_events = ["rank(vec_avg(mdl109_news_sent_1m)) > 0.8",
                  "ts_rank(vec_avg(mdl109_news_sent_1m),22) > 0.8",
                  "rank(rp_ess_business) > 0.8",
                  "ts_rank(rp_ess_business,22) > 0.8"]
    if region == "GLB": 
        events += open_events + glb_events 
    if region == "USA": 
        events += open_events + usa_events
    if region == "ASI": 
        events += open_events + asi_events
    if region == "EUR": 
        events += open_events + eur_events
    if region == "CHN": 
        events += open_events + chn_events

    for oe in events:
        for ee in exit_events:
            alpha = "%s(%s, %s, %s)"%(op, oe, field, ee)
            output.append(alpha)
    return output
 
def ts_factory(op, field):
    output = []
    # days = [3, 5, 10, 20, 60, 120, 240]
    # days = [5, 22, 66, 120, 240]
    days = [22,  120]
    if op =="ts_quantile":
        #ts_quantile(x,d, driver="gaussian" )
        for day in days:
            alpha = "%s(%s,%d,driver='gaussian')"%(op, field, day)
            output.append(alpha)
    if op == "jump_decay":
        for day in days:
            alpha = "%s(%s,%d,stddev=True,sensitivity=0.5,force=0.1)"%(op,field,day)
            output.append(alpha)
        return output
    if op == "kth_element":
        #kth_element(sales/assets,252,k="1",ignore="NAN 0")
        for day in days:
            alpha = "%s(%s,%d,k='1',ignore='NAN 0')"%(op,field, day)
            output.append(alpha)
        return output

    for day in days:
        alpha = "%s(%s, %d)"%(op, field, day)
        output.append(alpha)
    
    return output
 

def ts_comp_factory(op, field, factor, paras):
    output = []
    #l1, l2 = [3, 5, 10, 20, 60, 120, 240], paras
    # l1, l2 = [5, 22, 66, 240], paras
    l1, l2 = [22, 240], paras
    comb = list(product(l1, l2))
    
    for day,para in comb:
        
        if type(para) == float:
            alpha = "%s(%s, %d, %s=%.1f)"%(op, field, day, factor, para)
        elif type(para) == int:
            alpha = "%s(%s, %d, %s=%d)"%(op, field, day, factor, para)
            
        output.append(alpha)
    
    return output
 
def twin_field_factory(op, field, fields):
    
    output = []
    #days = [3, 5, 10, 20, 60, 120, 240]
    # days = [5, 22, 66, 240]
    days = [22, 240]
    outset = list(set(fields) - set([field]))
    
    for day in days:
        for counterpart in outset:
            alpha = "%s(%s, %s, %d)"%(op, field, counterpart, day)
            output.append(alpha)
    
    return output
 
 
def group_factory(op, field, region):
    output = []
    vectors = ["cap"] 
    
    chn_group_13 = ['pv13_h_min2_sector', 'pv13_di_6l', 'pv13_rcsed_6l', 'pv13_di_5l', 'pv13_di_4l', 
                        'pv13_di_3l', 'pv13_di_2l', 'pv13_di_1l', 'pv13_parent', 'pv13_level']
    
    
    chn_group_1 = ['sta1_top3000c30','sta1_top3000c20','sta1_top3000c10','sta1_top3000c2','sta1_top3000c5']
    
    chn_group_2 = ['sta2_top3000_fact4_c10','sta2_top2000_fact4_c50','sta2_top3000_fact3_c20']
 
    chn_group_7 = [ ] # 'oth171_region_sector_long_d1_sector','oth171_region_sector_short_d1_sector', 
                   
    
    hkg_group_13 = ['pv13_10_f3_g2_minvol_1m_sector', 'pv13_10_minvol_1m_sector', 'pv13_20_minvol_1m_sector', 
                    'pv13_2_minvol_1m_sector', 'pv13_5_minvol_1m_sector', 'pv13_1l_scibr', 'pv13_3l_scibr',
                    'pv13_2l_scibr', 'pv13_4l_scibr', 'pv13_5l_scibr']
    
    hkg_group_1 = ['sta1_allc50','sta1_allc5','sta1_allxjp_513_c20','sta1_top2000xjp_513_c5']
    
    hkg_group_2 = ['sta2_all_xjp_513_all_fact4_c10','sta2_top2000_xjp_513_top2000_fact3_c10',
                   'sta2_allfactor_xjp_513_13','sta2_top2000_xjp_513_top2000_fact3_c20']
    
    hkg_group_8 = ['oth455_relation_n2v_p10_q50_w5_kmeans_cluster_5']
    
    twn_group_13 = ['pv13_2_minvol_1m_sector','pv13_20_minvol_1m_sector','pv13_10_minvol_1m_sector',
                    'pv13_5_minvol_1m_sector','pv13_10_f3_g2_minvol_1m_sector','pv13_5_f3_g2_minvol_1m_sector',
                    #'pv13_2_f4_g3_minvol_1m_sector'
                    ]
    
    twn_group_1 = ['sta1_allc50','sta1_allxjp_513_c50','sta1_allxjp_513_c20','sta1_allxjp_513_c2',
                   'sta1_allc20','sta1_allxjp_513_c5','sta1_allxjp_513_c10','sta1_allc2','sta1_allc5']
    
    twn_group_2 = ['sta2_allfactor_xjp_513_0','sta2_all_xjp_513_all_fact3_c20',
                   'sta2_all_xjp_513_all_fact4_c20','sta2_all_xjp_513_all_fact4_c50']
    
    twn_group_8 = ['oth455_relation_n2v_p50_q200_w1_pca_fact1_cluster_20']
    
    usa_group_13 = ['pv13_h_min2_3000_sector','pv13_r2_min20_3000_sector','pv13_r2_min2_3000_sector',
                    'pv13_r2_min2_3000_sector', 'pv13_h_min2_focused_pureplay_3000_sector']
    
    usa_group_1 = ['sta1_top3000c50','sta1_allc20','sta1_allc10','sta1_top3000c20','sta1_allc5']
    
    usa_group_2 = ['sta2_top3000_fact3_c50','sta2_top3000_fact4_c20','sta2_top3000_fact4_c10']
    
    usa_group_3 = ['sta3_2_sector', 
                    'sta3_3_sector', 'sta3_news_sector', 'sta3_peer_sector',
                   'sta3_pvgroup1_sector', 'sta3_pvgroup2_sector', 'sta3_pvgroup3_sector', 'sta3_sec_sector']
    
    usa_group_4 = [#'rsk69_01c_1m', 'rsk69_57c_1m', 'rsk69_02c_2m', 'rsk69_5c_2m', 'rsk69_02c_1m',
                  # 'rsk69_05c_2m', 'rsk69_57c_2m', 'rsk69_5c_1m', 'rsk69_05c_1m', 'rsk69_01c_2m'
                  #'rsk72_top3000_dsrt'
                  ]
    
    usa_group_5 = [#'anl52_2000_backfill_d1_05c', 'anl52_3000_d1_05c', 'anl52_3000_backfill_d1_02c', 
                   #'anl52_3000_backfill_d1_5c', 'anl52_3000_backfill_d1_05c', 'anl52_3000_d1_5c'
                   ]
    
    usa_group_6 = [#'mdl10_group_name'
                   ]
    
    usa_group_7 = []
    
    usa_group_8 = ['oth455_competitor_n2v_p10_q50_w1_kmeans_cluster_10']
    
    
    asi_group_13 = ['pv13_20_minvol_1m_sector', 'pv13_5_f3_g2_minvol_1m_sector', 'pv13_10_f3_g2_minvol_1m_sector',
                    #'pv13_2_f4_g3_minvol_1m_sector',
                      'pv13_10_minvol_1m_sector', 'pv13_5_minvol_1m_sector']
    
    asi_group_1 = ['sta1_allc50', 'sta1_allc10',# 'sta1_minvol1mc50',
                   'sta1_minvol1mc20',
                   'sta1_minvol1m_normc20', 'sta1_minvol1m_normc50']
    
    asi_group_8 = ['oth455_partner_roam_w3_pca_fact1_cluster_5']
    
    jpn_group_1 = ['sta1_alljpn_513_c5', 'sta1_alljpn_513_c50', 'sta1_alljpn_513_c2', 'sta1_alljpn_513_c20']
    
    jpn_group_2 = ['sta2_top2000_jpn_513_top2000_fact3_c20', 'sta2_all_jpn_513_all_fact1_c5',
                   'sta2_allfactor_jpn_513_9', 'sta2_all_jpn_513_all_fact1_c10']
    
    jpn_group_8 = ['oth455_customer_n2v_p50_q50_w5_kmeans_cluster_10']
    
    jpn_group_13 = ['pv13_2_minvol_1m_sector', 
                    #'pv13_2_f4_g3_minvol_1m_sector', 
                    'pv13_10_minvol_1m_sector',
                    'pv13_10_f3_g2_minvol_1m_sector', 'pv13_all_delay_1_parent', 'pv13_all_delay_1_level']
    
    kor_group_13 = ['pv13_10_f3_g2_minvol_1m_sector', 'pv13_5_minvol_1m_sector', 'pv13_5_f3_g2_minvol_1m_sector',
                    'pv13_2_minvol_1m_sector', 'pv13_20_minvol_1m_sector'#, 'pv13_2_f4_g3_minvol_1m_sector'
                    ]
    
    kor_group_1 = ['sta1_allc20','sta1_allc50','sta1_allc2','sta1_allc10','sta1_minvol1mc50',
                   'sta1_allxjp_513_c10', 'sta1_top2000xjp_513_c50']
    
    kor_group_2 =['sta2_all_xjp_513_all_fact1_c50','sta2_top2000_xjp_513_top2000_fact2_c50',
                  'sta2_all_xjp_513_all_fact4_c50','sta2_all_xjp_513_all_fact4_c5']
    
    kor_group_8 = ['oth455_relation_n2v_p50_q200_w3_pca_fact3_cluster_5']
    
    eur_group_13 = ['pv13_5_sector', 'pv13_2_sector', 'pv13_v3_3l_scibr', 'pv13_v3_2l_scibr', 'pv13_2l_scibr',
                    'pv13_52_sector', 'pv13_v3_6l_scibr', 'pv13_v3_4l_scibr', 'pv13_v3_1l_scibr']
    
    eur_group_1 = ['sta1_allc10', 'sta1_allc2', 'sta1_top1200c2', 'sta1_allc20', 'sta1_top1200c10']
    
    eur_group_2 = ['sta2_top1200_fact3_c50','sta2_top1200_fact3_c20','sta2_top1200_fact4_c50']
    
    eur_group_3 = [#'sta3_6_sector', 'sta3_pvgroup4_sector', 'sta3_pvgroup5_sector']
                    ]
    eur_group_7 = []
    
    eur_group_8 = ['oth455_relation_n2v_p50_q200_w3_pca_fact1_cluster_5']

    eur_group_14 = ["group_cartesian_product(country, market)","group_cartesian_product(country, sector)", "group_cartesian_product(country, industry)","group_cartesian_product(country, subindustry)"]
    
    glb_group_13 = ["pv13_10_f3_g2_minvol_1m_sector", "pv13_10_sector", "pv13_10_f2_g3_minvol_1m_sector", "pv13_10_minvol_1m_sector","pv13_10_minvol_1m_sector"]
    
    glb_group_3 = [#'sta3_2_sector', 'sta3_3_sector', 'sta3_news_sector', 'sta3_peer_sector',
                   #'sta3_pvgroup1_sector', 'sta3_pvgroup2_sector', 'sta3_pvgroup3_sector', 'sta3_sec_sector'
                   ]
    
    glb_group_1 = ['sta1_allc20', 'sta1_allc10', 'sta1_allc50', 'sta1_allc5', 'sta1_allc2' ]
    
    glb_group_2 = [
                    # 'sta2_all_fact1_c10',
                    # 'sta2_all_fact2_c10',
                    # 'sta2_all_fact2_c50',
                    # 'sta2_all_fact3_c50',
                    'sta2_all_fact4_c50'
                    ]
    
    glb_group_13 = ['pv13_2_sector', 'pv13_3l_scibr', 'pv13_1l_scibr',
                    'pv13_52_minvol_1m_all_delay_1_sector','pv13_52_minvol_1m_sector']
    
    glb_group_7 = []  
    
    glb_group_8 = ['oth455_relation_n2v_p10_q200_w5_kmeans_cluster_5']
    
    amr_group_13 = ['pv13_4l_scibr', 'pv13_1l_scibr', 'pv13_hierarchy_min51_f1_sector',
                    'pv13_hierarchy_min2_600_sector', 'pv13_r2_min2_sector', 'pv13_h_min20_600_sector']
    
    amr_group_3 = ['sta3_news_sector', 'sta3_peer_sector', 'sta3_pvgroup1_sector',# 'sta3_pvgroup2_sector',
                   'sta3_pvgroup3_sector']
    
    amr_group_8 = ['oth455_relation_roam_w1_pca_fact2_cluster_10', 
                   'oth455_competitor_n2v_p50_q200_w5_kmeans_cluster_10']
    
    group_3 = []
    
    bps_group = "bucket(rank(fnd28_value_05480/close), range='0.2, 1, 0.2')"
    cap_group = "bucket(rank(cap), range='0.1, 1, 0.1')"
    sector_cap_group = "bucket(group_rank(cap,sector),range='0,1,0.1')"
    vol_group = "bucket(rank(ts_std_dev(ts_returns(close,1),20)),range = '0.1,1,0.1')"
    groups = ["market","sector", "industry", "subindustry", bps_group, cap_group, sector_cap_group]
    

    data = ["star_si_cap_rank","star_si_sector_rank",
"oth455_competitor_n2v_p10_q200_w1_kmeans_cluster_5",
"oth455_customer_n2v_p50_q50_w5_pca_fact3_cluster_20",
"oth455_partner_n2v_p10_q50_w2_kmeans_cluster_10",
"oth455_relation_n2v_p50_q200_w4_pca_fact1_cluster_5",
"oth455_competitor_n2v_p50_q200_w3_pca_fact2_cluster_20",
"oth455_customer_roam_w1_kmeans_cluster_5",
"oth455_partner_n2v_p50_q50_w4_pca_fact3_cluster_10",
"oth455_relation_n2v_p10_q200_w5_kmeans_cluster_20",
"oth455_competitor_n2v_p10_q50_w3_pca_fact1_cluster_5",
"oth455_customer_n2v_p10_q200_w4_pca_fact2_cluster_10",
"oth455_partner_roam_w5_pca_fact3_cluster_20",
"oth455_relation_n2v_p50_q50_w1_kmeans_cluster_5",
"oth455_competitor_roam_w3_pca_fact2_cluster_10",
"oth455_customer_n2v_p50_q200_w2_pca_fact3_cluster_5",
"oth455_partner_n2v_p10_q200_w1_pca_fact1_cluster_20",
"oth455_relation_n2v_p10_q50_w5_pca_fact2_cluster_10",
"oth455_competitor_n2v_p50_q50_w2_kmeans_cluster_20",
"oth455_customer_n2v_p10_q200_w3_kmeans_cluster_10",
"oth455_partner_roam_w2_pca_fact1_cluster_5",
"oth455_relation_roam_w4_kmeans_cluster_20"
    ]

    if region == "CHN":
        groups += chn_group_13 + chn_group_1 + chn_group_2 + data 
    if region == "TWN":
        groups += twn_group_13 + twn_group_1 + twn_group_2 + twn_group_8 + data
    if region == "ASI":
        groups += asi_group_13 + asi_group_1 + asi_group_8 + data
    if region == "USA":
        groups += usa_group_13 + usa_group_1 + usa_group_2 + usa_group_3 + usa_group_4 + usa_group_8 + group_3 
        groups += usa_group_5 + usa_group_6 + usa_group_7 + data
    if region == "HKG":
        groups += hkg_group_13 + hkg_group_1 + hkg_group_2 + hkg_group_8 + data
    if region == "KOR":
        groups += kor_group_13 + kor_group_1 + kor_group_2 + kor_group_8 + data
    if region == "EUR": 
        groups += eur_group_13 + eur_group_14 + eur_group_1 + eur_group_2 + eur_group_3 + eur_group_8 +  eur_group_7 + group_3 + data
    if region == "GLB":
        groups += glb_group_8 + glb_group_3 + glb_group_7 + group_3 + data
    if region == "AMR":
        groups += amr_group_3 + amr_group_13 + data
    if region == "JPN":
        groups += jpn_group_1 + jpn_group_2 + jpn_group_13 + jpn_group_8 + data
        
    for group in groups:
        if op == "group_mean":
            alpha = "%s(%s,1,densify(%s))"%(op, field, group)
            output.append(alpha)
        elif op == "group_normalize":
            #group_normalize(x, group, constantCheck=False, tolerance=0.01, scale=1)
            alpha = "%s(%s,densify(%s), constantCheck=False, tolerance=0.01, scale=1)"%(op, field, group)
            output.append(alpha)
        elif op.startswith("group_vector"):
            for vector in vectors:
                alpha = "%s(%s,%s,densify(%s))"%(op, field, vector, group)
                output.append(alpha)
        elif op.startswith("group_percentage"):
            alpha = "%s(%s,densify(%s),percentage=0.5)"%(op, field, group)
            output.append(alpha)
        else:
            alpha = "%s(%s,densify(%s))"%(op, field, group)
            output.append(alpha)
        
    return output