#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
临时导出 CSV 版本，不再写库，仅生成文件：
delay_total_<date>.csv
字段顺序与库表完全一致：
ID,ts,Delay_ms,Exchange,Calc_Date,category
"""
import re
import csv
from pathlib import Path
from typing import Dict, Any, List

# ==================== 配置区域 ====================
# 交易所名称映射
MARKET_MAP = {'上交所': '上交所', '深交所': '深交所', '北交所': '北交所', '港交所': '港交所'}

TASKS = [
    {"name": "API下单首次回报延迟", "in_dir": Path("csv汇总/1/min/API下单首次回报延迟")},
    {"name": "API下单taker延迟", "in_dir": Path("csv汇总/2/min/API下单taker延迟")},
    {"name": "交易系统下单首次回报延迟", "in_dir": Path("csv汇总/3/min/交易系统下单首次回报延迟")},
    {"name": "API撤单延迟", "in_dir": Path("csv汇总/4/min/API撤单延迟")},
    {"name": "交易系统撤单延迟", "in_dir": Path("csv汇总/5/min/交易系统撤单延迟")},
]

CATEGORY_MAP = {
    "API下单首次回报延迟": "api_order_first_ack_min",
    "API下单taker延迟": "api_order_taker_min",
    "API撤单延迟": "api_cancel_min",
    "交易系统下单首次回报延迟": "trd_sys_order_first_ack_min",
    "交易系统撤单延迟": "trd_sys_cancel_min",
}

# ==================== 功能函数 ====================
def get_date_input() -> str:
    while True:
        date1 = input('当前是分钟级数据写入库, 时间应为下午, 请输入该数据对应的当天日期（纯数字格式，例：20250924）：').strip()
        if not date1.isdigit() or len(date1) != 8:
            print('日期格式不正确，请输入8位纯数字！')
            continue
        date2 = input('请再次输入日期以确认：').strip()
        if date1 == date2:
            return date1
        print('两次输入不一致，请重新输入！')

def parse_first_col(s: str) -> Dict[str, str]:
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

def process_csv_file_to_list(src: Path, c_date: str, category: str) -> List[List[str]]:
    """解析单个 CSV，返回要写入的最终列表（与表字段同序）"""
    exchange = next((v for k, v in MARKET_MAP.items() if k in src.name), None)
    if not exchange:
        raise ValueError(f'无法从文件名识别交易所：{src.name}')

    rows_out: List[List[str]] = []
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
                if delay_str.strip() != '':
                    try:
                        delay = float(delay_str)
                        # 与表字段顺序保持一致
                        rows_out.append([_id, minute, str(delay), exchange, c_date, category])
                    except ValueError:
                        continue
    return rows_out

def run_task_to_list(task: Dict[str, Any], c_date: str, master: List[List[str]]):
    print(f"\n--- 开始处理任务: {task['name']} ---")
    in_dir = task['in_dir']
    category = CATEGORY_MAP[task['name']]
    csv_files = list(in_dir.glob('*.csv'))
    if not csv_files:
        print(f'目录 {in_dir.absolute()} 内未找到 csv 文件')
        return

    total_files = 0
    total_rows = 0
    for src in csv_files:
        try:
            rows = process_csv_file_to_list(src, c_date, category)
            master.extend(rows)
            total_files += 1
            total_rows += len(rows)
            print(f'  -> {src.name} 解析 {len(rows)} 条')
        except Exception as e:
            print(f'  -> 跳过 {src.name}：{e}')
            continue
    print(f"--- 任务 '{task['name']}' 完成！共处理 {total_files} 个文件，累计 {total_rows} 条记录 ---")

def main():
    c_date = get_date_input()
    out_file = Path(f'delay_total_{c_date}.csv')
    header_row = ['ID', 'ts', 'Delay_ms', 'Exchange', 'Calc_Date', 'category']

    all_rows: List[List[str]] = []
    for task in TASKS:
        run_task_to_list(task, c_date, all_rows)

    # 写出 CSV
    with out_file.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header_row)
        writer.writerows(all_rows)

    print(f'\n全部完成！共 {len(all_rows)} 条记录 -> {out_file.absolute()}')

if __name__ == '__main__':
    main()