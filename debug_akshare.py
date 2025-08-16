#!/usr/bin/env python3
"""
调试akshare美股接口
"""
import akshare as ak
import pandas as pd

def test_akshare_us_interfaces():
    """测试不同的akshare美股接口"""
    symbol = "AAPL"
    
    print("=== 测试 akshare 美股接口 ===")
    
    # 测试1: stock_us_hist
    print("\n1. 测试 ak.stock_us_hist:")
    try:
        df1 = ak.stock_us_hist(
            symbol=symbol,
            period="daily",
            start_date="20231220",
            end_date="20231222",
            adjust=""
        )
        print(f"  结果类型: {type(df1)}")
        if df1 is not None:
            print(f"  数据形状: {df1.shape}")
            print(f"  列名: {list(df1.columns)}")
            print(f"  前几行:\n{df1.head()}")
        else:
            print("  返回 None")
    except Exception as e:
        print(f"  错误: {e}")
    
    # 测试2: stock_us_daily
    print("\n2. 测试 ak.stock_us_daily:")
    try:
        df2 = ak.stock_us_daily(symbol=symbol)
        print(f"  结果类型: {type(df2)}")
        if df2 is not None:
            print(f"  数据形状: {df2.shape}")
            print(f"  列名: {list(df2.columns)}")
            print(f"  前几行:\n{df2.head()}")
        else:
            print("  返回 None")
    except Exception as e:
        print(f"  错误: {e}")
    
    # 测试3: 查看可用的美股接口
    print("\n3. 查看akshare中包含'us'的函数:")
    import inspect
    us_functions = [name for name, obj in inspect.getmembers(ak) 
                   if inspect.isfunction(obj) and 'us' in name.lower()]
    print(f"  找到 {len(us_functions)} 个相关函数:")
    for func in us_functions[:10]:  # 只显示前10个
        print(f"    - {func}")

if __name__ == "__main__":
    test_akshare_us_interfaces()