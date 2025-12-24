import re, chardet, pandas as pd
from pathlib import Path
from sqlalchemy import create_engine
from datetime import datetime   # 新增

# ========== 1. 基本配置 ==========
SRC_DIR   = Path('Total')

DB_URL = (
    'mysql+pymysql://delay_user:T7%23mK9%24vQ%21x2%40pL%26nR5%2AwE8sY%5Ea4FbN'
    '@10.0.0.4:3316/delay_data?charset=utf8mb4'
)
# 如果已有表名冲突，可以改这里
TABLE_NAME = 'parse_id'

engine = create_engine(DB_URL, pool_pre_ping=True)

# ========== 2. 老函数不动 ==========
# 读取文件的编码格式
def detect_encoding(file_path, n=2048):
    with open(file_path, 'rb') as f:
        return chardet.detect(f.read(n))['encoding'] or 'utf-8'

def parse_first_col(s: str):        #以正则表达式去解析
    pattern = r"""
        (?P<ID>\d{3,4})                    # 1. 3~4位数字
        (?P<ProductName>                   # 2. 保持原来的3种写法
            [\u4e00-\u9fa5]{2}\d
            | [\u4e00-\u9fa5]{2}(?!\d)
            | [\u4e00-\u9fa5]\d{2}
        )
        (?P<Broker>[\u4e00-\u9fa5]{2})     # 3. 2汉字
        (?P<TradeType>[^\x28]+)            # 4. 到左括号前
        \s*\(交易:\s*(?P<Trade_MC>[^)]+)\)  # 5. 交易必填
        (?:\(API:\s*(?P<API_MC>[^)]*)\))?   # 6. API可空，整体可选
    """
    m = re.match(pattern, s.strip(), re.VERBOSE)  #从头开始匹配 且同时删除空格，换行等
    return m.groupdict() if m else None

# ========== 3. 遍历解析  ==========

all_parts = []
now_str = datetime.now().strftime('%Y-%m-%d_%H:%M:%S')

for file in SRC_DIR.glob('*.csv'):
    enc = detect_encoding(file)
    try:
        df = pd.read_csv(file, usecols=[0], encoding=enc,
                         names=['desc'], skiprows=1)
    except UnicodeDecodeError:
        df = pd.read_csv(file, usecols=[0], encoding='utf-8',
                         names=['desc'], skiprows=1, encoding_errors='ignore')

    records = [parse_first_col(r) for r in df['desc'].dropna().astype(str)]
    records = [r for r in records if r]
    if records:
        part = pd.DataFrame(records)
        # 新增两列
        part['PK'] = part['ID'] + '&' + part['API_MC'].fillna('')
        part['Date'] = now_str
        all_parts.append(part)
    else:
        print(f'【提示】{file.name} 未匹配到任何记录，跳过')

if not all_parts:
    print('所有文件均未解析出有效数据，程序退出。')
    raise SystemExit(1)

final = pd.concat(all_parts, ignore_index=True)
# 1. 去掉完全重复的行（所有列都一样）
final = final.drop_duplicates()

# 2. 只按主键列去重（保留第一条）
final = final.drop_duplicates(subset=['PK'])


# ========== 4. 写入数据库（不变） ==========
from sqlalchemy import Table, Column, MetaData, VARCHAR, TIMESTAMP, PrimaryKeyConstraint

meta = MetaData()

# 1. 定义表结构，把 PK 设成主键
parse_id_table = Table(
    TABLE_NAME, meta,
    Column('ID',          VARCHAR(8)),
    Column('ProductName', VARCHAR(8)),
    Column('Broker',      VARCHAR(8)),
    Column('TradeType',   VARCHAR(20)),
    Column('Trade_MC',    VARCHAR(100)),
    Column('API_MC',      VARCHAR(100)),
    Column('PK',          VARCHAR(100), nullable=False),
    Column('Date',        TIMESTAMP),
    PrimaryKeyConstraint('PK', name='pk_parse_id')
)

# 2. 如果表已存在且想强制重建（测试阶段用）
# meta.drop_all(engine)
meta.create_all(engine, checkfirst=True)   # checkfirst=True 避免重复建表

# 3. 写入数据
final.to_sql(
    TABLE_NAME,
    con=engine,
    if_exists='append',
    index=False,
    dtype=None          # 已经用 Table 定义过结构，这里不用再指定
)
print(f'Finished! 共处理 {len(all_parts)} 个文件，合计 {len(final)} 条，已写入 {TABLE_NAME}。')