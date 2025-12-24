# %%
from main import *
s = login()


# # # %%

# df = get_datafields(s, dataset_id = 'analyst10', region='USA', universe='ILLIQUID_MINVOL1M', delay=1)
# print(df)
# print(df[df['type'] == "MATRIX"]["id"].tolist())
# pc_fields = process_datafields(df, "matrix")
# print(pc_fields)




# # df = get_datafields(s, dataset_id='news52', region='USA', universe='ILLIQUID_MINVOL1M', delay=1)
# # print(df[df['type'] == "VECTOR"]["id"].tolist())
# # print(len(df[df['type'] == "VECTOR"]["id"].tolist()))
# # ve_fields = process_datafields(df, "vector")
# # print(ve_fields)
# # print(len(ve_fields))




# first_order = first_order_factory(pc_fields, ops_set)
# print(first_order[:10])
# print(len(first_order))

# # Pad initial decay with alpha //每个alpha添加decay
# init_decay = 6
# fo_alpha_list = []
# for alpha in first_order:
#     fo_alpha_list.append((alpha, init_decay))
# print(len(fo_alpha_list))
# print(fo_alpha_list[:5])

# # Load alphas to task pools
# pools = load_task_pool(fo_alpha_list, 5,10)# 留一个位置用于网页回测
# print(pools[0])

# # Simulate First Order

# multi_simulate(pools, "STATISTICAL", "USA", "ILLIQUID_MINVOL1M", 390) #起始位置


# # %%

# # %%second
## get promising alphas to improve in the next order
# eg:
#    alphas = get_alphas("01-15 19:20:23", "01-15 22:02:12", 0.0, 0.0, "ASI", 100, "submit")    
fo_tracker = get_alphas("10-11 19:00:00", "10-20 22:02:12", 0.8, 0.5, "USA", 1600, "tarck") #[)
print(len(fo_tracker))



# %%
def prune(next_alpha_recs, prefix, keep_num):
    from collections import defaultdict
    output = []
    num_dict = defaultdict(int)

    # 先过滤：只保留含 prefix 的记录
    filtered_recs = [rec for rec in next_alpha_recs if prefix in rec[1]]

    for rec in filtered_recs:
        exp = rec[1]
        field = exp.split(prefix)[-1].split(",")[0]
        sharpe = rec[2]
        if sharpe < 0:
            field = "-" + field
        if num_dict[field] < keep_num:
            num_dict[field] += 1
            decay = rec[-1]
            output.append([exp, decay])
    return output
fo_layer = prune(fo_tracker, 'anl10_', 2)

for item in fo_layer:
    print(item[0], item[1], sep="\t")
print(len(fo_layer))



# %%

# %%
so_alpha_list = []
group_ops = ["group_neutralize", "group_rank",# "group_normalize",
              "group_scale",
                "group_zscore"]

for expr, decay in fo_layer:
    for alpha in get_group_second_order_factory([expr], group_ops, "USA"):
        so_alpha_list.append((alpha,decay))

print(len(so_alpha_list))
print(so_alpha_list[:3])




# %%

# %%
so_pools = load_task_pool(so_alpha_list, 9,10)
multi_simulate(so_pools, 'STATISTICAL', 'USA', 'ILLIQUID_MINVOL1M', 0)

# %% [markdown]
# ## Higher Order for improvement - Third Order
# group_ops(ts_ops(field, days), group) -> trade_when(entre_event, group_ops(ts_ops(field, days), group), exit_event)


# %%

# %%
## get promising alphas from second order to improve in the third order
# eg:
#    alphas = get_alphas("01-15 19:20:23", "01-15 22:02:12", 0.0, 0.0, "ASI", 100, "submit") 
so_tracker = get_alphas("10-11 19:00:00", "10-20 22:02:12", 1.0, 0.5, "USA", 600, "tarck")
print(len(so_tracker))

# 新剪枝，只为去掉alpha_id
def prune(next_alpha_recs, prefix, keep_num):
    from collections import defaultdict
    output = []
    num_dict = defaultdict(int)

    # 先过滤：只保留含 prefix 的记录
    filtered_recs = [rec for rec in next_alpha_recs if prefix in rec[1]]

    for rec in filtered_recs:
        exp = rec[1]
        field = exp.split(prefix)[-1].split(",")[0]
        sharpe = rec[2]
        if sharpe < 0:
            field = "-" + field
        
        num_dict[field] += 1
        decay = rec[-1]
        output.append([exp, decay])
    return output
fo_layer = prune(so_tracker, 'anl10_', 5)

for item in fo_layer:
    print(item[0], item[1], sep="\t")
print(fo_layer)
print(len(fo_layer))

# %%
# %%

# %% [markdown]
# ### Simulate Third Order


# %%
th_alpha_list = []
for expr, decay in fo_layer:
    for alpha in trade_when_factory("trade_when",expr,"USA"):
        th_alpha_list.append((alpha,decay))
print(len(th_alpha_list))
print(th_alpha_list[0])



# %%

# %%
# count = 0
# list = []
# for rec in th_alpha_list:
#         exp = rec[0]
#         if 'mdl138' in exp:
#                 print(exp)
#                 count += 1
#                 list.append(rec)

# print(count)

# %%
# Simulate third order
th_pools = load_task_pool(th_alpha_list, 9,10)
multi_simulate(th_pools, 'STATISTICAL', 'USA', 'ILLIQUID_MINVOL1M', 0)

# %% [markdown]
# ## 7, Get submittable alphas
# 


# %%

# %%
# 1.58 sharpe, 1 fitness, "submit"参数
# eg:
#    alphas = get_alphas("01-15 19:20:23", "01-15 22:02:12", 0.0, 0.0, "ASI", 100, "submit") 
th_tracker = get_alphas("10-11 19:00:00", "10-20 22:02:12", 1.58, 1.0, "USA", 600, "submit")

# %%
# count = 0
# list = []
# for rec in th_tracker:
#         exp = rec[1]
#         if 'mdl109' in exp:
#                 print(exp)
#                 count += 1
#                 list.append(rec)

# print(count)



# %%

# %%
## 将get的alpha的id取出至stone_bag，用api check submission
stone_bag = []
#for alpha in th_tracker:
for alpha in th_tracker:
    stone_bag.append(alpha[0])
print(len(stone_bag))
gold_bag = []
check_submission(stone_bag, gold_bag, 0)
print(gold_bag)

# %%
# 打印可提交的alpha信息并按sharpe排序，在网页上找到alpha手动提交
view_alphas(gold_bag)

# %% [markdown]
# ## 8, fine-tune submittable alphas
# neutralization, performance comparison, turnover, margin


