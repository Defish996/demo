#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
debug -> 正式运行合一版
"""
import pandas as pd
from sqlalchemy import create_engine
from datetime import date, timedelta
import time

# ---------- 连接 ----------
DB_USER = "delay_user"
DB_PASS = "T7%23mK9%24vQ%21x2%40pL%26nR5%2AwE8sY%5Ea4FbN"
DB_HOST = "10.0.0.4"
DB_PORT = 3316
DB_NAME = "delay_data"
engine = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    connect_args={"connect_timeout": 10}
)
TODAY = date(2025, 10, 31)

# ---------- 交易日 ----------
trade_dates = pd.read_sql(
    "SELECT TradeDate FROM TradeDate WHERE Market_open=1", engine
)
trade_dates["TradeDate"] = pd.to_datetime(trade_dates["TradeDate"]).dt.date
date_list = sorted(trade_dates["TradeDate"].tolist())
idx_today = date_list.index(TODAY)
dates_5  = date_list[max(0, idx_today-5):idx_today]
dates_10 = date_list[max(0, idx_today-10):idx_today]

# ---------- 只拉必要日期 + ts 直接转字符串 ----------
need_dates = [TODAY] + dates_10
date_str = "','".join([d.isoformat() for d in need_dates])

print("读取 delay_total ...")
t0 = time.time()
delay = pd.read_sql(
    f"""SELECT ID,
               CAST(ts AS CHAR) AS ts,  -- 关键：转字符串
               Delay_ms,
               Exchange,
               Calc_Date,
               category
        FROM delay_total
        WHERE Calc_Date IN ('{date_str}')""",
    engine
)
print("  返回行数:", len(delay), "耗时:", round(time.time()-t0, 2))
delay["Calc_Date"] = pd.to_datetime(delay["Calc_Date"]).dt.date

# ---------- 合并 & 构造 key / minute ----------
parse_id = pd.read_sql("SELECT ID, Trade_MC FROM parse_id", engine)
delay = delay.merge(parse_id, on="ID", how="left")
delay["key"] = (
    delay["ID"].astype(str) + "_" +
    delay["Trade_MC"].astype(str) + "_" +
    delay["category"].astype(str) + "_" +
    delay["Exchange"].astype(str)
)
delay["minute"] = pd.to_datetime(delay["ts"], format="%H:%M:%S").dt.floor("min").dt.time

# ---------- 聚合 ----------
def roll(df, dates, name):
    sub = df[df["Calc_Date"].isin(dates)]
    return (sub.groupby(["minute", "key"])["Delay_ms"]
            .mean() 
            .reset_index(name=name))

avg_5  = roll(delay, dates_5,  "avg_5d")
avg_10 = roll(delay, dates_10, "avg_10d")

# ---------- 合并输出 ----------
final = (
    avg_5
    .merge(avg_10, on=["minute", "key"], how="left")
)[["minute", "key", "avg_5d", "avg_10d"]].sort_values(["key", "minute"])

OUT_CSV = f"8800-近5-10天的平均延迟统计{TODAY:%Y%m%d}.csv"
final.to_csv(OUT_CSV, index=False, float_format="%.2f")
print("✅ 完成！文件已生成：", OUT_CSV)