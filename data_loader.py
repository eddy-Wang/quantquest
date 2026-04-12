"""
数据获取层：A 股用 akshare，美股用 yfinance。本地 parquet 缓存。
"""
import os
import time
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

CACHE_DIR = Path(__file__).parent / "data_cache"
CACHE_DIR.mkdir(exist_ok=True)

# 默认股票池
US_POOL = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM",
           "V", "WMT", "PG", "JNJ", "XOM", "KO", "DIS", "NFLX", "AMD", "INTC",
           "BAC", "PFE"]

# A 股池：用代码（akshare 格式：6位数字）
CN_POOL = [
    ("600519", "贵州茅台"), ("000858", "五粮液"), ("601318", "中国平安"),
    ("600036", "招商银行"), ("000333", "美的集团"), ("600276", "恒瑞医药"),
    ("000651", "格力电器"), ("601166", "兴业银行"), ("600030", "中信证券"),
    ("000001", "平安银行"), ("600000", "浦发银行"), ("601398", "工商银行"),
    ("600887", "伊利股份"), ("000568", "泸州老窖"), ("600585", "海螺水泥"),
    ("002415", "海康威视"), ("300750", "宁德时代"), ("600031", "三一重工"),
    ("601012", "隆基绿能"), ("002594", "比亚迪"),
]


def _cache_path(market: str, kind: str) -> Path:
    return CACHE_DIR / f"{market}_{kind}.parquet"


def load_us(start: str = "2020-01-01", end: str = None, force: bool = False):
    """返回 (close_df, volume_df)。"""
    p_close = _cache_path("us", "close")
    p_vol = _cache_path("us", "volume")
    if p_close.exists() and not force:
        return pd.read_parquet(p_close), pd.read_parquet(p_vol)

    import yfinance as yf
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    df = yf.download(US_POOL, start=start, end=end, auto_adjust=True, progress=False, threads=True)
    close = df["Close"].dropna(how="all")
    volume = df["Volume"].dropna(how="all")
    close.to_parquet(p_close)
    volume.to_parquet(p_vol)
    return close, volume


def load_cn(start: str = "2022-01-01", end: str = None, force: bool = False):
    p_close = _cache_path("cn", "close")
    p_vol = _cache_path("cn", "volume")
    if p_close.exists() and not force:
        return pd.read_parquet(p_close), pd.read_parquet(p_vol)

    import akshare as ak
    if end is None:
        end = datetime.now().strftime("%Y%m%d")
    s = start.replace("-", "")
    closes = {}
    vols = {}
    for code, name in CN_POOL:
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                     start_date=s, end_date=end, adjust="qfq")
            if df is None or df.empty:
                continue
            df["日期"] = pd.to_datetime(df["日期"])
            df = df.set_index("日期")
            closes[f"{code} {name}"] = df["收盘"]
            vols[f"{code} {name}"] = df["成交量"]
            time.sleep(0.15)
        except Exception as e:
            print(f"[CN] fail {code}: {e}")
    close = pd.DataFrame(closes).sort_index()
    volume = pd.DataFrame(vols).sort_index()
    close.to_parquet(p_close)
    volume.to_parquet(p_vol)
    return close, volume


def get_data(market: str, force: bool = False):
    if market == "us":
        return load_us(force=force)
    return load_cn(force=force)
