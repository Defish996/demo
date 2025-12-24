#!/bin/bash

if [ $# -ne 2 ]; then
    echo "用法: $0 <tradeDate> <accountID>"
    exit 1
fi
# 读取参数
TRADE_DATE="$1"
ACCOUNT_ID="$2"
# 前摇
mysql_query() {
    docker exec -e MYSQL_PWD=888888 mysql mysql -uroot ftdb_new -se "$1"
}
# 拆单监控中心数据
echo "----------拆单监控中心数据----------"
#总交易额
sum_amount=$(mysql_query "select ROUND(SUM(tradeVol * tradePrice) / 10000, 2) from orderinfo where tradeDate=$TRADE_DATE and accountID ='$ACCOUNT_ID';")
echo "总交易额（万元）: $sum_amount"

# 撤单率
read num den <<< $(mysql_query "
    SELECT
        SUM(CASE WHEN status IN (2,3,5) THEN 1 ELSE 0 END),
        COUNT(*)
    FROM orderinfo
    WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID';
")
# 处理 NULL（当没有数据时 SUM 可能返回 NULL）
num=${num:-0}
den=${den:-0}
if [ "$den" -eq 0 ]; then
    echo "总订单数为 0，撤单率为 0"
else
    ratio=$(awk "BEGIN {printf \"%.2f\", $num / $den * 100}")
    echo "撤单率%（撤单子单数/总子单数）: $ratio ($num / $den)"
fi
#总母单数
count_st=$(mysql_query "select count(*) from algo_profit where trade_date=$TRADE_DATE and account_id='$ACCOUNT_ID';")
echo "总母单数: $count_st"
#总买成交额
sum_buy=$(mysql_query "select ROUND(sum(tradeVol * tradePrice) / 10000, 2) from orderinfo where tradeDate=$TRADE_DATE and accountID='$ACCOUNT_ID' and bsFlag=1;")
echo "总买交易额（万元）: $sum_buy"
#总卖成交额
sum_sell=$(mysql_query "select ROUND(sum(tradeVol * tradePrice) / 10000, 2) from orderinfo where tradeDate=$TRADE_DATE and accountID='$ACCOUNT_ID' and bsFlag=2;")
echo "总卖交易额（万元）: $sum_sell"
#总进度
ratio=$(mysql_query "
  SELECT ROUND(
    (SELECT SUM(tradeVol * tradePrice)
     FROM orderinfo
     WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID'
    ) /
    NULLIF(
      (SELECT SUM(
          CASE
            WHEN trade_vol!=0 THEN order_vol * avg_trade_price
            WHEN trade_vol=0 and order_vol!=0 THEN order_vol * prev_close_price
            ELSE 0
          END
        ) FROM algo_profit
        WHERE trade_date = $TRADE_DATE AND account_id = '$ACCOUNT_ID' and status not in(6,7)),0)*100,2);")
echo "进度%: ${ratio:-0.00}"
#总错废单率
ratio=$(mysql_query "
  SELECT ROUND(
    SUM(CASE WHEN status IN (6,7) THEN 1 ELSE 0 END) /
    NULLIF(COUNT(*), 0)*100,2)
  FROM orderinfo
  WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID';")

echo "错废单率%: ${ratio:-0.00}"

# 拆单账户监控数据（选择买卖双方都有且交易量最大的账户）
echo "----------拆单账户监控数据（选择买卖双方都有且交易量最大的账户）---------"
#查找买卖双方都有且交易量最大的账户
TRADE_ACC=$(mysql_query "
    SELECT trade_acc
    FROM (
        SELECT
            trade_acc,
            COUNT(DISTINCT bs_flag) AS counts,
            SUM(trade_amount) AS trade_amount
        FROM algo_profit
        WHERE trade_date = $TRADE_DATE AND account_id = '$ACCOUNT_ID' and trade_amount!=0
        GROUP BY trade_acc
        HAVING counts = 2
        ORDER BY trade_amount DESC
        LIMIT 1
    ) t1;")
if [ -z "$TRADE_ACC" ] || [ "$TRADE_ACC" = "NULL" ]; then
    echo "未找到满足条件的 trade_acc（需同时有 B/S 且金额最高）"
    exit 1
fi
echo "选定的 trade_acc: $TRADE_ACC"
#买入计划
buy_c_ep=$(mysql_query "SELECT round(SUM(
        CASE
            WHEN trade_vol!=0 THEN order_vol * avg_trade_price
            WHEN trade_vol=0 and order_vol!=0 THEN order_vol * prev_close_price
            ELSE 0
        END
        ),2) FROM algo_profit
        WHERE trade_date = $TRADE_DATE AND account_id = '$ACCOUNT_ID' and trade_acc = '$TRADE_ACC' and bs_flag=1 and status not in(6,7);")
echo "买入计划: $buy_c_ep"
#卖出计划
sell_c_ep=$(mysql_query "SELECT round(SUM(
          CASE
            WHEN trade_vol!=0 THEN order_vol * avg_trade_price
            WHEN trade_vol=0 and order_vol!=0 THEN order_vol * prev_close_price
            ELSE 0
          END
        ),2) FROM algo_profit
        WHERE trade_date = $TRADE_DATE AND account_id = '$ACCOUNT_ID' and trade_acc = '$TRADE_ACC' and bs_flag=2 and status not in(6,7);")
echo "卖出计划: $sell_c_ep"
#买成交额
buy_c_amt=$(mysql_query "select round(sum(tradeVol*tradePrice),2) as trade_amount from orderinfo where tradeDate=$TRADE_DATE and accountID ='$ACCOUNT_ID' and bsFlag=1 and tradeAcc='$TRADE_ACC';")
echo "买成交额: $buy_c_amt"
#卖成交额
sell_c_amt=$(mysql_query "select round(sum(tradeVol*tradePrice),2) as trade_amount from orderinfo where tradeDate=$TRADE_DATE and accountID ='$ACCOUNT_ID' and bsFlag=2 and tradeAcc='$TRADE_ACC';")
echo "卖成交额: $sell_c_amt"
#总比例
buy_c_amt=${buy_c_amt:-0}; sell_c_amt=${sell_c_amt:-0}; buy_c_ep=${buy_c_ep:-0}; sell_c_ep=${sell_c_ep:-0}
den=$(awk "BEGIN {print $buy_c_ep + $sell_c_ep}")
if [ "$den" -eq 0 ]; then
    result="0.00"
else
    result=$(awk "BEGIN {printf \"%.2f\", ($buy_c_amt + $sell_c_amt) / ($buy_c_ep + $sell_c_ep) * 100}")
fi
echo "总比例: $result%"
#买入比例
buy_c_amt=${buy_c_amt:-0}
buy_c_ep=${buy_c_ep:-0}
if awk "BEGIN {exit ($buy_c_ep == 0) ? 0 : 1}"; then·
    echo "买入计划为 0，买入比例为 0"
else
    ratio=$(awk "BEGIN {printf \"%.2f\", $buy_c_amt/ $buy_c_ep * 100}")
    echo "买入比例%: $ratio"
fi
#卖出比例
sell_c_amt=${sell_c_amt:-0}
sell_c_ep=${sell_c_ep:-0}
if awk "BEGIN {exit ($sell_c_ep == 0) ? 0 : 1}"; then
    echo "卖出计划为 0，卖出比例为 0"
else
    ratio=$(awk "BEGIN {printf \"%.2f\", $sell_c_amt/ $sell_c_ep * 100}")
    echo "卖出比例%: $ratio"
fi
#多空暴露
buy_c_amt=${buy_c_amt:-0}; sell_c_amt=${sell_c_amt:-0}
den=$(awk "BEGIN {print $buy_c_amt + $sell_c_amt}")
if [ "$den" -eq 0 ]; then
    result="0.00"
else
    result=$(awk "BEGIN {printf \"%.2f\", ($buy_c_amt - $sell_c_amt) / ($buy_c_amt + $sell_c_amt) * 100}")
fi
echo "多空暴露%: $result%"
#撤单率
read num den <<< $(mysql_query "
    SELECT
        SUM(CASE WHEN status IN (2,3,5) THEN 1 ELSE 0 END),
        COUNT(*)
    FROM orderinfo
    WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID' and tradeAcc='$TRADE_ACC';")
num=${num:-0}
den=${den:-0}
if [ "$den" -eq 0 ]; then
    echo "总订单数为 0，撤单率为 0"
else
    ratio=$(awk "BEGIN {printf \"%.2f\", $num / $den * 100}")
    echo "撤单率%（撤单子单数/总子单数）: $ratio ($num / $den)"
fi
#废错单率
ratio=$(mysql_query "
  SELECT ROUND(
    SUM(CASE WHEN status IN (6,7) THEN 1 ELSE 0 END) /
    NULLIF(COUNT(*), 0)*100,2)
  FROM orderinfo
  WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID' and tradeAcc='$TRADE_ACC';")
echo "错废单率%: ${ratio:-0.00}"

# 拆单账户篮子数据（选择买卖双方都有且交易量最大的篮子）
echo "----------拆单账户篮子数据（选择买卖双方都有且交易量最大的篮子）---------"
#查找买卖双方都有且交易量最大的篮子
TRADE_basket=$(mysql_query "
    SELECT basket_id
    FROM (
        SELECT
            basket_id,
            COUNT(DISTINCT bs_flag) AS counts,
            SUM(trade_amount) AS trade_amount
        FROM algo_profit
        WHERE trade_date = $TRADE_DATE AND account_id = '$ACCOUNT_ID' and trade_amount!=0
        GROUP BY basket_id
        HAVING counts = 2
        ORDER BY trade_amount DESC
        LIMIT 1
    ) t1;")
if [ -z "$TRADE_basket" ] || [ "$TRADE_basket" = "NULL" ]; then
    echo "未找到满足条件的 basket_id（需同时有 B/S 且金额最高）"
    exit 1
fi
echo "选定的 basket_id: $TRADE_basket"
#篮子买入计划
buy_b_ep=$(mysql_query "SELECT round(SUM(
        CASE
            WHEN trade_vol!=0 THEN order_vol * avg_trade_price
            WHEN trade_vol=0 and order_vol!=0 THEN order_vol * prev_close_price
            ELSE 0
        END
        ),2) FROM algo_profit
        WHERE trade_date = $TRADE_DATE AND account_id = '$ACCOUNT_ID' and basket_id = '$TRADE_basket' and bs_flag=1;")
echo "篮子买入计划: $buy_b_ep"
#篮子卖出计划
sell_b_ep=$(mysql_query "SELECT round(SUM(
          CASE
            WHEN trade_vol!=0 THEN order_vol * avg_trade_price
            WHEN trade_vol=0 and order_vol!=0 THEN order_vol * prev_close_price
            ELSE 0
          END
        ),2) FROM algo_profit
        WHERE trade_date = $TRADE_DATE AND account_id = '$ACCOUNT_ID' and basket_id = '$TRADE_basket' and bs_flag=2;")
echo "篮子卖出计划: $sell_b_ep"

#篮子买成交额
buy_b_amt=$(mysql_query "select round(sum(tradeVol*tradePrice),2) as trade_amount from orderinfo where tradeDate=$TRADE_DATE and accountID ='$ACCOUNT_ID' and bsFlag=1 and basketId='$TRADE_basket';")
echo "篮子买成交额: $buy_b_amt"
#篮子卖成交额
sell_b_amt=$(mysql_query "select round(sum(tradeVol*tradePrice),2) as trade_amount from orderinfo where tradeDate=$TRADE_DATE and accountID ='$ACCOUNT_ID' and bsFlag=2 and basketId='$TRADE_basket';")
echo "篮子卖成交额: $sell_b_amt"

#篮子总比例
buy_b_amt=${buy_b_amt:-0}; sell_b_amt=${sell_b_amt:-0}; buy_b_ep=${buy_b_ep:-0}; sell_b_ep=${sell_b_ep:-0}
den=$(awk "BEGIN {print $buy_b_ep + $sell_b_ep}")
if ["$den" -eq 0]; then
    result="0.00"
else
    result=$(awk "BRGIN {printf \"%.2f\", ($buy_b_amt + $sell_b_amt) / ($buy_b_ep + $sell_b_ep) * 100}")
fi
echo "篮子总比例: $result%"
#篮子买入比例
buy_b_amt=${buy_b_amt:-0}
buy_b_ep=${buy_b_ep:-0}
if awk "BEGIN {exit ($buy_b_ep == 0) ? 0 : 1}"; then
    echo "篮子买入计划为 0，买入比例为 0"
else
    ratio=$(awk "BEGIN {printf \"%.2f\", $buy_b_amt/ $buy_b_ep * 100}")
    echo "篮子买入比例%: $ratio"
fi
#篮子卖出比例
sell_b_amt=${sell_b_amt:-0}
sell_b_ep=${sell_b_ep:-0}
if awk "BEGIN {exit ($sell_b_ep == 0) ? 0 : 1}"; then
    echo "篮子卖出计划为 0，卖出比例为 0"
else
    ratio=$(awk "BEGIN {printf \"%.2f\", $sell_b_amt/ $sell_b_ep * 100}")
    echo "篮子卖出比例%: $ratio"
fi  

#篮子多空暴露
buy_b_amt=${buy_b_amt:-0}; sell_b_amt=${sell_b_amt:-0}
den=$(awk "BEGIN {print $buy_b_amt + $sell_b_amt}")
if [ "$den" -eq 0 ]; then
    result="0.00"
else
    result=$(awk "BEGIN {printf \"%.2f\", ($buy_b_amt - $sell_b_amt) / ($buy_b_amt + $sell_b_amt) * 100}")
fi
echo "篮子多空暴露%: $result%"
#篮子撤单率
read num den <<< $(mysql_query "
    SELECT
        SUM(CASE WHEN status IN (2,3,5) THEN 1 ELSE 0 END),
        COUNT(*)
    FROM orderinfo
    WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID' and basketId='$TRADE_basket';")
num=${num:-0}
den=${den:-0}
if [ "$den" -eq 0 ]; then
    echo "篮子总订单数为 0，撤单率为 0"
else
    ratio=$(awk "BEGIN {printf \"%.2f\", $num / $den * 100}")
    echo "篮子撤单率%（撤单子单数/总子单数）: $ratio ($num / $den)"
fi
#篮子废错单率
ratio=$(mysql_query "
  SELECT ROUND(
    SUM(CASE WHEN status IN (6,7) THEN 1 ELSE 0 END) /
    NULLIF(COUNT(*), 0)*100,2)
  FROM orderinfo
  WHERE tradeDate = $TRADE_DATE AND accountID = '$ACCOUNT_ID' and basketId='$TRADE_basket';")
echo "篮子错废单率%: ${ratio:-0.00}" 




# 底仓增强监控（T0）
echo "----------底仓增强监控（T0）----------"

# 检查是否存在 T0 子单
t0_exists=$(mysql_query "SELECT COUNT(*) FROM orderinfo_t0 WHERE tradeDate=$TRADE_DATE AND accountID='$ACCOUNT_ID';")
if [ "$t0_exists" -eq 0 ]; then
    echo "无 T0 子单数据"
else
    # T0 买交易额、卖交易额、买数量、卖数量
    read buy_t0_amt buy_t0_vol <<< $(mysql_query "
        SELECT 
            IFNULL(ROUND(SUM(CASE WHEN bsFlag=1 THEN tradeVol * tradePrice END), 2), 0),
            IFNULL(SUM(CASE WHEN bsFlag=1 THEN tradeVol END), 0)
        FROM orderinfo_t0 
        WHERE tradeDate=$TRADE_DATE AND accountID='$ACCOUNT_ID';")
    
    read sell_t0_amt sell_t0_vol <<< $(mysql_query "
        SELECT 
            IFNULL(ROUND(SUM(CASE WHEN bsFlag=2 THEN tradeVol * tradePrice END), 2), 0),
            IFNULL(SUM(CASE WHEN bsFlag=2 THEN tradeVol END), 0)
        FROM orderinfo_t0 
        WHERE tradeDate=$TRADE_DATE AND accountID='$ACCOUNT_ID';")

    echo "T0 买交易额: $buy_t0_amt"
    echo "T0 卖交易额: $sell_t0_amt"
    echo "T0 买数量: $buy_t0_vol"
    echo "T0 卖数量: $sell_t0_vol"

    # 获取费率（假设买卖费率相同，取 settleRate，单位可能是万分之几，如 1.5 表示 1.5 bps = 0.015%）
    # 注意：实际中可能买/卖费率不同，此处简化
    settle_rate=$(mysql_query "
        SELECT IFNULL(MAX(settleRate), 0) 
        FROM Tradeaccinfo 
        WHERE accountId='$ACCOUNT_ID' AND settleByAmt IN (1,4,5); -- 假设只考虑让利/总对总等付费类型
    ")
    # 转换为小数（如果 settleRate 是 bps，如 15 表示 0.15%，则除以 10000）
    # 根据业务，这里假设 settleRate 单位是 %，如 0.03 表示 0.03%
    # 若实际是 bps（如 3 表示 0.03%），则需除以 10000；若已是小数（0.0003），则直接用
    # 此处保守处理：假设 settleRate 是 bps（常见），所以除以 10000
    fee_rate=$(awk "BEGIN {printf \"%.6f\", $settle_rate / 10000}")

    total_fee=$(awk "BEGIN {printf \"%.2f\", ($buy_t0_amt + $sell_t0_amt) * $fee_rate}")
    echo "估算总费用: $total_fee"

    # 计算最新价（用 T0 整体成交均价）
    total_vol=$((buy_t0_vol + sell_t0_vol))
    total_amt=$(awk "BEGIN {print $buy_t0_amt + $sell_t0_amt}")
    if [ "$total_vol" -eq 0 ]; then
        latest_price=0
    else
        latest_price=$(awk "BEGIN {printf \"%.4f\", $total_amt / $total_vol}")
    fi
    echo "估算最新价（成交均价）: $latest_price"

    # 实时盈亏 = 卖 - 买 + (买数量 - 卖数量) * 最新价 - 总费用
    net_qty=$((buy_t0_vol - sell_t0_vol))
    unrealized=$(awk "BEGIN {printf \"%.2f\", $net_qty * $latest_price}")
    real_pnl=$(awk "BEGIN {printf \"%.2f\", $sell_t0_amt - $buy_t0_amt + $unrealized - $total_fee}")
    echo "实时盈亏: $real_pnl"

    # 成交额收益率 = 实时盈亏 / (买+卖) * 2 （年化？或双边）
    total_turnover=$(awk "BEGIN {print $buy_t0_amt + $sell_t0_amt}")
    if (( $(echo "$total_turnover == 0" | bc -l) )); then
        turnover_return="0.00"
    else
        turnover_return=$(awk "BEGIN {printf \"%.4f\", $real_pnl / $total_turnover * 2 * 100}")
    fi
    echo "成交额收益率%: $turnover_return"

    # 授权金额：从 strategyorderinfo_t0 获取（strategyTypeId=200）
    # 注意：strategyorderinfo 在 FTDB_NEW 中，T0 母单 strategyTypeId=200
    auth_amount=$(mysql_query "
        SELECT IFNULL(ROUND(SUM(orderVol * Preprice), 2), 0)
        FROM strategyorderinfo
        WHERE tradeDate=$TRADE_DATE AND accountId='$ACCOUNT_ID' AND strategyTypeId=200;
    ")
    echo "授权金额: $auth_amount"

    if (( $(echo "$auth_amount == 0" | bc -l) )); then
        base_return="0.00"
    else
        base_return=$(awk "BEGIN {printf \"%.4f\", $real_pnl / $auth_amount * 100}")
    fi
    echo "底仓收益率%: $base_return"

    # 多头敞口 = max(净头寸 * 最新价, 0)
    long_exposure_val=$(awk "BEGIN {val = $net_qty * $latest_price; print (val > 0) ? val : 0}")
    short_exposure_val=$(awk "BEGIN {val = $net_qty * $latest_price; print (val < 0) ? -val : 0}")
    echo "多头敞口金额: $long_exposure_val"
    echo "空头敞口金额: $short_exposure_val"

    # T0 总子单数
    t0_total=$(mysql_query "SELECT COUNT(*) FROM orderinfo_t0 WHERE tradeDate=$TRADE_DATE AND accountID='$ACCOUNT_ID';")
    # T0 撤单数（status in (2,3,5)）
    t0_cancel=$(mysql_query "SELECT SUM(CASE WHEN status IN (2,3,5) THEN 1 ELSE 0 END) FROM orderinfo_t0 WHERE tradeDate=$TRADE_DATE AND accountID='$ACCOUNT_ID';")
    t0_cancel=${t0_cancel:-0}
    if [ "$t0_total" -eq 0 ]; then
        echo "T0 撤单率%: 0.00"
    else
        cancel_rate=$(awk "BEGIN {printf \"%.2f\", $t0_cancel / $t0_total * 100}")
        echo "T0 撤单率%: $cancel_rate"
    fi

    # T0 错废单率
    t0_error=$(mysql_query "SELECT SUM(CASE WHEN status IN (6,7) THEN 1 ELSE 0 END) FROM orderinfo_t0 WHERE tradeDate=$TRADE_DATE AND accountID='$ACCOUNT_ID';")
    t0_error=${t0_error:-0}
    if [ "$t0_total" -eq 0 ]; then
        echo "T0 错废单率%: 0.00"
    else
        error_rate=$(awk "BEGIN {printf \"%.2f\", $t0_error / $t0_total * 100}")
        echo "T0 错废单率%: $error_rate"
    fi
fi

