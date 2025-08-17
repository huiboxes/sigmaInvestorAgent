import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time
import logging
from typing import Optional
import re

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_stock_daily(symbol: str, start: Optional[str] = None, end: Optional[str] = None, max_retries: int = 3, retry_delay: float = 1.0) -> pd.DataFrame:
    """
    获取股票/ETF日线数据，支持A股、港股、美股
    
    Args:
        symbol: 股票/ETF代码
            A股：600519.SH / 000001.SZ / 835640.BJ / 510300.SH(ETF)
            港股：00700.HK
            美股：AAPL / SPY
        start: 开始日期 (YYYY-MM-DD)，默认为3年前
        end: 结束日期 (YYYY-MM-DD)，默认为今天
        max_retries: 最大重试次数
        retry_delay: 重试间隔(秒)
    
    Returns:
        DataFrame: 包含 Open,High,Low,Close,Volume 列的数据
    
    Raises:
        ValueError: 参数验证失败
        RuntimeError: 数据获取失败
    """
    
    if not symbol or not isinstance(symbol, str):
        raise ValueError("股票代码不能为空且必须是字符串")
    
    symbol = symbol.strip().upper()
    
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    
    if start is None:
        start_date = datetime.now() - timedelta(days=3*365)  # 3年前
        start = start_date.strftime("%Y-%m-%d")
    
    try:
        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d")
        if start_date >= end_date:
            start_date, end_date = end_date, start_date
    except ValueError as e:
        raise ValueError(f"日期格式错误，请使用 YYYY-MM-DD 格式: {e}")
    
    if not _validate_symbol_format(symbol):
        raise ValueError(f"不支持的股票代码格式: {symbol}")
    
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            logger.info(f"尝试获取 {symbol} 数据 (第 {attempt + 1}/{max_retries} 次)")
            
            if symbol.endswith((".SH", ".SZ", ".BJ")):
                return _fetch_a_stock(symbol, start, end)
            
            elif symbol.endswith(".HK"):
                return _fetch_hk_stock(symbol, start, end)
            
            else:
                return _fetch_us_stock(symbol, start, end)
                
        except Exception as e:
            last_exception = e
            error_msg = str(e)
            logger.warning(f"第 {attempt + 1} 次尝试失败: {e}")
            
            if attempt < max_retries - 1:
                logger.info(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
                retry_delay *= 1.5  # 指数退避
            
    raise RuntimeError(f"获取 {symbol} 数据失败，已重试 {max_retries} 次。最后错误: {last_exception}")


def _validate_symbol_format(symbol: str) -> bool:
    """验证股票/ETF代码格式"""
    if symbol.endswith((".SH", ".SZ", ".BJ")):
        code = symbol[:-3]
        return code.isdigit() and len(code) == 6
    
    if symbol.endswith(".HK"):
        code = symbol[:-3]
        return code.isdigit() and len(code) >= 4
    
    # 美股格式更宽松：允许字母、数字、点、连字符
    return bool(re.match(r'^[A-Z0-9.-]{1,10}$', symbol))


def _fetch_a_stock(symbol: str, start: str, end: str) -> pd.DataFrame:
    """获取A股数据 - 仅支持股票，不支持ETF"""
    code, ex = symbol.split(".")
    
    # 检查是否为ETF（通常以5开头的6位数字）
    if code.startswith('5') and len(code) == 6:
        raise RuntimeError(f"不支持ETF标的 {symbol}，请使用股票代码")
    
    try:
        df = ak.stock_zh_a_hist(
            symbol=code, 
            period="daily",
            start_date=start.replace("-", ""),
            end_date=end.replace("-", ""),
            adjust="qfq"  # 前复权
        )
        
        if df is None or df.empty:
            raise RuntimeError(f"未获取到 {symbol} 的数据")
        
        # 标准化列名
        column_mapping = {
            "日期": "Date", "开盘": "Open", "收盘": "Close",
            "最高": "High", "最低": "Low", "成交量": "Volume"
        }
        
        df = df.rename(columns=column_mapping)
        
        # 验证必要列是否存在
        required_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise RuntimeError(f"数据缺少必要列: {missing_cols}")
        
        df["Date"] = pd.to_datetime(df["Date"])
        df.set_index("Date", inplace=True)
        
        ohlcv_cols = ["Open", "High", "Low", "Close", "Volume"]
        return df[ohlcv_cols].sort_index()
        
    except Exception as e:
        raise RuntimeError(f"获取A股 {symbol} 数据失败: {e}")


def _fetch_hk_stock(symbol: str, start: str, end: str) -> pd.DataFrame:
    """获取港股数据"""
    code = symbol.replace(".HK", "")
    
    try:
        df = ak.stock_hk_hist(
            symbol=code, 
            period="daily",
            start_date=start.replace("-", ""),
            end_date=end.replace("-", ""), 
            adjust="qfq"  # 前复权
        )
        
        if df is None or df.empty:
            raise RuntimeError(f"未获取到 {symbol} 的数据")
        
        # 标准化列名
        column_mapping = {
            "日期": "Date", "开盘": "Open", "收盘": "Close",
            "最高": "High", "最低": "Low", "成交量": "Volume"
        }
        
        df = df.rename(columns=column_mapping)
        
        # 验证必要列
        required_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise RuntimeError(f"数据缺少必要列: {missing_cols}")
        
        df["Date"] = pd.to_datetime(df["Date"])
        df.set_index("Date", inplace=True)
        
        return df[["Open", "High", "Low", "Close", "Volume"]].sort_index()
        
    except Exception as e:
        raise RuntimeError(f"获取港股 {symbol} 数据失败: {e}")


def _fetch_us_stock(symbol: str, start: str, end: str) -> pd.DataFrame:
    """获取美股数据"""
    try:
        logger.info(f"获取 {symbol} 前复权数据")
        
        # 优先尝试使用前复权数据
        df = None
        
        # 直接使用原始数据，不进行手动修复
        # 原始数据可能包含股票分割，但手动修复会引入偏差
        try:
            df = ak.stock_us_daily(symbol=symbol)
            logger.info(f"使用 stock_us_daily 获取 {symbol} 原始数据")
        except Exception as e:
            logger.error(f"stock_us_daily 失败: {e}")
        
        if df is None or df.empty:
            raise RuntimeError(f"未获取到 {symbol} 的数据")
        
        # 处理不同接口的列名
        column_mapping = {
            'date': 'Date', '日期': 'Date',
            'open': 'Open', '开盘': 'Open',
            'high': 'High', '最高': 'High',
            'low': 'Low', '最低': 'Low',
            'close': 'Close', '收盘': 'Close',
            'volume': 'Volume', '成交量': 'Volume'
        }
        
        df = df.rename(columns=column_mapping)
        
        df["Date"] = pd.to_datetime(df["Date"])
        start_date = pd.to_datetime(start)
        end_date = pd.to_datetime(end)
        
        df = df[(df["Date"] >= start_date) & (df["Date"] <= end_date)]
        
        if df.empty:
            raise RuntimeError(f"{symbol} 在指定日期范围 {start} 到 {end} 内没有数据")
        
        df.set_index("Date", inplace=True)
        
        required_cols = ["Open", "High", "Low", "Close", "Volume"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise RuntimeError(f"数据缺少必要列: {missing_cols}")
        
        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        result_df = df[required_cols].dropna().sort_index()
        
        if result_df.empty:
            raise RuntimeError(f"{symbol} 数据清理后为空")

        # 验证数据连续性
        price_changes = result_df['Close'].pct_change().abs()
        extreme_changes = price_changes > 0.3  # 单日涨跌超过30%
        
        if extreme_changes.any():
            extreme_count = extreme_changes.sum()
            logger.warning(f"{symbol} 数据中有 {extreme_count} 个异常价格变动点，建议检查数据源")
        else:
            logger.info(f"{symbol} 数据连续性良好")
        
        logger.info(f"成功获取 {symbol} 数据，共 {len(result_df)} 条记录")
        return result_df
        
    except Exception as e:
        raise RuntimeError(f"获取美股 {symbol} 数据失败: {e}")


if __name__ == '__main__':
    # 测试用例
    test_cases = [
        ('SPY', '2023-12-20', '2023-12-22'),        # 美股
        ('600519.SH', '2023-12-20', '2023-12-22'),  # A股贵州茅台
        ('000700.HK', '2023-12-20', '2025-12-22'),  # A股贵州茅台
        ('002594.SZ', '2023-12-20', '2023-12-22'),  # A股比亚迪
    ]
    
    for symbol, start, end in test_cases:
        try:
            print(f"\n测试 {symbol} (start={start}, end={end}):")
            df = get_stock_daily(symbol, start, end)
            print(f"成功获取 {len(df)} 条数据")
            print(f"日期范围: {df.index.min()} 到 {df.index.max()}")
            print(df.head(2))
        except Exception as e:
            print(f"获取 {symbol} 失败: {e}")



