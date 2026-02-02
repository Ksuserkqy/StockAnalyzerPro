"""
股票数据获取模块
支持获取实时行情、历史K线、基本面数据和技术指标
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import akshare as ak
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')


class StockDataFetcher:
    """股票数据获取类"""
    
    def __init__(self):
        """初始化股票数据获取器"""
        self.stock_code = None
        self.stock_name = None
    
    def search_stock(self, keyword: str) -> Optional[Tuple[str, str]]:
        """
        搜索股票代码和名称
        
        Args:
            keyword: 股票代码或名称
            
        Returns:
            (股票代码, 股票名称) 或 None
        """
        try:
            keyword = (keyword or "").strip()
            if not keyword:
                print("请输入有效的股票代码或名称")
                return None

            # 如果输入是数字（可能是代码），直接使用
            if keyword.isdigit() and len(keyword) == 6:
                # 添加市场前缀（沪深京）
                code = self._with_market_prefix(keyword)
                # 验证代码有效性
                if self._validate_code(code):
                    self.stock_code = code
                    # 获取股票名称
                    self.stock_name = self._get_stock_name(code)
                    return code, self.stock_name

            # 使用股票代码/名称列表进行匹配
            try:
                stock_list = ak.stock_info_a_code_name()
            except Exception as e:
                print(f"获取股票列表失败: {e}")
                return None

            if stock_list is not None and not stock_list.empty:
                # 按代码或名称搜索
                matches = stock_list[
                    (stock_list['code'].astype(str).str.contains(keyword, case=False, na=False)) |
                    (stock_list['name'].astype(str).str.contains(keyword, case=False, na=False))
                ]

                if not matches.empty:
                    row = matches.iloc[0]
                    code_num = str(row['code']).zfill(6)
                    self.stock_code = self._with_market_prefix(code_num)
                    self.stock_name = str(row['name'])
                    return self.stock_code, self.stock_name

            print(f"未找到股票: {keyword}")
            return None
        except Exception as e:
            print(f"搜索股票时出错: {e}")
            return None

    @staticmethod
    def _with_market_prefix(code_num: str) -> str:
        """根据股票代码添加市场前缀"""
        if code_num.startswith("6"):
            return f"sh{code_num}"
        if code_num.startswith(("0", "3")):
            return f"sz{code_num}"
        if code_num.startswith(("8", "4")):
            return f"bj{code_num}"
        return f"sz{code_num}"

    @staticmethod
    def _validate_code(code: str) -> bool:
        """验证股票代码有效性"""
        try:
            data = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=(datetime.now() - timedelta(days=10)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d"),
                adjust="qfq"
            )
            return data is not None and not data.empty
        except Exception:
            return False
    
    def _get_stock_name(self, code: str) -> str:
        """获取股票名称"""
        try:
            if not code:
                return ""
            # 尝试从市场获取基本信息
            code_num = code.replace('sh', '').replace('sz', '').replace('bj', '')

            try:
                stock_list = ak.stock_info_a_code_name()
                match = stock_list[stock_list['code'].astype(str) == code_num]
                if not match.empty:
                    return str(match.iloc[0]['name'])
            except Exception:
                pass

            return f"股票{code_num}"
        except:
            return code
    
    def get_realtime_data(self) -> Dict:
        """
        获取实时行情数据
        
        Returns:
            包含最新价、开盘价、最高价、最低价、成交量、成交额的字典
        """
        if not self.stock_code:
            print("请先搜索股票")
            return {}
        
        try:
            code_num = self.stock_code.replace('sh', '').replace('sz', '').replace('bj', '')
            spot_error = None

            # 使用实时行情接口
            try:
                spot = ak.stock_zh_a_spot_em()
                if spot is not None and not spot.empty:
                    row = spot[spot['代码'].astype(str) == code_num]
                    if not row.empty:
                        r = row.iloc[0]
                        return {
                            "股票代码": self.stock_code,
                            "股票名称": self.stock_name,
                            "日期": datetime.now().strftime("%Y-%m-%d"),
                            "最新价": float(r.get('最新价', np.nan)),
                            "开盘价": float(r.get('今开', np.nan)),
                            "最高价": float(r.get('最高', np.nan)),
                            "最低价": float(r.get('最低', np.nan)),
                            "成交量": int(r.get('成交量', 0)),
                            "成交额": float(r.get('成交额', np.nan))
                        }
            except Exception as e:
                spot_error = e

            # 兜底：用最近交易日K线
            end_date = datetime.now()
            start_date = end_date - timedelta(days=10)
            data = ak.stock_zh_a_hist(
                symbol=code_num,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq"
            )
            if data is not None and not data.empty:
                row = data.iloc[-1]
                return {
                    "股票代码": self.stock_code,
                    "股票名称": self.stock_name,
                    "日期": row['日期'],
                    "最新价": float(row['收盘']),
                    "开盘价": float(row['开盘']),
                    "最高价": float(row['最高']),
                    "最低价": float(row['最低']),
                    "成交量": int(row['成交量']),
                    "成交额": float(row['成交额'])
                }

            if spot_error is not None:
                print("获取实时行情数据失败：实时行情接口不可用，已尝试使用最近交易日K线兜底。")
            else:
                print("获取实时行情数据失败：暂无可用数据。")
        except Exception as e:
            print(f"获取实时行情数据失败: {e}")
        
        return {}
    
    def get_kline_data(self, period: str = "daily", days: int = 100) -> pd.DataFrame:
        """
        获取历史K线数据
        
        Args:
            period: 周期，'daily'(日线), 'weekly'(周线), 'monthly'(月线)
            days: 获取天数（近似值）
            
        Returns:
            包含开盘价、收盘价、最高价、最低价、成交量的DataFrame
        """
        if not self.stock_code:
            print("请先搜索股票")
            return pd.DataFrame()
        
        try:
            # 计算开始日期
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            code_num = self.stock_code.replace('sh', '').replace('sz', '').replace('bj', '')
            kline_data = ak.stock_zh_a_hist(
                symbol=code_num,
                period=period,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq"
            )
            
            if not kline_data.empty:
                # 重命名列以便于理解
                kline_data = kline_data.rename(columns={
                    '日期': 'Date',
                    '开盘': 'Open',
                    '收盘': 'Close',
                    '最高': 'High',
                    '最低': 'Low',
                    '成交量': 'Volume',
                    '成交额': 'Amount'
                })
                
                # 选择需要的列
                kline_data = kline_data[['Date', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount']]
                kline_data['Date'] = pd.to_datetime(kline_data['Date'])
                
                return kline_data
        except Exception as e:
            print(f"获取K线数据失败: {e}")
        
        return pd.DataFrame()
    
    def get_fundamental_data(self) -> Dict:
        """
        获取基本面数据（财报数据）
        
        Returns:
            包含每股收益、净利润、营业总收入、净资产收益率、市盈率的字典
        """
        if not self.stock_code:
            print("请先搜索股票")
            return {}
        
        try:
            code_num = self.stock_code.replace('sh', '').replace('sz', '').replace('bj', '')
            fundamental_data = {
                "股票代码": self.stock_code,
                "股票名称": self.stock_name
            }
            
            # 方法1：获取财务指标数据
            try:
                finance_data = ak.stock_financial_analysis_indicator(symbol=code_num)
                if finance_data is not None and not finance_data.empty:
                    latest = finance_data.iloc[-1]
                    fundamental_data.update({
                        "每股收益(EPS)": self._safe_float(latest.get('每股收益')),
                        "净利润": self._safe_float(latest.get('净利润')),
                        "营业总收入": self._safe_float(latest.get('营业总收入')),
                        "净资产收益率(%)": self._safe_float(latest.get('净资产收益率')),
                        "市盈率(PE)": self._safe_float(latest.get('市盈率'))
                    })
                    return fundamental_data
            except Exception as e:
                pass
            
            # 方法2：获取A股财务报表数据
            try:
                report_data = ak.stock_main_indicator(symbol=code_num)
                if report_data is not None and not report_data.empty:
                    latest = report_data.iloc[-1]
                    
                    # 提取可用数据
                    eps = self._safe_float(latest.get('eps'))
                    roe = self._safe_float(latest.get('roe'))
                    pe = self._safe_float(latest.get('pe'))
                    
                    fundamental_data.update({
                        "每股收益(EPS)": eps if eps else "数据获取中",
                        "净资产收益率(%)": roe if roe else "数据获取中",
                        "市盈率(PE)": pe if pe else "数据获取中"
                    })
                    
                    if any(v and v != "数据获取中" for v in fundamental_data.values()):
                        return fundamental_data
            except Exception as e:
                pass
            
            # 方法3：获取实时基本面数据
            try:
                spot_data = ak.stock_zh_a_spot_em()
                if spot_data is not None and not spot_data.empty:
                    row = spot_data[spot_data['代码'].astype(str) == code_num]
                    if not row.empty:
                        r = row.iloc[0]
                        fundamental_data.update({
                            "总市值": self._safe_float(r.get('总市值')),
                            "市盈率(PE)": self._safe_float(r.get('市盈率')),
                            "市净率(PB)": self._safe_float(r.get('市净率')),
                            "最新价": self._safe_float(r.get('最新价'))
                        })
                        return fundamental_data
            except Exception as e:
                pass
            
            # 方法4：从东方财富获取基本数据
            try:
                bs_data = ak.stock_a_lg_indicator()
                if bs_data is not None and not bs_data.empty:
                    row = bs_data[bs_data['代码'].astype(str) == code_num]
                    if not row.empty:
                        r = row.iloc[0]
                        fundamental_data.update({
                            "市盈率(PE)": self._safe_float(r.get('最新价') / r.get('每股收益')) if r.get('每股收益') else "N/A",
                            "市净率(PB)": self._safe_float(r.get('市净率')),
                        })
                        return fundamental_data
            except Exception as e:
                pass
            
            # 如果所有方法都失败，返回提示
            if len(fundamental_data) == 2:
                fundamental_data["说明"] = "财报数据暂时无法获取，请检查网络连接或稍后重试"
            
            return fundamental_data
        except Exception as e:
            print(f"获取基本面数据失败: {e}")
            return {
                "股票代码": self.stock_code,
                "股票名称": self.stock_name,
                "说明": f"数据获取异常: {str(e)[:50]}"
            }
    
    @staticmethod
    def _safe_float(value) -> Optional[float]:
        """安全转换为浮点数"""
        try:
            if value is None or (isinstance(value, float) and np.isnan(value)):
                return None
            result = float(value)
            return result if not np.isnan(result) else None
        except:
            return None
    
    def get_technical_indicators(self, days: int = 100) -> pd.DataFrame:
        """
        计算技术指标数据
        
        Args:
            days: 计算周期天数
            
        Returns:
            包含MA、RSI、MACD的DataFrame
        """
        if not self.stock_code:
            print("请先搜索股票")
            return pd.DataFrame()
        
        try:
            # 获取K线数据
            kline_data = self.get_kline_data(period="daily", days=days)
            
            if kline_data.empty:
                return pd.DataFrame()
            
            # 将Close列转换为数值型
            kline_data['Close'] = pd.to_numeric(kline_data['Close'], errors='coerce')
            
            # 计算移动平均线 (MA)
            kline_data['MA5'] = kline_data['Close'].rolling(window=5).mean()
            kline_data['MA20'] = kline_data['Close'].rolling(window=20).mean()
            
            # 计算相对强弱指数 (RSI)
            kline_data['RSI'] = self._calculate_rsi(kline_data['Close'], period=14)
            
            # 计算移动平均收敛散度 (MACD)
            macd, signal, hist = self._calculate_macd(kline_data['Close'])
            kline_data['MACD'] = macd
            kline_data['Signal'] = signal
            kline_data['MACD_Hist'] = hist
            
            # 选择需要的列
            tech_data = kline_data[['Date', 'Close', 'MA5', 'MA20', 'RSI', 'MACD', 'Signal', 'MACD_Hist']]
            
            return tech_data
        except Exception as e:
            print(f"计算技术指标失败: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def _calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        """计算MACD指标"""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram


def get_all_stock_data(stock_input: str, kline_days: int = 100):
    """
    获取指定股票的所有数据
    
    Args:
        stock_input: 股票代码或名称
        kline_days: K线数据天数
    """
    print(f"\n{'='*60}")
    print(f"正在获取股票数据: {stock_input}")
    print(f"{'='*60}\n")
    
    fetcher = StockDataFetcher()
    
    # 搜索股票
    result = fetcher.search_stock(stock_input)
    if not result:
        return
    
    code, name = result
    print(f"✓ 找到股票: {code} - {name}\n")
    
    # 1. 实时行情数据
    print(f"\n{'='*60}")
    print("1️⃣  实时行情数据")
    print(f"{'='*60}")
    realtime_data = fetcher.get_realtime_data()
    if realtime_data:
        for key, value in realtime_data.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")
    
    # 2. 历史K线数据
    print(f"\n{'='*60}")
    print("2️⃣  历史K线数据（最近20条日线）")
    print(f"{'='*60}")
    kline_data = fetcher.get_kline_data(period="daily", days=kline_days)
    if not kline_data.empty:
        print("\n日线数据（最近20条）:")
        print(kline_data.tail(20).to_string(index=False))
    
    # 3. 基本面数据
    print(f"\n{'='*60}")
    print("3️⃣  基本面数据（财报）")
    print(f"{'='*60}")
    fundamental_data = fetcher.get_fundamental_data()
    if fundamental_data:
        for key, value in fundamental_data.items():
            if isinstance(value, float):
                if not np.isnan(value):
                    print(f"  {key}: {value:.2f}")
            elif isinstance(value, (int, str)):
                if value and str(value).strip():
                    print(f"  {key}: {value}")
            elif value is not None:
                print(f"  {key}: {value}")
    
    # 4. 技术指标数据
    print(f"\n{'='*60}")
    print("4️⃣  技术指标数据（最近20条）")
    print(f"{'='*60}")
    tech_data = fetcher.get_technical_indicators(days=kline_days)
    if not tech_data.empty:
        print("\n技术指标（最近20条）:")
        # 格式化输出
        display_data = tech_data.tail(20).copy()
        for col in ['Close', 'MA5', 'MA20', 'RSI', 'MACD', 'Signal']:
            if col in display_data.columns:
                display_data[col] = display_data[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
        print(display_data.to_string(index=False))
    
    print(f"\n{'='*60}\n")
    
    return {
        "realtime": realtime_data,
        "kline": kline_data,
        "fundamental": fundamental_data,
        "technical": tech_data
    }


if __name__ == "__main__":
    # 交互式输入股票代码/名称
    print("=" * 60)
    print("股票数据分析系统")
    print("=" * 60)
    print("\n支持的输入格式:")
    print("  - 股票代码: 600000, 000001")
    print("  - 股票名称: 浦发银行, 平安银行")
    print("\n")
    
    while True:
        stock_input = input("请输入股票代码或名称（输入'exit'退出）: ").strip()
        
        if stock_input.lower() == 'exit':
            print("\n谢谢使用，再见！")
            break
        
        if not stock_input:
            print("请输入有效的股票代码或名称\n")
            continue
        
        data = get_all_stock_data(stock_input)
        
        if data:
            save = input("\n是否保存数据到CSV文件？(y/n): ").strip().lower()
            if save == 'y':
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                if not data['kline'].empty:
                    kline_file = f"kline_{stock_input}_{timestamp}.csv"
                    data['kline'].to_csv(kline_file, index=False, encoding='utf-8-sig')
                    print(f"✓ K线数据已保存: {kline_file}")
                
                if not data['technical'].empty:
                    tech_file = f"technical_{stock_input}_{timestamp}.csv"
                    data['technical'].to_csv(tech_file, index=False, encoding='utf-8-sig')
                    print(f"✓ 技术指标已保存: {tech_file}")
