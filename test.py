import requests # 发送https请求
import json
from os.path import expanduser # 从 os.path 模块中导入 expanduser 函数,用于处理路径, 使用expanduser将 ~ 转换为当前用户的home目录
from requests.auth import HTTPBasicAuth # 从 requests 库中导入 HTTPBasicAuth 类。HTTPBasicAuth 类用于在发送 HTTP 请求时提供基本身份验证。

# 读取认证信息
with open(expanduser('brain_credentials.txt')) as f: # 使用 open 函数打开文件 brain_credentials.txt，文件路径通过 expanduser 函数进行扩展，确保路径中的 ~ 符号被正确解析为用户的家目录
    credentials = json.load(f) # 函数读取文件内容并将其解析为Python对象，存储在变量 credentials 中

# 从认证信息中提取用户名和密码
username, password = credentials # 提取这个元组中的两个值分别给 username 和 password

# 创建一个会话对象, 用于保持会话
sess = requests.Session() # 调用 request包中的Session() 方法创建一个会话对象

# 设置认证信息
sess.auth = HTTPBasicAuth(username, password)

# 发送post请求给这个API, 用于身份验证
response = sess.post('https://api.worldquantbrain.com/authentication')

# 打印状态码和响应内容
print(response.status_code)
print(response.json())

# 定义一个函数，用于获取满足条件的数据字段和ID
def get_datafields( # 该函数接收四个参数
    s, # 会话对象，用于发送 HTTP 请求
    searchScope, # 该字典包含搜索范围的参数
    dataset_id: str = '', # 指定字符集的ID 默认为空
    search: str = '' # 指定搜索关键字
):
    import pandas as pd # 引入该库用于数学分析, 并给一个别名叫做pd
    instrument_type = searchScope['instrumentType'] # 从searchScope中提取key为instrumentType的value, 表示工具类型
    region = searchScope['region'] # 区域
    delay = searchScope['delay'] # 延迟
    universe = searchScope['universe'] # 市场
    if len(search) == 0: # 若搜索关键字为空, 构建一个模版, 用于获取数据字段信息
        url_template = "https://api.worldquantbrain.com/data-fields?" +\
            f"&instrumentType={instrument_type}" +\
            f"&region={region}&delay={str(delay)}&universe={universe}&dataset.id={dataset_id}&limit=50" +\
            "&offset={x}"
        count = s.get(url_template.format(x=0)).json()['count'] # 发送GET请求, 获取总的数据字段数量
    else: # 构建另一个URL模板，这次包含search参数
        url_template = "https://api.worldquantbrain.com/data-fields?" +\
            f"&instrumentType={instrument_type}" +\
            f"&region={region}&delay={str(delay)}&universe={universe}&limit=50" +\
            f"&search={search}" +\
            "&offset={x}"
        count = 100 # 如果提供了搜索关键字，将固定获取100条记录。
        
    detafiles_list = [] # 储存每次请求的数据字段信息
    for x in range(0, count, 50): # 使用一个循环，每次请求50条记录，直到获取所有记录
        datafields = s.get(url_template.format(x=x)) # 发送HTTP GET请求到API，获取数据字段信息。
        detafiles_list.append(datafields.json()['results']) # 将每次请求的结果添加到列表中
    datafields_list_flat = [item for sublist in detafiles_list for item in sublist] # 将列表中的嵌套列表展平成一个单一列表

    datafields_df = pd.DataFrame(datafields_list_flat) # 使用Pandas将展平的列表转换为DataFrame。
    return datafields_df # 返回结果