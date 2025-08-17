import akshare as ak, pandas as pd
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
    """获取A股数据"""
    code, ex = symbol.split(".")
    
    try:
        df = ak.stock_zh_a_hist(
            symbol=code, 
            period="daily",
            start_date=start.replace("-", ""),
            end_date=end.replace("-", ""),
            adjust=""
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
        
        return df[["Open", "High", "Low", "Close", "Volume"]].sort_index()
        
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
            adjust=""
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
        df = ak.stock_us_daily(symbol=symbol)
        
        if df is None or df.empty:
            raise RuntimeError(f"未获取到 {symbol} 的数据")
        
        column_mapping = {
            'date': 'Date',
            'open': 'Open', 
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
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
        
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        result_df = df[required_cols].dropna()
        
        if result_df.empty:
            raise RuntimeError(f"{symbol} 数据清理后为空")

        return result_df.sort_index()
        
    except Exception as e:
        raise RuntimeError(f"获取美股 {symbol} 数据失败: {e}")


if __name__ == '__main__':
    # 测试用例
    test_cases = [
        ('SPY', '2023-12-20', '2023-12-22'),
        # ('600519.SH', '2023-12-20', '2023-12-22'),
        # ('00700.HK', '2023-12-20', '2023-12-22'),
        ('510300.SH', '2023-12-01', '2023-12-31'),  # 沪深300ETF
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