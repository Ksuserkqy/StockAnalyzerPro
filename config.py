import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "").strip()
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

    # 数据抓取参数（可按需调）
    hist_days: int = 60          # 取最近 N 个交易日
    topn_candidates: int = 10    # 名称模糊匹配时最多候选

settings = Settings()
if not settings.deepseek_api_key:
    raise RuntimeError("DEEPSEEK_API_KEY 未设置，请先在 .env 配置。")
