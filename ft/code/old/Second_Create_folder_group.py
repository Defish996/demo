import shutil
from pathlib import Path

source_dir  = Path(r"C:\Users\1\Downloads")   # CSV 源目录
# 1. 根目录固定到 C:\code
code_root   = Path(r"C:\code")

csv_files   = list(source_dir.glob("*.csv"))

# 2. 分类列表（保持顺序）
categories = []
for file in csv_files:
    name = file.stem
    if "（" in name:
        category = name.split("（")[0].strip("_").strip()
        if category not in categories:
            categories.append(category)

# 3. 手工给分类排个序号，和图里保持一致
#    按你给出的顺序 1~5，注意顺序别乱
order_map = {
    "API下单首次回报延迟": 1,
    "API下单taker延迟": 2,
    "交易系统下单首次回报延迟": 3,
    "API撤单延迟": 4,
    "交易系统撤单延迟": 5,
}

# 4. 复制文件
for category in categories:
    seq = order_map.get(category)          # 拿到 1~5, 并进行匹配放入
    if not seq:
        print(f"警告：未找到序号，跳过 {category}")
        continue
    target_dir = code_root / f"{seq}" / "sec" / category
    target_dir.mkdir(parents=True, exist_ok=True)

    for file in csv_files:
        name = file.stem
        if name.startswith(category):
            dest_file = target_dir / file.name
            shutil.copy(file, dest_file)   # 同名就直接覆盖
