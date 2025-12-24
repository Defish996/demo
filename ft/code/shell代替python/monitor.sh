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

echo "---------- 拆单监控中心数据 ----------"

# 总交易额（万元）
sum_amount_raw=$(mysql_query "SELECT SUM(tradeVol * tradePrice) FROM orderinfo WHERE tradeDate=$TRADE_DATE AND accountID='$ACCOUNT_ID';")
sum_amount=$(awk "BEGIN {printf \"%.2f\", (${sum_amount_raw:-0}) / 10000}")
echo "总交易额（万元）: $sum_amount"

# 撤单率
read num den <<<$(mysql_query "
	SELECT
		SUM(CASE WHEN status IN (2,3,5) THEN 1 ELSE 0 END),
		COUNT(*)
	FROM orderinfo
	WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID';
")
num=$(safe_num "$num")
den=$(safe_num "$den")
if awk "BEGIN {exit($den == 0 ? 0 : 1)}"; then
	echo "有效订单数为 0，撤单率为 0"
	cancel_ratio="0.00%"
else
	cancel_ratio=$(awk "BEGIN {printf \"%.2f\", $num / $den * 100}")
	echo "撤单率（撤单子单数/有效子单数）: $cancel_ratio% ($num / $den)"
fi

# 总母单数
count_st=$(mysql_query "SELECT COUNT(*) FROM algo_profit WHERE trade_date=$TRADE_DATE AND account_id='$ACCOUNT_ID';")
count_st=$(safe_num "$count_st")
echo "总母单数: $count_st"

# 交易账户数
trade_acc_count=$(mysql_query "SELECT COUNT(DISTINCT trade_acc) FROM algo_profit WHERE trade_date=$TRADE_DATE AND account_id='$ACCOUNT_ID' AND trade_acc IS NOT NULL AND trade_acc != '';")
trade_acc_count=$(safe_num "$trade_acc_count")
echo "交易账户数: $trade_acc_count"

# 总买/卖交易额（万元）
sum_buy_raw=$(mysql_query "SELECT SUM(tradeVol * tradePrice) FROM orderinfo WHERE tradeDate=$TRADE_DATE AND accountID='$ACCOUNT_ID' AND (bsFlag=1 OR bsFlag=11 OR bsFlag=21);")
sum_sell_raw=$(mysql_query "SELECT SUM(tradeVol * tradePrice) FROM orderinfo WHERE tradeDate=$TRADE_DATE AND accountID='$ACCOUNT_ID' AND (bsFlag=2 OR bsFlag=12 OR bsFlag=22);")
sum_buy=$(awk "BEGIN {printf \"%.2f\", (${sum_buy_raw:-0}) / 10000}")
sum_sell=$(awk "BEGIN {printf \"%.2f\", (${sum_sell_raw:-0}) / 10000}")
echo "总买交易额（万元）: $sum_buy"
echo "总卖交易额（万元）: $sum_sell"

# 进度%
ratio=$(mysql_query "
	SELECT ROUND(
		(SELECT SUM(tradeVol * tradePrice)
		 FROM orderinfo
		 WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID'
		) /
		NULLIF(
			(SELECT SUM(
				CASE
					WHEN trade_vol != 0 THEN order_vol * avg_trade_price
					WHEN trade_vol = 0 AND order_vol != 0 THEN order_vol * prev_close_price
					ELSE 0
				END
			) FROM algo_profit
			WHERE trade_date = $TRADE_DATE AND account_id = '$ACCOUNT_ID' AND status NOT IN (6,7)), 0) * 100, 2);
")
echo "进度: ${ratio:-0.00}%"

# 错废单率%
error_ratio=$(mysql_query "
	SELECT ROUND(
		SUM(CASE WHEN status IN (6,7) THEN 1 ELSE 0 END) /
		NULLIF(COUNT(*), 0) * 100, 2)
	FROM orderinfo
	WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID';
")
echo "错废单率: ${error_ratio:-0.00}%"

echo "---------- 拆单账户监控数据 ---------"

# 优先选有 B/S 的，否则选买入最大的
TRADE_ACC=$(mysql_query "
	SELECT trade_acc FROM (
		SELECT 
			trade_acc,
			1 AS priority,
			SUM(
				CASE
					WHEN trade_vol != 0 THEN order_vol * avg_trade_price
					WHEN trade_vol = 0 AND order_vol != 0 THEN order_vol * prev_close_price
					ELSE 0
				END
			) AS trade_amount
		FROM algo_profit
		WHERE trade_date = $TRADE_DATE 
			AND account_id = '$ACCOUNT_ID'
			AND trade_acc IS NOT NULL 
			AND trade_acc != ''
			AND order_vol > 0
		GROUP BY trade_acc
		HAVING COUNT(DISTINCT bs_flag) = 2

		UNION ALL

		SELECT 
			trade_acc,
			2 AS priority,
			SUM(
				CASE
					WHEN trade_vol != 0 THEN order_vol * avg_trade_price
					WHEN trade_vol = 0 AND order_vol != 0 THEN order_vol * prev_close_price
					ELSE 0
				END
			) AS trade_amount
		FROM algo_profit
		WHERE trade_date = $TRADE_DATE 
			AND account_id = '$ACCOUNT_ID'
			AND trade_acc IS NOT NULL 
			AND trade_acc != ''
			AND order_vol > 0
			AND bs_flag IN (1, 11, 21)
		GROUP BY trade_acc
		HAVING COUNT(DISTINCT bs_flag) >= 1

		ORDER BY priority, trade_amount DESC
		LIMIT 1
	) t_final;
")

if [ -z "$TRADE_ACC" ] || [ "$TRADE_ACC" = "NULL" ] || [ "$TRADE_ACC" = "" ]; then
	echo "未找到满足条件的 trade_acc（优先：有 B/S；其次：有买入）"
	exit 1
fi

TRADE_ACC_NAME=$(mysql_query "SELECT tradeAccName FROM tradeaccinfo WHERE tradeAcc='$TRADE_ACC' LIMIT 1;")
TRADE_ACC_NAME=$(safe_num "$TRADE_ACC_NAME")
if [ "$TRADE_ACC_NAME" = "0" ] || [ -z "$TRADE_ACC_NAME" ]; then
	TRADE_ACC_NAME="(无名称)"
fi

echo "选定的 trade_acc: $TRADE_ACC ($TRADE_ACC_NAME)"

# 买入/卖出计划
read buy_c_ep sell_c_ep <<<$(mysql_query "
	SELECT
		IFNULL(ROUND(SUM(CASE WHEN (bs_flag = 1 OR bs_flag = 11 OR bs_flag = 21) AND status NOT IN (6,7) THEN
			CASE
				WHEN trade_vol != 0 THEN order_vol * avg_trade_price
				WHEN trade_vol = 0 AND order_vol != 0 THEN order_vol * prev_close_price
				ELSE 0
			END
		END), 2), 0),
		IFNULL(ROUND(SUM(CASE WHEN (bs_flag = 2 OR bs_flag = 12 OR bs_flag = 22) AND status NOT IN (6,7) THEN
			CASE
				WHEN trade_vol != 0 THEN order_vol * avg_trade_price
				WHEN trade_vol = 0 AND order_vol != 0 THEN order_vol * prev_close_price
				ELSE 0
			END
		END), 2), 0)
	FROM algo_profit
	WHERE trade_date = $TRADE_DATE AND account_id = '$ACCOUNT_ID' AND trade_acc = '$TRADE_ACC';
")
buy_c_ep=$(safe_num "$buy_c_ep")
sell_c_ep=$(safe_num "$sell_c_ep")

# 买/卖交易额
read buy_c_amt sell_c_amt <<<$(mysql_query "
	SELECT
		IFNULL(SUM(CASE WHEN bsFlag IN (1,11,21) THEN tradeVol * tradePrice ELSE 0 END), 0),
		IFNULL(SUM(CASE WHEN bsFlag IN (2,12,22) THEN tradeVol * tradePrice ELSE 0 END), 0)
	FROM orderinfo
	WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID' AND tradeAcc = '$TRADE_ACC';
")
buy_c_amt=$(safe_num "$buy_c_amt")
sell_c_amt=$(safe_num "$sell_c_amt")

echo "买入计划（万元）: $(awk "BEGIN {printf \"%.2f\", $buy_c_ep / 10000}")"
echo "卖出计划（万元）: $(awk "BEGIN {printf \"%.2f\", $sell_c_ep / 10000}")"
echo "买交易额（万元）: $(awk "BEGIN {printf \"%.2f\", $buy_c_amt / 10000}")"
echo "卖交易额（万元）: $(awk "BEGIN {printf \"%.2f\", $sell_c_amt / 10000}")"

# 总比例
den=$(awk "BEGIN {print $buy_c_ep + $sell_c_ep}")
if awk "BEGIN {exit($den == 0 ? 0 : 1)}"; then
	result="0.00"
else
	result=$(awk "BEGIN {printf \"%.2f\", ($buy_c_amt + $sell_c_amt) / $den * 100}")
fi
echo "总比例: $result%"

# 买入比例
if awk "BEGIN {exit($buy_c_ep == 0 ? 0 : 1)}"; then
	echo "买入计划为 0，买入比例为 0"
else
	ratio=$(awk "BEGIN {printf \"%.2f\", $buy_c_amt / $buy_c_ep * 100}")
	echo "买入比例%: $ratio"
fi

# 卖出比例
if awk "BEGIN {exit($sell_c_ep == 0 ? 0 : 1)}"; then
	echo "卖出计划为 0，卖出比例为 0"
else
	ratio=$(awk "BEGIN {printf \"%.2f\", $sell_c_amt / $sell_c_ep * 100}")
	echo "卖出比例%: $ratio"
fi

# 多空暴露%
den=$(awk "BEGIN {print $buy_c_amt + $sell_c_amt}")
if awk "BEGIN {exit($den == 0 ? 0 : 1)}"; then
	result="0.00"
else
	result=$(awk "BEGIN {printf \"%.2f\", ($buy_c_amt - $sell_c_amt) / $den * 100}")
fi
echo "多空暴露: $result%"

# 撤单率
read num den <<<$(mysql_query "
	SELECT
		SUM(CASE WHEN status IN (2,3,5) THEN 1 ELSE 0 END),
		COUNT(*)
	FROM orderinfo
	WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID' AND tradeAcc = '$TRADE_ACC';
")
num=$(safe_num "$num")
den=$(safe_num "$den")
if awk "BEGIN {exit($den == 0 ? 0 : 1)}"; then
	echo "有效订单数为 0，撤单率为 0"
else
	ratio=$(awk "BEGIN {printf \"%.2f\", $num / $den * 100}")
	echo "撤单率（撤单子单数/有效子单数）: $ratio% ($num / $den)"
fi

# 错废单率
ratio=$(mysql_query "
	SELECT ROUND(
		SUM(CASE WHEN status IN (6,7) THEN 1 ELSE 0 END) /
		NULLIF(COUNT(*), 0) * 100, 2)
	FROM orderinfo
	WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID' AND tradeAcc = '$TRADE_ACC';
")
echo "错废单率: ${ratio:-0.00}%"

echo "---------- 拆单账户篮子数据 ---------"

# 注意：algo_profit 表中字段为 basket_id
TRADE_basket=$(mysql_query "
    SELECT basket_id FROM (
        -- 优先：同时有买和卖的篮子
        SELECT 
            basket_id,
            1 AS priority,
            SUM(
                CASE
                    WHEN trade_vol != 0 THEN order_vol * avg_trade_price
                    WHEN trade_vol = 0 AND order_vol != 0 THEN order_vol * prev_close_price
                    ELSE 0
                END
            ) AS trade_amount
        FROM algo_profit
        WHERE trade_date = $TRADE_DATE 
          AND account_id = '$ACCOUNT_ID'
          AND basket_id IS NOT NULL 
          AND basket_id != ''
          AND order_vol > 0
        GROUP BY basket_id
        HAVING COUNT(DISTINCT bs_flag) = 2

        UNION ALL

        -- 备选：只有买入的篮子（bs_flag IN (1,11,21)）
        SELECT 
            basket_id,
            2 AS priority,
            SUM(
                CASE
                    WHEN trade_vol != 0 THEN order_vol * avg_trade_price
                    WHEN trade_vol = 0 AND order_vol != 0 THEN order_vol * prev_close_price
                    ELSE 0
                END
            ) AS trade_amount
        FROM algo_profit
        WHERE trade_date = $TRADE_DATE 
          AND account_id = '$ACCOUNT_ID'
          AND basket_id IS NOT NULL 
          AND basket_id != ''
          AND order_vol > 0
          AND bs_flag IN (1, 11, 21)
        GROUP BY basket_id
        HAVING COUNT(DISTINCT bs_flag) >= 1

        ORDER BY priority, trade_amount DESC
        LIMIT 1
    ) t_final;
")

if [ -z "$TRADE_basket" ] || [ "$TRADE_basket" = "NULL" ] || [ "$TRADE_basket" = "" ]; then
	echo "未找到满足条件的 basket_id（优先：有 B/S；其次：有买入）"
	exit 1
fi
echo "选定的 basket_id: $TRADE_basket"

	# 篮子买入/卖出计划
	read buy_b_ep sell_b_ep <<<$(mysql_query "
        SELECT
            IFNULL(ROUND(SUM(CASE WHEN (bs_flag = 1 or bs_flag = 11 or bs_flag = 21) AND status not in(6,7) THEN
                CASE
                    WHEN trade_vol != 0 THEN order_vol * avg_trade_price
                    WHEN trade_vol = 0 AND order_vol != 0 THEN order_vol * prev_close_price
                    ELSE 0
                END
            END), 2), 0),
            IFNULL(ROUND(SUM(CASE WHEN (bs_flag = 2 or bs_flag = 12 or bs_flag = 22) AND status not in(6,7) THEN
                CASE
                    WHEN trade_vol != 0 THEN order_vol * avg_trade_price
                    WHEN trade_vol = 0 AND order_vol != 0 THEN order_vol * prev_close_price
                    ELSE 0
                END
            END), 2), 0)
        FROM algo_profit
        WHERE trade_date = $TRADE_DATE AND account_id = '$ACCOUNT_ID' AND basket_id = '$TRADE_basket';
    ")
	buy_b_ep=$(safe_num "$buy_b_ep")
	sell_b_ep=$(safe_num "$sell_b_ep")

	# 篮子买/卖交易额（注意字段名：basketId）
	read buy_b_amt sell_b_amt <<<$(mysql_query "
        SELECT
            IFNULL(SUM(CASE WHEN bsFlag IN (1,11,21) THEN tradeVol * tradePrice ELSE 0 END), 0),
            IFNULL(SUM(CASE WHEN bsFlag IN (2,12,22) THEN tradeVol * tradePrice ELSE 0 END), 0)
        FROM orderinfo
        WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID' AND basketId = '$TRADE_basket';
    ")
	buy_b_amt=$(safe_num "$buy_b_amt")
	sell_b_amt=$(safe_num "$sell_b_amt")

	echo "篮子买入计划: $buy_b_ep"
	echo "篮子卖出计划: $sell_b_ep"
	echo "篮子买交易额: $(awk "BEGIN {printf \"%.2f\", $buy_b_amt / 10000}")"
	echo "篮子卖交易额: $(awk "BEGIN {printf \"%.2f\", $sell_b_amt / 10000}")"

# 篮子总比例
den=$(awk "BEGIN {print $buy_b_ep + $sell_b_ep}")
if awk "BEGIN {exit($den == 0 ? 0 : 1)}"; then
	result="0.00"
else
	result=$(awk "BEGIN {printf \"%.2f\", ($buy_b_amt + $sell_b_amt) / $den * 100}")
fi
echo "篮子总比例: $result%"

# 篮子买入比例
if awk "BEGIN {exit($buy_b_ep == 0 ? 0 : 1)}"; then
	echo "篮子买入计划为 0，买入比例为 0"
else
	ratio=$(awk "BEGIN {printf \"%.2f\", $buy_b_amt / $buy_b_ep * 100}")
	echo "篮子买入比例: $ratio%"
fi

# 篮子卖出比例
if awk "BEGIN {exit($sell_b_ep == 0 ? 0 : 1)}"; then
	echo "篮子卖出计划为 0，卖出比例为 0"
else
	ratio=$(awk "BEGIN {printf \"%.2f\", $sell_b_amt / $sell_b_ep * 100}")
	echo "篮子卖出比例: $ratio%"
fi

# 篮子多空暴露%
den=$(awk "BEGIN {print $buy_b_amt + $sell_b_amt}")
# 用 awk 自己判断是否为 0，避免 bc 报错和空字符串导致的整数比较报错
if awk "BEGIN {exit($den == 0 ? 0 : 1)}"; then
	result="0.00"
else
	result=$(awk "BEGIN {printf \"%.2f\", ($buy_b_amt - $sell_b_amt) / $den * 100}")
fi
echo "篮子多空暴露%: $result%"

# 篮子撤单率（排除错废单）
read num den <<<$(mysql_query "
    SELECT
        SUM(CASE WHEN status IN (2,3,5) THEN 1 ELSE 0 END),
        count(*)
    FROM orderinfo
    WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID' AND basketId='$TRADE_basket';")
num=$(safe_num "$num")
den=$(safe_num "$den")
if awk "BEGIN {exit($den == 0 ? 0 : 1)}"; then
	echo "篮子有效订单数为 0，撤单率为 0"
else
	ratio=$(awk "BEGIN {printf \"%.2f\", $num / $den * 100}")
	echo "篮子撤单率（撤单子单数/有效子单数）: $ratio% ($num / $den)"
fi

# 篮子错废单率
ratio=$(mysql_query "
  SELECT ROUND(
    SUM(CASE WHEN status IN (6,7) THEN 1 ELSE 0 END) /
    NULLIF(COUNT(*), 0) * 100, 2)
  FROM orderinfo
  WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID' AND basketId='$TRADE_basket';")
echo "篮子错废单率: ${ratio:-0.00}%"

# ---------- 底仓增强监控（T0） ----------
echo "----------底仓增强监控中心----------"

# Step 1: 获取 T0 母单数（来自 t0_profitinfo）
t0_mother_count=$(mysql_query "
    SELECT COUNT(*) 
    FROM t0_profitinfo 
    WHERE tradeDate = $TRADE_DATE AND accountId = '$ACCOUNT_ID' AND status not in (7);")
t0_mother_count=$(safe_num "$t0_mother_count")

if [ "$t0_mother_count" -eq 0 ]; then
	echo "无 T0 母单数据（t0_profitinfo 为空）"
else
	echo "T0 总母单数: $t0_mother_count"

	# Step 2: 从 t0_profitinfo 获取母单级汇总
	t0_summary=$(mysql_query "
        SELECT
            IFNULL(SUM(plan_vol * prePrice), 0) AS auth_amount,
            IFNULL(SUM(profit), 0) AS real_pnl_final,   -- 直接使用系统计算好的 profit
            IFNULL(SUM(fee), 0) AS total_fee,
            IFNULL(SUM(buy_vol), 0) AS buy_vol,
            IFNULL(SUM(sell_vol), 0) AS sell_vol
        FROM t0_profitinfo
        WHERE tradeDate = $TRADE_DATE AND accountId = '$ACCOUNT_ID';
    ")
	read auth_amount real_pnl_final total_fee buy_vol sell_vol <<<"$t0_summary"
	auth_amount=$(safe_num "$auth_amount")
	real_pnl_final=$(safe_num "$real_pnl_final")
	total_fee=$(safe_num "$total_fee")
	buy_vol=$(safe_num "$buy_vol")
	sell_vol=$(safe_num "$sell_vol")

	# Step 3: 从 orderinfo_t0 获取子单级数据（交易额、子单数、状态）
	sub_order_stats=$(mysql_query "
        SELECT
            IFNULL(SUM(CASE WHEN (bsFlag = 1 or bsFlag = 11 or bsFlag = 21) THEN tradeVol * tradePrice END), 0),
            IFNULL(SUM(CASE WHEN (bsFlag = 2 or bsFlag = 12 or bsFlag = 22) THEN tradeVol * tradePrice END), 0),
            COUNT(*),
            SUM(CASE WHEN status IN (2,3,5) THEN 1 ELSE 0 END),   -- 撤单：已撤(2)、部撤(3)、拒单(5)?
            SUM(CASE WHEN status IN (6,7) THEN 1 ELSE 0 END)     -- 错废单
        FROM orderinfo_t0
        WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID';
    ")
	read buy_t0_amt sell_t0_amt total_sub_orders cancel_num error_num <<<"$sub_order_stats"
	buy_t0_amt=$(safe_num "$buy_t0_amt")
	sell_t0_amt=$(safe_num "$sell_t0_amt")
	total_sub_orders=$(safe_num "$total_sub_orders")
	cancel_num=$(safe_num "$cancel_num")
	error_num=$(safe_num "$error_num")

	# 多头/空头敞口
	read long_exp short_exp <<<$(mysql_query "
        SELECT
            IFNULL(SUM(CASE WHEN (buy_vol - sell_vol) * latest_price > 0 THEN (buy_vol - sell_vol) * latest_price ELSE 0 END), 0),
            IFNULL(SUM(CASE WHEN (buy_vol - sell_vol) * latest_price < 0 THEN -(buy_vol - sell_vol) * latest_price ELSE 0 END), 0)
        FROM t0_profitinfo
        WHERE tradeDate = $TRADE_DATE AND accountId = '$ACCOUNT_ID';
    ")
	long_exp=$(safe_num "$long_exp")
	short_exp=$(safe_num "$short_exp")

	# 关键指标
	total_turnover=$(awk "BEGIN {print $buy_t0_amt + $sell_t0_amt}")
	if awk "BEGIN {exit($total_turnover == 0 ? 0 : 1)}"; then
		turnover_return="0.0000"
	else
		turnover_return=$(awk "BEGIN {printf \"%.4f\", $real_pnl_final / $total_turnover * 2 * 100}")
	fi

	if awk "BEGIN {exit($auth_amount == 0 ? 0 : 1)}"; then
		base_return="0.0000"
	else
		base_return=$(awk "BEGIN {printf \"%.4f\", $real_pnl_final / $auth_amount * 100}")
	fi

	if [ "$total_sub_orders" -gt 0 ]; then
		cancel_rate=$(awk "BEGIN {printf \"%.2f\", $cancel_num / $total_sub_orders * 100}")
		error_rate=$(awk "BEGIN {printf \"%.2f\", $error_num / $total_sub_orders * 100}")
	else
		cancel_rate="0.00"
		error_rate="0.00"
	fi

	# 输出
	echo "T0 总子单数: $total_sub_orders"
	echo "T0 总买交易额（万元）: $(awk "BEGIN {printf \"%.2f\", $buy_t0_amt / 10000}")"
	echo "T0 总卖交易额（万元）: $(awk "BEGIN {printf \"%.2f\", $sell_t0_amt / 10000}")"
	echo "实时盈亏: $(awk "BEGIN {printf \"%.2f\", $real_pnl_final}")"
	echo "交易额收益率: ${turnover_return}%"
	echo "授权金额（万元）: $(awk "BEGIN {printf \"%.2f\", $auth_amount / 10000}")"
	echo "底仓收益率: ${base_return}%"
	echo "多头敞口金额（万元）: $(awk "BEGIN {printf \"%.2f\", $long_exp / 10000}")"
	echo "空头敞口金额（万元）: $(awk "BEGIN {printf \"%.2f\", $short_exp / 10000}")"
	echo "T0 撤单率: ${cancel_rate}%"
	echo "T0 错废单率: ${error_rate}%"
fi

# ========== T0 账户监控：选择交易最活跃且有买卖的 tradeAcc ==========
echo "---------- T0 账户监控 ----------"
# Step 1: 找出同时有买有卖、且成交总额最大的 tradeAcc
T0_TRADE_ACC=$(mysql_query "
    SELECT tradeAcc
    FROM (
        SELECT
            tradeAcc,
            SUM(CASE WHEN bsFlag IN (1,11,21) THEN tradeVol * tradePrice ELSE 0 END) AS buy_amt,
            SUM(CASE WHEN bsFlag IN (2,12,22) THEN tradeVol * tradePrice ELSE 0 END) AS sell_amt
        FROM orderinfo_t0
        WHERE tradeDate = $TRADE_DATE
          AND accountID = '$ACCOUNT_ID'
          AND tradeAcc IS NOT NULL AND tradeAcc != ''
        GROUP BY tradeAcc
        HAVING buy_amt > 0 AND sell_amt > 0
        ORDER BY (buy_amt + sell_amt) DESC
        LIMIT 1
    ) t;
")

if [ -z "$T0_TRADE_ACC" ] || [ "$T0_TRADE_ACC" = "NULL" ]; then
	echo "未找到符合条件的 T0 tradeAcc"
	T0_ACC_NAME="(无)"
	real_pnl="0.00"
	turnover_return_rate="0.0000"
	base_return_rate="0.0000"
	auth_amount="0.00"
	buy_ratio="0.00"
	sell_ratio="0.00"
	long_exposure="0.00"
	short_exposure="0.00"
	cancel_rate="0.00"
	error_rate="0.00"
else
	# 获取账户名称
	T0_ACC_NAME=$(mysql_query "SELECT tradeAccName FROM tradeaccinfo WHERE tradeAcc='$T0_TRADE_ACC' LIMIT 1;")
	[ -z "$T0_ACC_NAME" ] && T0_ACC_NAME="(无名称)"

	# -------------------------------------------------
	# Step 2: 获取【全局】授权指标（全账户，不按 tradeAcc）
	# -------------------------------------------------
	read global_auth_amount global_plan_vol <<<$(mysql_query "
        SELECT
            IFNULL(SUM(plan_vol * prePrice), 0),
            IFNULL(SUM(plan_vol), 0)
        FROM t0_profitinfo
        WHERE tradeDate = $TRADE_DATE
          AND accountId = '$ACCOUNT_ID';
    ")
	global_auth_amount=$(safe_num "$global_auth_amount")
	global_plan_vol=$(safe_num "$global_plan_vol")

	# -------------------------------------------------
	# Step 3: 获取【当前 tradeAcc】的盈亏
	# -------------------------------------------------
	real_pnl=$(mysql_query "
        SELECT IFNULL(SUM(profit), 0)
        FROM t0_profitinfo
        WHERE tradeDate = $TRADE_DATE
          AND accountId = '$ACCOUNT_ID'
          AND tradeAcc = '$T0_TRADE_ACC';
    ")
	real_pnl=$(safe_num "$real_pnl")

	# -------------------------------------------------
	# Step 4: 计算多头/空头敞口（按 tradeAcc）
	# -------------------------------------------------
	read long_exposure short_exposure <<<$(mysql_query "
        SELECT
            IFNULL(SUM(CASE WHEN (buy_vol - sell_vol) * latest_price > 0 THEN (buy_vol - sell_vol) * latest_price ELSE 0 END), 0),
            IFNULL(SUM(CASE WHEN (buy_vol - sell_vol) * latest_price < 0 THEN -(buy_vol - sell_vol) * latest_price ELSE 0 END), 0)
        FROM t0_profitinfo
        WHERE tradeDate = $TRADE_DATE
          AND accountId = '$ACCOUNT_ID'
          AND tradeAcc = '$T0_TRADE_ACC';
    ")
	long_exposure=$(safe_num "$long_exposure")
	short_exposure=$(safe_num "$short_exposure")

	# -------------------------------------------------
	# Step 5: 从 orderinfo_t0 获取成交额和订单统计（按 tradeAcc）
	# -------------------------------------------------
	read buy_amt sell_amt total_sub_orders cancel_num error_num <<<$(mysql_query "
        SELECT
            IFNULL(SUM(CASE WHEN bsFlag IN (1,11,21) THEN tradeVol * tradePrice ELSE 0 END), 0),
            IFNULL(SUM(CASE WHEN bsFlag IN (2,12,22) THEN tradeVol * tradePrice ELSE 0 END), 0),
            COUNT(*),
            SUM(CASE WHEN status IN (2,3,5) THEN 1 ELSE 0 END),
            SUM(CASE WHEN status IN (6,7) THEN 1 ELSE 0 END)
        FROM orderinfo_t0
        WHERE tradeDate = $TRADE_DATE
          AND accountID = '$ACCOUNT_ID'
          AND tradeAcc = '$T0_TRADE_ACC';
    ")
	buy_amt=$(safe_num "$buy_amt")
	sell_amt=$(safe_num "$sell_amt")
	total_sub_orders=$(safe_num "$total_sub_orders")
	cancel_num=$(safe_num "$cancel_num")
	error_num=$(safe_num "$error_num")

	total_turnover=$(awk "BEGIN {print $buy_amt + $sell_amt}")

	# -------------------------------------------------
	# Step 6: 计算四个关键指标（修正版）
	# -------------------------------------------------

	# 授权金额 → 按 tradeAcc 查询
	auth_amount=$(mysql_query "
        SELECT IFNULL(SUM(plan_vol * prePrice), 0)
        FROM t0_profitinfo
        WHERE tradeDate = $TRADE_DATE
          AND accountId = '$ACCOUNT_ID'
          AND tradeAcc = '$T0_TRADE_ACC';
    ")
	auth_amount=$(safe_num "$auth_amount")

	# 成交额收益率 = real_pnl / total_turnover * 200%
	if awk "BEGIN {exit($total_turnover > 0.01 ? 0 : 1)}"; then
		turnover_return_rate=$(awk "BEGIN {printf \"%.4f\", $real_pnl / $total_turnover * 20000}")
	else
		turnover_return_rate="0.0000"
	fi

	# 底仓收益率 = real_pnl / 该 tradeAcc 授权金额 * 100%
	if awk "BEGIN {exit($auth_amount > 0.01 ? 0 : 1)}"; then
		base_return_rate=$(awk "BEGIN {printf \"%.4f\", $real_pnl / $auth_amount * 100}")
	else
		base_return_rate="0.0000"
	fi

	# 买比例、卖比例 = 该 tradeAcc 成交额 / 该 tradeAcc 授权金额
	if awk "BEGIN {exit($auth_amount > 0 ? 0 : 1)}"; then
		buy_ratio=$(awk "BEGIN {printf \"%.2f\", $buy_amt / $auth_amount * 100}")
		sell_ratio=$(awk "BEGIN {printf \"%.2f\", $sell_amt / $auth_amount * 100}")
	else
		buy_ratio="0.00"
		sell_ratio="0.00"
	fi

	# 撤单率 & 错废单率
	if [ "$total_sub_orders" -gt 0 ]; then
		cancel_rate=$(awk "BEGIN {printf \"%.2f\", $cancel_num / $total_sub_orders * 100}")
		error_rate=$(awk "BEGIN {printf \"%.2f\", $error_num / $total_sub_orders * 100}")
	else
		cancel_rate="0.00"
		error_rate="0.00"
	fi
fi

	# 输出
	echo "账户名称: $T0_ACC_NAME"
	echo "账户ID: ${T0_TRADE_ACC:-N/A}"
	echo "实时盈亏（万元）: $(awk "BEGIN {printf \"%.2f\", $real_pnl}")"
	echo "成交额收益率: $(awk "BEGIN {printf \"%.4f\", $turnover_return_rate}")%"
	echo "底仓收益率: $(awk "BEGIN {printf \"%.4f\", $base_return_rate}")%"
	echo "授权金额: $(awk "BEGIN {printf \"%.2f\", $auth_amount / 10000}")万"
	echo "买比例: $(awk "BEGIN {printf \"%.2f\", $buy_ratio}")%"
	echo "卖比例: $(awk "BEGIN {printf \"%.2f\", $sell_ratio}")%"
	echo "多头敞口金额: $(awk "BEGIN {printf \"%.2f\", $long_exposure}")"
	echo "空头敞口金额: $(awk "BEGIN {printf \"%.2f\", -$short_exposure}")"
	echo "撤单率: $(awk "BEGIN {printf \"%.2f\", $cancel_rate}")%"
	echo "错废单率: $(awk "BEGIN {printf \"%.2f\", $error_rate}")%"

# ---------- T0 篮子数据（选择买卖双方都有且交易量最大的 basketId） ----------
echo "---------- T0 篮子数据 ----------"

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

	# 成交与订单统计
	read buy_amt_b sell_amt_b total_sub_orders cancel_num error_num <<<$(mysql_query "
        SELECT
            IFNULL(SUM(CASE WHEN bsFlag IN (1,11,21) THEN tradeVol * tradePrice ELSE 0 END), 0),
            IFNULL(SUM(CASE WHEN bsFlag IN (2,12,22) THEN tradeVol * tradePrice ELSE 0 END), 0),
            COUNT(*),
            SUM(CASE WHEN status IN (2,3,5) THEN 1 ELSE 0 END),
            SUM(CASE WHEN status IN (6,7) THEN 1 ELSE 0 END)
        FROM orderinfo_t0
        WHERE tradeDate = $TRADE_DATE
          AND accountID = '$ACCOUNT_ID'
          AND basketId = $T0_BASKET_ID;
    ")
	buy_amt_b=$(safe_num "$buy_amt_b")
	sell_amt_b=$(safe_num "$sell_amt_b")
	total_sub_orders=$(safe_num "$total_sub_orders")
	cancel_num=$(safe_num "$cancel_num")
	error_num=$(safe_num "$error_num")

	# 盈亏、授权与敞口（合并查询，减少数据库访问）
	read real_pnl_final auth_amount long_exposure short_exposure <<<$(mysql_query "
        SELECT
            IFNULL(SUM(profit), 0),
            IFNULL(SUM(plan_vol * prePrice), 0),
            IFNULL(SUM(CASE WHEN (buy_vol - sell_vol) * latest_price > 0 THEN (buy_vol - sell_vol) * latest_price ELSE 0 END), 0),
            IFNULL(SUM(CASE WHEN (buy_vol - sell_vol) * latest_price < 0 THEN -(buy_vol - sell_vol) * latest_price ELSE 0 END), 0)
        FROM t0_profitinfo
        WHERE tradeDate = $TRADE_DATE
          AND accountId = '$ACCOUNT_ID'
          AND basketId = $T0_BASKET_ID;
    ")
	real_pnl_final=$(safe_num "$real_pnl_final")
	auth_amount=$(safe_num "$auth_amount")
	long_exposure=$(safe_num "$long_exposure")
	short_exposure=$(safe_num "$short_exposure")

	# 关键指标
	total_turnover=$(awk "BEGIN {print $buy_amt_b + $sell_amt_b}")
	# 用 awk 判断，避免 bc 报错
	if awk "BEGIN {exit($total_turnover > 0.01 ? 0 : 1)}"; then
		turnover_return=$(awk "BEGIN {printf \"%.4f\", $real_pnl_final / $total_turnover * 20000}")
	else
		turnover_return="0.0000"
	fi

	if awk "BEGIN {exit($auth_amount > 0.01 ? 0 : 1)}"; then
		base_return_rate=$(awk "BEGIN {printf \"%.4f\", $real_pnl_final / $auth_amount * 10000}")
	else
		base_return_rate="0.0000"
	fi

	if awk "BEGIN {exit($auth_amount > 0 ? 0 : 1)}"; then
		buy_ratio=$(awk "BEGIN {printf \"%.2f\", $buy_amt_b / $auth_amount * 100}")
		sell_ratio=$(awk "BEGIN {printf \"%.2f\", $sell_amt_b / $auth_amount * 100}")
	else
		buy_ratio="0.00"
		sell_ratio="0.00"
	fi

	if [ "$total_sub_orders" -gt 0 ]; then
		cr=$(awk "BEGIN {printf \"%.2f\", $cancel_num / $total_sub_orders * 100}")
		er=$(awk "BEGIN {printf \"%.2f\", $error_num / $total_sub_orders * 100}")
	else
		cr="0.00"
		er="0.00"
	fi

	# 输出
	echo "T0 篮子实时盈亏（万元）: $(awk "BEGIN {printf \"%.2f\", $real_pnl_final}")"
	echo "成交额收益率: $(awk "BEGIN {printf \"%.2f\", $turnover_return}")bp"
	echo "T0 篮子底仓收益率: $(awk "BEGIN {printf \"%.2f\", $base_return_rate}")bp"
	echo "T0 篮子授权金额: $(awk "BEGIN {printf \"%.2f\", $auth_amount / 10000}")万"
	echo "T0 篮子买比例: $(awk "BEGIN {printf \"%.2f\", $buy_ratio}")%"
	echo "T0 篮子卖比例: $(awk "BEGIN {printf \"%.2f\", $sell_ratio}")%"
	echo "T0 篮子多头敞口金额: $(awk "BEGIN {printf \"%.2f\", $long_exposure}")"
	echo "T0 篮子空头敞口金额: $(awk "BEGIN {printf \"%.2f\", -$short_exposure}")"
	echo "T0 篮子撤单率: ${cr}%"
	echo "T0 篮子错废单率: ${er}%"
fi
