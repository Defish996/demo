import pandas as pd
from sqlalchemy import create_engine
from datetime import date, timedelta

# 1. 基本配置 -----------------------------------------------------------------
# MySQL 连接串
DB_USER = "delay_user"
DB_PASS = "T7%23mK9%24vQ%21x2%40pL%26nR5%2AwE8sY%5Ea4FbN"
DB_HOST = "10.0.0.4"
DB_PORT = 3316
DB_NAME = "delay_data"

engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


TODAY = date(2025, 10, 30)          # 今天
OUT_CSV = f"delay_5_10_avg_{TODAY:%Y%m%d}.csv"

# 2. 读表 ---------------------------------------------------------------------
# 2.1 交易日表：只要 Market_open=1 的日期
trade_dates = pd.read_sql(
    "SELECT TradeDate FROM TradeDate WHERE Market_open=1", engine
)
trade_dates['TradeDate'] = pd.to_datetime(trade_dates['TradeDate']).dt.date
date_list = sorted(trade_dates['TradeDate'].tolist())

# 2.2 parse_id：ID 与 Trade_MC 的映射
parse_id = pd.read_sql(
    "SELECT ID, Trade_MC FROM parse_id", engine
)

# 2.3 delay_total：只要今天及之前 20 个自然日（保险值，后面再按交易日筛）
start_pull = TODAY - timedelta(days=20)
delay = pd.read_sql(
    f"""SELECT ID, ts, Delay_ms, Exchange, Calc_Date, category
        FROM delay_total
        WHERE Calc_Date BETWEEN '{start_pull}' AND '{TODAY}'""",
    engine
)
delay['Calc_Date'] = pd.to_datetime(delay['Calc_Date']).dt.date

# 3. 合并 & 构造“ID_机器_Exchange_category”字段 -----------------------------
delay = delay.merge(parse_id, on='ID', how='left')
delay['key'] = (
    delay['ID'].astype(str) + '_' +
    delay['Trade_MC'].astype(str) + '_' +
    delay['Exchange'].astype(str) + '_' +
    delay['category'].astype(str)
)

# 4. 按分钟聚合当日均值 --------------------------------------------------------
delay['minute'] = pd.to_datetime(delay['ts'], format='%H:%M:%S').dt.floor('min')
today_df = delay[delay['Calc_Date'] == TODAY]
min_avg = (
    today_df.groupby(['minute', 'key'])['Delay_ms']
    .mean()
    .reset_index()
    .rename(columns={'Delay_ms': 'today_avg'})
)

# 5. 构造过去 5/10 个交易日的日期列表 -----------------------------------------
idx_today = date_list.index(TODAY)
dates_5  = date_list[max(0, idx_today-5):idx_today]
dates_10 = date_list[max(0, idx_today-10):idx_today]

# 6. 计算 5 日、10 日平均 -----------------------------------------------------
hist = delay[delay['Calc_Date'].isin(dates_10)]  # 只要这 10 天
hist['minute'] = pd.to_datetime(hist['ts'], format='%H:%M:%S').dt.floor('min')

def roll_avg(df, date_lst):
    sub = df[df['Calc_Date'].isin(date_lst)]
    return (
        sub.groupby(['minute', 'key'])['Delay_ms']
        .mean()
        .reset_index()
        .rename(columns={'Delay_ms': f'avg_{len(date_lst)}d'})
    )

avg_5  = roll_avg(hist, dates_5)
avg_10 = roll_avg(hist, dates_10)

# 7. 三表合并 -----------------------------------------------------------------
final = (
    min_avg
    .merge(avg_5,  on=['minute', 'key'], how='left')
    .merge(avg_10, on=['minute', 'key'], how='left')
)

# 8. 整理列顺序 & 输出 ---------------------------------------------------------
final = final[['minute', 'key', 'avg_5d', 'avg_10d', 'today_avg']]
final = final.sort_values(['key', 'minute'])
final.to_csv(OUT_CSV, index=False, float_format='%.2f')

print(f"Done! 文件已生成：{OUT_CSV}")