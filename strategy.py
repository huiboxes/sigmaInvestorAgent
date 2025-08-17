import backtrader as bt


class BaseStrategy(bt.Strategy):
    """基础策略类，用于记录买卖点"""
    
    def __init__(self):
        super().__init__()
        self.buy_signals = []
        self.sell_signals = []
    
    def buy(self, *args, **kwargs):
        """重写买入方法，记录买入信号"""
        result = super().buy(*args, **kwargs)
        if result:
            self.buy_signals.append({
                "date": self.data.datetime.date(0).strftime("%Y-%m-%d"),
                "price": self.data.close[0]
            })
        return result
    
    def sell(self, *args, **kwargs):
        """重写卖出方法，记录卖出信号"""
        result = super().sell(*args, **kwargs)
        if result:
            self.sell_signals.append({
                "date": self.data.datetime.date(0).strftime("%Y-%m-%d"),
                "price": self.data.close[0]
            })
        return result
    
    def close(self, *args, **kwargs):
        """重写平仓方法，记录卖出信号"""
        result = super().close(*args, **kwargs)
        if result:
            self.sell_signals.append({
                "date": self.data.datetime.date(0).strftime("%Y-%m-%d"),
                "price": self.data.close[0]
            })
        return result

class SmaCross(BaseStrategy):
    params = dict(fast=10, slow=30)
    
    def __init__(self):
        super().__init__()
        self.fast_ma = bt.ind.SMA(period=self.p.fast)
        self.slow_ma = bt.ind.SMA(period=self.p.slow)
        self.crossover = bt.ind.CrossOver(self.fast_ma, self.slow_ma)
    
    def next(self):
        if not self.position and self.crossover > 0:
            self.buy(size=1)
        elif self.position and self.crossover < 0:
            self.close()

class BuyHold(BaseStrategy):
    def next(self):
        if not self.position:
            self.buy(size=1)

class RSI(BaseStrategy):
    params = dict(rsi_period=14, buy_level=30, sell_level=70)
    def __init__(self):
        super().__init__()
        self.rsi = bt.ind.RSI(self.data.close, period=self.p.rsi_period)
    def next(self):
        if self.rsi < self.p.buy_level and not self.position:
            self.buy(size=1)
        elif self.rsi > self.p.sell_level and self.position:
            self.close()

class MACD(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.macd = bt.ind.MACD()
    def next(self):
        if not self.position and self.macd.macd > self.macd.signal:
            self.buy(size=1)
        elif self.position and self.macd.macd < self.macd.signal:
            self.close()

class Boll(BaseStrategy):
    params = dict(bb_period=20, bb_dev=2)
    def __init__(self):
        super().__init__()
        self.bb = bt.ind.BollingerBands(period=self.p.bb_period, devfactor=self.p.bb_dev)
    def next(self):
        if not self.position and self.data.close < self.bb.lines.bot:
            self.buy(size=1)
        elif self.position and self.data.close > self.bb.lines.top:
            self.close()

class Turtle(BaseStrategy):
    params = dict(entry=20, exit=10)
    def __init__(self):
        super().__init__()
        self.highest = bt.ind.Highest(self.data.high, period=self.p.entry)
        self.lowest  = bt.ind.Lowest(self.data.low, period=self.p.exit)
    def next(self):
        if not self.position and self.data.close > self.highest[-1]:
            self.buy(size=1)
        elif self.position and self.data.close < self.lowest[-1]:
            self.close()

class Grid(BaseStrategy):
    params = dict(step=0.05)
    def __init__(self):
        super().__init__()
        self.last_price = None
    def next(self):
        price = self.data.close[0]
        if self.last_price is None:
            self.last_price = price
            return
        if not self.position:
            self.buy(size=1)
            self.last_price = price
        elif price >= self.last_price * (1+self.p.step):
            self.sell(size=1)
            self.last_price = price
        elif price <= self.last_price * (1-self.p.step):
            self.buy(size=1)
            self.last_price = price

class DualThrust(BaseStrategy):
    params = dict(k1=0.5, k2=0.5, period=4)
    def __init__(self):
        super().__init__()
        self.hh = bt.ind.Highest(self.data.high, period=self.p.period)
        self.ll = bt.ind.Lowest(self.data.low, period=self.p.period)
        self.close = bt.ind.Lowest(self.data.close, period=self.p.period)
    def next(self):
        if len(self) < self.p.period: return
        r = self.hh[0] - self.ll[0]
        buy  = self.data.open[0] + self.p.k1 * r
        sell = self.data.open[0] - self.p.k2 * r
        if not self.position and self.data.close[0] > buy:
            self.buy(size=1)
        elif self.position and self.data.close[0] < sell:
            self.close()