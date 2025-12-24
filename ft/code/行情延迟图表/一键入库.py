#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV -> MySQL 一键入库（支持目录通配）
宽表转长表，主键(machine, ts, calc_date, exchange, prices)
"""
import datetime
import glob
import os
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

# ---------- 1. 参数 ----------
CSV_PATTERN = r'./行情延迟图表/*.csv'      # 改成你的路径
DB_URL = (
    'mysql+pymysql://delay_user:T7%23mK9%24vQ%21x2%40pL%26nR5%2AwE8sY%5Ea4FbN'
    '@10.0.0.4:3316/delay_data?charset=utf8mb4'
)
# DB_URL = (
#     'mysql+pymysql://root:hgz9580k.'
#     '@localhost:3306/test?charset=utf8mb4'
# )
TABLE_NAME = 'prices_total'

# ---------- 2. 建表 ----------
DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    machine    VARCHAR(64) NOT NULL,
    ts         TIME        NOT NULL,
    calc_date  DATE        NOT NULL,
    exchange   VARCHAR(8)  NOT NULL,
    prices     VARCHAR(32) NOT NULL,
    delay_ms   FLOAT,
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (machine, ts, calc_date, exchange, prices)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

# ---------- 3. 文件名 -> prices 映射 ----------
PRICES_MAP = {
    'A': 'a',
    'CB': 'cb',
    'ETF': 'etf',
    'FAST_INDEX': 'highway_index',
    'Futures': 'futures',
    'XUXIN': 'a_test',
    'XUXIN_CB': 'cb_test',
    'HK': 'hkex_test'
}

# ---------- 4. 工具：INSERT IGNORE 批量写入 ----------
def bulk_insert_ignore(engine, table: str, df: pd.DataFrame):
    if df.empty:
        return
    cols = ','.join(df.columns)
    placeholders = ','.join([f':{c}' for c in df.columns])
    sql = f"INSERT IGNORE INTO {table} ({cols}) VALUES ({placeholders})"
    with engine.begin() as conn:
        conn.execute(text(sql), df.to_dict(orient='records'))

# ---------- 5. 读取+转换 ----------
def load_csv(csv_path: str, calc_date: datetime.date, exchange: str, prices: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    # 第一列当索引，其余列转时间
    df = df.set_index(df.columns[0])
    df.columns = pd.to_datetime(df.columns, format='%H:%M:%S').time

    # 宽表变长表
    df = df.stack().reset_index()
    df.columns = ['machine', 'ts', 'delay_ms']

    # 清洗
    df = df[df['delay_ms'] != 'no data'].copy()
    df['delay_ms'] = df['delay_ms'].astype(float)

    # 补充字段
    df['calc_date'] = calc_date
    df['exchange'] = exchange
    df['prices'] = prices
    df['created_at'] = datetime.datetime.now()
    return df

# ---------- 6. 主入口 ----------
def main():
    engine = create_engine(DB_URL, future=True)
    with engine.begin() as conn:
        conn.execute(text(DDL))

    csv_files = glob.glob(CSV_PATTERN)
    if not csv_files:
        print('>>> 未匹配到任何 CSV 文件，程序结束。')
        return

    total = 0
    for csv_path in csv_files:
        fname = Path(csv_path).stem
        # 提取日期
        m_date = re.search(r'(\d{4}-\d{2}-\d{2})', fname)
        # 提取交易所
        m_ex = re.search(r'_([^_]+?)_ave$', fname)
        if not (m_date and m_ex):
            print(f'>>> 跳过文件（无法提取日期或交易所）：{fname}')
            continue

        calc_date = datetime.datetime.strptime(m_date.group(1), '%Y-%m-%d').date()
        exchange_raw = m_ex.group(1).lower()          # 原始字符串先小写
        exchange = 'ZCE' if exchange_raw == 'unknow' else exchange_raw.upper()  # 替换+大写
        print('交易所:', exchange)                    # 打印最终入库的交易所
        # 删掉下面这一行！
        # exchange = exchange_raw.upper()


        # 根据后缀映射 prices
        # 取出品类字段（在日期之后、交易所之前）
        # stock_delay_2025-10-23_CB_SSE_ave          -> CB
        # stock_delay_2025-10-23_XUXIN_CB_SSE_ave    -> XUXIN_CB
        parts = fname.split('_')
        try:
            date_idx = next(i for i, v in enumerate(parts) if re.match(r'\d{4}-\d{2}-\d{2}', v))
            exchange_idx = len(parts) - 2          # 倒数第二个字段一定是交易所
        except StopIteration:
            print(f'>>> 跳过文件（无法定位日期或交易所）：{fname}')
            continue
        suffix = '_'.join(parts[date_idx + 1 : exchange_idx])   # 取中间那一段
        prices = PRICES_MAP.get(suffix)
        if prices is None:
            print(f'>>> 跳过文件（未知 prices 类型）：{fname}')
            continue

        df = load_csv(csv_path, calc_date, exchange, prices)
        if df.empty:
            continue

        bulk_insert_ignore(engine, TABLE_NAME, df)
        total += len(df)
        print(f'>>> 已处理 {os.path.basename(csv_path)}，写入 {len(df)} 条')

    print(f'>>> 全部完成，累计写入 {total} 条记录')


if __name__ == '__main__':
    main()