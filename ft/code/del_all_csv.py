# -*- coding: utf-8 -*-
"""
批量删除指定目录下所有 CSV 文件（含子目录）
python del_all_csv.py  D:\MyData
"""

import os
import sys
import send2trash  # 比 os.remove 安全，删到回收站；pip install Send2Trash

def collect_csv(root_dir):
    """返回 root_dir 下所有 *.csv 文件的绝对路径列表"""
    csv_list = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.lower().endswith('.csv'):
                csv_list.append(os.path.join(dirpath, f))
    return csv_list

def main(root_dir, dry_run=True):
    if not os.path.isdir(root_dir):
        print('路径不存在:', root_dir)
        sys.exit(1)

    csv_files = collect_csv(root_dir)
    if not csv_files:
        print('未找到任何 CSV 文件，无需删除。')
        return

    print('共发现 {} 个 CSV 文件，清单如下：'.format(len(csv_files)))
    for p in csv_files:
        print('  ', p)

    # 写入备份清单
    list_file = os.path.join(root_dir, 'to_be_deleted_csv_list.txt')
    with open(list_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(csv_files))
    print('\n已把待删列表写入:', list_file)

    if dry_run:
        print('\n*** 当前为试运行模式，未真正删除。***')
        print('确认无误后，把 dry_run 设为 False 再执行一次即可。')
        return

    # 真正删除
    ans = input('\n确认要永久删除上述 {} 个 CSV 文件吗？[y/N] '.format(len(csv_files)))
    if ans.lower() != 'y':
        print('已取消。')
        return

    for p in csv_files:
        try:
            send2trash.send2trash(p)
            print('已删除:', p)
        except Exception as e:
            print('删除失败:', p, e)
    print('全部处理完成。')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python del_all_csv.py  <目标目录>')
        sys.exit(1)
    target = os.path.abspath(sys.argv[1])
    main(target, dry_run=False)   # 第一次先跑 dry_run，确认无误后改成 False