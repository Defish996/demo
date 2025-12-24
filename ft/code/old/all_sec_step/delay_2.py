import re
import csv
from pathlib import Path
import pymysql

# ---------- 全局参数 ----------
while True:
    date1 = input('请输入该数据对应的当天日期,并非下载时日期（纯数字格式，例：20250924）：').strip()
    date2 = input('请再次输入日期以确认：').strip()
    if date1 == date2:
        C_DATE = date1
        break
    print('两次输入不一致，请重新输入！')
MARKET_MAP = {'上交所': '上交所', '深交所': '深交所', '北交所': '北交所', '港交所': '港交所'}
IN_DIR = Path('2/sec/API下单taker延迟')

# ---------- MySQL 连接配置 ----------
DB_CFG = dict(
    host='10.0.0.4',
    port=3316,
    user='delay_user',
    password='T7#mK9$vQ!x2@pL&nR5*wE8sY^a4FbN',
    database='delay_data',
    charset='utf8mb4'
)

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
def process_one(src: Path, c_date: str, conn):
    se = next((v for k, v in MARKET_MAP.items() if k in src.name), None)
    if not se:
        raise ValueError(f'无法从文件名识别交易所：{src.name}')

    sql = """
        INSERT INTO api_order_taker_sec
          (ID, second_time, Delay_ms, Exchange, Calc_date, id_date_minute_bourse)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
          delay_ms=VALUES(delay_ms), created_at=NOW()
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
                key = f"{_id}&{c_date}&{minute}&{se}"
                buffer.append((_id, minute, delay, se, c_date, key))
                rows_out += 1

                if len(buffer) >= 1000:
                    with conn.cursor() as cur:
                        cur.executemany(sql, buffer)
                    conn.commit()
                    buffer.clear()

    if buffer:          # 余数
        with conn.cursor() as cur:
            cur.executemany(sql, buffer)
        conn.commit()

    return rows_out

# ---------- 批量 ----------
def main():
    csv_files = list(IN_DIR.glob('*.csv'))
    if not csv_files:
        print(f'目录 {IN_DIR.absolute()} 内未找到 csv 文件')
        return

    conn = pymysql.connect(**DB_CFG)
    try:
        # —— 自动建表（仅第一次） ——
        create_sql = """
        CREATE TABLE IF NOT EXISTS api_order_taker_sec (
            ID                  VARCHAR(10)     NOT NULL,
            second_time         TIME            NOT NULL,
            Delay_ms            DOUBLE          NOT NULL,
            Exchange            VARCHAR(10)     NOT NULL,
            Calc_date           DATE            NOT NULL,
            id_date_minute_bourse VARCHAR(100) NOT NULL,
            created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id_date_minute_bourse)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        with conn.cursor() as cur:
            cur.execute(create_sql)
        conn.commit()
        # —— 建表结束 ——

        total_files = 0
        total_rows = 0
        for src in csv_files:
            try:
                rows = process_one(src, C_DATE, conn)
                total_files += 1
                total_rows += rows
                print(f'{src.name} 入库 {rows} 条')
            except Exception as e:
                print(f'跳过 {src.name} ：{e}')
                continue
        print(f'\n全部完成！共处理 {total_files} 个文件，累计 {total_rows} 条延迟记录')
    finally:
        conn.close()

# ---------- 入口 ----------
if __name__ == '__main__':
    main()