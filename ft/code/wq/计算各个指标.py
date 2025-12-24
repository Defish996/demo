from main import * 
import pandas as pd
import requests
import time
import logging
from typing import List, Dict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def fetch_submitted_alphas(
        session: requests.Session,
        start_date: str,
        end_date: str,
        max_offset: int = 9900  # 最大偏移量限制
) -> List[Dict]:
    """
    拉取指定日期范围内提交的Alpha信息（基于count自动分页）

    参数:
        session: 已登录的requests会话对象
        start_date/end_date: 日期范围（格式：YYYY-MM-DD）
        max_offset: 最大偏移量（防止无限循环）

    返回:
        符合条件的Alpha信息列表
    """
    alpha_list = []
    offset = 0  # 起始偏移量

    while True:
        # 构建请求URL（恢复原始筛选条件，移除sharpe等额外筛选）
        url = (
            f"https://api.worldquantbrain.com/users/self/alphas?limit=100&offset={offset}"
            "&status!=UNSUBMITTED%1FIS_FAIL"
            f"&dateSubmitted%3E={start_date}T00:00:00-04:00"
            f"&dateSubmitted%3C={end_date}T00:00:00-04:00"
            "&order=-is.sharpe&hidden=false"
        )

        # 发送请求
        response = session.get(url)

        try:
            logger.info(f"当前偏移量: {offset}")
            # 解析响应数据
            response_data = response.json()
            total_count = response_data.get("count", 0)
            logger.info(f"符合条件的总数量: {total_count}")

            # 提取当前页结果
            if "results" in response_data:
                alpha_list.extend(response_data["results"])
                logger.info(f"累计获取: {len(alpha_list)} 条Alpha")

            # 判断终止条件：偏移量超过总数或达到最大限制
            offset += 100
            if offset >= total_count or offset > max_offset:
                logger.info("分页拉取完成")
                break

            # 避免请求过于频繁
            time.sleep(1)

        except Exception as e:
            logger.error(f"拉取失败: {str(e)}")
            # 回退偏移量并重试
            offset -= 100
            logger.info("等待10秒后重试...")
            time.sleep(10)
            # 重新登录获取会话
            session = login()
            # 确保偏移量不为负
            if offset < 0:
                offset = 0

    return alpha_list


def calculate_region_statistics(alpha_records: List[Dict]) -> pd.DataFrame:
    """按地区统计Alpha的关键指标"""
    analysis_data = []
    for alpha in alpha_records:
        # 提取地区信息
        region = alpha.get("settings", {}).get("region", "UNKNOWN")
        # 提取IS指标
        is_metrics = alpha.get("is", {})

        analysis_data.append({
            "region": region,
            "is_sharpe": is_metrics.get("sharpe"),
            "is_fitness": is_metrics.get("fitness"),
            "is_margin": is_metrics.get("margin")
        })

    # 分组统计
    alpha_df = pd.DataFrame(analysis_data)
    return alpha_df.groupby("region").agg(
        alpha_count=("region", "count"),
        avg_is_sharpe=("is_sharpe", "mean"),
        avg_is_fitness=("is_fitness", "mean"),
        avg_is_margin=("is_margin", "mean")
    ).reset_index()


def main():
    # 登录获取会话
    logger.info("开始登录...")
    session = login()
    if not session:
        logger.error("登录失败，无法继续")
        return

    # 拉取Alpha数据（使用原始日期范围）
    logger.info("开始拉取Alpha信息...")
    alphas = fetch_submitted_alphas(
        session=session,
        start_date="2024-01-01",
        end_date="2099-11-01"
    )
    logger.info(f"拉取完成，共获取 {len(alphas)} 条Alpha信息")

    # 统计并展示结果
    if alphas:
        stats = calculate_region_statistics(alphas)
        logger.info("\n===== 各地区Alpha统计结果 =====")
        print(stats.to_string(index=False))
    else:
        logger.info("未获取到任何Alpha信息，无法统计")


if __name__ == "__main__":
    main()