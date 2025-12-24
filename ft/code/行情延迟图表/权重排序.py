import pandas as pd

# ----------------------------
# 配置区
# ----------------------------
INPUT_FILE = r"c:/code/行情延迟图表/query_result_2025-10-30T09_53_34.563454+08_00.csv"
OUTPUT_TO_CSV = True  # True: 输出到 CSV；False: 屏幕打印

# ----------------------------
# 数据读取（跳过最后一行可能的错误表头）
# ----------------------------
df_raw = pd.read_csv(
    INPUT_FILE,
    header=None,
    names=["时间", "机器", "当前延迟", "近4天平均延迟", "比例", "derive"],
    engine='python'
)

# 过滤掉“时间”列为“时间”的行（即表头行）
df = df_raw[df_raw["时间"] != "时间"].copy()

# 确保数值列是数字类型（避免字符串导致计算错误）
df["当前延迟"] = pd.to_numeric(df["当前延迟"], errors='coerce')
df["比例"] = pd.to_numeric(df["比例"], errors='coerce')
df = df.dropna(subset=["当前延迟", "比例"])  # 删除无法转数字的行

# ----------------------------
# 分组聚合：按 时间 + 机器
# ----------------------------
def agg_group(group):
    # 找当前延迟最大的行（若多个相同，取第一个）
    max_idx = group["当前延迟"].idxmax()
    row = group.loc[max_idx]
    derives = "|".join(group["derive"].astype(str).dropna().tolist())
    return pd.Series({
        "时间": row["时间"],
        "机器": row["机器"],
        "当前延迟": row["当前延迟"],
        "近5天平均延迟": row["近4天平均延迟"],
        "最高比例": row["比例"],
        "derive汇总": derives
    })

result_df = df.groupby(["时间", "机器"], as_index=False).apply(agg_group).reset_index(drop=True)

# ----------------------------
# 新增：计算“延迟影响权重”并排序（方案2）
# ----------------------------
result_df["延迟影响权重"] = (result_df["当前延迟"] * result_df["最高比例"]).round(1)
result_df = result_df.sort_values(by="延迟影响权重", ascending=False).reset_index(drop=True)

# 可选：删除“延迟影响权重”列（如果不想在输出中显示）
# result_df = result_df.drop(columns=["延迟影响权重"])

# ----------------------------
# 输出
# ----------------------------
if OUTPUT_TO_CSV:
    output_file = "权重排序结果.csv"
    result_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"✅ 处理完成，结果已按【延迟影响权重 = 当前延迟 × 最高比例】降序排序并保存到: {output_file}")
else:
    print("\n📊 处理结果预览（按延迟影响权重降序，前20行）:")
    print(result_df.head(20).to_string(index=False))
    print(f"\n📌 总共 {len(result_df)} 条记录。")