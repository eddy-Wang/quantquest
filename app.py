"""
量化因子科普平台 - FastAPI 后端
启动: python app.py  → 浏览器打开 http://localhost:8765
"""
import os
import json
import numpy as np
import pandas as pd
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from factors import FACTOR_REGISTRY, compute_factor, information_coefficient, quintile_backtest
from data_loader import get_data, US_POOL, CN_POOL

ROOT = Path(__file__).parent
app = FastAPI(title="量化因子科普平台")


# ----------- 模型 -----------
class ComputeReq(BaseModel):
    market: str = "us"     # us | cn
    factor: str = "momentum_60d"
    start: str = None
    end: str = None
    fwd: int = 5           # 未来 N 日收益用于 IC
    n_groups: int = 5
    hold: int = 5


# ----------- 工具 -----------
def df_to_records(df: pd.DataFrame, max_points: int = 400):
    """对长序列做下采样，避免前端卡。"""
    if len(df) > max_points:
        step = len(df) // max_points
        df = df.iloc[::step]
    out = {"index": [str(d.date()) if hasattr(d, "date") else str(d) for d in df.index]}
    for c in df.columns:
        out[str(c)] = [None if pd.isna(v) else float(v) for v in df[c]]
    return out


def series_to_records(s: pd.Series, max_points: int = 400):
    if len(s) > max_points:
        step = len(s) // max_points
        s = s.iloc[::step]
    return {
        "index": [str(d.date()) if hasattr(d, "date") else str(d) for d in s.index],
        "values": [None if pd.isna(v) else float(v) for v in s.values],
    }


# ----------- API -----------
@app.get("/api/factors")
def list_factors():
    out = []
    for k, v in FACTOR_REGISTRY.items():
        out.append({
            "key": k,
            "title": v["title"],
            "category": v["category"],
            "story": v["story"],
            "formula": v["formula"],
            "intuition": v["intuition"],
        })
    return out


@app.get("/api/universe")
def universe(market: str = "us"):
    if market == "us":
        return {"market": "us", "tickers": US_POOL}
    return {"market": "cn", "tickers": [f"{c} {n}" for c, n in CN_POOL]}


@app.get("/api/prices")
def prices(market: str = "us", ticker: str = None):
    """返回单只股票的价格序列，给科普模块画 K 线/收益图。"""
    close, _ = get_data(market)
    if ticker is None:
        ticker = close.columns[0]
    if ticker not in close.columns:
        raise HTTPException(404, f"{ticker} not found")
    s = close[ticker].dropna()
    return {
        "ticker": ticker,
        "data": series_to_records(s, max_points=600),
        "stats": {
            "n_days": int(len(s)),
            "total_return": float(s.iloc[-1] / s.iloc[0] - 1),
            "ann_return": float((s.iloc[-1] / s.iloc[0]) ** (252 / len(s)) - 1),
            "ann_vol": float(s.pct_change().std() * np.sqrt(252)),
            "max_drawdown": float(((s / s.cummax()) - 1).min()),
        },
    }


@app.post("/api/compute")
def compute(req: ComputeReq):
    import traceback as _tb
    try:
        return _compute_inner(req)
    except HTTPException:
        raise
    except Exception as e:
        detail = _tb.format_exc()
        print(detail)
        raise HTTPException(500, detail=detail)


def _compute_inner(req: ComputeReq):
    if req.factor not in FACTOR_REGISTRY:
        raise HTTPException(404, "unknown factor")
    close, volume = get_data(req.market)
    if req.start:
        close = close.loc[req.start:]
        volume = volume.loc[req.start:]
    if req.end:
        close = close.loc[:req.end]
        volume = volume.loc[:req.end]

    factor = compute_factor(req.factor, close, volume)
    ic = information_coefficient(factor, close, fwd=req.fwd)
    nav = quintile_backtest(factor, close, n_groups=req.n_groups, hold=req.hold)

    # 因子值快照（最新一天）
    last_day = factor.dropna(how="all").iloc[-1].dropna().sort_values()
    snapshot = [{"ticker": str(k), "value": float(v)} for k, v in last_day.items()]

    # 因子值分布（所有日期所有股票，抽样）
    flat = factor.values.flatten()
    flat = flat[~np.isnan(flat)]
    if len(flat) > 5000:
        flat = np.random.choice(flat, 5000, replace=False)

    # 因子时间序列（取池里前 5 只）
    sample_cols = list(factor.columns[:5])
    factor_ts = df_to_records(factor[sample_cols].dropna(how="all"))

    spec = FACTOR_REGISTRY[req.factor]
    return {
        "factor": req.factor,
        "meta": {k: spec[k] for k in ("title", "category", "story", "formula", "intuition")},
        "ic": series_to_records(ic),
        "ic_stats": {
            "mean": float(ic.mean()) if len(ic) else 0,
            "std": float(ic.std()) if len(ic) else 0,
            "ir": float(ic.mean() / ic.std()) if len(ic) and ic.std() > 0 else 0,
            "win_rate": float((ic > 0).mean()) if len(ic) else 0,
            "n_periods": int(len(ic)),
        },
        "nav": df_to_records(nav),
        "nav_stats": {col: {
            "total_return": float(nav[col].iloc[-1] - 1),
            "ann_return": float(nav[col].iloc[-1] ** (252 / len(nav)) - 1) if len(nav) > 0 else 0,
            "max_dd": float(((nav[col] / nav[col].cummax()) - 1).min()),
        } for col in nav.columns},
        "snapshot": snapshot,
        "distribution": [float(x) for x in flat.tolist()],
        "factor_ts": factor_ts,
    }


GLOSSARY = [
    {"term": "因子 (Factor)", "def": "一个能在横截面上区分股票未来收益的指标。比如'过去 60 日涨幅'就是一个动量因子。"},
    {"term": "Alpha", "def": "扣除市场涨跌后剩下的'额外收益'。量化的圣杯。"},
    {"term": "Beta", "def": "你和市场一起涨跌的程度。Beta=1 表示和大盘同步。"},
    {"term": "IC (Information Coefficient)", "def": "因子值与未来收益的截面相关系数。绝对值 > 0.05 已经是不错的因子。"},
    {"term": "IR (Information Ratio)", "def": "IC 的均值 / IC 的标准差。衡量因子的稳定性，越高越稳。"},
    {"term": "夏普比率 (Sharpe)", "def": "(年化收益 - 无风险利率) / 年化波动。> 1 还行，> 2 优秀，> 3 怀疑过拟合。"},
    {"term": "最大回撤 (Max Drawdown)", "def": "净值从最高点跌到最低点的幅度。代表最坏情况下的亏损。"},
    {"term": "分层回测 (Quintile Backtest)", "def": "把股票按因子值分 5 组，看高组是否系统性跑赢低组。检验因子有效性的标准操作。"},
    {"term": "多空组合 (Long-Short)", "def": "买高组、卖空低组。剥离市场涨跌，纯赚因子的钱。"},
    {"term": "动量 (Momentum)", "def": "过去涨得多的继续涨。中期 3-12 月最有效。"},
    {"term": "反转 (Reversal)", "def": "过去涨得多的会回调。短期（1 周）和长期（3-5 年）都存在。"},
    {"term": "低波动异象", "def": "理论上高风险该高收益，实际上低波动股票长期跑赢。最反直觉的发现之一。"},
    {"term": "过拟合 (Overfitting)", "def": "在历史数据上完美，未来一塌糊涂。量化最大的敌人。"},
    {"term": "回测 (Backtest)", "def": "用历史数据模拟策略表现。注意：好的回测 ≠ 好的未来。"},
    {"term": "调仓周期", "def": "多久重新选一次股票。越短越敏感但成本越高。"},
    {"term": "股票池 (Universe)", "def": "策略可选的股票范围。比如沪深 300 成分股。"},
]


@app.get("/api/glossary")
def glossary():
    return GLOSSARY


LESSONS = [
    {
        "id": 1, "xp": 10, "title": "什么是量化投资",
        "body": "**量化投资** = 用数据和数学规则做决策，而不是靠感觉。\n\n传统投资是'我觉得茅台是好公司'，量化是'过去 20 年，所有 ROE>15% 且 PE<30 的股票，年化跑赢大盘 6%'。\n\n核心区别：**可重复、可检验、可规模化**。",
        "quiz": {"q": "下列哪个最像量化思路？", "options": [
            "听朋友说某股票要涨", "财报很厉害的公司值得买",
            "回测显示低波动股票过去 10 年年化 12%", "CEO 接受了央视采访"
        ], "answer": 2}
    },
    {
        "id": 2, "xp": 15, "title": "什么是因子",
        "body": "**因子** 是一个能给所有股票打分的指标。\n\n比如'过去 60 日涨幅'：今天我能给所有股票算出一个数字，然后按这个数字排序。如果排名靠前的股票未来真的更容易涨，这个因子就'有效'。\n\n经典的因子大类：\n- **价值**：便宜的更好（低 PE/PB）\n- **动量**：涨得多的继续涨\n- **质量**：赚钱能力强的（高 ROE）\n- **波动**：低波动反而更好\n- **规模**：小盘股长期跑赢大盘股",
        "quiz": {"q": "因子的本质是？", "options": [
            "一个买卖信号", "一个能给股票横向打分的指标",
            "公司的内在价值", "K 线形态"
        ], "answer": 1}
    },
    {
        "id": 3, "xp": 20, "title": "如何检验因子是否有效",
        "body": "两个最常用的方法：\n\n**1. IC（信息系数）**\n每天算一次：今天的因子值，和未来 5 天的收益，相关性是多少？把每天的相关系数取均值。|IC|>0.03 算可用，>0.05 算不错。\n\n**2. 分层回测**\n每天把股票按因子值分 5 组，看第 5 组（高分组）是否系统性跑赢第 1 组（低分组）。如果 5 个组的累计收益像彩虹一样从 Q1 到 Q5 单调排开，那这就是个好因子。\n\n**多空组合**：买 Q5、卖 Q1，赚的就是纯因子收益，和大盘涨跌无关。",
        "quiz": {"q": "IC 是什么的相关性？", "options": [
            "两只股票之间", "因子值和未来收益（截面）",
            "策略和大盘", "今天和昨天"
        ], "answer": 1}
    },
    {
        "id": 4, "xp": 20, "title": "回测的陷阱",
        "body": "回测好看，未来不一定好。常见坑：\n\n- **过拟合**：参数试了 100 次，挑出最好看的那组。换个时间段就崩。\n- **未来函数**：不小心用了未来才知道的数据（比如用今天收盘价决定今天买什么）。\n- **幸存者偏差**：只看现在还活着的公司，那些退市的烂公司没算进去。\n- **交易成本**：忽略了手续费、滑点、冲击成本。高频策略尤其致命。\n\n**黄金准则**：留一段时间不参与调参，最后只跑一次看结果。",
        "quiz": {"q": "下面哪个不是回测陷阱？", "options": [
            "过拟合", "幸存者偏差", "未来函数", "使用真实历史价格"
        ], "answer": 3}
    },
    {
        "id": 5, "xp": 25, "title": "上手实践",
        "body": "去【实践工坊】选一个市场、一个因子、一段时间，亲手算一下：\n\n- 看 IC 时间序列是不是稳定为正/负\n- 看分层回测的 5 条曲线有没有从 Q1 到 Q5 拉开\n- 看多空组合（LongShort）是否单调向上\n\n试试不同因子在不同市场表现的差异。比如动量因子在 A 股和美股就完全不一样。",
        "quiz": {"q": "好因子的分层回测应该长什么样？", "options": [
            "5 条线缠在一起", "Q1 到 Q5 单调排开",
            "Q3 最高", "随机"
        ], "answer": 1}
    },
]


@app.get("/api/lessons")
def lessons():
    return LESSONS


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
