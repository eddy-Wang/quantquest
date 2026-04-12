"""
量化因子计算库
每个因子都是一个函数，输入价格 DataFrame（index=date, columns=tickers），返回因子值 DataFrame
所有因子在每个截面（每一天）对全部股票同时计算
"""
import numpy as np
import pandas as pd


# ---------- 动量类 ----------
def momentum(prices: pd.DataFrame, window: int = 60) -> pd.DataFrame:
    """过去 N 个交易日累计收益率。直觉：强者恒强。"""
    return prices.pct_change(window)


def reversal(prices: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """短期反转。直觉：短期涨多了会回调。返回负的短期收益。"""
    return -prices.pct_change(window)


# ---------- 波动类 ----------
def volatility(prices: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """过去 N 日收益率的年化标准差。低波动因子在很多市场长期有效。"""
    rets = prices.pct_change()
    return rets.rolling(window).std() * np.sqrt(252)


def downside_vol(prices: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """只算负收益的波动。下行风险。"""
    rets = prices.pct_change()
    neg = rets.where(rets < 0)
    return neg.rolling(window).std() * np.sqrt(252)


# ---------- 技术类 ----------
def rsi(prices: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """相对强弱指标。0~100，越高越超买。"""
    delta = prices.diff()
    up = delta.clip(lower=0).rolling(window).mean()
    down = (-delta.clip(upper=0)).rolling(window).mean()
    rs = up / down.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def macd(prices: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD 柱状值（DIF - DEA）。常用择时信号。"""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    return dif - dea


def bollinger_pct(prices: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """布林带位置：(price - mid) / (2*std)。+1 接近上轨，-1 接近下轨。"""
    mid = prices.rolling(window).mean()
    std = prices.rolling(window).std()
    return (prices - mid) / (2 * std)


# ---------- 量价类 ----------
def amihud_illiq(prices: pd.DataFrame, volumes: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Amihud 非流动性。|收益|/成交额。流动性差的小盘股因子。"""
    rets = prices.pct_change().abs()
    dollar_vol = (prices * volumes).replace(0, np.nan)
    daily = rets / dollar_vol
    return daily.rolling(window).mean()


# ---------- 价值/质量（用价格代理：长期均值回归代替 PE） ----------
def long_reversal(prices: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    """长期反转：过去一年收益的负值。学术上常作为'价值'代理。"""
    return -prices.pct_change(window)


FACTOR_REGISTRY = {
    "momentum_60d":   {"fn": momentum,       "kwargs": {"window": 60},  "category": "动量",
                        "title": "60日动量",
                        "story": "买过去 3 个月涨得多的，卖跌得多的。Jegadeesh & Titman 1993 经典发现：动量在中期（3-12 月）显著有效。",
                        "formula": r"MOM_t = P_t / P_{t-60} - 1",
                        "intuition": "趋势会延续一段时间，因为信息扩散和投资者反应不足。"},
    "reversal_5d":    {"fn": reversal,       "kwargs": {"window": 5},   "category": "反转",
                        "title": "5日短期反转",
                        "story": "短期涨太多的容易回调（流动性提供者收取的补偿）。",
                        "formula": r"REV_t = -(P_t / P_{t-5} - 1)",
                        "intuition": "短期价格冲击 → 均值回归。"},
    "volatility_20d": {"fn": volatility,     "kwargs": {"window": 20},  "category": "波动",
                        "title": "20日波动率",
                        "story": "低波动异象：长期看，低波动股票的风险调整后收益反而更高。",
                        "formula": r"VOL_t = std(r_{t-20:t}) \times \sqrt{252}",
                        "intuition": "高波动股常被过度炒作，低波动股被忽视。"},
    "downside_vol":   {"fn": downside_vol,   "kwargs": {"window": 20},  "category": "波动",
                        "title": "下行波动率",
                        "story": "只惩罚向下的波动，更贴近真实风险厌恶。",
                        "formula": r"DV_t = std(r^-_{t-20:t}) \times \sqrt{252}",
                        "intuition": "投资者怕亏不怕赚。"},
    "rsi_14":         {"fn": rsi,            "kwargs": {"window": 14},  "category": "技术",
                        "title": "RSI(14)",
                        "story": "Wilder 1978。>70 超买，<30 超卖。",
                        "formula": r"RSI = 100 - \frac{100}{1+RS},\ RS=\frac{avg\ gain}{avg\ loss}",
                        "intuition": "极端区域容易反转。"},
    "macd_hist":      {"fn": macd,           "kwargs": {},              "category": "技术",
                        "title": "MACD 柱",
                        "story": "Appel 1979。快慢均线之差再做一次平滑。",
                        "formula": r"MACD = EMA_{12} - EMA_{26},\ HIST = MACD - EMA_9(MACD)",
                        "intuition": "捕捉中期趋势拐点。"},
    "boll_pct":       {"fn": bollinger_pct,  "kwargs": {"window": 20},  "category": "技术",
                        "title": "布林带位置",
                        "story": "价格相对布林带的位置。",
                        "formula": r"\%B = (P - MA_{20}) / (2 \sigma_{20})",
                        "intuition": "超过 +1/-1 视为极端。"},
    "long_reversal":  {"fn": long_reversal,  "kwargs": {"window": 252}, "category": "价值",
                        "title": "长期反转(价值代理)",
                        "story": "DeBondt & Thaler 1985。过去 3-5 年表现差的股票未来反而更强。",
                        "formula": r"LR_t = -(P_t / P_{t-252} - 1)",
                        "intuition": "市场长期过度反应，会均值回归。"},
}


# ---------- 因子评估：IC + 分层回测 ----------
def compute_factor(name: str, prices: pd.DataFrame, volumes: pd.DataFrame = None) -> pd.DataFrame:
    spec = FACTOR_REGISTRY[name]
    fn = spec["fn"]
    if name == "amihud":
        return fn(prices, volumes, **spec["kwargs"])
    return fn(prices, **spec["kwargs"])


def information_coefficient(factor: pd.DataFrame, prices: pd.DataFrame, fwd: int = 5) -> pd.Series:
    """每天的截面 Spearman IC：因子值与未来 fwd 日收益的秩相关。"""
    fwd_ret = prices.pct_change(fwd).shift(-fwd)
    ic = []
    idx = []
    for date in factor.index:
        f = factor.loc[date]
        r = fwd_ret.loc[date] if date in fwd_ret.index else None
        if r is None:
            continue
        df = pd.concat([f, r], axis=1).dropna()
        if len(df) < 5:
            continue
        ic.append(df.iloc[:, 0].corr(df.iloc[:, 1], method="spearman"))
        idx.append(date)
    return pd.Series(ic, index=idx, name="IC")


def quintile_backtest(factor: pd.DataFrame, prices: pd.DataFrame, n_groups: int = 5, hold: int = 5):
    """
    每 hold 日按因子值把股票分 n 组，等权持有 hold 日。
    返回每组的累计净值曲线。约定：因子值越大 → 第 N 组（高组）。
    """
    rets = prices.pct_change().fillna(0)
    rebal_dates = factor.index[::hold]
    group_rets = {g: [] for g in range(1, n_groups + 1)}
    dates_out = []

    for i, d in enumerate(rebal_dates[:-1]):
        f = factor.loc[d].dropna()
        if len(f) < n_groups:
            continue
        try:
            q = pd.qcut(f.rank(method="first"), n_groups, labels=False) + 1
        except ValueError:
            continue
        next_d = rebal_dates[i + 1]
        period_rets = rets.loc[d:next_d].iloc[1:]
        for g in range(1, n_groups + 1):
            members = q[q == g].index
            if len(members) == 0:
                continue
            grp_ret = period_rets[members].mean(axis=1)
            group_rets[g].append(grp_ret)
        dates_out.append((d, next_d))

    out = {}
    for g, lst in group_rets.items():
        if not lst:
            continue
        s = pd.concat(lst).sort_index()
        s = s[~s.index.duplicated(keep="first")]
        out[f"Q{g}"] = (1 + s).cumprod()
    nav = pd.DataFrame(out).fillna(method="ffill")

    # 多空组合
    if "Q1" in nav and f"Q{n_groups}" in nav:
        ls_ret = nav[f"Q{n_groups}"].pct_change().fillna(0) - nav["Q1"].pct_change().fillna(0)
        nav["LongShort"] = (1 + ls_ret).cumprod()
    return nav
