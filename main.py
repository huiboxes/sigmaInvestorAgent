import json
import logging
import datetime as dt
import backtrader as bt

from data_fetcher import get_stock_daily
from strategy import *  
    

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
    cerebro = bt.Cerebro()
    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)

    # 根据标的选择合适的基准
    bench_start = df.index[0].strftime("%Y-%m-%d")
    bench_end = df.index[-1].strftime("%Y-%m-%d")
    
    # 选择基准
    if symbol.endswith(('.SH', '.SZ', '.BJ')):
        # A股使用沪深300ETF作为基准
        benchmark_symbol = "510300.SH"
    elif symbol.endswith('.HK'):
        # 港股使用恒生指数ETF作为基准
        benchmark_symbol = "02800.HK"  # 盈富基金

    else:
        # 美股使用标普500 SPY ETF作为基准
        benchmark_symbol = "SPY"
    
    try:
        bench_df = get_stock_daily(benchmark_symbol, bench_start, bench_end)
        bench_df["pct"] = bench_df["Close"].pct_change().fillna(0)
        bench_val = (bench_df["pct"] + 1).cumprod() * 100
        benchmark_values = bench_val.tolist()
        benchmark_dates = [d.strftime("%Y-%m-%d") for d in bench_df.index]
    except Exception as e:
        # 如果基准数据获取失败，使用空数据
        print(f"警告：无法获取基准数据 {benchmark_symbol}: {e}")
        benchmark_values = []
        benchmark_dates = []

    cerebro.addstrategy(strategy_cls, **kwargs)
    cerebro.broker.setcash(cash)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="ret")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")

    res = cerebro.run()[0]
    strat = res

    # 提取策略曲线
    value_series = strat.observers.broker.lines.value.array
    # 转换为Python列表以确保JSON序列化
    value_series = [float(x) for x in value_series]
    dates = [d.strftime("%Y-%m-%d") for d in df.index[-len(value_series):]]

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
    ret = strat.analyzers.ret.get_analysis()
    total_ret = ret["rtot"]
    annual_ret = ret["rnorm100"]

    # 计算胜率
    trade_analysis = strat.analyzers.trades.get_analysis()
    total_trades = trade_analysis.get('total', {}).get('total', 0)
    won_trades = trade_analysis.get('won', {}).get('total', 0)
    win_rate = won_trades / total_trades if total_trades > 0 else 0

    summary = {
        "total_return": float(total_ret) if total_ret is not None else 0.0,
        "annual_return": float(annual_ret) if annual_ret is not None else 0.0,
        "max_drawdown": float(max_dd / 100) if isinstance(max_dd, (int, float)) else 0.0,
        "max_drawdown_length": int(max_dd_len) if max_dd_len is not None else 0,
        "max_drawdown_start": max_dd_start,
        "max_drawdown_end": max_dd_end,
        "sharpe": float(sharpe) if sharpe is not None else 0.0,
        "win_rate": float(win_rate)
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
    # 测试不同策略
    test_cases = [
        {
            "name": "移动平均交叉策略 (美股ETF)",
            "event": {
                "symbol": "AAPL",
                "strategy": "SmaCross",
                "start": "2023-01-01",
                "end": "2024-01-01",
                "cash": 100000,
                "params": {
                    "fast": 10,
                    "slow": 30
                }
            }
        },
        {
            "name": "定投策略 (美股ETF)",
            "event": {
                "symbol": "SPY",
                "strategy": "DCA",
                "start": "2022-01-01",
                "end": "2024-01-01",
                "cash": 100000,
                "params": {
                    "invest_period": 22,    # 每月定投
                    "invest_amount": 2000   # 每次投资2000元
                }
            }
        },
        {
            "name": "微笑曲线策略 (美股科技ETF)",
            "event": {
                "symbol": "QQQ",
                "strategy": "SmileCurve",
                "start": "2022-01-01",
                "end": "2024-01-01",
                "cash": 100000,
                "params": {
                    "lookback_period": 60,   # 60天回看期
                    "invest_period": 10,     # 每10天检查一次
                    "base_amount": 1500,     # 基础投资金额
                    "max_multiplier": 3.0    # 最大投资倍数
                }
            }
        },
        {
            "name": "定投策略 (A股沪深300ETF)",
            "event": {
                "symbol": "510300.SH",  # 华泰柏瑞沪深300ETF
                "strategy": "DCA",
                "start": "2022-01-01",
                "end": "2024-01-01",
                "cash": 100000,
                "params": {
                    "invest_period": 22,    # 每月定投
                    "invest_amount": 2000   # 每次投资2000元
                }
            }
        },
        {
            "name": "微笑曲线策略 (A股创业板ETF)",
            "event": {
                "symbol": "159915.SZ",  # 易方达创业板ETF
                "strategy": "SmileCurve",
                "start": "2022-01-01",
                "end": "2024-01-01",
                "cash": 100000,
                "params": {
                    "lookback_period": 60,   # 60天回看期
                    "invest_period": 10,     # 每10天检查一次
                    "base_amount": 1500,     # 基础投资金额
                    "max_multiplier": 3.0    # 最大投资倍数
                }
            }
        },
        {
            "name": "买入持有策略 (A股中证500ETF)",
            "event": {
                "symbol": "510500.SH",  # 南方中证500ETF
                "strategy": "BuyHold",
                "start": "2022-01-01",
                "end": "2024-01-01",
                "cash": 100000
            }
        },
        {
            "name": "定投策略-每周定投 (A股科技ETF)",
            "event": {
                "symbol": "515000.SH",  # 华夏中证人工智能ETF
                "strategy": "DCA",
                "start": "2022-01-01",
                "end": "2024-01-01",
                "cash": 100000,
                "params": {
                    "invest_period": 5,     # 每周定投（5个交易日）
                    "invest_amount": 500    # 每次投资500元
                }
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"测试 {i}: {test_case['name']}")
        print(f"{'='*60}")
        
        event = test_case['event']
        print(f"标的: {event['symbol']}")
        print(f"策略: {event['strategy']}")
        print(f"时间: {event['start']} 到 {event['end']}")
        print(f"初始资金: ${event['cash']:,}")
        
        if 'params' in event and event['params']:
            print("策略参数:")
            for key, value in event['params'].items():
                print(f"  {key}: {value}")
        else:
            print("策略参数: 使用默认参数")
        
        try:
            result = main(event, None)
            
            if result['statusCode'] == 200:
                data = json.loads(result['body'])
                summary = data['summary']
                
                print(f"\n📊 回测结果:")
                print(f"总收益率: {summary['total_return']:.2%}")
                print(f"年化收益率: {summary['annual_return']:.2%}")
                print(f"最大回撤: {summary['max_drawdown']:.2%}")
                print(f"夏普比率: {summary['sharpe']:.3f}")
                print(f"胜率: {summary['win_rate']:.2%}")
                
                # 显示买卖点数量
                chart = data['chart']
                buy_count = len(chart['buy_points'])
                sell_count = len(chart['sell_points'])
                print(f"买入次数: {buy_count}")
                print(f"卖出次数: {sell_count}")
                
            else:
                error_data = json.loads(result['body'])
                print(f"❌ 测试失败: {error_data['msg']}")
                
        except Exception as e:
            print(f"❌ 测试异常: {str(e)}")
    
    print(f"\n{'='*60}")
    print("所有测试完成！")
    print(f"{'='*60}")