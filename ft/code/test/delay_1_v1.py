import re
import csv
import os
from datetime import datetime
from pathlib import Path

# ---------- 参数 ----------
RAW_FILE = Path('API下单首次回报延迟（平均）（上交所）.csv')   # 原始文件
OUT_FILE = RAW_FILE.with_name('clean_delay.csv')               # 清洗后文件
while True:
    date1 = input('请输入该数据对应的当天日期,并非下载时日期（纯数字格式，例：20250924）：').strip()
    date2 = input('请再次输入日期以确认：').strip()
    if date1 == date2:
        C_DATE = date1
        break
    print('两次输入不一致，请重新输入！')                                            # 固定生成日期
# 文件名 → 市场简写
MARKET_MAP = {'上交所': '上交所', '深交所': '深交所', '北交所' : '北交所', '港交所':'港交所'}

# ---------------------------

# ---------- 正则 ----------
def parse_first_col(s: str):
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
    m = re.match(pattern, s.strip(), re.VERBOSE)
    return m.groupdict() if m else None

# ---------- 主逻辑 ----------
def clean_delay_csv(src: Path, dst: Path, c_date: str):
    # 1. 从文件名拿市场
    se = ''
    for k, v in MARKET_MAP.items():
        if k in src.name:
            se = v
            break
    if not se:
        raise ValueError('无法从文件名识别交易所')

    with src.open(newline='', encoding='utf-8-sig') as f_in, \
         dst.open('w', newline='', encoding='utf-8') as f_out:

        reader = csv.reader(f_in)
        header = next(reader)          # 第一行是表头
        minutes = header[1:]            # 09:30:00 ...

        writer = csv.writer(f_out)
        # 写新 header
        writer.writerow(['ID', 'Minute', 'Delay', 'SE', 'C_Date', 'ID_DATE_MINUTE_BOURSE'])

        for row in reader:
            if not row:                # 空行
                continue
            first, *delays = row
            meta = parse_first_col(first)
            if not meta:               # 正则没匹配上
                continue
            _id = meta['ID']

            for minute, delay_str in zip(minutes, delays):
                if delay_str == '0' or delay_str == '':   # 只保留非 0 有效值
                    continue
                try:
                    delay = float(delay_str)
                except ValueError:
                    continue
                key = f"{_id}&{c_date}&{minute}&{se}"
                writer.writerow([_id, minute, delay, se, c_date, key])

    print(f'清洗完成 → {dst}')

# ---------- 运行 ----------
# ---------- 运行 ----------
if __name__ == '__main__':
    clean_delay_csv(RAW_FILE, OUT_FILE, C_DATE)
    # 统一在这里统计
    with OUT_FILE.open(encoding='utf-8') as f:
        rows = sum(1 for _ in f) - 1
    print(f'共输出 {rows} 条延迟记录')