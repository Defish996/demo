#!/bin/bash

if [ $# -ne 2 ]; then
	echo "用法: $0 <tradeDate> <accountID>"
	exit 1
fi

# 读取参数
TRADE_DATE="$1"
ACCOUNT_ID="$2"

# 前摇：MySQL 查询函数
mysql_query() {
	docker exec -e MYSQL_PWD=888888 mysql mysql -uroot ftdb_new -se "$1"
}
# 安全获取数值（空值转0）
safe_num() {
	echo "${1:-0}" | sed 's/NULL/0/g'
}

echo "----------T0 篮子数据（选择买卖双方都有且交易量最大的 basketId）----------"

T0_BASKET_ID=$(mysql_query "
    SELECT basketId
    FROM (
        SELECT
            basketId,
            COUNT(DISTINCT CASE WHEN buy_vol > 0 THEN 'B' WHEN sell_vol > 0 THEN 'S' END) AS bs_count,
            SUM((buy_vol + sell_vol) * prePrice) AS approx_amount
        FROM t0_profitinfo
        WHERE tradeDate = $TRADE_DATE 
          AND accountId = '$ACCOUNT_ID'
          AND (buy_vol > 0 OR sell_vol > 0)
          AND basketId IS NOT NULL AND basketId != ''
        GROUP BY basketId
        HAVING bs_count = 2
        ORDER BY approx_amount DESC
        LIMIT 1
    ) t;
")

if [ -z "$T0_BASKET_ID" ] || [ "$T0_BASKET_ID" = "NULL" ]; then
	echo "未找到 T0 中同时有买卖的 basketId"
else
	echo "选定的 T0 basketId: $T0_BASKET_ID"
    read global_auth_amount global_plan_vol <<<$(mysql_query "
        SELECT
            IFNULL(SUM(plan_vol * prePrice), 0),
            IFNULL(SUM(plan_vol), 0)
        FROM t0_profitinfo
        WHERE tradeDate = $TRADE_DATE
          AND accountId = '$ACCOUNT_ID'
          AND  basketId= '$T0_BASKET_ID';
    ")
    echo "$global_auth_amount, $global_plan_vol"
	auth_amount=$global_auth_amount
    sub_order_stats=$(mysql_query "
        SELECT
            IFNULL(SUM(CASE WHEN (bsFlag = 1 or bsFlag = 11 or bsFlag = 21) THEN tradeVol * tradePrice END), 0),
            IFNULL(SUM(CASE WHEN (bsFlag = 2 or bsFlag = 12 or bsFlag = 22) THEN tradeVol * tradePrice END), 0)
        FROM orderinfo_t0
        WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID' AND  basketId= '$T0_BASKET_ID';
    ")
	read buy_t0_vol sell_t0_vol <<<"$sub_order_stats"
	buy_t0_vol=$(safe_num "$buy_t0_vol")
	sell_t0_vol=$(safe_num "$sell_t0_vol")
	acc_buy_vol=$buy_t0_vol
	acc_sell_vol=$sell_t0_vol
    if [ "$(echo "$global_plan_vol > 0" | bc -l)" -eq 1 ]; then
		buy_ratio=$(awk "BEGIN {printf \"%.2f\", $acc_buy_vol / $auth_amount * 100}")
		sell_ratio=$(awk "BEGIN {printf \"%.2f\", $acc_sell_vol / $auth_amount * 100}")
	else
		buy_ratio="0.00"
		sell_ratio="0.00"
	fi

	echo "T0 篮子买比例: $(awk "BEGIN {printf \"%.2f\", $buy_ratio}")%"
	echo "T0 篮子卖比例: $(awk "BEGIN {printf \"%.2f\", $sell_ratio}")%"
fi