from main import *
s = login()



# df = get_datafields(s, dataset_id = 'analyst10', region='USA', universe='ILLIQUID_MINVOL1M', delay=1)
# print(df)
# print(df[df['type'] == "MATRIX"]["id"].tolist())
# pc_fields = process_datafields(df, "matrix")
# print(pc_fields)


# # %%
df = get_datafields(s, dataset_id='earnings7', region='USA', universe='ILLIQUID_MINVOL1M', delay=1)
print(df[df['type'] == "VECTOR"]["id"].tolist())
print(len(df[df['type'] == "VECTOR"]["id"].tolist()))
ve_fields = process_datafields(df, "vector")
print(ve_fields)
print(len(ve_fields))

# 定义可能的 decay 参数
decays = [5, 10, 20, 60, 120]
op = 'ts_rank'
first_list = []
for field in ve_fields:
    alpha = ts_factory(op, field)
    first_list.append(alpha)

op_list = ["ts_median","ts_sum", "ts_max", "ts_zscore", "ts_arg_max","ts_std_dev","ts_product","ts_delta","ts_delay","ts_count_nans","ts_av_diff","ts_arg_min","ts_arg_max"]
second_list = []
for alpha in first_list:
    for oper in op_list:
        tmp = ts_factory(oper, alpha)
        second_list.append(tmp)

print(second_list[:10])
print(len(second_list))

init_decay = 6
fo_alpha_list = []
for alpha in second_list:
    fo_alpha_list.append((alpha, init_decay))
print(fo_alpha_list[:10])
print(len(second_list))

pools = load_task_pool(fo_alpha_list, 4, 9)
print(pools[0])

multi_simulate(pools, "SUBINDUSTRY", "USA", "ILLIQUID_MINVOL1M", 0)