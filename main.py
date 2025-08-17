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
    fast     = int(evt.get("fast", 10))
    slow     = int(evt.get("slow", 30))
    
    return symbol, strategy, start, end, cash, fast, slow

def run_backtest(symbol, strategy_cls, start, end, cash, **kwargs):
    """backtrader 回测"""
    df = get_stock_daily(symbol, start, end)
    cerebro = bt.Cerebro()
    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)

    # benchmark（标普500 SPY ETF）
    bench_start = df.index[0].strftime("%Y-%m-%d")
    bench_end = df.index[-1].strftime("%Y-%m-%d")
    bench_df = get_stock_daily("SPY", bench_start, bench_end)
    bench_df["pct"] = bench_df["Close"].pct_change().fillna(0)
    bench_val = (bench_df["pct"] + 1).cumprod() * 100
    benchmark_values = bench_val.tolist()
    benchmark_dates = [d.strftime("%Y-%m-%d") for d in bench_df.index]

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

    chart = {
        "dates": dates,
        "strategy_values": value_series,
        "benchmark_values": [float(x) for x in benchmark_values[-len(value_series):]],
        "benchmark_dates": benchmark_dates[-len(value_series):],
        "buy_points": buy_points,
        "sell_points": sell_points
    }

    return {"summary": summary, "chart": chart}


def main(event, context):
    try:
        symbol, strategy, start, end, cash, fast, slow = parse_event(event)
        StrategyCls = getattr(__import__("strategy", fromlist=[strategy]), strategy)
        result = run_backtest(symbol, StrategyCls, start, end, cash, fast=fast, slow=slow)
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
    # Test event data
    test_event = {
        "symbol": "AAPL",
        "strategy": "SmaCross",
        "start": "2023-01-01",
        "end": "2024-01-01",
        "cash": 100000,
        "fast": 10,
        "slow": 30
    }
    
    print("Running backtest with test data...")
    print(f"Symbol: {test_event['symbol']}")
    print(f"Strategy: {test_event['strategy']}")
    print(f"Period: {test_event['start']} to {test_event['end']}")
    
    result = main(test_event, None)
    print("\nBacktest Results:")
    print(json.dumps(result, indent=2))