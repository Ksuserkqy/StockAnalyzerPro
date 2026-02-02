
import os
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd
import requests
from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.table import Table


console = Console()


def _read_env():
	load_dotenv()
	api_key = os.getenv("OPENAI_API_KEY")
	base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL")
	model = os.getenv("OPENAI_MODEL") or os.getenv("DEEPSEEK_MODEL") or "deepseek-chat"
	if not api_key:
		raise RuntimeError("缺少环境变量 OPENAI_API_KEY")
	return api_key, base_url, model


def _pick_stock(df: pd.DataFrame, keyword: str) -> pd.Series | None:
	keyword = keyword.strip()
	if not keyword:
		return None

	code_col = "代码"
	name_col = "名称"
	if keyword.isdigit():
		candidates = df[df[code_col].str.contains(keyword, na=False)]
	else:
		candidates = df[df[name_col].str.contains(keyword, na=False)]

	if candidates.empty:
		return None

	if len(candidates) == 1:
		return candidates.iloc[0]

	table = Table(title="匹配到多只股票，请选择")
	table.add_column("序号", justify="right")
	table.add_column("代码")
	table.add_column("名称")
	table.add_column("最新价", justify="right")
	table.add_column("涨跌幅(%)", justify="right")
	for idx, row in candidates.head(10).reset_index(drop=True).iterrows():
		table.add_row(
			str(idx + 1),
			str(row.get(code_col, "")),
			str(row.get(name_col, "")),
			str(row.get("最新价", "")),
			str(row.get("涨跌幅", "")),
		)
	console.print(table)
	while True:
		sel = input("输入序号(1-10)选择：").strip()
		if sel.isdigit():
			sel_idx = int(sel) - 1
			if 0 <= sel_idx < min(10, len(candidates)):
				return candidates.reset_index(drop=True).iloc[sel_idx]
		console.print("无效选择，请重试。")


def _fetch_spot() -> pd.DataFrame:
	try:
		return ak.stock_zh_a_spot_em()
	except requests.exceptions.ProxyError:
		_console_proxy_notice()
		_disable_proxy_env()
		return ak.stock_zh_a_spot_em()


def _fetch_history(code: str) -> pd.DataFrame:
	end = datetime.now().strftime("%Y%m%d")
	start = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
	try:
		hist = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start, end_date=end, adjust="")
	except requests.exceptions.ProxyError:
		_console_proxy_notice()
		_disable_proxy_env()
		hist = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start, end_date=end, adjust="")
	if hist.empty:
		return hist
	hist = hist.rename(columns={
		"日期": "date",
		"开盘": "open",
		"收盘": "close",
		"最高": "high",
		"最低": "low",
		"成交量": "volume",
		"成交额": "amount",
		"振幅": "amplitude",
		"涨跌幅": "pct_change",
		"涨跌额": "change",
		"换手率": "turnover",
	})
	return hist


def _calc_indicators(hist: pd.DataFrame) -> dict:
	if hist.empty:
		return {}
	df = hist.copy()
	df["close"] = pd.to_numeric(df["close"], errors="coerce")
	df = df.dropna(subset=["close"])
	if df.empty:
		return {}
	df["ma5"] = df["close"].rolling(5).mean()
	df["ma10"] = df["close"].rolling(10).mean()
	df["ma20"] = df["close"].rolling(20).mean()

	delta = df["close"].diff()
	gain = delta.clip(lower=0).rolling(14).mean()
	loss = (-delta.clip(upper=0)).rolling(14).mean()
	rs = gain / loss.replace(0, pd.NA)
	df["rsi14"] = 100 - (100 / (1 + rs))

	latest = df.iloc[-1]
	return {
		"ma5": round(float(latest.get("ma5", 0) or 0), 4),
		"ma10": round(float(latest.get("ma10", 0) or 0), 4),
		"ma20": round(float(latest.get("ma20", 0) or 0), 4),
		"rsi14": round(float(latest.get("rsi14", 0) or 0), 4),
	}


def _build_prompt(spot_row: pd.Series, hist: pd.DataFrame, indicators: dict) -> str:
	latest = hist.tail(20).to_dict(orient="records") if not hist.empty else []
	spot_info = {
		"代码": spot_row.get("代码"),
		"名称": spot_row.get("名称"),
		"最新价": spot_row.get("最新价"),
		"涨跌幅": spot_row.get("涨跌幅"),
		"涨跌额": spot_row.get("涨跌额"),
		"成交量": spot_row.get("成交量"),
		"成交额": spot_row.get("成交额"),
		"今开": spot_row.get("今开"),
		"昨收": spot_row.get("昨收"),
		"最高": spot_row.get("最高"),
		"最低": spot_row.get("最低"),
		"换手率": spot_row.get("换手率"),
		"市盈率": spot_row.get("市盈率-动态") or spot_row.get("市盈率"),
		"市净率": spot_row.get("市净率"),
		"总市值": spot_row.get("总市值"),
		"流通市值": spot_row.get("流通市值"),
	}
	payload = {
		"spot": spot_info,
		"indicators": indicators,
		"recent_kline": latest,
		"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
	}
	return (
		"你是专业的量化与基本面结合的股票分析助手。"
		"基于给定的实时行情、近期K线与技术指标，"
		"给出简洁、谨慎的建议，包含：趋势判断、风险提示、操作建议(观望/轻仓/中仓/减仓)。"
		"不要编造数据。输出中文，控制在200字以内。\n"
		f"数据：{payload}"
	)


def _disable_proxy_env() -> None:
	for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
		os.environ.pop(key, None)
	os.environ["NO_PROXY"] = "*"
	os.environ["no_proxy"] = "*"


def _console_proxy_notice() -> None:
	console.print("检测到代理错误，已尝试临时禁用系统代理后重试。")


def _call_model(prompt: str, api_key: str, base_url: str | None, model: str) -> str:
	client = OpenAI(api_key=api_key, base_url=base_url)
	response = client.chat.completions.create(
		model=model,
		messages=[
			{"role": "system", "content": "你是严谨的金融分析助手。"},
			{"role": "user", "content": prompt},
		],
		temperature=0.2,
	)
	return response.choices[0].message.content.strip()


def main():
	console.print("输入股票代码或名称：")
	keyword = input().strip()
	if not keyword:
		console.print("未输入内容，已退出。")
		return

	console.print("正在获取实时行情...")
	spot_df = _fetch_spot()
	row = _pick_stock(spot_df, keyword)
	if row is None:
		console.print("未找到匹配的股票。")
		return

	code = row.get("代码")
	name = row.get("名称")
	console.print(f"已选择：{code} {name}")

	console.print("正在拉取历史行情...")
	hist = _fetch_history(str(code))
	indicators = _calc_indicators(hist)

	api_key, base_url, model = _read_env()
	prompt = _build_prompt(row, hist, indicators)

	console.print("模型分析中...")
	advice = _call_model(prompt, api_key, base_url, model)

	console.print("\n[结果] 建议：")
	console.print(advice)


if __name__ == "__main__":
	main()
