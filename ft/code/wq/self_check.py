from main import * 
sess = sign_in(cfg.username, cfg.password)
# 增量下载数据
download_data(flag_increment=True)
alpha_id = '3qqzvOo0'
os_alpha_ids, os_alpha_rets = load_data()
calc_self_corr(
        alpha_id=alpha_id,
        os_alpha_rets=os_alpha_rets,
        os_alpha_ids=os_alpha_ids,
    )
