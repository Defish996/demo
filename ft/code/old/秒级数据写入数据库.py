import re
import csv
from pathlib import Path
import pymysql

# ---------- 全局参数 ----------
while True:
    date1 = input('当前是秒级数据写入库,时间应为上午,请输入该数据对应的当天日期,并非下载时日期（纯数字格式，例：20250924）：').strip()
    date2 = input('请再次输入日期以确认：').strip()
    if date1 == date2:
        C_DATE = date1
        break
    print('两次输入不一致，请重新输入！')

MARKET_MAP = {'上交所': '上交所', '深交所': '深交所', '北交所': '北交所', '港交所': '港交所'}

# ---------- MySQL 连接配置 ----------
DB_CFG = dict(
    host='10.0.0.4',
    port=3316,
    user='delay_user',
    password='T7#mK9$vQ!x2@pL&nR5*wE8sY^a4FbN',
    database='delay_data',
    charset='utf8mb4'
)
# DB_CFG = dict(
#     host='127.0.0.1',
#     port=3306,
#     user='root',
#     password='hgz9580k.',
#     database='test',
#     charset='utf8mb4'
# )

# ---------- 任务配置 ----------
CONFIGS = [
    {
        "in_dir": Path("1/sec/API下单首次回报延迟"),
        "table_name": "api_order_first_ack_sec",
    },
    {
        "in_dir": Path("2/sec/API下单taker延迟"),
        "table_name": "api_order_taker_sec",
    },
    {
        "in_dir": Path("3/sec/交易系统下单首次回报延迟"),
        "table_name": "trd_sys_order_first_ack_sec",
    },
    {
        "in_dir": Path("4/sec/API撤单延迟"),
        "table_name": "api_cancel_sec",
    },
    {
        "in_dir": Path("5/sec/交易系统撤单延迟"),
        "table_name": "trd_sys_cancel_sec",
    },
]

# ---------- 正则 ----------
def parse_first_col(s: str):
    pattern = r"""
        (?P<ID>\d{3,4})
        (?P<ProductName>
            [\u4e00-\u9fa5]{2}\d
            | [\u4e00-\u9fa5]{2}(?!\d)
            | [\u4e00-\u9fa5]\d{2}
        )
        (?P<Broker>[\u4e00-\u9fa5]{2})
        (?P<TradeType>[^\x28]+)
        \s*\(交易:\s*(?P<Trade_MC>[^)]+)\)
        (?:\(API:\s*(?P<API_MC>[^)]*)\))?
    """
    m = re.match(pattern, s.strip(), re.VERBOSE)
    return m.groupdict() if m else None

# ---------- 单文件处理 ----------
def process_one(src: Path, c_date: str, conn, table_name: str):
    se = next((v for k, v in MARKET_MAP.items() if k in src.name), None)
    if not se:
        raise ValueError(f'无法从文件名识别交易所：{src.name}')

    sql = f"""
        INSERT INTO {table_name}
          (ID, second_time, Delay_ms, Exchange, Calc_date)
        VALUES (%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
          Delay_ms=VALUES(Delay_ms), created_at=NOW()
    """

    rows_out = 0
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
                if delay_str in ('0', ''):
                    continue
                try:
                    delay = float(delay_str)
                except ValueError:
                    continue
                buffer.append((_id, minute, delay, se, c_date))
                rows_out += 1

                if len(buffer) >= 1000:
                    with conn.cursor() as cur:
                        cur.executemany(sql, buffer)
                    conn.commit()
                    buffer.clear()

    if buffer:
        with conn.cursor() as cur:
            cur.executemany(sql, buffer)
        conn.commit()

    return rows_out

# ---------- 批量 ----------
def process_config(config: dict, conn):
    in_dir = config["in_dir"]
    table_name = config["table_name"]

    csv_files = list(in_dir.glob('*.csv'))
    if not csv_files:
        print(f'目录 {in_dir.absolute()} 内未找到 csv 文件')
        return

    # —— 自动建表（仅第一次） ——
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        ID                  VARCHAR(10)     NOT NULL,
        second_time         TIME            NOT NULL,
        Delay_ms            DOUBLE          NOT NULL,
        Exchange            VARCHAR(10)     NOT NULL,
        Calc_date           DATE            NOT NULL,
        created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (ID, Calc_date, second_time, Exchange)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """
    with conn.cursor() as cur:
        cur.execute(create_sql)
    conn.commit()
    # —— 建表结束 ——

    total_files = 0
    total_rows = 0
    print(f"--- 开始处理 {in_dir} ---")
    for src in csv_files:
        try:
            rows = process_one(src, C_DATE, conn, table_name)
            total_files += 1
            total_rows += rows
            print(f'{src.name} 入库 {rows} 条')
        except Exception as e:
            print(f'跳过 {src.name} ：{e}')
            continue
    print(f'--- {in_dir} 处理完成！共处理 {total_files} 个文件，累计 {total_rows} 条延迟记录 ---\n')


def main():
    conn = pymysql.connect(**DB_CFG)
    try:
        for config in CONFIGS:
            process_config(config, conn)
    finally:
        conn.close()
    print("所有任务全部完成！")

# ---------- 入口 ----------
if __name__ == '__main__':
    main()