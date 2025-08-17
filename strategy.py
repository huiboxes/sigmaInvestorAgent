import backtrader as bt


class BaseStrategy(bt.Strategy):
    """基础策略类，用于记录买卖点"""
    
    params = dict(
        position_pct=1.0,  # 每次买入使用的资金比例，1.0表示全仓，0.5表示半仓
    )
    
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
    
    def calculate_position_size(self):
        """计算买入数量"""
        available_cash = self.broker.getcash() * self.p.position_pct
        return available_cash / self.data.close[0]

class SmaCross(BaseStrategy):
    params = dict(fast=10, slow=30)
    
    def __init__(self):
        super().__init__()
        self.fast_ma = bt.ind.SMA(period=self.p.fast)
        self.slow_ma = bt.ind.SMA(period=self.p.slow)
        self.crossover = bt.ind.CrossOver(self.fast_ma, self.slow_ma)
    
    def next(self):
        # 确保有足够的数据进行计算
        if len(self) < self.p.slow:
            return
            
        if not self.position and self.crossover > 0:
            size = self.calculate_position_size()
            self.buy(size=size)
        elif self.position and self.crossover < 0:
            self.close()

class BuyHold(BaseStrategy):
    def next(self):
        if not self.position:
            size = self.calculate_position_size()
            self.buy(size=size)

class RSI(BaseStrategy):
    params = dict(rsi_period=14, buy_level=30, sell_level=70)
    def __init__(self):
        super().__init__()
        self.rsi = bt.ind.RSI(self.data.close, period=self.p.rsi_period)
    def next(self):
        # 确保RSI指标有足够数据
        if len(self) < self.p.rsi_period:
            return
            
        if self.rsi < self.p.buy_level and not self.position:
            size = self.calculate_position_size()
            self.buy(size=size)
        elif self.rsi > self.p.sell_level and self.position:
            self.close()

class MACD(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.macd = bt.ind.MACD()
    def next(self):
        # MACD需要足够的数据
        if len(self) < 35:  # MACD默认需要约35个数据点
            return
            
        if not self.position and self.macd.macd > self.macd.signal:
            size = self.calculate_position_size()
            self.buy(size=size)
        elif self.position and self.macd.macd < self.macd.signal:
            self.close()

class Boll(BaseStrategy):
    params = dict(bb_period=20, bb_dev=2)
    def __init__(self):
        super().__init__()
        self.bb = bt.ind.BollingerBands(period=self.p.bb_period, devfactor=self.p.bb_dev)
    def next(self):
        # 布林带需要足够的数据
        if len(self) < self.p.bb_period:
            return
            
        if not self.position and self.data.close < self.bb.lines.bot:
            size = self.calculate_position_size()
            self.buy(size=size)
        elif self.position and self.data.close > self.bb.lines.top:
            self.close()

class Turtle(BaseStrategy):
    params = dict(entry=20, exit=10)
    def __init__(self):
        super().__init__()
        self.highest = bt.ind.Highest(self.data.high, period=self.p.entry)
        self.lowest  = bt.ind.Lowest(self.data.low, period=self.p.exit)
    def next(self):
        # 海龟策略需要足够的数据
        if len(self) < max(self.p.entry, self.p.exit):
            return
            
        if not self.position and self.data.close > self.highest[-1]:
            size = self.calculate_position_size()
            self.buy(size=size)
        elif self.position and self.data.close < self.lowest[-1]:
            self.close()

class Grid(BaseStrategy):
    params = dict(step=0.05, position_size=0.1)  # 每次使用10%资金
    def __init__(self):
        super().__init__()
        self.last_price = None
    def next(self):
        price = self.data.close[0]
        if self.last_price is None:
            self.last_price = price
            return
        
        # 计算每次交易的资金量
        trade_value = self.broker.getcash() * self.p.position_size
        trade_size = trade_value / price
        
        if not self.position:
            self.buy(size=trade_size)
            self.last_price = price
        elif price >= self.last_price * (1+self.p.step):
            # 网格卖出，卖出部分持仓
            sell_size = min(trade_size, self.position.size)
            self.sell(size=sell_size)
            self.last_price = price
        elif price <= self.last_price * (1-self.p.step):
            # 网格买入
            self.buy(size=trade_size)
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
            size = self.calculate_position_size()
            self.buy(size=size)
        elif self.position and self.data.close[0] < sell:
            self.close()

class DCA(BaseStrategy):
    """定投策略 (Dollar Cost Averaging)
    
    每隔固定周期投入固定金额，不管市场涨跌。
    这是最适合普通投资者的长期投资策略。
    
    参数说明：
    - invest_period: 投资周期（交易日）
      * 5 = 每周定投
      * 10 = 每两周定投  
      * 22 = 每月定投（默认）
      * 66 = 每季度定投
    - invest_amount: 每次投资金额
    """
    params = dict(
        invest_period=22,  # 投资周期（交易日），22天约等于1个月
        invest_amount=1000  # 每次投资金额
    )
    
    def __init__(self):
        super().__init__()
        self.day_count = 0
        self.total_invested = 0
        
    def next(self):
        self.day_count += 1
        
        # 每隔指定周期进行定投
        if self.day_count % self.p.invest_period == 0:
            # 计算可以买入的份额（基于当前价格）
            shares_to_buy = self.p.invest_amount / self.data.close[0]
            self.buy(size=shares_to_buy)
            self.total_invested += self.p.invest_amount


class ValueAveraging(BaseStrategy):
    """价值平均策略 (Value Averaging)
    
    设定目标价值增长路径，根据实际价值与目标价值的差异来调整投资金额。
    当实际价值低于目标时加大投资，高于目标时减少投资或卖出。
    """
    params = dict(
        check_period=22,  # 检查周期（交易日）
        target_growth=0.01,  # 目标月增长率 1%
        initial_target=10000  # 初始目标价值
    )
    
    def __init__(self):
        super().__init__()
        self.day_count = 0
        self.period_count = 0
        self.target_value = self.p.initial_target
        
    def next(self):
        self.day_count += 1
        
        if self.day_count % self.p.check_period == 0:
            self.period_count += 1
            
            # 计算目标价值（复合增长）
            self.target_value = self.p.initial_target * ((1 + self.p.target_growth) ** self.period_count)
            
            # 计算当前投资组合价值
            current_value = self.broker.getvalue()
            
            # 计算需要调整的金额
            value_diff = self.target_value - current_value
            
            if value_diff > 0:
                # 当前价值低于目标，需要买入
                shares_to_buy = value_diff / self.data.close[0]
                if shares_to_buy > 0:
                    self.buy(size=shares_to_buy)
            elif value_diff < 0 and self.position:
                # 当前价值高于目标，需要卖出
                shares_to_sell = min(abs(value_diff) / self.data.close[0], self.position.size)
                if shares_to_sell > 0:
                    self.sell(size=shares_to_sell)


class SmileCurve(BaseStrategy):
    """微笑曲线策略 (Smile Curve Strategy)
    
    基于价格相对位置进行投资：
    - 价格下跌时（相对低位）加大投资力度
    - 价格上涨时（相对高位）减少投资或获利了结
    适合波动较大的市场环境。
    """
    params = dict(
        lookback_period=60,  # 回看周期，用于计算价格位置
        invest_period=10,    # 投资周期
        base_amount=1000,    # 基础投资金额
        max_multiplier=3.0   # 最大投资倍数
    )
    
    def __init__(self):
        super().__init__()
        self.day_count = 0
        self.highest = bt.ind.Highest(self.data.close, period=self.p.lookback_period)
        self.lowest = bt.ind.Lowest(self.data.close, period=self.p.lookback_period)
        
    def next(self):
        if len(self) < self.p.lookback_period:
            return
            
        self.day_count += 1
        
        if self.day_count % self.p.invest_period == 0:
            # 计算当前价格在历史区间中的位置 (0-1)
            price_range = self.highest[0] - self.lowest[0]
            if price_range > 0:
                price_position = (self.data.close[0] - self.lowest[0]) / price_range
            else:
                price_position = 0.5  # 如果没有波动，使用中位数
            
            # 根据价格位置调整投资金额（价格越低，投资越多）
            # 使用反向的微笑曲线：低位时投资倍数高，高位时投资倍数低
            if price_position <= 0.2:
                # 价格在底部20%，最大投资
                multiplier = self.p.max_multiplier
            elif price_position <= 0.4:
                # 价格在20%-40%，较大投资
                multiplier = self.p.max_multiplier * 0.8
            elif price_position <= 0.6:
                # 价格在40%-60%，正常投资
                multiplier = 1.0
            elif price_position <= 0.8:
                # 价格在60%-80%，减少投资
                multiplier = 0.5
            else:
                # 价格在顶部20%，考虑获利了结
                if self.position.size > 0:
                    # 卖出部分持仓
                    sell_ratio = 0.1  # 卖出10%
                    shares_to_sell = self.position.size * sell_ratio
                    self.sell(size=shares_to_sell)
                return
            
            # 执行买入
            invest_amount = self.p.base_amount * multiplier
            shares_to_buy = invest_amount / self.data.close[0]
            self.buy(size=shares_to_buy)