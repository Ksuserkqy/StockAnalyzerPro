from __future__ import annotations
import os

for k in ["HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy"]:
    os.environ.pop(k, None)

import requests
from akshare import stock

# 修改全局配置：增加重试次数
requests.adapters.DEFAULT_RETRIES = 5  # 最大重试次数
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(max_retries=5)
session.mount('http://', adapter)
session.mount('https://', adapter)

# 让 akshare 使用新的 session
stock.set_session(session)


import pandas as pd
from rich.console import Console
from rich.table import Table

from config import settings
from data_provider import AkshareProvider
from llm_client import DeepSeekLLM
from prompt import SYSTEM_PROMPT, USER_TEMPLATE


console = Console()


def df_to_compact_json_table(df: pd.DataFrame) -> str:
    """
    把K线压缩成模型更容易吃的格式（避免把整张DataFrame原样塞进去太冗余）
    """
    # 尽量映射常见列名
    col_map = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
    }
    df2 = df.copy()
    for k, v in col_map.items():
        if k in df2.columns and v not in df2.columns:
            df2[v] = df2[k]

    # 只保留需要的列
    keep = [c for c in ["date", "open", "close", "high", "low", "volume", "amount"] if c in df2.columns]
    df2 = df2[keep].copy()

    # 日期转字符串
    if "date" in df2.columns:
        df2["date"] = pd.to_datetime(df2["date"]).dt.strftime("%Y-%m-%d")

    # 输出为紧凑的“每行一条”
    lines = []
    for _, r in df2.iterrows():
        lines.append(str(r.to_dict()))
    return "\n".join(lines)


def print_candidates(cand_df: pd.DataFrame):
    t = Table(title="匹配到多个候选（按成交额/顺序排列）")
    # 尽量显示前几列
    cols = cand_df.columns.tolist()
    show_cols = cols[:8]
    for c in show_cols:
        t.add_column(str(c))
    for _, row in cand_df.iterrows():
        t.add_row(*[str(row[c]) for c in show_cols])
    console.print(t)


def main():
    provider = AkshareProvider(snapshot_ttl_sec=10)
    llm = DeepSeekLLM()

    console.print("[bold green]实时股票分析 CLI（输入代码或名称，输入 exit 退出）[/bold green]")

    while True:
        user_query = console.input("\n[bold cyan]请输入股票代码/名称> [/bold cyan]").strip()
        if user_query.lower() in {"exit", "quit", "q"}:
            break
        if not user_query:
            continue

        try:
            code, name, hit_df = provider.resolve_symbol(user_query, topn=settings.topn_candidates)

            # 如果多候选，给用户选；这里为了“最小可用”，默认用第一条，同时展示候选表
            if len(hit_df) > 1:
                print_candidates(hit_df)
                console.print(f"[yellow]默认选择第一条：{code} {name}（你也可以改成让用户输入序号选择）[/yellow]")

            snap = provider.get_realtime_snapshot(code)
            hist = provider.get_hist_daily(code, days=settings.hist_days, adjust="qfq")

            hist_table = df_to_compact_json_table(hist)

            user_prompt = USER_TEMPLATE.format(
                user_query=user_query,
                code=snap.code,
                name=snap.name,
                latest=snap.latest,
                pct=snap.pct,
                turnover=snap.turnover,
                amount=snap.amount,
                hist_days=settings.hist_days,
                hist_table=hist_table,
            )

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            console.print("\n[bold magenta]模型建议（流式输出）>[/bold magenta]")
            buf = []
            for token in llm.stream_chat(messages, temperature=0.2):
                buf.append(token)
                console.print(token, end="")
            console.print("\n")  # 换行

        except Exception as e:
            console.print(f"[bold red]错误：{e}[/bold red]")


if __name__ == "__main__":
    main()
