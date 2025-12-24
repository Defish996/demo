#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV -> MySQL 一键入库（支持目录通配）
宽表转长表，主键(machine, ts, calc_date, exchange)
exchange 取自文件名：stock_delay_2025-10-27_XXX_SSE_ave -> SSE
"""
import datetime
import glob
import os
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


# ---------- 1. 参数 ----------
CSV_PATTERN = r'./行情延迟图表/test/*.csv'      # 通配符路径
DB_URL      = 'mysql+pymysql://root:hgz9580k.@127.0.0.1:3306/test?charset=utf8mb4'
TABLE_NAME = 'machine_delay'


# ---------- 2. 建表 ----------
DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    machine    VARCHAR(64) NOT NULL,
    ts         TIME        NOT NULL,
    calc_date  DATE        NOT NULL,
    exchange   VARCHAR(8)  NOT NULL,
    delay_ms   FLOAT,
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (machine, ts, calc_date, exchange)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


# ---------- 3. 工具：INSERT IGNORE 批量写入 ----------
def bulk_insert_ignore(engine, table: str, df: pd.DataFrame):
    """重复主键自动跳过"""
    if df.empty:
        return
    cols = ','.join(df.columns)
    placeholders = ','.join([f':{c}' for c in df.columns])
    sql = f"INSERT IGNORE INTO {table} ({cols}) VALUES ({placeholders})"
    with engine.begin() as conn:
        conn.execute(text(sql), df.to_dict(orient='records'))


# ---------- 4. 读取+转换 ----------
def load_csv(csv_path: str, calc_date: datetime.date, exchange: str) -> pd.DataFrame:
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
    df['exchange']  = exchange
    df['created_at'] = datetime.datetime.now()
    return df


# ---------- 5. 主入口 ----------
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
        m_date = re.search(r'(\d{4}-\d{2}-\d{2})', fname)
        m_ex   = re.search(r'_([^_]+?)_ave$', fname)   # 交易所
        if not (m_date and m_ex):
            print(f'>>> 跳过文件（无法提取日期或交易所）：{fname}')
            continue

        calc_date = datetime.datetime.strptime(m_date.group(1), '%Y-%m-%d').date()
        exchange  = m_ex.group(1).upper()

        df = load_csv(csv_path, calc_date, exchange)
        if df.empty:
            continue

        bulk_insert_ignore(engine, TABLE_NAME, df)
        total += len(df)
        print(f'>>> 已处理 {os.path.basename(csv_path)}，写入 {len(df)} 条')

    print(f'>>> 全部完成，累计写入 {total} 条记录')


if __name__ == '__main__':
    main()