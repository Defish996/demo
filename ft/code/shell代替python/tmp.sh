
# ---------- 监控中心（普通拆单） ----------
echo "----------监控中心（普通拆单）----------"

# 1. 买/卖交易额 & 数量（单位：元）
read buy_amt buy_vol <<< $(mysql_query "
    SELECT 
        IFNULL(SUM(CASE WHEN (bsFlag = 1 or bsFlag = 11 or bsFlag = 21) THEN tradeVol * tradePrice END), 0),
        IFNULL(SUM(CASE WHEN (bsFlag = 1 or bsFlag = 11 or bsFlag = 21) THEN tradeVol END), 0)
    FROM orderinfo 
    WHERE tradeDate=$TRADE_DATE AND accountID='$ACCOUNT_ID';")

read sell_amt sell_vol <<< $(mysql_query "
    SELECT 
        IFNULL(SUM(CASE WHEN (bsFlag = 2 or bsFlag = 12 or bsFlag = 22) THEN tradeVol * tradePrice END), 0),
        IFNULL(SUM(CASE WHEN (bsFlag = 2 or bsFlag = 12 or bsFlag = 22) THEN tradeVol END), 0)
    FROM orderinfo 
    WHERE tradeDate=$TRADE_DATE AND accountID='$ACCOUNT_ID';")

buy_amt=$(safe_num "$buy_amt"); buy_vol=$(safe_num "$buy_vol")
sell_amt=$(safe_num "$sell_amt"); sell_vol=$(safe_num "$sell_vol")

# 转换为万元，保留两位小数
buy_amt_wan=$(awk "BEGIN {printf \"%.2f\", $buy_amt / 10000}")
sell_amt_wan=$(awk "BEGIN {printf \"%.2f\", $sell_amt / 10000}")

echo "总买交易额（万元）: $buy_amt_wan"
echo "总卖交易额（万元）: $sell_amt_wan"
echo "买数量: $buy_vol"
echo "卖数量: $sell_vol"

# 2. 费用
settle_rate_raw=$(mysql_query "
    SELECT IFNULL(MAX(settleRate), 0) 
    FROM tradeaccinfo 
    WHERE id='$ACCOUNT_ID' AND settleByAmt IN (1,4,5);")
settle_rate=$(safe_num "$settle_rate_raw")
fee_rate=$(awk "BEGIN {printf \"%.6f\", $settle_rate / 10000}")
total_fee=$(awk "BEGIN {printf \"%.2f\", ($buy_amt + $sell_amt) * $fee_rate}")
echo "总费用: $total_fee"

# 3. 最新价（交易均价，券商版接受此近似）
total_vol=$(awk "BEGIN {print $buy_vol + $sell_vol}")
if [ "$(echo "$total_vol == 0" | bc -l)" -eq 1 ]; then
    latest_price=0
else
    total_turnover=$(awk "BEGIN {print $buy_amt + $sell_amt}")
    latest_price=$(awk "BEGIN {printf \"%.4f\", $total_turnover / $total_vol}")
fi
echo "最新价（交易均价）: $latest_price"

# 4. 实时盈亏
net_qty=$(awk "BEGIN {print $buy_vol - $sell_vol}")
unrealized=$(awk "BEGIN {printf \"%.2f\", $net_qty * $latest_price}")
real_pnl=$(awk "BEGIN {printf \"%.2f\", $sell_amt - $buy_amt + $unrealized - $total_fee}")
echo "实时盈亏: $real_pnl"

# 5. 交易额收益率
total_turnover=$(awk "BEGIN {print $buy_amt + $sell_amt}")
if awk "BEGIN {exit($total_turnover == 0 ? 0 : 1)}"; then
    turnover_return="0.00"
else
    turnover_return=$(awk "BEGIN {printf \"%.4f\", $real_pnl / $total_turnover * 2 * 100}")
fi
echo "交易额收益率: $turnover_return%"

# 6. 授权金额（券商版：保留你的 CASE 逻辑）
auth_amount=$(mysql_query "
    SELECT IFNULL(ROUND(SUM(
        CASE
            WHEN trade_vol != 0 THEN order_vol * avg_trade_price
            WHEN trade_vol = 0 AND order_vol != 0 THEN order_vol * prev_close_price
            ELSE 0
        END
    ), 2), 0)
    FROM algo_profit
    WHERE trade_date = $TRADE_DATE AND account_id = '$ACCOUNT_ID';")
auth_amount=$(safe_num "$auth_amount")
auth_wan=$(awk "BEGIN {printf \"%.2f\", $auth_amount / 10000}")
echo "授权金额（万元）: $auth_wan"

# 7. 底仓收益率
if [ "$(echo "$auth_amount == 0" | bc -l)" -eq 1 ]; then
    base_return="0.00"
else
    base_return=$(awk "BEGIN {printf \"%.4f\", $real_pnl / $auth_amount * 100}")
fi
echo "底仓收益率: $base_return%"

# 8. 买比例 / 卖比例
if [ "$(echo "$auth_amount == 0" | bc -l)" -eq 1 ]; then
    buy_prop="0.00"; sell_prop="0.00"
else
    buy_prop=$(awk "BEGIN {printf \"%.2f\", $buy_amt / $auth_amount * 100}")
    sell_prop=$(awk "BEGIN {printf \"%.2f\", $sell_amt / $auth_amount * 100}")
fi
echo "买比例: $buy_prop%"
echo "卖比例: $sell_prop%"

# 9. 多头/空头敞口
exposure_val=$(awk "BEGIN {printf \"%.2f\", $net_qty * $latest_price}")
if [ "$(echo "$exposure_val > 0" | bc -l)" -eq 1 ]; then
    long_exposure="$exposure_val"
    short_exposure="0.00"
else
    long_exposure="0.00"
    short_exposure=$(awk "BEGIN {printf \"%.2f\", -$exposure_val}")
fi
long_exposure_wand=$(awk "BEGIN {printf \"%.2f\", $long_exposure / 10000}")
echo "多头敞口金额: $long_exposure"
echo "空头敞口金额: $short_exposure"

# 10. 撤单率（同上，排除错废单）
read cancel_num total_all <<< $(mysql_query "
    SELECT
        SUM(CASE WHEN status IN (2,3,5) THEN 1 ELSE 0 END),
        COUNT(*)
    FROM orderinfo
    WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID';")
cancel_num=$(safe_num "$cancel_num"); total_all=$(safe_num "$total_all")
if [ "$(echo "$total_all == 0" | bc -l)" -eq 1 ]; then
    echo "撤单率: 0.00%"
else
    cancel_rate=$(awk "BEGIN {printf \"%.2f\", $cancel_num / $total_all * 100}")
    echo "撤单率: $cancel_rate%"
fi

# 11. 错废单率（不变）
error_num=$(mysql_query "
    SELECT SUM(CASE WHEN status IN (6,7) THEN 1 ELSE 0 END)
    FROM orderinfo
    WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID';")
error_num=$(safe_num "$error_num")
total_all=$(mysql_query "SELECT COUNT(*) FROM orderinfo WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID';")
total_all=$(safe_num "$total_all")
if [ "$(echo "$total_all == 0" | bc -l)" -eq 1 ]; then
    echo "错废单率: 0.00%"
else
    error_rate=$(awk "BEGIN {printf \"%.2f\", $error_num / $total_all * 100}")
    echo "错废单率: $error_rate%"
fi
