import json
import os
from datetime import datetime


def main(event, context):
    """生成回测结果的可视化图表"""
    chart = event.get("chart", {})
    summary = event.get("summary", {})
    symbol = summary.get("symbol", "").upper()

    title = event.get("title", f"{symbol} 回测结果")

    # 1. 策略净值数据
    dates = chart.get("dates", [])
    strategy_values = chart.get("strategy_values", [])

    # 2. 基准净值数据
    bench_dates = chart.get("benchmark_dates", [])
    benchmark_values = chart.get("benchmark_values", [])

    # 3. 买卖点数据
    buy_points = chart.get("buy_points", [])
    sell_points = chart.get("sell_points", [])

    # 提取买卖点的日期和价格
    buy_dates = [p.get("date", "") for p in buy_points]
    buy_prices = [p.get("price", 0) for p in buy_points]
    sell_dates = [p.get("date", "") for p in sell_points]
    sell_prices = [p.get("price", 0) for p in sell_points]

    # 4. 准备JavaScript数据
    dates_js = json.dumps(dates)
    strategy_js = json.dumps(strategy_values)
    bench_dates_js = json.dumps(bench_dates)
    benchmark_js = json.dumps(benchmark_values)
    buy_dates_js = json.dumps(buy_dates)
    buy_prices_js = json.dumps(buy_prices)
    sell_dates_js = json.dumps(sell_dates)
    sell_prices_js = json.dumps(sell_prices)

    # 5. 回测统计数据
    total_return = summary.get("total_return", 0)
    annual_return = summary.get("annual_return", 0)
    max_drawdown = summary.get("max_drawdown", 0)
    sharpe_ratio = summary.get("sharpe", 0)
    win_rate = summary.get("win_rate", 0)
    buy_hold_return = summary.get("buy_hold_return", 0)

    # 处理日期显示
    start_date = dates[0] if dates else 'N/A'
    end_date = dates[-1] if dates else 'N/A'

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.bootcdn.net/ajax/libs/plotly.js/3.0.3/plotly-finance.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0f0f, #1a1a1a);
            color: #ffffff;
            line-height: 1.6;
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: #2d2d2d;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            overflow: hidden;
            border: 1px solid #404040;
        }}
        
        .header-section {{
            background: linear-gradient(135deg, #2d2d2d, #353535);
            padding: 30px;
            border-bottom: 1px solid #404040;
        }}
        
        .title {{
            font-size: 32px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 25px;
            text-align: center;
            text-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        
        .stat-card {{
            background: #1a1a1a;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #404040;
            text-align: center;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
        }}
        
        .stat-label {{
            font-size: 12px;
            color: #b0b0b0;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }}
        
        .stat-value {{
            font-size: 24px;
            font-weight: 600;
            color: #ffffff;
        }}
        
        .positive {{ color: #00ff88; }}
        .negative {{ color: #ff4444; }}
        
        .chart-section {{
            padding: 40px 30px;
            background: #1a1a1a;
        }}
        
        .chart-container {{
            position: relative;
            height: 600px;
            background: #0f0f0f;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #404040;
        }}
        
        .legend-section {{
            background: #2d2d2d;
            padding: 25px 30px;
            border-top: 1px solid #404040;
        }}
        
        .legend-grid {{
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 14px;
            color: #b0b0b0;
        }}
        
        .legend-color {{
            width: 20px;
            height: 3px;
            border-radius: 2px;
        }}
        
        .legend-point {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            border: 2px solid #ffffff;
        }}
        
        .strategy-line {{ background: #00ff88; }}
        .baseline-line {{ background: #808080; }}
        .buy-point {{ background: #00ff88; }}
        .sell-point {{ background: #ff4444; }}
        
        @media (max-width: 768px) {{
            .container {{
                margin: 10px;
                border-radius: 15px;
            }}
            
            .header-section, .chart-section, .legend-section {{
                padding: 20px;
            }}
            
            .title {{
                font-size: 24px;
            }}
            
            .chart-container {{
                height: 400px;
            }}
            
            .summary-grid {{
                grid-template-columns: 1fr;
            }}
            
            .legend-grid {{
                flex-direction: column;
                align-items: center;
                gap: 15px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header class="header-section">
            <h1 class="title">{symbol} Strategy Analysis</h1>
            <div class="summary-grid">
                <div class="stat-card">
                    <div class="stat-label">Strategy Return</div>
                    <div class="stat-value {'positive' if total_return >= 0 else 'negative'}">{total_return:+.2%}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Buy & Hold Return</div>
                    <div class="stat-value {'positive' if buy_hold_return >= 0 else 'negative'}">{buy_hold_return:+.2%}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Annual Return</div>
                    <div class="stat-value {'positive' if annual_return >= 0 else 'negative'}">{annual_return:+.2%}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Max Drawdown</div>
                    <div class="stat-value negative">{max_drawdown:.2%}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Sharpe Ratio</div>
                    <div class="stat-value {'positive' if sharpe_ratio >= 0 else 'negative'}">{sharpe_ratio:.2f}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Win Rate</div>
                    <div class="stat-value">{win_rate:.1%}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Start Date</div>
                    <div class="stat-value">{start_date}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">End Date</div>
                    <div class="stat-value">{end_date}</div>
                </div>
            </div>
        </header>
        
        <main class="chart-section">
            <div class="chart-container">
                <div id="performanceChart"></div>
            </div>
        </main>
        
        <footer class="legend-section">
            <div class="legend-grid">
                <div class="legend-item">
                    <div class="legend-color strategy-line"></div>
                    <span>Strategy Performance</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color baseline-line"></div>
                    <span>Buy & Hold Baseline</span>
                </div>
                <div class="legend-item">
                    <div class="legend-point buy-point"></div>
                    <span>Buy Signals</span>
                </div>
                <div class="legend-item">
                    <div class="legend-point sell-point"></div>
                    <span>Sell Signals</span>
                </div>
            </div>
        </footer>
    </div>
    
    <script>
        // Prepare data for Plotly.js
        const strategyDates = {dates_js};
        const strategyValues = {strategy_js};
        const benchmarkDates = {bench_dates_js};
        const benchmarkValues = {benchmark_js};
        const buyDates = {buy_dates_js};
        const buyPrices = {buy_prices_js};
        const sellDates = {sell_dates_js};
        const sellPrices = {sell_prices_js};
        
        // 工具函数
        function formatChineseCurrency(value) {{
            return '¥' + parseFloat(value).toLocaleString('zh-CN', {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
        }}
        
        function calculateReturn(currentValue, initialValue) {{
            if (!initialValue || initialValue === 0) return '0.00';
            return ((currentValue - initialValue) / initialValue * 100).toFixed(2);
        }}
        
        // 创建Plotly轨迹
        const traces = [];
        const initialStrategyValue = strategyValues.length > 0 ? strategyValues[0] : 1;
        const initialBenchmarkValue = benchmarkValues.length > 0 ? benchmarkValues[0] : 1;
        
        // 策略表现线 - 带收益率悬浮提示
        if (strategyDates.length > 0 && strategyValues.length > 0) {{
            const strategyReturns = strategyValues.map(value => calculateReturn(value, initialStrategyValue));
            
            traces.push({{
                x: strategyDates,
                y: strategyValues,
                type: 'scatter',
                mode: 'lines',
                name: '策略表现',
                line: {{
                    color: '#2962ff',
                    width: 2.5
                }},
                customdata: strategyReturns,
                hovertemplate: '<b>策略表现</b><br>' +
                              '日期: %{{x}}<br>' +
                              '组合价值: %{{y:,.2f}}<br>' +
                              '累计收益率: %{{customdata}}%<br>' +
                              '<extra></extra>'
            }});
        }}
        
        // 基准表现线 - 带收益率悬浮提示
        if (benchmarkDates.length > 0 && benchmarkValues.length > 0) {{
            const benchmarkReturns = benchmarkValues.map(value => calculateReturn(value, initialBenchmarkValue));
            
            traces.push({{
                x: benchmarkDates,
                y: benchmarkValues,
                type: 'scatter',
                mode: 'lines',
                name: '买入持有基准',
                line: {{
                    color: '#787b86',
                    width: 2,
                    dash: 'dot'
                }},
                customdata: benchmarkReturns,
                hovertemplate: '<b>买入持有基准</b><br>' +
                              '日期: %{{x}}<br>' +
                              '组合价值: %{{y:,.2f}}<br>' +
                              '累计收益率: %{{customdata}}%<br>' +
                              '<extra></extra>'
            }});
        }}
        
        // 买入信号点 - 尺寸减半
        if (buyDates.length > 0 && buyPrices.length > 0) {{
            const buyYValues = buyDates.map((date, index) => {{
                const strategyIndex = strategyDates.findIndex(d => d === date);
                if (strategyIndex >= 0) {{
                    return strategyValues[strategyIndex];
                }} else {{
                    const dateObj = new Date(date);
                    const beforeIndex = strategyDates.findIndex(d => new Date(d) > dateObj) - 1;
                    const afterIndex = beforeIndex + 1;
                    
                    if (beforeIndex >= 0 && afterIndex < strategyDates.length) {{
                        const beforeDate = new Date(strategyDates[beforeIndex]);
                        const afterDate = new Date(strategyDates[afterIndex]);
                        const beforeValue = strategyValues[beforeIndex];
                        const afterValue = strategyValues[afterIndex];
                        
                        const ratio = (dateObj - beforeDate) / (afterDate - beforeDate);
                        return beforeValue + (afterValue - beforeValue) * ratio;
                    }} else {{
                        return buyPrices[index];
                    }}
                }}
            }});
            
            traces.push({{
                x: buyDates,
                y: buyYValues,
                type: 'scatter',
                mode: 'markers',
                name: '买入信号',
                marker: {{
                    color: '#089981',
                    size: 3,
                    symbol: 'circle',
                    line: {{
                        color: '#ffffff',
                        width: 0.5
                    }}
                }},
                hovertemplate: '<b>🟢 买入信号</b><br>' +
                              '日期: %{{x}}<br>' +
                              '买入价格: ¥%{{customdata:,.2f}}<br>' +
                              '组合价值: ¥%{{y:,.2f}}<br>' +
                              '<extra></extra>',
                customdata: buyPrices
            }});
        }}
        
        // 卖出信号点 - 尺寸减半
        if (sellDates.length > 0 && sellPrices.length > 0) {{
            const sellYValues = sellDates.map((date, index) => {{
                const strategyIndex = strategyDates.findIndex(d => d === date);
                if (strategyIndex >= 0) {{
                    return strategyValues[strategyIndex];
                }} else {{
                    const dateObj = new Date(date);
                    const beforeIndex = strategyDates.findIndex(d => new Date(d) > dateObj) - 1;
                    const afterIndex = beforeIndex + 1;
                    
                    if (beforeIndex >= 0 && afterIndex < strategyDates.length) {{
                        const beforeDate = new Date(strategyDates[beforeIndex]);
                        const afterDate = new Date(strategyDates[afterIndex]);
                        const beforeValue = strategyValues[beforeIndex];
                        const afterValue = strategyValues[afterIndex];
                        
                        const ratio = (dateObj - beforeDate) / (afterDate - beforeDate);
                        return beforeValue + (afterValue - beforeValue) * ratio;
                    }} else {{
                        return sellPrices[index];
                    }}
                }}
            }});
            
            traces.push({{
                x: sellDates,
                y: sellYValues,
                type: 'scatter',
                mode: 'markers',
                name: '卖出信号',
                marker: {{
                    color: '#f23645',
                    size: 3,
                    symbol: 'triangle-up',
                    line: {{
                        color: '#ffffff',
                        width: 0.5
                    }}
                }},
                hovertemplate: '<b>🔴 卖出信号</b><br>' +
                              '日期: %{{x}}<br>' +
                              '卖出价格: ¥%{{customdata:,.2f}}<br>' +
                              '组合价值: ¥%{{y:,.2f}}<br>' +
                              '<extra></extra>',
                customdata: sellPrices
            }});
        }}
        
        // TradingView风格布局
        const layout = {{
            title: {{
                text: '',
                font: {{ color: '#d1d4dc' }}
            }},
            plot_bgcolor: '#131722',
            paper_bgcolor: '#131722',
            font: {{ color: '#d1d4dc', family: '微软雅黑, Microsoft YaHei, Segoe UI, sans-serif' }},
            xaxis: {{
                title: {{
                    text: '日期',
                    font: {{ color: '#787b86', size: 12 }}
                }},
                gridcolor: '#2a2e39',
                tickfont: {{ color: '#787b86', size: 10 }},
                linecolor: '#363a45',
                zerolinecolor: '#363a45',
                type: 'date'
            }},
            yaxis: {{
                title: {{
                    text: '组合价值 (¥)',
                    font: {{ color: '#787b86', size: 12 }}
                }},
                gridcolor: '#2a2e39',
                tickfont: {{ color: '#787b86', size: 10 }},
                linecolor: '#363a45',
                zerolinecolor: '#363a45',
                tickformat: ',.0f'
            }},
            legend: {{
                orientation: 'h',
                yanchor: 'bottom',
                y: 1.02,
                xanchor: 'center',
                x: 0.5,
                bgcolor: 'rgba(19, 23, 34, 0.9)',
                bordercolor: '#363a45',
                borderwidth: 1,
                font: {{ color: '#d1d4dc', size: 11 }}
            }},
            margin: {{
                l: 80,
                r: 40,
                t: 60,
                b: 80
            }},
            hovermode: 'closest',
            hoverlabel: {{
                bgcolor: '#1e222d',
                bordercolor: '#363a45',
                font: {{ color: '#d1d4dc', family: '微软雅黑, Microsoft YaHei' }}
            }}
        }};
        
        // 配置选项
        const config = {{
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ['pan2d', 'select2d', 'lasso2d', 'autoScale2d', 'toggleSpikelines'],
            displaylogo: false,
            toImageButtonOptions: {{
                format: 'png',
                filename: '{symbol}_strategy_chart',
                height: 600,
                width: 1200,
                scale: 2
            }}
        }};
        
        // 创建图表
        try {{
            if (traces.length === 0) {{
                document.getElementById('performanceChart').innerHTML = 
                    '<div style="color: #f23645; text-align: center; padding: 50px; font-size: 16px;">⚠️ 暂无可用数据显示图表</div>';
            }} else {{
                Plotly.newPlot('performanceChart', traces, layout, config);
                console.log('✅ 图表渲染成功，使用TradingView风格配色');
            }}
        }} catch (error) {{
            console.error('❌ 图表创建失败:', error);
            document.getElementById('performanceChart').innerHTML = 
                '<div style="color: #f23645; text-align: center; padding: 50px; font-size: 16px;">❌ 图表创建失败: ' + error.message + '</div>';
        }}
    </script>
</body>
</html>'''

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "code": 0,
            "html_content": html_content,
            "message": "图表生成成功"
        })
    }


def generate_chart_from_file(json_file_path, output_file_path=None):
    """从JSON文件生成图表"""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 提取数据
        chart_event = {
            "symbol": data.get("symbol", "UNKNOWN"),
            "chart": data.get("chart", {}),
            "summary": data.get("summary", {}),
            "title": f"{data.get('symbol', 'UNKNOWN')} 回测结果可视化"
        }

        # 生成图表
        result = main(chart_event, None)

        if result['statusCode'] == 200:
            chart_data = json.loads(result['body'])
            html_content = chart_data['html_content']

            # 确定输出文件名
            if output_file_path is None:
                base_name = os.path.splitext(os.path.basename(json_file_path))[0]
                output_file_path = f"{base_name}_chart.html"

            # 保存HTML文件
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            print(f"✅ 图表已生成: {output_file_path}")
            return output_file_path
        else:
            print("❌ 图表生成失败")
            return None

    except Exception as e:
        print(f"❌ 生成图表时出错: {e}")
        return None


if __name__ == '__main__':
    import sys

    # 检查是否有命令行参数
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        generate_chart_from_file(json_file, output_file)
    else:
        # 默认处理 aapl_dca_data.json
        json_files = ['aapl_dca_data.json', 'backtest_result.json']

        for json_file in json_files:
            if os.path.exists(json_file):
                print(f"📊 处理文件: {json_file}")
                generate_chart_from_file(json_file)
                break
        else:
            print("❌ 未找到回测数据文件")
            print("请先运行 'python main.py' 生成回测数据，或指定JSON文件路径:")
            print("用法: python plot.py <json_file_path> [output_html_path]")
            print("示例: python plot.py aapl_dca_data.json aapl_chart.html")
