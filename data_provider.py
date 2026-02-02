# data_provider.py
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional, Tuple, List, Callable, Any

import pandas as pd
import akshare as ak


# -----------------------------
# 数据结构
# -----------------------------
@dataclass
class StockSnapshot:
    code: str
    name: str
    latest: float
    pct: float
    turnover: float
    amount: float


# -----------------------------
# AKShare Provider（含缓存 + 重试 + 容错）
# -----------------------------
class AkshareProvider:
    """
    AKShare 数据提供器：
    - 用东方财富全市场快照做 code/name 解析
    - 拉实时快照
    - 拉历史日K线（近 N 个交易日）
    - 内置重试与指数退避，解决 RemoteDisconnected / Connection aborted 等网络抖动
    """

    def __init__(
        self,
        snapshot_ttl_sec: int = 10,
        max_retries: int = 5,
        base_delay_sec: float = 1.5,
        backoff: float = 1.8,
        jitter_sec: float = 0.2,
        verbose_retry: bool = True,
    ):
        self.snapshot_ttl_sec = snapshot_ttl_sec

        self.max_retries = max_retries
        self.base_delay_sec = base_delay_sec
        self.backoff = backoff
        self.jitter_sec = jitter_sec
        self.verbose_retry = verbose_retry

        self._snapshot_cache: Optional[pd.DataFrame] = None
        self._snapshot_cache_ts: float = 0.0

    # -----------------------------
    # 工具：列名选择、输入识别
    # -----------------------------
    @staticmethod
    def _pick_col(cols: List[str], candidates: List[str]) -> Optional[str]:
        for c in candidates:
            if c in cols:
                return c
        return None

    @staticmethod
    def _is_code(s: str) -> bool:
        s = s.strip()
        return bool(re.fullmatch(r"\d{6}", s))

    @staticmethod
    def _sleep_with_backoff(attempt: int, base: float, backoff: float, jitter: float):
        # attempt 从 0 开始
        delay = base * (backoff ** attempt)
        delay = delay + (jitter * (attempt + 1))  # 轻微抖动，避免同频打爆
        time.sleep(delay)

    def _call_with_retry(self, fn: Callable[[], Any], label: str) -> Any:
        """
        统一重试封装：专治 RemoteDisconnected / Connection aborted / 连接被对端断开等抖动
        """
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                return fn()
            except Exception as e:
                last_err = e
                if self.verbose_retry:
                    print(f"[AKShare] {label} 失败，重试 {attempt + 1}/{self.max_retries}，错误：{e}")
                if attempt < self.max_retries - 1:
                    self._sleep_with_backoff(
                        attempt=attempt,
                        base=self.base_delay_sec,
                        backoff=self.backoff,
                        jitter=self.jitter_sec,
                    )
        raise RuntimeError(f"[AKShare] {label} 连续失败（已重试 {self.max_retries} 次）：{last_err}") from last_err

    # -----------------------------
    # 1) 全市场快照（缓存 + 重试）
    # -----------------------------
    def _get_spot_df(self) -> pd.DataFrame:
        now = time.time()

        # 缓存命中
        if self._snapshot_cache is not None and (now - self._snapshot_cache_ts) <= self.snapshot_ttl_sec:
            return self._snapshot_cache

        def fetch():
            # 东方财富全市场快照（分页拉取，可能出现进度条）
            return ak.stock_zh_a_spot_em()

        df = self._call_with_retry(fetch, "获取全市场实时快照 stock_zh_a_spot_em")
        df = df.copy()

        self._snapshot_cache = df
        self._snapshot_cache_ts = now
        return df

    # -----------------------------
    # 2) 解析输入：代码或名称 → (code, name, hit_df)
    # -----------------------------
    def resolve_symbol(self, query: str, topn: int = 10) -> Tuple[str, str, pd.DataFrame]:
        """
        输入：股票代码(6位) 或 名称关键字（模糊包含）
        输出：(code, name, hit_df)
        - hit_df 若多候选，会返回前 topn 行（按成交额优先）
        """
        q = query.strip()
        if not q:
            raise ValueError("输入为空，请输入股票代码或名称")

        spot = self._get_spot_df()
        cols = spot.columns.tolist()

        col_code = self._pick_col(cols, ["代码", "symbol", "股票代码", "code"])
        col_name = self._pick_col(cols, ["名称", "name", "股票名称"])
        col_amount = self._pick_col(cols, ["成交额", "成交额(元)", "amount"])
        # 其他列不一定需要在这里用

        if not col_code or not col_name:
            raise RuntimeError(f"无法从快照识别代码/名称列。当前列：{cols}")

        # 根据输入类型筛选
        if self._is_code(q):
            hit = spot[spot[col_code].astype(str) == q]
        else:
            hit = spot[spot[col_name].astype(str).str.contains(q, na=False)]

        if hit.empty:
            raise ValueError(f"未找到匹配股票：{query}（可能输入有误，或数据源暂不可用）")

        # 多候选：按成交额排序后取 topn
        if len(hit) > 1:
            hit2 = hit.copy()
            if col_amount:
                # 成交额可能是字符串/带逗号，转数值容错
                hit2[col_amount] = pd.to_numeric(hit2[col_amount], errors="coerce")
                hit2 = hit2.sort_values(col_amount, ascending=False)
            hit2 = hit2.head(topn)

            row0 = hit2.iloc[0]
            code = str(row0[col_code])
            name = str(row0[col_name])
            return code, name, hit2

        row = hit.iloc[0]
        code = str(row[col_code])
        name = str(row[col_name])
        return code, name, hit.iloc[0:1]

    # -----------------------------
    # 3) 实时快照：从 spot 中抽取字段
    # -----------------------------
    def get_realtime_snapshot(self, symbol: str) -> StockSnapshot:
        spot = self._get_spot_df()
        cols = spot.columns.tolist()

        col_code = self._pick_col(cols, ["代码", "symbol", "股票代码", "code"])
        col_name = self._pick_col(cols, ["名称", "name", "股票名称"])
        col_latest = self._pick_col(cols, ["最新价", "最新", "最新价格", "price"])
        col_pct = self._pick_col(cols, ["涨跌幅", "涨跌幅(%)", "pct_chg"])
        col_turnover = self._pick_col(cols, ["换手率", "换手率(%)", "turnover"])
        col_amount = self._pick_col(cols, ["成交额", "成交额(元)", "amount"])

        if not col_code or not col_name:
            raise RuntimeError(f"无法识别快照中的代码/名称列。当前列：{cols}")

        hit = spot[spot[col_code].astype(str) == str(symbol)]
        if hit.empty:
            raise ValueError(f"快照中找不到该代码：{symbol}（可能行情源暂不可用或代码不在A股范围）")

        r = hit.iloc[0]

        def to_float(x) -> float:
            try:
                return float(x)
            except Exception:
                return float("nan")

        latest = to_float(r[col_latest]) if col_latest and pd.notna(r[col_latest]) else float("nan")
        pct = to_float(r[col_pct]) if col_pct and pd.notna(r[col_pct]) else float("nan")
        turnover = to_float(r[col_turnover]) if col_turnover and pd.notna(r[col_turnover]) else float("nan")
        amount = to_float(r[col_amount]) if col_amount and pd.notna(r[col_amount]) else float("nan")

        return StockSnapshot(
            code=str(r[col_code]),
            name=str(r[col_name]),
            latest=latest,
            pct=pct,
            turnover=turnover,
            amount=amount,
        )

    # -----------------------------
    # 4) 历史日K：重试 + 取最近 N 个交易日
    # -----------------------------
    def get_hist_daily(self, symbol: str, days: int = 60, adjust: str = "qfq") -> pd.DataFrame:
        """
        东方财富-个股历史行情（日频）
        adjust: qfq(前复权) / hfq(后复权) / ""(不复权)
        """
        symbol = str(symbol).strip()

        def fetch():
            return ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust=adjust)

        df = self._call_with_retry(fetch, f"获取历史日K stock_zh_a_hist({symbol})")
        df = df.copy()

        # 日期列容错
        if "日期" in df.columns:
            df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
            df = df.dropna(subset=["日期"]).sort_values("日期")

        # 只取最后 days 行
        if days and days > 0 and len(df) > days:
            df = df.tail(days)

        return df

    # -----------------------------
    # 5) 手动清缓存（可选）
    # -----------------------------
    def clear_cache(self):
        self._snapshot_cache = None
        self._snapshot_cache_ts = 0.0
