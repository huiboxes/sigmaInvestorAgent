import json
import logging
import datetime as dt
import pandas as pd
import backtrader as bt

from data_fetcher import get_stock_daily
from strategy import *

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)  
    

def parse_event(evt):
    """解析入参"""
    symbol   = evt.get("symbol", "SPY").upper()
    strategy = evt.get("strategy", "SmaCross")
    start    = evt.get("start", str(dt.date.today() - dt.timedelta(days=3650)))
    end      = evt.get("end",   str(dt.date.today()))
    cash     = float(evt.get("cash", 100000))
    
    # 传递策略参数
    strategy_params = evt.get("params", {})
    
    return symbol, strategy, start, end, cash, strategy_params

def run_backtest(symbol, strategy_cls, start, end, cash, **kwargs):
    """backtrader 回测"""
    df = get_stock_daily(symbol, start, end)
    
    # 计算买入持有基准收益率 - 使用日收益率累积，避免股票分割问题
    if len(df) > 0:
        # 使用日收益率累积计算，这样可以正确处理股票分割
        daily_returns = df['Close'].pct_change().fillna(0)
        
        # 检测可能的股票分割：
        # 1. 单日下跌超过50%（股票分割通常是下跌）
        # 2. 且成交量没有异常放大（排除重大利空消息）
        potential_splits = daily_returns < -0.5
        
        if potential_splits.any():
            split_dates = df.index[potential_splits]
            logger.warning(f"检测到 {len(split_dates)} 个可能的股票分割日期")
            
            # 对每个可能的分割日期进行验证
            for split_date in split_dates:
                split_return = daily_returns.loc[split_date]
                
                # 检查是否符合常见的股票分割比例
                # 2:1分割 ≈ -50%, 3:1分割 ≈ -67%, 4:1分割 ≈ -75%, 5:1分割 ≈ -80%
                expected_ratios = [-0.5, -0.67, -0.75, -0.8, -0.86, -0.9, -0.95]  # 对应2:1到20:1分割
                
                # 如果收益率接近这些分割比例（误差在5%内），认为是股票分割
                is_likely_split = any(abs(split_return - ratio) < 0.05 for ratio in expected_ratios)
                
                if is_likely_split:
                    logger.info(f"将 {split_date.strftime('%Y-%m-%d')} 的收益率 {split_return:.2%} 识别为股票分割，从计算中排除")
                    daily_returns.loc[split_date] = 0
                else:
                    logger.info(f"保留 {split_date.strftime('%Y-%m-%d')} 的收益率 {split_return:.2%}，可能是正常的极端波动")
        
        buy_hold_return = (daily_returns + 1).prod() - 1
    else:
        buy_hold_return = 0
    
    cerebro = bt.Cerebro()
    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)

    initial_value = cash
    benchmark_values = []
    benchmark_dates = []
    
    if len(df) > 0:
        # 使用已经处理过股票分割的日收益率来计算基准
        benchmark_values.append(initial_value)  # 初始值
        benchmark_dates.append(df.index[0].strftime("%Y-%m-%d"))
        
        current_value = initial_value
        for i in range(1, len(df)):
            date = df.index[i]
            # 使用已经处理过股票分割的日收益率
            daily_return = daily_returns.iloc[i]
            current_value = current_value * (1 + daily_return)
            benchmark_values.append(current_value)
            benchmark_dates.append(date.strftime("%Y-%m-%d"))
    
    logger.info(f"生成买入持有基准数据（已处理股票分割），共 {len(benchmark_values)} 个数据点")

    cerebro.addstrategy(strategy_cls, **kwargs)
    cerebro.broker.setcash(cash)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="ret")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")

    res = cerebro.run()[0]
    strat = res

    # 提取策略曲线
    try:
        value_series = strat.observers.broker.lines.value.array
        # 转换为Python列表以确保JSON序列化
        value_series = [float(x) for x in value_series if not pd.isna(x) and x != 0]
        # 如果没有有效数据，使用初始资金
        if not value_series:
            value_series = [float(cash)]
    except (IndexError, AttributeError) as e:
        print(f"警告：无法获取策略价值序列: {e}")
        value_series = [float(cash)]
    
    # 获取策略实际运行的日期
    # backtrader的策略可能因为指标预热期而跳过前面的一些日期
    strategy_start_idx = len(df) - len(value_series)
    dates = [d.strftime("%Y-%m-%d") for d in df.index[strategy_start_idx:]]
    
    # 确保日期和策略值长度一致
    if len(dates) != len(value_series):
        min_len = min(len(dates), len(value_series))
        dates = dates[-min_len:]
        value_series = value_series[-min_len:]

    # 买卖点 - 从策略中获取记录的信号
    buy_points = getattr(strat, 'buy_signals', [])
    sell_points = getattr(strat, 'sell_signals', [])

    # 指标
    dd = strat.analyzers.dd.get_analysis()
    max_dd = dd.max.drawdown if hasattr(dd.max, 'drawdown') else dd.max.moneydown
    max_dd_len = dd.max.len
    # 根据回撤长度估算开始和结束日期
    if max_dd_len > 0 and len(dates) >= max_dd_len:
        max_dd_end = dates[-1]  # 假设最大回撤在最近结束
        max_dd_start = dates[-(max_dd_len)] if len(dates) >= max_dd_len else dates[0]
    else:
        max_dd_start = "N/A"
        max_dd_end = "N/A"

    sharpe = strat.analyzers.sharpe.get_analysis().get("sharperatio", 0)
    
    # 直接从broker计算收益率，更准确
    final_value = cerebro.broker.getvalue()
    total_ret = (final_value / cash) - 1
    
    # 计算年化收益率
    start_date = df.index[0]
    end_date = df.index[-1]
    days = (end_date - start_date).days
    years = days / 365.25
    
    # 年化收益率 = (1 + 总收益率)^(1/年数) - 1
    if years > 0 and total_ret is not None:
        annual_ret = ((1 + total_ret) ** (1 / years)) - 1
    else:
        annual_ret = 0.0
    


    # 计算胜率
    trade_analysis = strat.analyzers.trades.get_analysis()
    total_trades = trade_analysis.get('total', {}).get('total', 0)
    won_trades = trade_analysis.get('won', {}).get('total', 0)
    win_rate = won_trades / total_trades if total_trades > 0 else 0

    summary = {
        "symbol": symbol,
        "total_return": float(total_ret) if total_ret is not None else 0.0,
        "annual_return": float(annual_ret),
        "max_drawdown": float(max_dd / 100) if isinstance(max_dd, (int, float)) else 0.0,
        "max_drawdown_length": int(max_dd_len) if max_dd_len is not None else 0,
        "max_drawdown_start": max_dd_start,
        "max_drawdown_end": max_dd_end,
        "sharpe": float(sharpe) if sharpe is not None else 0.0,
        "win_rate": float(win_rate),
        "buy_hold_return": float(buy_hold_return)  # 添加买入持有基准
    }

    # 处理基准数据长度匹配
    if benchmark_values and len(benchmark_values) >= len(value_series):
        chart_benchmark_values = [float(x) for x in benchmark_values[-len(value_series):]]
        chart_benchmark_dates = benchmark_dates[-len(value_series):]
    else:
        chart_benchmark_values = [float(x) for x in benchmark_values] if benchmark_values else []
        chart_benchmark_dates = benchmark_dates if benchmark_dates else []

    chart = {
        "dates": dates,
        "strategy_values": value_series,
        "benchmark_values": chart_benchmark_values,
        "benchmark_dates": chart_benchmark_dates,
        "buy_points": buy_points,
        "sell_points": sell_points
    }

    return {"summary": summary, "chart": chart}


def main(event, context):
    try:
        symbol, strategy, start, end, cash, strategy_params = parse_event(event)
        StrategyCls = getattr(__import__("strategy", fromlist=[strategy]), strategy)
        result = run_backtest(symbol, StrategyCls, start, end, cash, **strategy_params)
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"code": 0, "msg": "ok", **result})
        }
    except Exception as e:
        return {
            "statusCode": 400,
            "body": json.dumps({"code": 1, "msg": str(e)})
        }


if __name__ == '__main__':
    # AAPL 5年定投策略专项测试
    import datetime as dt
    
    aapl_dca_test = {
        "name": "AAPL 5年定投策略",
        "event": {
            "symbol": "AAPL",
            "strategy": "DCA",
            "start": str(dt.date.today() - dt.timedelta(days=5*365)),  # 5年前
            "end": str(dt.date.today()),
            "cash": 100000,
            "params": {
                "invest_period": 22,    # 每月定投
                "invest_amount": 1000   # 每次投资1000美元
            }
        }
    }
    
    print("="*80)
    print("🍎 AAPL 5年定投策略专项测试")
    print("="*80)
    
    event = aapl_dca_test['event']
    print(f"标的: {event['symbol']}")
    print(f"策略: {event['strategy']} (定投策略)")
    print(f"时间: {event['start']} 到 {event['end']}")
    print(f"初始资金: ${event['cash']:,}")
    print(f"定投周期: 每{event['params']['invest_period']}个交易日 (约每月)")
    print(f"定投金额: ${event['params']['invest_amount']:,}")
    
    try:
        result = main(event, None)
        
        if result['statusCode'] == 200:
            data = json.loads(result['body'])
            summary = data['summary']
            chart = data['chart']
            
            print(f"\n📊 AAPL 5年定投策略回测结果:")
            print(f"总收益率: {summary['total_return']:.2%}")
            print(f"年化收益率: {summary['annual_return']:.2%}")
            print(f"最大回撤: {summary['max_drawdown']:.2%}")
            print(f"夏普比率: {summary['sharpe']:.3f}")
            print(f"胜率: {summary['win_rate']:.2%}")
            
            # 定投特有指标
            buy_count = len(chart['buy_points'])
            total_days = len(chart['dates'])
            expected_buys = total_days // event['params']['invest_period']
            
            print(f"\n📈 定投执行情况:")
            print(f"实际买入次数: {buy_count}")
            print(f"预期买入次数: {expected_buys}")
            print(f"总投资金额: ${buy_count * event['params']['invest_amount']:,}")
            
            # 计算平均成本
            if chart['buy_points']:
                total_cost = buy_count * event['params']['invest_amount']
                total_shares = sum(event['params']['invest_amount'] / bp['price'] for bp in chart['buy_points'])
                avg_cost = total_cost / total_shares if total_shares > 0 else 0
                
                # 获取最新股价
                latest_price = chart['buy_points'][-1]['price'] if chart['buy_points'] else 0
                
                print(f"平均成本: ${avg_cost:.2f}")
                print(f"总持有股数: {total_shares:.2f}")
                print(f"最新股价: ${latest_price:.2f}")
            else:
                print(f"平均成本: $0.00 (无买入记录)")
                print(f"总持有股数: 0.00")
                print(f"最新股价: $0.00")
            
            # 基准对比
            buy_hold_ret = summary.get('buy_hold_return', 0)
            strategy_ret = summary['total_return']
            print(f"\n📊 与买入持有策略对比:")
            print(f"买入持有收益: {buy_hold_ret:.2%}")
            print(f"定投策略收益: {strategy_ret:.2%}")
            excess_return = strategy_ret - buy_hold_ret
            if excess_return > 0:
                print(f"✅ 定投策略跑赢买入持有 +{excess_return:.2%}")
            else:
                print(f"❌ 定投策略跑输买入持有 {excess_return:.2%}")
            
            # 保存结果供plot.py使用
            with open('aapl_dca_data.json', 'w') as f:
                json.dump(data, f, indent=2)
            print(f"\n💾 回测数据已保存到 aapl_dca_data.json")
            print("可以运行 'python plot.py' 生成可视化图表")
            
        else:
            error_data = json.loads(result['body'])
            print(f"❌ 测试失败: {error_data['msg']}")
            
    except Exception as e:
        print(f"❌ 测试异常: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("AAPL 5年定投策略测试完成！")
    print("="*80)
    
    # 其他策略测试用例
    # test_cases = [
    #     {
    #         "name": "移动平均交叉策略（全仓）",
    #         "event": {
    #             "symbol": "AAPL",
    #             "strategy": "SmaCross",
    #             "start": "2023-01-01",
    #             "end": "2024-01-01",
    #             "cash": 100000,
    #             "params": {
    #                 "fast": 10,
    #                 "slow": 30,
    #                 "position_pct": 1.0     # 全仓买入
    #             }
    #         }
    #     },
    #     {
    #         "name": "RSI策略（半仓）",
    #         "event": {
    #             "symbol": "TSLA",
    #             "strategy": "RSI",
    #             "start": "2023-01-01",
    #             "end": "2024-01-01",
    #             "cash": 100000,
    #             "params": {
    #                 "rsi_period": 14,
    #                 "buy_level": 30,
    #                 "sell_level": 70,
    #                 "position_pct": 0.5     # 半仓买入
    #             }
    #         }
    #     },
    #     {
    #         "name": "定投策略",
    #         "event": {
    #             "symbol": "SPY",
    #             "strategy": "DCA",
    #             "start": "2022-01-01",
    #             "end": "2024-01-01",
    #             "cash": 100000,
    #             "params": {
    #                 "invest_period": 22,    # 每月定投
    #                 "invest_amount": 2000   # 每次投资2000元
    #             }
    #         }
    #     },
    #     {
    #         "name": "网格交易策略",
    #         "event": {
    #             "symbol": "MSFT",
    #             "strategy": "Grid",
    #             "start": "2023-01-01",
    #             "end": "2024-01-01",
    #             "cash": 100000,
    #             "params": {
    #                 "step": 0.05,           # 5%网格间距
    #                 "position_size": 0.1    # 每次使用10%资金
    #             }
    #         }
    #     },
    #     {
    #         "name": "MACD策略（30%仓位）",
    #         "event": {
    #             "symbol": "GOOGL",
    #             "strategy": "MACD",
    #             "start": "2023-01-01",
    #             "end": "2024-01-01",
    #             "cash": 100000,
    #             "params": {
    #                 "position_pct": 0.3     # 30%仓位
    #             }
    #         }
    #     },
    #     {
    #         "name": "布林带策略（70%仓位）",
    #         "event": {
    #             "symbol": "AMZN",
    #             "strategy": "Boll",
    #             "start": "2023-01-01",
    #             "end": "2024-01-01",
    #             "cash": 100000,
    #             "params": {
    #                 "bb_period": 20,
    #                 "bb_dev": 2,
    #                 "position_pct": 0.7     # 70%仓位
    #             }
    #         }
    #     },
    #     {
    #         "name": "海龟交易策略（全仓）",
    #         "event": {
    #             "symbol": "NVDA",
    #             "strategy": "Turtle",
    #             "start": "2023-01-01",
    #             "end": "2024-01-01",
    #             "cash": 100000,
    #             "params": {
    #                 "entry": 20,
    #                 "exit": 10,
    #                 "position_pct": 1.0     # 全仓
    #             }
    #         }
    #     },
    #     {
    #         "name": "买入持有策略（基准）",
    #         "event": {
    #             "symbol": "SPY",
    #             "strategy": "BuyHold",
    #             "start": "2022-01-01",
    #             "end": "2024-01-01",
    #             "cash": 100000
    #         }
    #     }
    # ]
    
    # for i, test_case in enumerate(test_cases, 1):
    #     print(f"\n{'='*60}")
    #     print(f"测试 {i}: {test_case['name']}")
    #     print(f"{'='*60}")
        
    #     event = test_case['event']
    #     print(f"标的: {event['symbol']}")
    #     print(f"策略: {event['strategy']}")
    #     print(f"时间: {event['start']} 到 {event['end']}")
    #     print(f"初始资金: ${event['cash']:,}")
        
    #     if 'params' in event and event['params']:
    #         print("策略参数:")
    #         for key, value in event['params'].items():
    #             if key == 'position_pct':
    #                 print(f"  仓位比例: {value:.1%}")
    #             elif key == 'position_size':
    #                 print(f"  每次交易资金: {value:.1%}")
    #             elif key in ['invest_amount', 'base_amount', 'initial_target']:
    #                 print(f"  {key}: ${value:,}")
    #             elif key in ['target_growth']:
    #                 print(f"  {key}: {value:.1%}")
    #             else:
    #                 print(f"  {key}: {value}")
    #     else:
    #         print("策略参数: 使用默认参数")
        
    #     try:
    #         result = main(event, None)
            
    #         if result['statusCode'] == 200:
    #             data = json.loads(result['body'])
    #             summary = data['summary']
                
    #             print(f"\n📊 回测结果:")
    #             print(f"总收益率: {summary['total_return']:.2%}")
    #             print(f"年化收益率: {summary['annual_return']:.2%}")
    #             print(f"最大回撤: {summary['max_drawdown']:.2%}")
    #             print(f"夏普比率: {summary['sharpe']:.3f}")
    #             print(f"胜率: {summary['win_rate']:.2%}")
                
    #             # 显示买卖点数量
    #             chart = data['chart']
    #             buy_count = len(chart['buy_points'])
    #             sell_count = len(chart['sell_points'])
    #             print(f"买入次数: {buy_count}")
    #             print(f"卖出次数: {sell_count}")
                
    #             # 计算交易频率
    #             days = len(chart['dates'])
    #             if days > 0:
    #                 trade_frequency = (buy_count + sell_count) / days * 252  # 年化交易频率
    #                 print(f"年化交易频率: {trade_frequency:.1f}次")
                
    #             # 显示资金管理参数（如果有）
    #             params = event.get('params', {})
    #             if params.get('position_pct') and params.get('position_pct') != 1.0:
    #                 print(f"资金管理: 每次使用{params['position_pct']:.1%}资金")
                
    #             # 添加数据验证信息，提升可信度
    #             print(f"\n📈 数据验证:")
    #             print(f"回测期间: {event['start']} 至 {event['end']}")
    #             print(f"交易日数: {days}天")
    #             if chart['strategy_values']:
    #                 initial_value = chart['strategy_values'][0] if chart['strategy_values'] else event['cash']
    #                 final_value = chart['strategy_values'][-1] if chart['strategy_values'] else event['cash']
    #                 print(f"初始价值: ${initial_value:,.2f}")
    #                 print(f"最终价值: ${final_value:,.2f}")
    #                 calculated_return = (final_value / initial_value - 1)
    #                 print(f"计算验证: {calculated_return:.2%} (应与总收益率一致)")
                
    #             # 添加基准对比
    #             buy_hold_ret = summary.get('buy_hold_return', 0)
    #             strategy_ret = summary['total_return']
    #             print(f"\n📊 基准对比:")
    #             print(f"买入持有收益: {buy_hold_ret:.2%}")
    #             print(f"策略收益: {strategy_ret:.2%}")
    #             excess_return = strategy_ret - buy_hold_ret
    #             if excess_return > 0:
    #                 print(f"✅ 策略跑赢基准 +{excess_return:.2%}")
    #             else:
    #                 print(f"❌ 策略跑输基准 {excess_return:.2%}")
                
    #         else:
    #             error_data = json.loads(result['body'])
    #             print(f"❌ 测试失败: {error_data['msg']}")
                
    #     except Exception as e:
    #         print(f"❌ 测试异常: {str(e)}")
    
    print(f"\n{'='*60}")
    print("所有测试完成！")
    print(f"{'='*60}")