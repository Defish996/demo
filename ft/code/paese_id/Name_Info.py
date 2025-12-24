# Name_Info.py
import re, os, glob, pathlib, argparse, pandas as pd

try:
    from sqlalchemy import create_engine, text
except ImportError:
    create_engine = text = None
# -------------------------------------------------
# 1. 读文件（自动试编码）
# -------------------------------------------------
def try_read_first_col(path: pathlib.Path, encodings=None):
    if encodings is None:
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb18030', 'latin1']
    last_exc = None
    for enc in encodings:
        try:
            df = pd.read_csv(path, usecols=[0], encoding=enc,
                             names=['desc'], skiprows=1)
            print(f'成功读取，编码: {enc}')
            return df, enc
        except Exception as e:
            print(f'尝试编码 {enc} 失败: {type(e).__name__}: {e}')
            last_exc = e
    raise RuntimeError(f'所有编码尝试失败。最后一个错误: {last_exc}')

# -------------------------------------------------
# 2. 解析单行
# -------------------------------------------------
def parse_first_col(s: str):
    pattern = r"""
        (?P<ID>\d{3})
        (?P<ProductName>
              [\u4e00-\u9fa5]{2}\d
            | [\u4e00-\u9fa5]{2}(?!\d)
            | [\u4e00-\u9fa5]\d{2}
        )
        (?P<Broker>[\u4e00-\u9fa5]{2})
        (?P<TradeType>[^\x28]+)
        \s*\(交易:\s*(?P<Trade_MC>[^)]+)\)
        \s*\(API:\s*(?P<API_MC>[^)]+)\)
    """
    m = re.match(pattern, s.strip(), re.VERBOSE)
    if not m:
        return pd.Series([None]*6, index=['ID','ProductName','Broker',
                                          'TradeType','Trade_MC','API_MC'])
    return pd.Series(m.groupdict())

# -------------------------------------------------
# 3. 处理单个文件
# -------------------------------------------------
def process_one_csv(csv_path: pathlib.Path) -> pd.DataFrame:
    print(f'正在处理: {csv_path}')
    meta, _ = try_read_first_col(csv_path)
    # 解析
    meta = meta.join(meta['desc'].apply(parse_first_col))
    meta = meta.drop(columns='desc')
    # 类型/缺失值整理
    cols_for_pk = ['ID','ProductName','Broker','TradeType']
    meta[cols_for_pk] = meta[cols_for_pk].fillna('').astype(str)
    meta.replace({'None':None,'':None}, inplace=True)
    meta = meta.dropna(subset=['ID','Trade_MC'])
    meta['Date'] = pd.Timestamp.now()
    # 保证 Date 在最后
    cols = [c for c in meta if c != 'Date'] + ['Date']
    return meta[cols]

# -------------------------------------------------
# 4. 写入 MySQL（增量）
# -------------------------------------------------

def write_to_mysql(df: pd.DataFrame, table_name='parse_id'):
    if create_engine is None:
        raise RuntimeError('sqlalchemy 未安装，无法写入。')

    DB_URL = ('mysql+pymysql://delay_user:T7%23mK9%24vQ%21x2%40pL%26nR5%2AwE8sY'
              '%5Ea4FbN@10.0.0.4:3316/delay_data?charset=utf8mb4')
    engine = create_engine(DB_URL)

    # 重命名时间列
    df = df.rename(columns={'Date': 'created_at'})
    if 'created_at' not in df.columns:
        df['created_at'] = pd.Timestamp.now()

    # 保证列顺序
    cols = ['ID', 'ProductName', 'Broker', 'TradeType', 'Trade_MC', 'API_MC', 'created_at']
    df = df.reindex(columns=cols)

    # 批量构造 INSERT IGNORE 语句
    rows = [tuple(row) for row in df.itertuples(index=False, name=None)]
    if not rows:
        print('无新行需要插入。')
        return

    conn = engine.raw_connection()
    try:
        with conn.cursor() as cur:
            sql = f"""
                INSERT IGNORE INTO {table_name}
                (ID, ProductName, Broker, TradeType, Trade_MC, API_MC, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cur.executemany(sql, rows)
        conn.commit()
        print(f'写入完成: {cur.rowcount} 行插入表 {table_name}')
    finally:
        conn.close()

# -------------------------------------------------
# 5. 入口
# -------------------------------------------------
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-f','--folder', default=r'C:\code\csv汇总',
                        help='存放 csv 的文件夹')
    args = parser.parse_args()

    files = list(pathlib.Path(args.folder).rglob('*.csv'))
    if not files:
        print('指定目录下没有找到任何 CSV 文件，程序结束。')
        exit()

    all_df = pd.concat([process_one_csv(pathlib.Path(f)) for f in files],
                       ignore_index=True)
    print(f'共解析 {len(all_df)} 条记录，准备增量写入...')
    print('尝试写入:\n')
    print(all_df.head(20))
    try:
        write_to_mysql(all_df, table_name='parse_id')
    except Exception as e:
        print('写入 MySQL 失败:', type(e).__name__, e)