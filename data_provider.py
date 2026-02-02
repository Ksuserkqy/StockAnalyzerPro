from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional, Tuple, List

import pandas as pd
import akshare as ak


@dataclass
class StockSnapshot:
    code: str
    name: str
    latest: float
    pct: float
    turnover: float
    amount: float


class AkshareProvider:
    """
    AKShare 数据提供器（带简易缓存，避免每次都拉全市场快照）
    """
    def __init__(self, snapshot_ttl_sec: int = 10):
        self.snapshot_ttl_sec = snapshot_ttl_sec
        self._snapshot_cache: Optional[pd.DataFrame] = None
        self._snapshot_cache_ts: float = 0.0

    def _get_spot_df(self) -> pd.DataFrame:
        now = time.time()
        if self._snapshot_cache is None or (now - self._snapshot_cache_ts) > self.snapshot_ttl_sec:
            df = ak.stock_zh_a_spot_em()
            # 统一列名：不同版本 AKShare 可能列有差异，尽量做容错
            df = df.copy()
            # 常见列：代码/名称/最新价/涨跌幅/换手率/成交额
            # 若你的 AKShare 列名不同，print(df.columns) 看一下然后在这里映射
            self._snapshot_cache = df
            self._snapshot_cache_ts = now
        return self._snapshot_cache

    @staticmethod
    def _is_code(s: str) -> bool:
        s = s.strip()
        return bool(re.fullmatch(r"\d{6}", s))

    def resolve_symbol(self, query: str, topn: int = 10) -> Tuple[str, str, pd.DataFrame]:
        """
        输入：股票代码(6位) 或 名称（支持模糊）
        输出：(symbol, name, spot_row_df)
        """
        q = query.strip()
        spot = self._get_spot_df()

        # 尝试识别列
        cols = spot.columns.tolist()

        def pick_col(candidates: List[str]) -> Optional[str]:
            for c in candidates:
                if c in cols:
                    return c
            return None

        col_code = pick_col(["代码", "symbol", "股票代码", "code"])
        col_name = pick_col(["名称", "name", "股票名称"])
        col_latest = pick_col(["最新价", "最新", "最新价格", "price"])
        col_pct = pick_col(["涨跌幅", "涨跌幅(%)", "pct_chg"])
        col_turnover = pick_col(["换手率", "换手", "turnover"])
        col_amount = pick_col(["成交额", "成交额(元)", "amount"])

        if not col_code or not col_name:
            raise RuntimeError(f"无法从AKShare快照识别代码/名称列。当前列：{cols}")

        if self._is_code(q):
            hit = spot[spot[col_code].astype(str) == q]
        else:
            # 名称模糊匹配：包含即可
            hit = spot[spot[col_name].astype(str).str.contains(q, na=False)]

        if hit.empty:
            raise ValueError(f"未找到匹配股票：{query}")

        # 如果多条：按成交额降序取前 topn，提示用户候选
        if len(hit) > 1:
            if col_amount:
                hit2 = hit.sort_values(col_amount, ascending=False).head(topn)
            else:
                hit2 = hit.head(topn)
            # 让上层做交互选择：这里直接取第一条也行，但我建议显示候选更稳
            # 这里返回 hit2，让上层决定
            row0 = hit2.iloc[0:1]
            code = str(row0.iloc[0][col_code])
            name = str(row0.iloc[0][col_name])
            return code, name, hit2

        row = hit.iloc[0:1]
        code = str(row.iloc[0][col_code])
        name = str(row.iloc[0][col_name])
        return code, name, row

    def get_realtime_snapshot(self, symbol: str) -> StockSnapshot:
        spot = self._get_spot_df()
        # 尝试识别列
        cols = spot.columns.tolist()
        col_code = "代码" if "代码" in cols else ("symbol" if "symbol" in cols else None)
        col_name = "名称" if "名称" in cols else ("name" if "name" in cols else None)
        col_latest = "最新价" if "最新价" in cols else None
        col_pct = "涨跌幅" if "涨跌幅" in cols else None
        col_turnover = "换手率" if "换手率" in cols else None
        col_amount = "成交额" if "成交额" in cols else None

        if not col_code or not col_name:
            raise RuntimeError(f"无法识别快照列。当前列：{cols}")

        hit = spot[spot[col_code].astype(str) == symbol]
        if hit.empty:
            raise ValueError(f"快照中找不到该代码：{symbol}")

        r = hit.iloc[0]
        latest = float(r[col_latest]) if col_latest and pd.notna(r[col_latest]) else float("nan")
        pct = float(r[col_pct]) if col_pct and pd.notna(r[col_pct]) else float("nan")
        turnover = float(r[col_turnover]) if col_turnover and pd.notna(r[col_turnover]) else float("nan")
        amount = float(r[col_amount]) if col_amount and pd.notna(r[col_amount]) else float("nan")

        return StockSnapshot(
            code=str(r[col_code]),
            name=str(r[col_name]),
            latest=latest,
            pct=pct,
            turnover=turnover,
            amount=amount,
        )

    def get_hist_daily(self, symbol: str, days: int = 60, adjust: str = "qfq") -> pd.DataFrame:
        """
        东方财富-个股历史行情（日频）
        返回列一般包含：日期/开盘/收盘/最高/最低/成交量/成交额 等
        """
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust=adjust)
        df = df.copy()

        # 统一日期列
        if "日期" in df.columns:
            df["日期"] = pd.to_datetime(df["日期"])
            df = df.sort_values("日期")
        return df.tail(days)
