# 确定是否需要删除：比如相反方向的同个地址；相同方向的同个地址
# 有需要删除的群内确认
# 确认后如果是范围，代码转化一下；如果有相同方向的，代码去重重复值一下

# 十六进制范围输出
def print_hex_range(start_hex, end_hex, width=6, uppercase=True):
    start = int(start_hex, 16) if isinstance(start_hex, str) else start_hex
    end = int(end_hex, 16) if isinstance(end_hex, str) else end_hex
    # 构建格式字符串，例如 '0x{:06X}'
    fmt = f'0x{{:0{width}{"X" if uppercase else "x"}}}'
    # 生成所有格式化后的地址字符串
    addresses = [fmt.format(addr) for addr in range(start, end + 1)]
    # 一行输出，英文逗号 + 空格分隔
    print(",".join(addresses))

# 十六进制地址去重
def dedup_hex_addresses(hex_str):
    # 1. 按逗号分割，去除空格
    parts = [part.strip() for part in hex_str.split(",") if part.strip()]
    # 2. 标准化：转为小写（或大写）用于去重比较，但保留原始格式用于输出？
    # 这里我们统一转为小写进行比较，但输出时用规范格式（如 0x20002F → 统一为大写）
    normalized_to_original = {}
    seen_normalized = set()
    duplicates = set()
    unique_normalized = []
    for addr in parts:
        # 验证是否是合法十六进制地址（以 0x 开头）
        if not addr.startswith(("0x", "0X")):
            raise ValueError(f"无效地址格式: {addr}")
        try:
            # 转为整数再转回标准十六进制（统一格式）
            num = int(addr, 16)
            normalized = f"0x{num:X}"  # 统一用大写，如 0x20002F
        except ValueError:
            raise ValueError(f"无法解析十六进制地址: {addr}")
        if normalized in seen_normalized:
            duplicates.add(normalized)
        else:
            seen_normalized.add(normalized)
            unique_normalized.append(normalized)
    print("重复的地址:")
    if duplicates:
        print(",".join(sorted(duplicates)))
    else:
        print("无重复")
    print("\n去重后的地址（按首次出现顺序）:")
    print(",".join(unique_normalized))

# 核验两个字符串是否一致
def normalize_hex_list(hex_list_str, width=64):
    """
    将逗号分隔的十六进制地址列表标准化为固定宽度，并返回排序后的集合（用于比对）
    """
    # 拆分字符串
    hex_items = [item.strip() for item in hex_list_str.split(',')]

    normalized = set()
    for item in hex_items:
        if not item:
            continue
        # 转为整数再格式化为固定宽度
        val = int(item, 16)
        max_val = (1 << width) - 1
        if val > max_val:
            raise ValueError(f"Address {item} too large for {width}-bit")
        # 格式化为固定宽度小写 hex（无 0x 前缀）
        fixed_hex = f"{val:0{width // 4}x}"
        normalized.add(fixed_hex)

    return normalized  # 用 set 便于比对（忽略顺序和重复）

# 移除下划线
def remove_underscores(s):
    return s.replace('_', '')


# # 调用函数-十六进制范围输出
# print_hex_range("0x200011", "0x20002f")
#
# # 调用函数-十六进制去重
# input_str = "0x200011,0x200012,0x200013,0x200014,0x200015,0x200016,0x200017,0x200018,0x200019,0x20001A,0x20001B,0x20001C,0x20001D,0x20001E,0x20001F,0x200020,0x200021,0x200022,0x200023,0x200024,0x200025,0x200026,0x200027,0x200028,0x200029,0x20002A,0x20002B,0x20002C,0x20002D,0x20002E,0x20002F,0x20_00_11,0x20_00_12,0x20_00_13,0x20_00_14,0x20_00_15,0x20_00_16,0x20_00_17,0x20_00_18,0x20_00_19,0x20_00_1a"
# dedup_hex_addresses(input_str)
#
# # 调用核验两个字符串是否一致
# list1 = "0x200011,0x200012,0x200013,0x200014,0x200015,0x200016,0x200017,0x200018,0x200019,0x20001A,0x20001B,0x20001C,0x20001D,0x20001E,0x20001F,0x200020,0x200021,0x200022,0x200023,0x200024,0x200025,0x200026,0x200027,0x200028,0x200029,0x20002A,0x20002B,0x20002C,0x20002D,0x20002E,0x20002F"
# list2 = "0x200011,0x200012,0x200013,0x200014,0x200015,0x200016,0x200017,0x200018,0x200019,0x20001a,0x20001b,0x20001c,0x20001d,0x20001e,0x20001f,0x200020,0x200021,0x200022,0x200023,0x200024,0x200025,0x200026,0x200027,0x200028,0x200029,0x20002a,0x20002b,0x20002c,0x20002d,0x20002e,0x20002f"  # 顺序不同
# set1 = normalize_hex_list(list1, 64)
# set2 = normalize_hex_list(list2, 64)
# print("是否一致？", set1 == set2)  # True
# print("标准化后的地址：", sorted(set1))

# 调用移除下划线
# 提示用户输入，并将输入内容赋值给 text 变量
while 1:
    text = input("请输入类似格式的字符串（例如：0x20_00_60,0x20_00_61,...）：")
    print("你输入的内容是：", text)
    clean_text = remove_underscores(text)
    # 假设 clean_text 是已处理好的文本（字符串类型）
    # 打开文件（'w' 表示写入模式，若文件不存在则创建，存在则覆盖）
    with open('output.txt', 'w', encoding='utf-8') as f:
        # 将 clean_text 写入文件（若需保留 print 的换行效果，可添加 \n）
        f.write(f"{clean_text}\n")

