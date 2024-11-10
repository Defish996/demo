# 读取文件内容到列表，同时忽略空行
with open('alpha.txt', 'r') as file:
    # 仅当行不是空行时才添加到列表
    lines = [line.strip() for line in file if line.strip()]

# 输出列表以验证内容
lines