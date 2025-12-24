from main import * 

def get_simulation_result_json(s, alpha_id):
    return s.get('https://api.worldquantbrain.com' + "/alphas/" + alpha_id).json()


#  根据alpha ID 获取 prod correlation
def get_prod_corr(session, alpha_id):
    response = session.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}/correlations/prod")
    if response.status_code == 200 and "records" in response.json():
        columns = [dct["name"] for dct in response.json()["schema"]["properties"]]
        self_corr_df = pd.DataFrame(response.json()["records"], columns=columns)
        if not self_corr_df.empty:
            print(f'{alpha_id} max: {response.json()["max"]} min: {response.json()["min"]}')
            set_alpha_desc(session, alpha_id, f' max: {response.json()["max"]} min: {response.json()["min"]}')
        return self_corr_df
    else:
        return pd.DataFrame(columns=["correlation"])

# 因为经常第一次获取不到内容，可以调用这个函数来多次获取
def get_prod_corr_waiting(session, alpha_id, max_times=3):
    retry_count = 0
    while retry_count < max_times:
        try:
            self_corr_df = get_prod_corr(session, alpha_id)
            if not self_corr_df.empty:
                return self_corr_df
        except json.JSONDecodeError:
            pass
        retry_count += 1
        time.sleep(60)  # Wait for 60 second before the next retry
        print(retry_count)
    return pd.DataFrame(columns=["correlation"])

s = login()
start_time = datetime.now()
pass_pc_ids = []
last_request_time = datetime.now()
max_sleep_time = 60 * 5 # 最大睡眠时间1小时
current_sleep_time = 60 # 初始睡眠时间60秒
# 定义重连时间间隔
reconnect_interval = timedelta(hours=3.5)
for id in batch_ids:
# 检查是否需要重新登录
current_time = datetime.now()
if current_time - start_time >= reconnect_interval:
s = login()
start_time = current_time
# 记录请求开始时间
request_start_time = datetime.now()
# 调用 get_prod_corr
pc = get_prod_corr(s, id)
# 记录请求结束时间
request_end_time = datetime.now()
request_duration = (request_end_time - request_start_time).total_seconds()
# 检查相关性
if pc > 0.7:
    set_alpha_properties(s,id,name_value,selection_desc=name_value,combo_desc=name_value,tags = ['PROD Correlation'])
elif pc >0.5:
    set_alpha_properties(s,id,name_value,selection_desc=name_value,combo_desc=name_value,tags = ['ace_tag'])

else:
    result = get_simulation_result_json(s,id)

    selection = result['selection']['code']

    tag_value = ['PC 0.5','Ready to Submit']

    name_value = result['name']

if "own" in selection:

    color = 'GREEN'

    count = count+1

else:

    color = 'None'
    combo = result['combo']['code']
while len(selection)<100:
    selection = selection + selection
while len(combo)<100:
    combo = combo + combo set_alpha_properties(s,id,name_value,selection_desc=selection,combo_desc=combo,tags=tag_value,color=color)
    pass_pc_ids.append(id)
    print(id,pc)
# 计算上次请求到本次请求的时间间隔
time_since_last_request = (request_start_time - last_request_time).total_seconds()
# 如果请求时间明显增加，调整睡眠时间
if request_duration > current_sleep_time * 1.5:
    current_sleep_time = min(max_sleep_time, current_sleep_time * 2)
else:
    current_sleep_time = 60 # 如果请求时间正常，恢复默认睡眠时间
# 更新上次请求时间
last_request_time = request_start_time

# 等待当前睡眠时间

time.sleep(current_sleep_time)

print(len(pass_pc_ids))