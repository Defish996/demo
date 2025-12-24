import re
import csv
from pathlib import Path
import pymysql
from typing import Dict, Any, List

# ==================== 配置区域 ====================

# 定义所有处理任务
# 每个任务是一个字典，包含名称、输入目录和数据库表名
TASKS = [
    {
        "name": "API下单首次回报延迟",
        "in_dir": Path("csv汇总/1/min/API下单首次回报延迟"),
        "table_name": "api_order_first_ack_min",
    },
    {
        "name": "API下单taker延迟",
        "in_dir": Path("csv汇总/2/min/API下单taker延迟"),
        "table_name": "api_order_taker_min",
    },
    {
        "name": "交易系统下单首次回报延迟",
        "in_dir": Path("csv汇总/3/min/交易系统下单首次回报延迟"),
        "table_name": "trd_sys_order_first_ack_min",
    },
    {
        "name": "API撤单延迟",
        "in_dir": Path("csv汇总/4/min/API撤单延迟"),
        "table_name": "api_cancel_min",
    },
    {
        "name": "交易系统撤单延迟",
        "in_dir": Path("csv汇总/5/min/交易系统撤单延迟"),
        "table_name": "trd_sys_cancel_min",
    },
]

# 数据库连接配置
DB_CFG = dict(
    host='10.0.0.4',
    port=3316,
    user='delay_user',
    password='T7#mK9$vQ!x2@pL&nR5*wE8sY^a4FbN',
    database='delay_data',
    charset='utf8mb4'
)

# 交易所名称映射
MARKET_MAP = {'上交所': '上交所', '深交所': '深交所', '北交所': '北交所', '港交所': '港交所'}

# ==================== 功能函数 ====================

def get_date_input() -> str:
    """提示用户输入并确认日期。"""
    while True:
        date1 = input('当前是分钟级数据写入库, 时间应为下午, 请输入该数据对应的当天日期,并非下载时日期（纯数字格式，例：20250924）：').strip()
        if not date1.isdigit() or len(date1) != 8:
            print('日期格式不正确，请输入8位纯数字！')
            continue
        date2 = input('请再次输入日期以确认：').strip()
        if date1 == date2:
            return date1
        print('两次输入不一致，请重新输入！')

def parse_first_col(s: str) -> Dict[str, str]:
    """使用正则表达式解析 CSV 的第一列。"""
    pattern = r"""
        (?P<ID>\d{3,4})
        (?P<ProductName>[\u4e00-\u9fa5]{2}\d|[\u4e00-\u9fa5]{2}(?!\d)|[\u4e00-\u9fa5]\d{2})
        (?P<Broker>[\u4e00-\u9fa5]{2})
        (?P<TradeType>[^\x28]+)
        \s*\(交易:\s*(?P<Trade_MC>[^)]+)\)
        (?:\(API:\s*(?P<API_MC>[^)]*)\))?
    """
    m = re.match(pattern, s.strip(), re.VERBOSE)
    return m.groupdict() if m else None

def process_csv_file(src: Path, c_date: str, table_name: str, conn: pymysql.Connection) -> int:
    """处理单个 CSV 文件并将其数据插入数据库。"""
    exchange = next((v for k, v in MARKET_MAP.items() if k in src.name), None)
    if not exchange:
        raise ValueError(f'无法从文件名识别交易所：{src.name}')

    sql = f"""
        INSERT INTO {table_name}
          (ID, Minute, Delay_ms, Exchange, Calc_Date)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
          Delay_ms=VALUES(Delay_ms), created_at=NOW()
    """

    buffer = []
    with src.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader)
        minutes = header[1:]

        for row in reader:
            if not row:
                continue
            first, *delays = row
            meta = parse_first_col(first)
            if not meta:
                continue
            _id = meta['ID']

            for minute, delay_str in zip(minutes, delays):
                if delay_str not in ('', '0'):
                    try:
                        delay = float(delay_str)
                        buffer.append((_id, minute, delay, exchange, c_date))
                    except ValueError:
                        continue

    if buffer:
        with conn.cursor() as cur:
            cur.executemany(sql, buffer)
        conn.commit()

    return len(buffer)

def run_task(task: Dict[str, Any], c_date: str, conn: pymysql.Connection):
    """执行单个处理任务。"""
    print(f"\n--- 开始处理任务: {task['name']} ---")
    in_dir = task['in_dir']
    table_name = task['table_name']

    csv_files = list(in_dir.glob('*.csv'))
    if not csv_files:
        print(f'目录 {in_dir.absolute()} 内未找到 csv 文件')
        return

    # 自动建表
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
      ID                    varchar(10)  NOT NULL,
      Minute                time         DEFAULT NULL,
      Delay_ms              double       NOT NULL,
      Exchange              varchar(10)  NOT NULL,
      Calc_Date             date         DEFAULT NULL,
      created_at            datetime     DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (ID, Calc_Date, Minute, Exchange)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """
    with conn.cursor() as cur:
        cur.execute(create_sql)
    conn.commit()

    total_files = 0
    total_rows = 0
    for src in csv_files:
        try:
            rows = process_csv_file(src, c_date, table_name, conn)
            total_files += 1
            total_rows += rows
            print(f'  -> {src.name} 入库 {rows} 条')
        except Exception as e:
            print(f'  -> 跳过 {src.name}：{e}')
            continue
    print(f"--- 任务 '{task['name']}' 完成！共处理 {total_files} 个文件，累计 {total_rows} 条记录 ---")

# ==================== 主入口 ====================

def main():
    """主函数，程序入口。"""
    # 1. 选择任务
    print("请选择要执行的任务:")
    for i, task in enumerate(TASKS):
        print(f"  {i + 1}: {task['name']}")
    print("  0: 全部执行")

    choice = input("请输入选项 (0-5): ").strip()

    selected_tasks: List[Dict] = []
    if choice == '0':
        selected_tasks = TASKS
    elif choice.isdigit() and 1 <= int(choice) <= len(TASKS):
        selected_tasks.append(TASKS[int(choice) - 1])
    else:
        print("无效的选项！")
        return

    # 2. 获取日期
    c_date = get_date_input()

    # 3. 执行任务
    conn = None
    try:
        conn = pymysql.connect(**DB_CFG)
        for task in selected_tasks:
            run_task(task, c_date, conn)
        print("\n所有选定任务已完成！")
    except pymysql.Error as e:
        print(f"数据库连接或操作失败: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    main()