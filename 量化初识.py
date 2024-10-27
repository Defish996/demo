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
    searchScope,
    dataset_id: str = '',
    search: str = ''
):
    import pandas as pd
    instrument_type = searchScope['instrumentType']
    region = searchScope['region']
    delay = searchScope['delay']
    universe = searchScope['universe']
    if len(search) == 0:
        url_template = "https://api.worldquantbrain.com/data-fields?" +\
            f"&instrumentType={instrument_type}" +\
            f"&region={region}&delay={str(delay)}&universe={universe}&dataset.id={dataset_id}&limit=50" +\
            "&offset={x}"
        count = s.get(url_template.format(x=0)).json()['count']
    else:
        url_template = "https://api.worldquantbrain.com/data-fields?" +\
            f"&instrumentType={instrument_type}" +\
            f"&region={region}&delay={str(delay)}&universe={universe}&limit=50" +\
            f"&search={search}" +\
            "&offset={x}"
        count = 100
        
    detafiles_list = []
    for x in range(0, count, 50):
        datafields = s.get(url_template.format(x=x))
        detafiles_list.append(datafields.json()['results'])
    datafields_list_flat = [item for sublist in detafiles_list for item in sublist]

    datafields_df = pd.DataFrame(datafields_list_flat)
    return datafields_df