# ============================================================
# 股市K线肌肉记忆训练器 - 精致版
# 第1段：基础框架（数据源 + 指标 + 绘图 + 错题本SQLite）
# ============================================================
# 【本段做什么】
#   1. 导入所有依赖
#   2. 配置页面样式（深色、红涨绿跌）
#   3. 数据源适配层：同花顺API为主，AkShare为备用
#   4. 技术指标计算：MA/MACD/RSI/KDJ/BOLL/ATR/ADX
#   5. K线绘图：Plotly红涨绿跌
#   6. 错题本：SQLite持久化存储
#
# 【使用说明】
#   本段代码是"地基"，后面11段会不断调用这里的函数。
#   拼接顺序：第1段→第2段→...→第12段，全部拼完后运行。
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import random
import sqlite3
import os
import json
from datetime import datetime, timedelta

# ============================================================
# 1. 页面配置
# ============================================================
st.set_page_config(
    page_title="K线肌肉训练器",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 全局浅色样式（高对比度，护眼）
st.markdown("""
<style>
    .red-text { color: #e60000 !important; font-weight: bold; }
    .green-text { color: #008000 !important; font-weight: bold; }
    .yellow-text { color: #b38f00 !important; }
    .info-box {
        padding: 10px 14px; border-radius: 8px; margin: 6px 0;
        border-left: 4px solid #ffcc00; background-color: #fff9e6;
    }
    .success-box {
        padding: 10px 14px; border-radius: 8px; margin: 6px 0;
        border-left: 4px solid #00cc66; background-color: #e6ffee;
    }
    .error-box {
        padding: 10px 14px; border-radius: 8px; margin: 6px 0;
        border-left: 4px solid #ff4444; background-color: #ffeeee;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 2. API Key 读取
# ============================================================
try:
    API_KEY = st.secrets["TONGHUASHUN_API_KEY"]
except Exception:
    API_KEY = ""

# ============================================================
# 3. 股票池 + 行业映射
# ============================================================
STOCK_POOL = [
    ("600519", "贵州茅台"), ("000858", "五粮液"), ("600036", "招商银行"),
    ("000002", "万科A"),   ("002415", "海康威视"), ("600276", "恒瑞医药"),
    ("000651", "格力电器"), ("601318", "中国平安"), ("600030", "中信证券"),
    ("000725", "京东方A"), ("002594", "比亚迪"),   ("600900", "长江电力"),
    ("601166", "兴业银行"), ("600887", "伊利股份"), ("600309", "万华化学"),
    ("000333", "美的集团"), ("000568", "泸州老窖"), ("300750", "宁德时代"),
    ("600809", "山西汾酒"), ("601012", "隆基绿能"), ("002714", "牧原股份"),
    ("600048", "保利发展"), ("601088", "中国神华"), ("600585", "海螺水泥"),
]

INDUSTRY_MAP = {
    "600519": "白酒", "000858": "白酒", "000568": "白酒", "600809": "白酒",
    "600036": "银行", "601166": "银行",
    "600030": "券商", "601318": "保险",
    "000002": "房地产", "600048": "房地产",
    "002415": "安防", "000725": "面板显示",
    "300750": "锂电池", "002594": "新能源车", "601012": "光伏",
    "600276": "医药", "600887": "食品饮料",
    "000333": "家电", "000651": "家电",
    "600309": "化工", "600585": "建材",
    "600900": "电力", "601088": "煤炭",
    "002714": "养殖",
}
ALL_INDUSTRIES = sorted(list(set(INDUSTRY_MAP.values())))

# 获取股票名称
def get_stock_name(code: str) -> str:
    for c, name in STOCK_POOL:
        if c == code:
            return name
    return code

# 获取行业
def get_industry(code: str) -> str:
    return INDUSTRY_MAP.get(code, "未知行业")

# ============================================================
# 4. 数据源适配层
# ============================================================
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_daily(symbol: str, days: int = 250):
    """
    获取日线数据。优先同花顺API，失败则切AkShare。
    
    参数：
        symbol: 6位股票代码，如 "600519"
        days: 获取最近多少自然日的数据
    返回：
        DataFrame(date, open, high, low, close, volume) 或 None
    """
    # ---------- 方案A：同花顺API ----------
    if API_KEY:
        try:
            if symbol.startswith(("60", "68")):
                ths_code = symbol + ".SH"
            else:
                ths_code = symbol + ".SZ"

            url = "https://fuyao.aicubes.cn/api/a-share/prices/historical"
            headers = {"X-api-key": API_KEY}
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            params = {
                "thscode": ths_code,
                "interval": "1d",
                "start": int(start_date.timestamp() * 1000),
                "end": int(end_date.timestamp() * 1000),
                "adjust": "forward"
            }
            for attempt in range(3):
                try:
                    r = requests.get(url, headers=headers, params=params, timeout=15)
                    if r.status_code == 200:
                        data = r.json()
                        if data.get("code") == 0:
                            items = data.get("data", {}).get("item", [])
                            if items:
                                df = pd.DataFrame(items).rename(columns={
                                    "date_ms": "date",
                                    "open_price": "open",
                                    "high_price": "high",
                                    "low_price": "low",
                                    "close_price": "close",
                                    "volume": "volume"
                                })
                                df["date"] = pd.to_datetime(df["date"], unit="ms")
                                return df[["date", "open", "high", "low", "close", "volume"]]
                except Exception:
                    if attempt < 2:
                        import time
                        time.sleep(1)
        except Exception:
            pass

    # ---------- 方案B：AkShare备用 ----------
    try:
        import akshare as ak
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(
            symbol=symbol, period="daily",
            start_date=start, end_date=end, adjust="qfq"
        )
        if df is None or df.empty:
            return None
        df = df.rename(columns={
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume"
        })
        df["date"] = pd.to_datetime(df["date"])
        return df[["date", "open", "high", "low", "close", "volume"]]
    except Exception:
        return None

def fetch_market_index(index_code: str = "000001", days: int = 250):
    """
    获取大盘指数日线。指数代码：
        000001=上证指数, 399001=深证成指, 399006=创业板指
    """
    try:
        import akshare as ak
        prefix = "sh" if index_code.startswith("000") else "sz"
        df = ak.stock_zh_index_daily(symbol=f"{prefix}{index_code}")
        df["date"] = pd.to_datetime(df["date"])
        df = df.rename(columns={
            "date": "date", "open": "open", "high": "high",
            "low": "low", "close": "close", "volume": "volume"
        })
        return df.sort_values("date").tail(days).reset_index(drop=True)
    except Exception:
        return None

# ============================================================
# 5. 技术指标计算
# ============================================================
def calc_all_indicators(df: pd.DataFrame, idx: int = None) -> dict:
    """
    计算全部技术指标，返回字典。
    
    参数：
        df: 包含 open/high/low/close/volume 的DataFrame
        idx: 只计算到第idx根（用于分时/趋势模块的"只看历史"）
             默认None表示计算到最后一根
    """
    if idx is None:
        idx = len(df) - 1
    d = df.iloc[:idx + 1].copy()
    last = d.iloc[-1]
    n = len(d)

    # ---------- 均线 ----------
    ma5  = d["close"].rolling(5).mean().iloc[-1]  if n >= 5  else last["close"]
    ma10 = d["close"].rolling(10).mean().iloc[-1] if n >= 10 else ma5
    ma20 = d["close"].rolling(20).mean().iloc[-1] if n >= 20 else ma5
    ma60 = d["close"].rolling(60).mean().iloc[-1] if n >= 60 else ma20

    # 均线排列
    if last["close"] > ma5 > ma20:
        ma_alignment = "多头排列（强势）"
    elif last["close"] < ma5 < ma20:
        ma_alignment = "空头排列（弱势）"
    else:
        ma_alignment = "均线交织（震荡）"

    # 价格相对MA5位置
    if last["close"] > ma5 * 1.005:
        price_position = "高于MA5（偏强）"
    elif last["close"] < ma5 * 0.995:
        price_position = "低于MA5（偏弱）"
    else:
        price_position = "接近MA5（中性）"

    # ---------- 均价线（VWAP累计） ----------
    avg_p = (d["open"] + d["high"] + d["low"] + d["close"]) / 4
    vwap = (avg_p * d["volume"]).cumsum() / d["volume"].cumsum()
    current_avg_price = vwap.iloc[-1]
    if last["close"] > current_avg_price * 1.002:
        avg_position = "高于均价线（偏强）"
    elif last["close"] < current_avg_price * 0.998:
        avg_position = "低于均价线（偏弱）"
    else:
        avg_position = "接近均价线（中性）"

    # ---------- 量比 ----------
    if n >= 6:
        vol_avg = d["volume"].iloc[-6:-1].mean()
    else:
        vol_avg = d["volume"].mean()
    vol_ratio = last["volume"] / vol_avg if vol_avg > 0 else 1.0
    vol_status = "放量" if vol_ratio > 1.5 else "缩量" if vol_ratio < 0.8 else "正常"

    # 量价关系
    if n >= 2:
        prev_close = d["close"].iloc[-2]
        if vol_ratio > 1.5:
            vol_price_status = "放量上涨（强势）" if last["close"] > prev_close else "放量下跌（弱势）"
        elif vol_ratio < 0.8:
            vol_price_status = "缩量上涨（谨慎）" if last["close"] > prev_close else "缩量下跌（企稳）"
        else:
            vol_price_status = "量价正常"
    else:
        vol_price_status = "数据不足"

    # ---------- MACD ----------
    if n >= 30:
        exp12 = d["close"].ewm(span=12, adjust=False).mean()
        exp26 = d["close"].ewm(span=26, adjust=False).mean()
        dif = exp12 - exp26
        dea = dif.ewm(span=9, adjust=False).mean()
        macd_hist = dif - dea
        macd_value = dif.iloc[-1]
        macd_signal_value = dea.iloc[-1]
        macd_hist_value = macd_hist.iloc[-1]
        if macd_hist.iloc[-1] > 0 and macd_hist.iloc[-1] > macd_hist.iloc[-2]:
            macd_status = "多头增强"
        elif macd_hist.iloc[-1] > 0:
            macd_status = "多头减弱"
        elif macd_hist.iloc[-1] < 0 and macd_hist.iloc[-1] < macd_hist.iloc[-2]:
            macd_status = "空头增强"
        else:
            macd_status = "空头减弱"
        if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]:
            macd_cross = "金叉（偏多）"
        elif dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2]:
            macd_cross = "死叉（偏空）"
        else:
            macd_cross = "无交叉"
    else:
        macd_value = macd_signal_value = macd_hist_value = 0
        macd_status = macd_cross = "数据不足"

    # ---------- RSI ----------
    if n >= 15:
        delta = d["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - 100 / (1 + rs.iloc[-1]) if not pd.isna(rs.iloc[-1]) else 50
        rsi_status = "超买区" if rsi > 70 else "超卖区" if rsi < 30 else "中性"
    else:
        rsi, rsi_status = 50, "数据不足"

    # ---------- KDJ ----------
    if n >= 9:
        low9 = d["low"].rolling(9).min()
        high9 = d["high"].rolling(9).max()
        rsv = (d["close"] - low9) / (high9 - low9).replace(0, np.nan) * 100
        rsv = rsv.fillna(50)
        k_val = rsv.ewm(com=2, adjust=False).mean().iloc[-1]
        d_val = rsv.ewm(com=2, adjust=False).mean().ewm(com=2, adjust=False).mean().iloc[-1]
        j_val = 3 * k_val - 2 * d_val
        kdj_status = "超买" if j_val > 100 else "超卖" if j_val < 0 else "中性"
    else:
        k_val = d_val = j_val = 50
        kdj_status = "数据不足"

    # ---------- 布林带 ----------
    if n >= 20:
        bb_mid = d["close"].rolling(20).mean().iloc[-1]
        bb_std = d["close"].rolling(20).std().iloc[-1]
        bb_up = bb_mid + 2 * bb_std
        bb_low = bb_mid - 2 * bb_std
        bb_pos = (last["close"] - bb_low) / (bb_up - bb_low) * 100 if bb_up > bb_low else 50
        if last["close"] > bb_up:
            boll_status = "触及上轨（压力）"
        elif last["close"] < bb_low:
            boll_status = "触及下轨（支撑）"
        else:
            boll_status = "中轨附近"
    else:
        bb_up = bb_low = bb_mid = last["close"]
        bb_pos, boll_status = 50, "数据不足"

    # ---------- ATR ----------
    if n >= 14:
        high, low = d["high"], d["low"]
        prev_close = d["close"].shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
    else:
        atr = last["high"] - last["low"]

    # ---------- ADX（趋势强度） ----------
    if n >= 28:
        up_move = d["high"].diff()
        down_move = -d["low"].diff()
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        tr14 = tr.rolling(14).sum()
        plus_di = 100 * pd.Series(plus_dm).rolling(14).sum() / tr14
        minus_di = 100 * pd.Series(minus_dm).rolling(14).sum() / tr14
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.rolling(14).mean().iloc[-1]
    else:
        adx = 25

    # ---------- 短期趋势 ----------
    if n >= 3:
        recent3 = d["close"].iloc[-3:]
        short_trend = "上涨" if recent3.iloc[-1] > recent3.iloc[0] else "下跌"
    else:
        short_trend = "震荡"

    # ---------- 累计涨跌幅 ----------
    first_open = d["open"].iloc[0]
    pct_change = (last["close"] - first_open) / first_open * 100

    # ---------- 价格区间位置 ----------
    day_high = d["high"].max()
    day_low = d["low"].min()
    rng = day_high - day_low
    price_pos_pct = (last["close"] - day_low) / rng * 100 if rng > 0 else 50
    price_zone = "高位区" if price_pos_pct > 70 else "低位区" if price_pos_pct < 30 else "中位区"

    # ---------- 乖离率 ----------
    bias = (last["close"] - ma5) / ma5 * 100 if ma5 > 0 else 0
    bias_status = "超买" if bias > 2 else "超卖" if bias < -2 else "正常"

    # ---------- 5/10日涨幅 ----------
    pct_5d  = (last["close"] - d["close"].iloc[-6]) / d["close"].iloc[-6] * 100 if n >= 6 else 0
    pct_10d = (last["close"] - d["close"].iloc[-11]) / d["close"].iloc[-11] * 100 if n >= 11 else 0

    return {
        "last_close": last["close"], "last_open": last["open"],
        "last_high": last["high"], "last_low": last["low"],
        "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
        "ma_alignment": ma_alignment, "price_position": price_position,
        "current_avg_price": current_avg_price, "avg_position": avg_position,
        "last_volume": last["volume"], "vol_avg": vol_avg,
        "vol_ratio": vol_ratio, "vol_status": vol_status,
        "vol_price_status": vol_price_status,
        "macd_value": macd_value, "macd_signal_value": macd_signal_value,
        "macd_hist_value": macd_hist_value,
        "macd_status": macd_status, "macd_cross": macd_cross,
        "rsi": rsi, "rsi_status": rsi_status,
        "k_val": k_val, "d_val": d_val, "j_val": j_val, "kdj_status": kdj_status,
        "boll_up": bb_up, "boll_low": bb_low, "boll_mid": bb_mid,
        "boll_status": boll_status, "bb_position": bb_pos,
        "atr": atr, "adx": adx,
        "day_high": day_high, "day_low": day_low,
        "price_position_pct": price_pos_pct, "price_zone": price_zone,
        "bias": bias, "bias_status": bias_status,
        "short_trend": short_trend, "pct_change": pct_change,
        "pct_5d": pct_5d, "pct_10d": pct_10d,
    }

# ============================================================
# 6. K线绘图（Plotly，红涨绿跌）
# ============================================================
def plot_kline(df, title="", show_ma=True, show_volume=True, height=520, is_intraday=False):
    """
    绘制K线图。
    参数：
        df: DataFrame，日线用date列，分时用time列
        is_intraday: True时用time列做x轴
    """
    x_col = "time" if is_intraday else "date"
    x_vals = df[x_col]

    rows = 2 if show_volume else 1
    fig = make_subplots(
        rows=rows, cols=1, shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.72, 0.28] if show_volume else [1.0],
    )

    # K线主体（红涨绿跌）
    fig.add_trace(go.Candlestick(
        x=x_vals, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color="#ff4444",
        decreasing_line_color="#00cc66",
        increasing_fillcolor="#ff4444",
        decreasing_fillcolor="#00cc66",
        name="K线", showlegend=False
    ), row=1, col=1)

    # 均线
    if show_ma:
        for p, color in [(5, "#ffcc00"), (10, "#00aaff"), (20, "#ff88cc")]:
            if len(df) >= p:
                fig.add_trace(go.Scatter(
                    x=x_vals, y=df["close"].rolling(p).mean(),
                    mode="lines", name=f"MA{p}",
                    line=dict(color=color, width=1.2)
                ), row=1, col=1)

    # 成交量柱
    if show_volume:
        colors = ["#ff4444" if c >= o else "#00cc66"
                  for o, c in zip(df["open"], df["close"])]
        fig.add_trace(go.Bar(
            x=x_vals, y=df["volume"],
            marker_color=colors, name="成交量", showlegend=False
        ), row=2, col=1)

    # 布局
    fig.update_layout(
        title=title, height=height,
        template="plotly_white",
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified"
    )
    fig.update_xaxes(showgrid=True, gridcolor="#2a2a2a")
    fig.update_yaxes(showgrid=True, gridcolor="#2a2a2a")
    return fig

# ============================================================
# 7. 错题本（SQLite持久化）
# ============================================================
DB_FILE = "wrong_answers.db"

def init_db():
    """初始化错题本数据库"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS wrong_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module TEXT NOT NULL,
            question TEXT NOT NULL,
            user_answer TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            analysis TEXT,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_wrong(module, question, user_answer, correct_answer, analysis=""):
    """写入一道错题"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO wrong_answers
        (module, question, user_answer, correct_answer, analysis, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (module, question, user_answer, correct_answer, analysis,
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_wrong_list(module=None, limit=200):
    """查询错题，返回DataFrame"""
    conn = sqlite3.connect(DB_FILE)
    if module and module != "全部":
        df = pd.read_sql_query(
            "SELECT * FROM wrong_answers WHERE module=? ORDER BY timestamp DESC LIMIT ?",
            conn, params=(module, limit)
        )
    else:
        df = pd.read_sql_query(
            "SELECT * FROM wrong_answers ORDER BY timestamp DESC LIMIT ?",
            conn, params=(limit,)
        )
    conn.close()
    return df

def get_wrong_stats():
    """按模块统计错题数量"""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT module, COUNT(*) as count FROM wrong_answers GROUP BY module ORDER BY count DESC",
        conn
    )
    conn.close()
    return df

def clear_wrong(module=None):
    """清空错题"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if module and module != "全部":
        c.execute("DELETE FROM wrong_answers WHERE module=?", (module,))
    else:
        c.execute("DELETE FROM wrong_answers")
    conn.commit()
    conn.close()

# 启动时初始化数据库
init_db()

# ============================================================
# 8. 通用辅助函数
# ============================================================
def color_pct(v):
    """返回带颜色的百分比HTML"""
    if v > 0:
        return f'<span class="red-text">+{v:.2f}%</span>'
    elif v < 0:
        return f'<span class="green-text">{v:.2f}%</span>'
    return f'<span style="color:#888;">0.00%</span>'

def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

# ============================================================
# 第1段结束
# ============================================================# ============================================================
# 第2段：30种K线形态检测算法库
# ============================================================
# 【本段做什么】
#   为30种K线形态各写一个"检测函数"。
#   每个函数输入K线DataFrame，输出 True/False。
#   这样出题时只从"真实出现过的形态"里选，不再瞎猜。
#
# 【30种形态分类】
#   单根K线（6种）：大阳线、大阴线、十字星、T字线、一字涨停、一字跌停
#   双根组合（12种）：看涨吞没、看跌吞没、曙光初现、乌云盖顶、
#                     身怀六甲、平底、平顶、穿头破脚、
#                     好友反攻、淡友反攻、旭日东升、倾盆大雨
#   三根组合（8种）：早晨之星、黄昏之星、红三兵、黑三鸦、
#                   上升三法、下降三法、两阳夹一阴、两阴夹一阳
#   特殊形态（4种）：锤子线、射击之星、倒锤子线、跳空缺口
# ============================================================

# ------------------------------------------------------------
# 形态元数据（名称、类别、含义、看涨看跌、教学）
# ------------------------------------------------------------
PATTERN_DATA = {
    # ===== 单根K线 =====
    "大阳线": {
        "category": "单根K线", "bias": "看涨",
        "meaning": "收盘远高于开盘，实体很长，几乎无上下影线，买方力量极强。",
        "key_features": "实体长度 ≥ 当日振幅的70%，且涨幅 > 2%",
        "teaching": "低位出现大阳线 → 反转信号；高位出现大阳线 → 强势延续但别追高。"
    },
    "大阴线": {
        "category": "单根K线", "bias": "看跌",
        "meaning": "收盘远低于开盘，实体很长，几乎无上下影线，卖方力量极强。",
        "key_features": "实体长度 ≥ 当日振幅的70%，且跌幅 > 2%",
        "teaching": "高位出现大阴线 → 见顶信号；低位出现大阴线 → 恐慌杀跌，别抄底。"
    },
    "十字星": {
        "category": "单根K线", "bias": "中性",
        "meaning": "开盘与收盘几乎相等，实体极小，多空力量均衡。",
        "key_features": "实体 ≤ 当日振幅的10%，上下影线明显",
        "teaching": "高位十字星 → 上涨动能衰竭；低位十字星 → 下跌动能衰竭，等下一根确认。"
    },
    "T字线": {
        "category": "单根K线", "bias": "看涨",
        "meaning": "开盘=收盘，长下影线，无上影线，下方支撑极强。",
        "key_features": "上影线 ≈ 0，下影线 ≥ 实体2倍，开盘≈收盘",
        "teaching": "下跌末端出现T字线 → 股价被买盘托起，止跌信号。"
    },
    "一字涨停": {
        "category": "单根K线", "bias": "看涨",
        "meaning": "开盘即涨停，全天无波动，买方绝对强势。",
        "key_features": "开盘=收盘=最高=最低，且相比前收涨幅≥9.9%",
        "teaching": "持有一字涨停股票 → 继续持有，不要卖。"
    },
    "一字跌停": {
        "category": "单根K线", "bias": "看跌",
        "meaning": "开盘即跌停，全天无波动，卖方绝对强势。",
        "key_features": "开盘=收盘=最高=最低，且相比前收跌幅≤-9.9%",
        "teaching": "持有一字跌停股票 → 次日开盘第一时间挂单卖出。"
    },

    # ===== 双根组合 =====
    "看涨吞没": {
        "category": "双根组合", "bias": "看涨",
        "meaning": "下跌趋势中，第二根大阳线完全包住前一根阴线实体。",
        "key_features": "前阴后阳，阳线实体完全覆盖阴线实体",
        "teaching": "多头完全压倒空头，主力低位大量买入。"
    },
    "看跌吞没": {
        "category": "双根组合", "bias": "看跌",
        "meaning": "上涨趋势中，第二根大阴线完全包住前一根阳线实体。",
        "key_features": "前阳后阴，阴线实体完全覆盖阳线实体",
        "teaching": "空头完全压倒多头，主力高位大量卖出。"
    },
    "曙光初现": {
        "category": "双根组合", "bias": "看涨",
        "meaning": "下跌趋势中，先阴线后大阳线，阳线收盘深入阴线实体一半以上。",
        "key_features": "前阴后阳，阳线收盘 > 阴线实体中点",
        "teaching": "多头开始反击，力度弱于看涨吞没，但也是见底信号。"
    },
    "乌云盖顶": {
        "category": "双根组合", "bias": "看跌",
        "meaning": "上涨趋势中，先阳线后大阴线，阴线收盘深入阳线实体一半以上。",
        "key_features": "前阳后阴，阴线收盘 < 阳线实体中点",
        "teaching": "空头开始反击，力度弱于看跌吞没，但也是见顶信号。"
    },
    "身怀六甲": {
        "category": "双根组合", "bias": "中性",
        "meaning": "一根大K线后面跟一根小K线，小K线实体完全被大K线实体包裹。",
        "key_features": "前大后小，后一根实体完全在前一根实体内",
        "teaching": "动能衰竭，趋势可能反转，等下一根确认方向。"
    },
    "平底": {
        "category": "双根组合", "bias": "看涨",
        "meaning": "连续两根K线最低价相同或非常接近，形成水平支撑。",
        "key_features": "两根最低价相差 < 0.3%",
        "teaching": "支撑位被反复确认，可在支撑位附近买入。"
    },
    "平顶": {
        "category": "双根组合", "bias": "看跌",
        "meaning": "连续两根K线最高价相同或非常接近，形成水平压力。",
        "key_features": "两根最高价相差 < 0.3%",
        "teaching": "压力位被反复确认，可在压力位附近卖出，不要追高。"
    },
    "穿头破脚": {
        "category": "双根组合", "bias": "看涨/看跌",
        "meaning": "第二根K线的最高>前高且最低<前低（穿头破脚），方向相反时反转力度极强。",
        "key_features": "后一根的high > 前高 且 low < 前低",
        "teaching": "比普通吞没更强，说明主力资金集中买入或卖出。"
    },
    "好友反攻": {
        "category": "双根组合", "bias": "看涨",
        "meaning": "下跌趋势中，先阴线，后阳线跳空低开，但收盘回到阴线收盘价附近。",
        "key_features": "前阴后阳，阳线开盘低于前收，阳线收盘≥前阴收盘",
        "teaching": "空头最后一击失败，多头强势反攻。"
    },
    "淡友反攻": {
        "category": "双根组合", "bias": "看跌",
        "meaning": "上涨趋势中，先阳线，后阴线跳空高开，但收盘回到阳线收盘价附近。",
        "key_features": "前阳后阴，阴线开盘高于前收，阴线收盘≤前阳收盘",
        "teaching": "多头最后一冲失败，空头开始反攻。"
    },
    "旭日东升": {
        "category": "双根组合", "bias": "看涨",
        "meaning": "下跌趋势中，先阴线，后阳线开盘低于阴线收盘，但收盘高于阴线开盘。",
        "key_features": "前阴后阳，阳线完全收复阴线实体",
        "teaching": "多头不仅收复前一天跌幅，还创出新高，反转力度强。"
    },
    "倾盆大雨": {
        "category": "双根组合", "bias": "看跌",
        "meaning": "上涨趋势中，先阳线，后阴线开盘高于阳线收盘，但收盘低于阳线开盘。",
        "key_features": "前阳后阴，阴线完全吞没阳线实体",
        "teaching": "空头不仅吞没前一天涨幅，还创出新低，反转力度强。"
    },

    # ===== 三根组合 =====
    "早晨之星": {
        "category": "三根组合", "bias": "看涨",
        "meaning": "下跌末端：阴线 + 十字星 + 阳线，空头→犹豫→多头，经典底部反转。",
        "key_features": "第一根阴线，第二根小实体，第三根阳线收盘 > 第一根中点",
        "teaching": "三根K线讲述完整的'空头衰竭→多空平衡→多头反攻'故事。"
    },
    "黄昏之星": {
        "category": "三根组合", "bias": "看跌",
        "meaning": "上涨末端：阳线 + 十字星 + 阴线，多头→犹豫→空头，经典顶部反转。",
        "key_features": "第一根阳线，第二根小实体，第三根阴线收盘 < 第一根中点",
        "teaching": "三根K线讲述完整的'多头衰竭→多空平衡→空头反攻'故事。"
    },
    "红三兵": {
        "category": "三根组合", "bias": "看涨",
        "meaning": "连续三根阳线，每根收盘价都比前一根高，持续看涨。",
        "key_features": "三根阳线，收盘逐日抬高，每根实体≥1%",
        "teaching": "多头力量持续增强，每日都有新买盘推高股价。"
    },
    "黑三鸦": {
        "category": "三根组合", "bias": "看跌",
        "meaning": "连续三根阴线，每根收盘价都比前一根低，持续看跌。",
        "key_features": "三根阴线，收盘逐日降低，每根实体≥1%",
        "teaching": "空头力量持续增强，每日都有新卖盘压低股价。"
    },
    "上升三法": {
        "category": "三根组合", "bias": "看涨",
        "meaning": "上涨趋势中：大阳线 + 三根小阴线回踩 + 大阳线创新高。",
        "key_features": "大阳 + 3小阴(整体在大阳实体内) + 大阳创新高",
        "teaching": "主力洗盘后继续拉升，上涨趋势非常健康。"
    },
    "下降三法": {
        "category": "三根组合", "bias": "看跌",
        "meaning": "下跌趋势中：大阴线 + 三根小阳线反弹 + 大阴线创新低。",
        "key_features": "大阴 + 3小阳(整体在大阴实体内) + 大阴创新低",
        "teaching": "主力诱多后继续出货，下跌趋势延续。"
    },
    "两阳夹一阴": {
        "category": "三根组合", "bias": "看涨",
        "meaning": "上涨趋势中：阳线 + 小阴线 + 阳线，中间阴线被两边阳线夹住。",
        "key_features": "阳→阴→阳，中间阴线实体小于两边阳线",
        "teaching": "多头强势整理，中间小阴线只是短暂回调。"
    },
    "两阴夹一阳": {
        "category": "三根组合", "bias": "看跌",
        "meaning": "下跌趋势中：阴线 + 小阳线 + 阴线，中间阳线被两边阴线夹住。",
        "key_features": "阴→阳→阴，中间阳线实体小于两边阴线",
        "teaching": "空头强势整理，中间小阳线只是短暂反弹。"
    },

    # ===== 特殊形态 =====
    "锤子线": {
        "category": "特殊形态", "bias": "看涨",
        "meaning": "下跌末端，长下影线（≥实体2倍），小实体，看涨。",
        "key_features": "下影线 ≥ 实体2倍，上影线很短，实体在顶部",
        "teaching": "股价跌下去后被快速拉起来，下方有很强承接力。"
    },
    "射击之星": {
        "category": "特殊形态", "bias": "看跌",
        "meaning": "上涨末端，长上影线（≥实体2倍），小实体，看跌。",
        "key_features": "上影线 ≥ 实体2倍，下影线很短，实体在底部",
        "teaching": "股价涨上去后被快速打压下来，上方有很强卖压。"
    },
    "倒锤子线": {
        "category": "特殊形态", "bias": "看涨",
        "meaning": "下跌末端，长上影线（≥实体2倍），小实体，看涨。",
        "key_features": "上影线 ≥ 实体2倍，下影线很短，出现在下跌后",
        "teaching": "多头开始试探性进攻，需次日阳线确认。"
    },
    "跳空缺口": {
        "category": "特殊形态", "bias": "看涨/看跌",
        "meaning": "今日开盘价高于昨日最高（向上跳空）或低于昨日最低（向下跳空）。",
        "key_features": "今开 > 昨高（向上缺口）或 今开 < 昨低（向下缺口）",
        "teaching": "向上跳空代表多头强势，向下跳空代表空头强势。"
    },
}

# 按类别分组，出题时干扰项只从同类里选
PATTERN_BY_CATEGORY = {}
for name, meta in PATTERN_DATA.items():
    PATTERN_BY_CATEGORY.setdefault(meta["category"], []).append(name)


# ============================================================
# 辅助函数：K线几何特征
# ============================================================
def _body(o, c):
    """实体长度（绝对值）"""
    return abs(c - o)

def _upper_shadow(o, h, c):
    """上影线长度"""
    return h - max(o, c)

def _lower_shadow(o, l, c):
    """下影线长度"""
    return min(o, c) - l

def _is_yang(o, c):
    """是否阳线"""
    return c > o

def _is_yin(o, c):
    """是否阴线"""
    return c < o

def _range(h, l):
    """振幅"""
    return h - l if h > l else 0.0001


# ============================================================
# 单根形态检测
# ============================================================
def detect_大阳线(df, i):
    o, h, l, c = df.iloc[i][["open", "high", "low", "close"]]
    if not _is_yang(o, c):
        return False
    body = _body(o, c)
    rng = _range(h, l)
    pct = (c - o) / o * 100 if o > 0 else 0
    return body / rng >= 0.70 and pct >= 2.0

def detect_大阴线(df, i):
    o, h, l, c = df.iloc[i][["open", "high", "low", "close"]]
    if not _is_yin(o, c):
        return False
    body = _body(o, c)
    rng = _range(h, l)
    pct = (o - c) / o * 100 if o > 0 else 0
    return body / rng >= 0.70 and pct >= 2.0

def detect_十字星(df, i):
    o, h, l, c = df.iloc[i][["open", "high", "low", "close"]]
    body = _body(o, c)
    rng = _range(h, l)
    return body / rng <= 0.10 and _upper_shadow(o, h, c) > body and _lower_shadow(o, l, c) > body

def detect_T字线(df, i):
    o, h, l, c = df.iloc[i][["open", "high", "low", "close"]]
    body = _body(o, c)
    upper = _upper_shadow(o, h, c)
    lower = _lower_shadow(o, l, c)
    rng = _range(h, l)
    return upper <= rng * 0.05 and lower >= body * 2 and body / rng <= 0.20

def detect_一字涨停(df, i):
    if i == 0:
        return False
    o, h, l, c = df.iloc[i][["open", "high", "low", "close"]]
    prev_c = df.iloc[i - 1]["close"]
    return abs(h - l) / max(o, 0.01) < 0.001 and (c - prev_c) / prev_c >= 0.095

def detect_一字跌停(df, i):
    if i == 0:
        return False
    o, h, l, c = df.iloc[i][["open", "high", "low", "close"]]
    prev_c = df.iloc[i - 1]["close"]
    return abs(h - l) / max(o, 0.01) < 0.001 and (c - prev_c) / prev_c <= -0.095


# ============================================================
# 双根形态检测
# ============================================================
def detect_看涨吞没(df, i):
    if i < 1:
        return False
    p = df.iloc[i - 1]; t = df.iloc[i]
    return (_is_yin(p["open"], p["close"]) and _is_yang(t["open"], t["close"])
            and t["open"] <= p["close"] and t["close"] >= p["open"]
            and _body(t["open"], t["close"]) > _body(p["open"], p["close"]))

def detect_看跌吞没(df, i):
    if i < 1:
        return False
    p = df.iloc[i - 1]; t = df.iloc[i]
    return (_is_yang(p["open"], p["close"]) and _is_yin(t["open"], t["close"])
            and t["open"] >= p["close"] and t["close"] <= p["open"]
            and _body(t["open"], t["close"]) > _body(p["open"], p["close"]))

def detect_曙光初现(df, i):
    if i < 1:
        return False
    p = df.iloc[i - 1]; t = df.iloc[i]
    if not (_is_yin(p["open"], p["close"]) and _is_yang(t["open"], t["close"])):
        return False
    mid = (p["open"] + p["close"]) / 2
    return t["close"] > mid and t["close"] < p["open"]

def detect_乌云盖顶(df, i):
    if i < 1:
        return False
    p = df.iloc[i - 1]; t = df.iloc[i]
    if not (_is_yang(p["open"], p["close"]) and _is_yin(t["open"], t["close"])):
        return False
    mid = (p["open"] + p["close"]) / 2
    return t["close"] < mid and t["close"] > p["open"]

def detect_身怀六甲(df, i):
    if i < 1:
        return False
    p = df.iloc[i - 1]; t = df.iloc[i]
    p_big = _body(p["open"], p["close"])
    t_small = _body(t["open"], t["close"])
    return (t_small < p_big * 0.5
            and max(t["open"], t["close"]) <= max(p["open"], p["close"])
            and min(t["open"], t["close"]) >= min(p["open"], p["close"]))

def detect_平底(df, i):
    if i < 1:
        return False
    p = df.iloc[i - 1]; t = df.iloc[i]
    return abs(t["low"] - p["low"]) / max(p["low"], 0.01) < 0.003

def detect_平顶(df, i):
    if i < 1:
        return False
    p = df.iloc[i - 1]; t = df.iloc[i]
    return abs(t["high"] - p["high"]) / max(p["high"], 0.01) < 0.003

def detect_穿头破脚(df, i):
    if i < 1:
        return False
    p = df.iloc[i - 1]; t = df.iloc[i]
    return t["high"] > p["high"] and t["low"] < p["low"] and _body(t["open"], t["close"]) > _body(p["open"], p["close"])

def detect_好友反攻(df, i):
    if i < 1:
        return False
    p = df.iloc[i - 1]; t = df.iloc[i]
    if not (_is_yin(p["open"], p["close"]) and _is_yang(t["open"], t["close"])):
        return False
    return t["open"] < p["close"] and t["close"] >= p["close"] * 0.995

def detect_淡友反攻(df, i):
    if i < 1:
        return False
    p = df.iloc[i - 1]; t = df.iloc[i]
    if not (_is_yang(p["open"], p["close"]) and _is_yin(t["open"], t["close"])):
        return False
    return t["open"] > p["close"] and t["close"] <= p["close"] * 1.005

def detect_旭日东升(df, i):
    if i < 1:
        return False
    p = df.iloc[i - 1]; t = df.iloc[i]
    if not (_is_yin(p["open"], p["close"]) and _is_yang(t["open"], t["close"])):
        return False
    return t["open"] < p["close"] and t["close"] > p["open"]

def detect_倾盆大雨(df, i):
    if i < 1:
        return False
    p = df.iloc[i - 1]; t = df.iloc[i]
    if not (_is_yang(p["open"], p["close"]) and _is_yin(t["open"], t["close"])):
        return False
    return t["open"] > p["close"] and t["close"] < p["open"]


# ============================================================
# 三根形态检测
# ============================================================
def detect_早晨之星(df, i):
    if i < 2:
        return False
    a, b, c = df.iloc[i - 2], df.iloc[i - 1], df.iloc[i]
    if not (_is_yin(a["open"], a["close"]) and _is_yang(c["open"], c["close"])):
        return False
    b_body = _body(b["open"], b["close"])
    a_body = _body(a["open"], a["close"])
    if b_body > a_body * 0.5:
        return False
    mid_a = (a["open"] + a["close"]) / 2
    return c["close"] > mid_a

def detect_黄昏之星(df, i):
    if i < 2:
        return False
    a, b, c = df.iloc[i - 2], df.iloc[i - 1], df.iloc[i]
    if not (_is_yang(a["open"], a["close"]) and _is_yin(c["open"], c["close"])):
        return False
    b_body = _body(b["open"], b["close"])
    a_body = _body(a["open"], a["close"])
    if b_body > a_body * 0.5:
        return False
    mid_a = (a["open"] + a["close"]) / 2
    return c["close"] < mid_a

def detect_红三兵(df, i):
    if i < 2:
        return False
    a, b, c = df.iloc[i - 2], df.iloc[i - 1], df.iloc[i]
    if not all(_is_yang(x["open"], x["close"]) for x in [a, b, c]):
        return False
    if not (b["close"] > a["close"] and c["close"] > b["close"]):
        return False
    for x in [a, b, c]:
        if _body(x["open"], x["close"]) / max(x["open"], 0.01) < 0.01:
            return False
    return True

def detect_黑三鸦(df, i):
    if i < 2:
        return False
    a, b, c = df.iloc[i - 2], df.iloc[i - 1], df.iloc[i]
    if not all(_is_yin(x["open"], x["close"]) for x in [a, b, c]):
        return False
    if not (b["close"] < a["close"] and c["close"] < b["close"]):
        return False
    for x in [a, b, c]:
        if _body(x["open"], x["close"]) / max(x["open"], 0.01) < 0.01:
            return False
    return True

def detect_上升三法(df, i):
    if i < 4:
        return False
    a = df.iloc[i - 4]  # 大阳
    mids = [df.iloc[i - 3], df.iloc[i - 2], df.iloc[i - 1]]
    e = df.iloc[i]      # 大阳
    if not (_is_yang(a["open"], a["close"]) and _is_yang(e["open"], e["close"])):
        return False
    if _body(a["open"], a["close"]) / max(a["open"], 0.01) < 0.02:
        return False
    a_high = max(a["open"], a["close"])
    a_low = min(a["open"], a["close"])
    for m in mids:
        if not (_is_yin(m["open"], m["close"])):
            return False
        if max(m["open"], m["close"]) > a_high or min(m["open"], m["close"]) < a_low:
            return False
    return e["close"] > a["close"]

def detect_下降三法(df, i):
    if i < 4:
        return False
    a = df.iloc[i - 4]
    mids = [df.iloc[i - 3], df.iloc[i - 2], df.iloc[i - 1]]
    e = df.iloc[i]
    if not (_is_yin(a["open"], a["close"]) and _is_yin(e["open"], e["close"])):
        return False
    if _body(a["open"], a["close"]) / max(a["open"], 0.01) < 0.02:
        return False
    a_high = max(a["open"], a["close"])
    a_low = min(a["open"], a["close"])
    for m in mids:
        if not (_is_yang(m["open"], m["close"])):
            return False
        if max(m["open"], m["close"]) > a_high or min(m["open"], m["close"]) < a_low:
            return False
    return e["close"] < a["close"]

def detect_两阳夹一阴(df, i):
    if i < 2:
        return False
    a, b, c = df.iloc[i - 2], df.iloc[i - 1], df.iloc[i]
    if not (_is_yang(a["open"], a["close"]) and _is_yin(b["open"], b["close"]) and _is_yang(c["open"], c["close"])):
        return False
    a_body = _body(a["open"], a["close"])
    b_body = _body(b["open"], b["close"])
    c_body = _body(c["open"], c["close"])
    return b_body < a_body and b_body < c_body

def detect_两阴夹一阳(df, i):
    if i < 2:
        return False
    a, b, c = df.iloc[i - 2], df.iloc[i - 1], df.iloc[i]
    if not (_is_yin(a["open"], a["close"]) and _is_yang(b["open"], b["close"]) and _is_yin(c["open"], c["close"])):
        return False
    a_body = _body(a["open"], a["close"])
    b_body = _body(b["open"], b["close"])
    c_body = _body(c["open"], c["close"])
    return b_body < a_body and b_body < c_body


# ============================================================
# 特殊形态检测
# ============================================================
def detect_锤子线(df, i):
    o, h, l, c = df.iloc[i][["open", "high", "low", "close"]]
    body = _body(o, c)
    upper = _upper_shadow(o, h, c)
    lower = _lower_shadow(o, l, c)
    if body <= 0:
        return False
    return lower >= body * 2 and upper <= body * 0.5 and (h - l) / max(c, 0.01) > 0.01

def detect_射击之星(df, i):
    o, h, l, c = df.iloc[i][["open", "high", "low", "close"]]
    body = _body(o, c)
    upper = _upper_shadow(o, h, c)
    lower = _lower_shadow(o, l, c)
    if body <= 0:
        return False
    return upper >= body * 2 and lower <= body * 0.5 and (h - l) / max(c, 0.01) > 0.01

def detect_倒锤子线(df, i):
    # 倒锤子线与射击之星形态相同，区别在于出现位置：需要先判断是下跌末端
    if i < 5:
        return False
    o, h, l, c = df.iloc[i][["open", "high", "low", "close"]]
    body = _body(o, c)
    upper = _upper_shadow(o, h, c)
    lower = _lower_shadow(o, l, c)
    if body <= 0:
        return False
    if not (upper >= body * 2 and lower <= body * 0.5):
        return False
    # 前面必须是下跌趋势（最近5根累计跌幅 > 3%）
    prev5 = df.iloc[i - 5:i]["close"]
    return (prev5.iloc[-1] - prev5.iloc[0]) / prev5.iloc[0] < -0.03

def detect_跳空缺口(df, i):
    if i < 1:
        return False
    p = df.iloc[i - 1]; t = df.iloc[i]
    gap_up = t["low"] > p["high"]
    gap_down = t["high"] < p["low"]
    return gap_up or gap_down


# ============================================================
# 形态检测器注册表
# ============================================================
PATTERN_DETECTORS = {
    # 单根
    "大阳线": detect_大阳线, "大阴线": detect_大阴线,
    "十字星": detect_十字星, "T字线": detect_T字线,
    "一字涨停": detect_一字涨停, "一字跌停": detect_一字跌停,
    # 双根
    "看涨吞没": detect_看涨吞没, "看跌吞没": detect_看跌吞没,
    "曙光初现": detect_曙光初现, "乌云盖顶": detect_乌云盖顶,
    "身怀六甲": detect_身怀六甲, "平底": detect_平底, "平顶": detect_平顶,
    "穿头破脚": detect_穿头破脚, "好友反攻": detect_好友反攻,
    "淡友反攻": detect_淡友反攻, "旭日东升": detect_旭日东升,
    "倾盆大雨": detect_倾盆大雨,
    # 三根
    "早晨之星": detect_早晨之星, "黄昏之星": detect_黄昏之星,
    "红三兵": detect_红三兵, "黑三鸦": detect_黑三鸦,
    "上升三法": detect_上升三法, "下降三法": detect_下降三法,
    "两阳夹一阴": detect_两阳夹一阴, "两阴夹一阳": detect_两阴夹一阳,
    # 特殊
    "锤子线": detect_锤子线, "射击之星": detect_射击之星,
    "倒锤子线": detect_倒锤子线, "跳空缺口": detect_跳空缺口,
}


# ============================================================
# 上下文判断：位置 + 趋势
# ============================================================
def get_position_context(df, i, lookback=20):
    """
    判断当前K线在最近lookback根中的相对位置。
    返回："低位区" / "中位区" / "高位区"
    """
    start = max(0, i - lookback)
    window = df.iloc[start:i + 1]
    if len(window) < 3:
        return "中位区"
    high = window["high"].max()
    low = window["low"].min()
    rng = high - low
    if rng <= 0:
        return "中位区"
    pos = (window["close"].iloc[-1] - low) / rng * 100
    if pos > 70:
        return "高位区"
    elif pos < 30:
        return "低位区"
    return "中位区"

def get_trend_context(df, i, lookback=10):
    """
    判断当前K线之前的趋势方向。
    返回："上涨趋势" / "下跌趋势" / "震荡"
    """
    start = max(0, i - lookback)
    window = df.iloc[start:i]
    if len(window) < 3:
        return "震荡"
    change = (window["close"].iloc[-1] - window["close"].iloc[0]) / window["close"].iloc[0]
    if change > 0.05:
        return "上涨趋势"
    elif change < -0.05:
        return "下跌趋势"
    return "震荡"


# ============================================================
# 检测单根K线位置上的所有形态
# ============================================================
def detect_patterns_at(df, i):
    """
    检测第i根K线上出现的所有形态。
    返回：列表，如 [{"name": "锤子线", "bias": "看涨", ...}, ...]
    """
    hits = []
    for name, fn in PATTERN_DETECTORS.items():
        try:
            if fn(df, i):
                meta = PATTERN_DATA[name]
                hits.append({
                    "name": name,
                    "category": meta["category"],
                    "bias": meta["bias"],
                    "meaning": meta["meaning"],
                    "key_features": meta["key_features"],
                    "teaching": meta["teaching"],
                    "position": get_position_context(df, i),
                    "trend": get_trend_context(df, i),
                })
        except Exception:
            continue
    return hits


# ============================================================
# 遍历历史，找出所有形态出现的位置
# ============================================================
@st.cache_data(ttl=1800, show_spinner=False)
def find_all_pattern_occurrences(symbol: str):
    """
    对某只股票的历史数据，找出所有形态出现的位置。
    
    返回：
        list of dict: [{
            "pattern": 形态名,
            "idx": 在df中的位置,
            "category": 类别,
            "bias": 看涨/看跌/中性,
            "position": 高位/中位/低位,
            "trend": 上涨/下跌/震荡,
        }, ...]
    """
    df = fetch_daily(symbol, days=250)
    if df is None or len(df) < 60:
        return []

    occurrences = []
    # 从第60根开始扫（保证有足够历史计算趋势）
    for i in range(60, len(df)):
        hits = detect_patterns_at(df, i)
        for h in hits:
            occurrences.append({
                "pattern": h["name"],
                "idx": i,
                "category": h["category"],
                "bias": h["bias"],
                "position": h["position"],
                "trend": h["trend"],
            })
    return occurrences


# ============================================================
# 生成一道形态识别题（真实出现过的形态）
# ============================================================
def generate_pattern_question():
    """
    从股票池中随机选一只股票，遍历其历史，
    找出所有真实出现过的形态，随机抽一个出题。
    
    返回：
        dict: {
            "symbol": 股票代码,
            "df": 截止到形态位置的K线数据,
            "occurrence": 选中的形态信息,
            "correct": 正确答案,
            "options": 4个选项（含正确答案）,
            "meta": 该形态的元数据,
        }
    """
    pool = STOCK_POOL.copy()
    random.shuffle(pool)

    for code, name in pool[:8]:  # 最多试8只，避免太慢
        occs = find_all_pattern_occurrences(code)
        if not occs:
            continue

        # 优先挑选"有意义"的形态：避免全是"跳空缺口"这种太常见的
        # 过滤掉位置和趋势组合过弱的
        good_occs = [o for o in occs if o["pattern"] != "跳空缺口"] or occs
        chosen = random.choice(good_occs)

        # 获取完整K线并截断到形态位置
        df = fetch_daily(code, days=250)
        if df is None or chosen["idx"] >= len(df):
            continue
        df_show = df.iloc[:chosen["idx"] + 1].tail(60).reset_index(drop=True)

        correct = chosen["pattern"]
        meta = PATTERN_DATA[correct]

        # 干扰项：只从同类别形态中选
        same_cat = [n for n in PATTERN_BY_CATEGORY.get(meta["category"], [])
                    if n != correct]
        if len(same_cat) < 3:
            # 同类别不足3个，从相邻类别补
            all_other = [n for n in PATTERN_DATA.keys() if n != correct]
            same_cat = list(set(same_cat + all_other))
        distractors = random.sample(same_cat, min(3, len(same_cat)))

        options = [correct] + distractors
        random.shuffle(options)

        return {
            "symbol": code, "name": name,
            "df": df_show,
            "occurrence": chosen,
            "correct": correct,
            "options": options,
            "meta": meta,
        }
    return None


# ============================================================
# 第2段结束
# ============================================================# ============================================================
# 第3段：形态识别训练页面
# ============================================================
# 【本段做什么】
#   1. 真实出题：从历史K线中检测真实出现过的形态
#   2. 同类干扰：干扰项只从同类别形态中选
#   3. 详细对比：答错时对比"你选的"和"正确答案"的关键区别
#   4. 自动记错：错题写入SQLite数据库
#   5. 上下文提示：显示形态出现的位置（高位/低位）和趋势（上涨/下跌）
#
# 【依赖第1段和第2段的函数】
#   - fetch_daily, plot_kline, add_wrong
#   - generate_pattern_question, PATTERN_DATA, PATTERN_BY_CATEGORY
# ============================================================

def render_pattern_training():
    """
    渲染"形态识别"训练页面。
    这是整个训练器最核心的模块。
    """

    # ---------- 页面标题和说明 ----------
    st.markdown("## 📊 形态识别训练")
    st.markdown("""
    **训练目标**：看到K线图，第一反应就能认出形态名称。

    **玩法**：系统从历史K线中检测真实出现过的形态，展示截止到该位置的K线图，
    你从4个选项中选出正确的形态。答错会显示详细对比分析，并自动记录错题。

    **出题规则**：
    - ✅ 只出真实出现过的形态（系统自动检测）
    - ✅ 干扰项只从同类别形态中选取（不会出现明显不合理的选项）
    - ✅ 答错时对比"你选的"和"正确答案"的关键区别
    """)

    # ---------- 初始化 session_state ----------
    if "pat_question" not in st.session_state:
        st.session_state.pat_question = None
        st.session_state.pat_answered = False
        st.session_state.pat_user_choice = None
        st.session_state.pat_score = {"correct": 0, "total": 0}

    # ---------- 出题按钮 ----------
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🎲 随机出题", type="primary", use_container_width=True, key="pat_gen"):
            with st.spinner("正在从历史K线中检测真实形态..."):
                q = generate_pattern_question()
                if q:
                    st.session_state.pat_question = q
                    st.session_state.pat_answered = False
                    st.session_state.pat_user_choice = None
                else:
                    st.error("无法获取数据，请稍后重试。可能API暂时不可用。")
    with col2:
        if st.session_state.pat_score["total"] > 0:
            rate = st.session_state.pat_score["correct"] / st.session_state.pat_score["total"] * 100
            st.metric("正确率", f"{rate:.1f}%")
    with col3:
        st.metric("答题数", st.session_state.pat_score["total"])

    # ---------- 如果没有题目，自动生成第一题 ----------
    if st.session_state.pat_question is None:
        with st.spinner("首次加载，正在准备题目..."):
            q = generate_pattern_question()
            if q:
                st.session_state.pat_question = q
            else:
                st.warning("无法获取数据，请检查API Key和网络连接。")
                return

    q = st.session_state.pat_question
    if q is None:
        return

    # ---------- 显示K线图 ----------
    df = q["df"]
    occ = q["occurrence"]

    # 标题：显示股票名称和位置信息
    position_emoji = {"高位区": "🔴", "低位区": "🟢", "中位区": "⚪"}.get(occ["position"], "⚪")
    trend_emoji = {"上涨趋势": "📈", "下跌趋势": "📉", "震荡": "➡️"}.get(occ["trend"], "➡️")

    st.markdown(f"""
    ### {q['name']}（{q['symbol']}）
    **当前状态**：{position_emoji} {occ['position']} | {trend_emoji} {occ['trend']}
    """)

    # 绘制K线图（只显示形态位置之前的K线）
    fig = plot_kline(df, title=f"{q['name']} 日K线（截止到形态出现位置）", 
                     show_ma=True, show_volume=True, height=500)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("👆 图中最后一根K线就是需要判断的形态")

    # ---------- 显示选项 ----------
    if not st.session_state.pat_answered:
        st.markdown("### 请选择最符合的形态：")
        cols = st.columns(4)
        for i, opt in enumerate(q["options"]):
            with cols[i]:
                if st.button(opt, key=f"pat_opt_{i}", use_container_width=True):
                    st.session_state.pat_user_choice = opt
                    st.session_state.pat_answered = True
                    st.session_state.pat_score["total"] += 1
                    if opt == q["correct"]:
                        st.session_state.pat_score["correct"] += 1
                    st.rerun()

    # ---------- 已作答：显示结果和详细对比 ----------
    if st.session_state.pat_answered:
        user_choice = st.session_state.pat_user_choice
        correct = q["correct"]
        meta = q["meta"]

        st.markdown("---")

        if user_choice == correct:
            # ✅ 回答正确
            st.markdown(f"""
            <div class="success-box">
            <h3>✅ 回答正确！</h3>
            <p><b>{correct}</b> — {meta['meaning']}</p>
            </div>
            """, unsafe_allow_html=True)

            # 教学提示
            st.info(f"📚 **实战要点**：{meta['teaching']}")

        else:
            # ❌ 回答错误
            st.markdown(f"""
            <div class="error-box">
            <h3>❌ 回答错误</h3>
            <p>你选了 <b>{user_choice}</b>，正确答案是 <b>{correct}</b>。</p>
            </div>
            """, unsafe_allow_html=True)

            # ---------- 详细对比分析 ----------
            st.markdown("### 📊 详细对比分析")

            # 正确答案的特征
            st.markdown(f"#### ✅ 正确答案：{correct}")
            st.markdown(f"- **含义**：{meta['meaning']}")
            st.markdown(f"- **关键特征**：{meta['key_features']}")
            st.markdown(f"- **实战要点**：{meta['teaching']}")
            st.markdown(f"- **类别**：{meta['category']}")

            # 你选的答案的特征
            user_meta = PATTERN_DATA.get(user_choice, {})
            if user_meta:
                st.markdown(f"#### ❌ 你选的：{user_choice}")
                st.markdown(f"- **含义**：{user_meta['meaning']}")
                st.markdown(f"- **关键特征**：{user_meta['key_features']}")
                st.markdown(f"- **类别**：{user_meta['category']}")

            # 关键区别对比表
            st.markdown("#### 🔍 关键区别")
            st.markdown(f"""
            | 对比项 | {correct}（正确） | {user_choice}（你选的） |
            |--------|------------------|------------------------|
            | 类别 | {meta['category']} | {user_meta.get('category', '未知')} |
            | 关键特征 | {meta['key_features']} | {user_meta.get('key_features', '未知')} |
            | 看涨/看跌 | {meta['bias']} | {user_meta.get('bias', '未知')} |
            """)

            # 如果同类别，提示更细致的区别
            if user_meta.get("category") == meta["category"]:
                st.warning(f"⚠️ 你选的 **{user_choice}** 和正确答案 **{correct}** 属于同一类别（{meta['category']}），"
                          f"需要更仔细地观察关键特征的细微差别。")

            # 记录错题
            analysis = (f"正确答案：{correct}（{meta['key_features']}）\n"
                       f"你选的：{user_choice}（{user_meta.get('key_features', '未知')}）")
            add_wrong(
                module="形态识别",
                question=f"{q['name']}（{q['symbol']}）— 判断形态",
                user_answer=user_choice,
                correct_answer=correct,
                analysis=analysis
            )
            st.caption("📝 本题已自动记录到错题本")

        # ---------- 显示形态的完整教学 ----------
        with st.expander("📖 查看该形态的详细教学", expanded=False):
            st.markdown(f"### {correct}")
            st.markdown(f"- **类别**：{meta['category']}")
            st.markdown(f"- **方向**：{meta['bias']}")
            st.markdown(f"- **含义**：{meta['meaning']}")
            st.markdown(f"- **关键特征**：{meta['key_features']}")
            st.markdown(f"- **实战教学**：{meta['teaching']}")

            # 同类别其他形态
            st.markdown("---")
            st.markdown("#### 同类别其他形态（容易混淆）")
            same_cat = [n for n in PATTERN_BY_CATEGORY.get(meta["category"], []) if n != correct]
            for n in same_cat[:5]:
                m = PATTERN_DATA[n]
                st.markdown(f"- **{n}**：{m['meaning']} | 特征：{m['key_features']}")

        # ---------- 下一题按钮 ----------
        st.markdown("---")
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("➡️ 下一题", type="primary", use_container_width=True, key="pat_next"):
                with st.spinner("正在检测新的形态..."):
                    new_q = generate_pattern_question()
                    if new_q:
                        st.session_state.pat_question = new_q
                        st.session_state.pat_answered = False
                        st.session_state.pat_user_choice = None
                        st.rerun()
                    else:
                        st.error("无法获取新题目，请重试。")


# ============================================================
# 第3段结束
# ============================================================# ============================================================
# 第4段：分时实战模块
# ============================================================
# 【本段做什么】
#   1. 从日线数据模拟多天5分钟K线（每天48根，9:30-15:00）
#   2. 随机截取一段（100根）展示，让用户判断"下一根"是涨还是跌
#   3. 答完显示完整复盘：量价、均线、MACD、RSI、KDJ、布林带
#   4. 答错自动记录到错题本
#
# 【为什么用模拟数据】
#   真实5分钟数据需要付费接口。用日线OHLC反推5分钟路径，
#   既保证每天首尾价格与真实日线吻合，又能在训练场景下使用。
#   重点是练"盘感判断"，不是练"数据获取"。
# ============================================================

def generate_intraday_data(daily_df, num_days=7, bars_per_day=48):
    """
    从日线数据生成多天5分钟K线。

    参数：
        daily_df: 日线DataFrame（含 open/high/low/close/volume）
        num_days: 拼接多少天
        bars_per_day: 每天多少根K线（默认48根 = 4小时 / 5分钟）

    返回：
        DataFrame(time, open, high, low, close, volume)
    """
    if daily_df is None or len(daily_df) < num_days:
        return None

    # 随机选一段连续的日线
    max_start = len(daily_df) - num_days
    start_idx = random.randint(0, max_start)
    selected = daily_df.iloc[start_idx:start_idx + num_days].copy().reset_index(drop=True)

    all_times, all_opens, all_highs, all_lows, all_closes, all_volumes = [], [], [], [], [], []
    base_time = datetime.strptime("09:30", "%H:%M").time()

    for day_idx, day in selected.iterrows():
        op = day["open"]; hp = day["high"]; lp = day["low"]
        cp = day["close"]; vol = day["volume"]

        # 用随机游走生成当天价格路径
        np.random.seed(random.randint(0, 100000) + day_idx * 1000 + int(op * 100))
        steps = np.random.normal(0, 0.15, bars_per_day)
        prices = np.cumsum(steps)
        prices = prices - prices[0] + op

        # 把路径缩放到日线的高低范围
        min_p, max_p = np.min(prices), np.max(prices)
        rng = max_p - min_p if max_p - min_p > 0 else 0.01
        scale = (hp - lp) / rng
        prices_scaled = lp + (prices - min_p) * scale

        # 强制终点等于日线收盘价
        end_diff = cp - prices_scaled[-1]
        if bars_per_day > 1:
            prices_scaled = prices_scaled + np.linspace(0, end_diff, bars_per_day)

        # 构造每根5分钟的OHLC
        opens = [prices_scaled[0]] + [prices_scaled[i - 1] for i in range(1, bars_per_day)]
        closes = prices_scaled.tolist()

        highs, lows = [], []
        for i in range(bars_per_day):
            o, c = opens[i], closes[i]
            if o < c:
                low = o - (c - o) * random.uniform(0.2, 0.6)
                high = c + (c - o) * random.uniform(0.2, 0.6)
            else:
                high = o + (o - c) * random.uniform(0.2, 0.6)
                low = c - (o - c) * random.uniform(0.2, 0.6)
            lows.append(max(low, lp * 0.98))
            highs.append(min(high, hp * 1.02))

        # 模拟成交量（涨跌幅越大，量越大）
        returns = np.diff(closes, prepend=opens[0])
        vol_base = vol / bars_per_day
        vols = []
        for r in returns:
            v = vol_base * (1 + abs(r) * 8) * random.uniform(0.7, 1.3)
            vols.append(max(v, 30000))
        # 归一化，使总量接近日线
        vs = sum(vols)
        if vs > 0:
            vols = [v * (vol / vs) for v in vols]

        # 时间标签
        day_label = f"D{day_idx + 1}"
        times = [
            f"{day_label} {(datetime.combine(datetime.today(), base_time) + timedelta(minutes=5 * i)).time().strftime('%H:%M')}"
            for i in range(bars_per_day)
        ]

        all_times.extend(times)
        all_opens.extend(opens)
        all_highs.extend(highs)
        all_lows.extend(lows)
        all_closes.extend(closes)
        all_volumes.extend(vols)

    return pd.DataFrame({
        "time": all_times, "open": all_opens, "high": all_highs,
        "low": all_lows, "close": all_closes, "volume": all_volumes
    })


def plot_intraday(df, title="", height=460):
    """
    绘制分时图（含K线 + 均价线 + MA5）。
    与 plot_kline 的区别：x轴用time字符串，加均价线。
    """
    x = df["time"].tolist()

    # 计算均价线（VWAP累计）
    avg_p = (df["high"] + df["low"] + df["close"]) / 3
    vwap = (avg_p * df["volume"]).cumsum() / df["volume"].cumsum()

    # x轴刻度：每30根标一个
    step = max(1, len(x) // 20)
    tick_vals = x[::step]

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.72, 0.28]
    )

    # K线
    fig.add_trace(go.Candlestick(
        x=x, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color="#ff4444",
        decreasing_line_color="#00cc66",
        increasing_fillcolor="#ff4444",
        decreasing_fillcolor="#00cc66",
        name="K线", showlegend=False
    ), row=1, col=1)

    # 均价线
    fig.add_trace(go.Scatter(
        x=x, y=vwap, mode="lines", name="均价线",
        line=dict(color="#ffcc00", width=1.5)
    ), row=1, col=1)

    # MA5
    if len(df) >= 5:
        fig.add_trace(go.Scatter(
            x=x, y=df["close"].rolling(5).mean(),
            mode="lines", name="MA5",
            line=dict(color="#00aaff", width=1)
        ), row=1, col=1)

    # 成交量
    colors = ["#ff4444" if c >= o else "#00cc66"
              for o, c in zip(df["open"], df["close"])]
    fig.add_trace(go.Bar(
        x=x, y=df["volume"],
        marker_color=colors, name="成交量", showlegend=False
    ), row=2, col=1)

    fig.update_layout(
        title=title, height=height, template="plotly_white",
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified"
    )
    fig.update_xaxes(tickvals=tick_vals, tickangle=45)
    fig.update_xaxes(showgrid=True, gridcolor="#2a2a2a")
    fig.update_yaxes(showgrid=True, gridcolor="#2a2a2a")
    return fig


def generate_intraday_question():
    """
    生成一道分时题：
      1. 随机选股票，取日线
      2. 生成多天5分钟K线
      3. 随机截取一段（100根）展示
      4. 记录"下一根"的实际涨跌，作为正确答案
      5. 计算截止到当前的所有指标，用于复盘

    返回：
        dict 或 None
    """
    pool = STOCK_POOL.copy()
    random.shuffle(pool)

    for code, name in pool[:6]:
        df_daily = fetch_daily(code, days=250)
        if df_daily is None or len(df_daily) < 20:
            continue

        df_intra = generate_intraday_data(df_daily,
                                          num_days=random.randint(5, 8))
        if df_intra is None or len(df_intra) < 150:
            continue

        total = len(df_intra)
        # 截取点：保证前后都有足够数据
        cut = random.randint(100, total - 5)
        display = df_intra.iloc[cut - 100:cut].copy().reset_index(drop=True)
        if len(display) < 100:
            continue

        next_row = df_intra.iloc[cut]
        last_close = display.iloc[-1]["close"]
        direction = "涨" if next_row["close"] > last_close else "跌"
        change_pct = (next_row["close"] - last_close) / last_close * 100

        # 计算指标（基于展示的100根）
        ind = calc_all_indicators(display, idx=len(display) - 1)

        return {
            "symbol": code, "name": name,
            "df": display,
            "next_row": next_row,
            "actual_direction": direction,
            "actual_pct": change_pct,
            "indicators": ind,
            "last_close": last_close,
        }
    return None


def render_intraday_training():
    """
    渲染"分时实战"训练页面。
    """
    st.markdown("## ⚡ 分时实战训练")
    st.markdown("""
    **训练目标**：面对一段真实的5分钟K线走势，判断下一根是涨还是跌。

    **玩法**：系统展示最近100根5分钟K线（约2天），你判断下一根是涨是跌。
    答完后系统会展示下一根实际走势，并逐项复盘量价、均线、MACD、RSI、KDJ、布林带。

    **复盘价值**：不是猜对猜错，而是学会"用什么指标判断方向"。
    """)

    if "intra_q" not in st.session_state:
        st.session_state.intra_q = None
        st.session_state.intra_answered = False
        st.session_state.intra_user = None
        st.session_state.intra_score = {"correct": 0, "total": 0}

    # 出题按钮
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🎲 随机出题", type="primary", use_container_width=True, key="intra_gen"):
            with st.spinner("正在生成分时数据..."):
                q = generate_intraday_question()
                if q:
                    st.session_state.intra_q = q
                    st.session_state.intra_answered = False
                    st.session_state.intra_user = None
                else:
                    st.error("数据加载失败，请检查API Key或网络。")
    with col2:
        if st.session_state.intra_score["total"] > 0:
            rate = st.session_state.intra_score["correct"] / st.session_state.intra_score["total"] * 100
            st.metric("正确率", f"{rate:.1f}%")
    with col3:
        st.metric("答题数", st.session_state.intra_score["total"])

    # 首次进入自动出题
    if st.session_state.intra_q is None:
        with st.spinner("首次加载..."):
            q = generate_intraday_question()
            if q:
                st.session_state.intra_q = q
            else:
                st.warning("无法加载数据。请检查API Key。")
                return

    q = st.session_state.intra_q
    if q is None:
        return

    ind = q["indicators"]

    # 标题
    st.markdown(f"### {q['name']}（{q['symbol']}）分时图")
    st.caption("图中每一根 = 5分钟。最后一根K线之后，下一根是涨还是跌？")

    # 画图
    fig = plot_intraday(q["df"], title=f"{q['name']} 分时")
    # 加一条竖线标记"当前时刻"
    fig.add_vline(x=q["df"]["time"].iloc[-1], line_width=2,
                  line_dash="dash", line_color="#ffcc00")
    st.plotly_chart(fig, use_container_width=True)

    # 实时指标展示
    st.markdown("### 📊 当前盘面指标")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("当前价", f"{ind['last_close']:.2f}",
              delta=f"{ind['pct_change']:+.2f}%")
    c2.metric("量比", f"{ind['vol_ratio']:.2f}", delta=ind['vol_status'])
    c3.metric("RSI", f"{ind['rsi']:.1f}", delta=ind['rsi_status'])
    c4.metric("MACD柱", f"{ind['macd_hist_value']:.3f}", delta=ind['macd_status'])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("均线排列", ind['ma_alignment'])
    c2.metric("价格位置", ind['price_position'])
    c3.metric("均价线", ind['avg_position'])
    c4.metric("量价", ind['vol_price_status'])

    # 答题按钮
    if not st.session_state.intra_answered:
        st.markdown("### 请判断：下一根5分钟K线是——")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📈 涨", use_container_width=True, key="intra_up"):
                st.session_state.intra_user = "涨"
                st.session_state.intra_answered = True
                st.session_state.intra_score["total"] += 1
                if q["actual_direction"] == "涨":
                    st.session_state.intra_score["correct"] += 1
                st.rerun()
        with c2:
            if st.button("📉 跌", use_container_width=True, key="intra_down"):
                st.session_state.intra_user = "跌"
                st.session_state.intra_answered = True
                st.session_state.intra_score["total"] += 1
                if q["actual_direction"] == "跌":
                    st.session_state.intra_score["correct"] += 1
                st.rerun()

    # 答题后：完整复盘
    if st.session_state.intra_answered:
        user = st.session_state.intra_user
        actual = q["actual_direction"]

        st.markdown("---")
        if user == actual:
            st.markdown(f"""
            <div class="success-box">
            <h3>✅ 判断正确！</h3>
            <p>实际走势：<b>{actual}</b>（{q['actual_pct']:+.2f}%）</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="error-box">
            <h3>❌ 判断错误</h3>
            <p>你选了 <b>{user}</b>，实际走势是 <b>{actual}</b>（{q['actual_pct']:+.2f}%）</p>
            </div>
            """, unsafe_allow_html=True)

            # 记录错题
            add_wrong(
                module="分时实战",
                question=f"{q['name']}（{q['symbol']}）分时判断第101根",
                user_answer=user,
                correct_answer=actual,
                analysis=f"实际涨跌：{q['actual_pct']:+.2f}%。"
                         f"当前MA排列：{ind['ma_alignment']}；"
                         f"MACD：{ind['macd_status']}；"
                         f"量价：{ind['vol_price_status']}；"
                         f"RSI：{ind['rsi']:.1f}（{ind['rsi_status']}）"
            )
            st.caption("📝 本题已记录到错题本")

        # ---------- 完整复盘 ----------
        st.markdown("### 📚 完整复盘：为什么下一根会是这个方向？")

        # 显示下一根的实际K线
        next_row = q["next_row"]
        st.markdown(f"""
        **下一根实际K线**：
        - 开：{next_row['open']:.2f}  高：{next_row['high']:.2f}
        - 低：{next_row['low']:.2f}  收：{next_row['close']:.2f}
        - 涨跌：**{q['actual_pct']:+.2f}%**
        """)

        # 逐指标复盘
        st.markdown("#### 🔍 逐指标复盘")

        with st.expander("1️⃣ 量价关系", expanded=True):
            st.markdown(f"- **量比**：{ind['vol_ratio']:.2f}（{ind['vol_status']}）")
            st.markdown(f"- **量价状态**：{ind['vol_price_status']}")
            if "放量上涨" in ind['vol_price_status']:
                st.info("👉 放量上涨说明买盘积极，下一根继续涨的概率较大。")
            elif "放量下跌" in ind['vol_price_status']:
                st.warning("👉 放量下跌说明抛压重，下一根容易继续跌。")
            elif "缩量上涨" in ind['vol_price_status']:
                st.warning("👉 缩量上涨说明追高意愿不足，可能冲高回落。")
            elif "缩量下跌" in ind['vol_price_status']:
                st.info("👉 缩量下跌说明抛压减轻，可能企稳反弹。")

        with st.expander("2️⃣ 均线系统", expanded=False):
            st.markdown(f"- **价格位置**：{ind['price_position']}")
            st.markdown(f"- **均线排列**：{ind['ma_alignment']}")
            st.markdown(f"- **均价线位置**：{ind['avg_position']}")
            if "多头排列" in ind['ma_alignment']:
                st.info("👉 多头排列，短期趋势向上。")
            elif "空头排列" in ind['ma_alignment']:
                st.warning("👉 空头排列，短期趋势向下。")

        with st.expander("3️⃣ MACD", expanded=False):
            st.markdown(f"- **状态**：{ind['macd_status']}")
            st.markdown(f"- **交叉**：{ind['macd_cross']}")
            st.markdown(f"- **MACD柱值**：{ind['macd_hist_value']:.4f}")
            if "多头增强" in ind['macd_status']:
                st.info("👉 红柱变长，多头动能增强。")
            elif "空头增强" in ind['macd_status']:
                st.warning("👉 绿柱变长，空头动能增强。")

        with st.expander("4️⃣ RSI", expanded=False):
            st.markdown(f"- **RSI(14)**：{ind['rsi']:.1f}（{ind['rsi_status']}）")
            if ind['rsi'] > 70:
                st.warning("👉 超买区，短期有回调压力。")
            elif ind['rsi'] < 30:
                st.info("👉 超卖区，短期有反弹需求。")
            else:
                st.info("👉 中性区，方向由其他指标决定。")

        with st.expander("5️⃣ KDJ", expanded=False):
            st.markdown(f"- **K**：{ind['k_val']:.1f}   **D**：{ind['d_val']:.1f}   **J**：{ind['j_val']:.1f}")
            st.markdown(f"- **状态**：{ind['kdj_status']}")
            if ind['j_val'] > 100:
                st.warning("👉 J值超买，短线可能回调。")
            elif ind['j_val'] < 0:
                st.info("👉 J值超卖，短线可能反弹。")

        with st.expander("6️⃣ 布林带", expanded=False):
            st.markdown(f"- **上轨**：{ind['boll_up']:.2f}")
            st.markdown(f"- **中轨**：{ind['boll_mid']:.2f}")
            st.markdown(f"- **下轨**：{ind['boll_low']:.2f}")
            st.markdown(f"- **当前价**：{ind['last_close']:.2f}（位置 {ind['bb_position']:.1f}%）")
            st.markdown(f"- **状态**：{ind['boll_status']}")

        # 下一题
        st.markdown("---")
        if st.button("➡️ 下一题", type="primary", key="intra_next"):
            with st.spinner("生成新的分时题..."):
                new_q = generate_intraday_question()
                if new_q:
                    st.session_state.intra_q = new_q
                    st.session_state.intra_answered = False
                    st.session_state.intra_user = None
                    st.rerun()
                else:
                    st.error("新题加载失败，请重试。")


# ============================================================
# 第4段结束
# ============================================================# ============================================================
# 第5段：板块认知 + 买卖点判断
# ============================================================
# 【本段做什么】
#   模块A：板块认知
#     - 从股票池随机抽一只股票，让用户判断所属行业
#     - 干扰项从所有行业中随机抽，保证不重复
#     - 答错记录到错题本
#     - 答完显示行业学习提示 + 该股票近期K线
#
#   模块B：买卖点判断
#     - 从历史K线中识别出5种典型场景：
#         突破买入、回踩买入、跌破卖出、冲高卖出、震荡观望
#     - 让用户判断应该买、卖、还是观望
#     - 答完显示后续5天真实走势
#     - 答错对比"你的选择"和"正确操作"的逻辑区别
# ============================================================


# ============================================================
# 模块A：板块认知
# ============================================================
# 行业学习提示（一句话描述 + 代表股）
INDUSTRY_DESC = {
    "白酒": "消费板块，高毛利、品牌壁垒强。代表：贵州茅台、五粮液、泸州老窖、山西汾酒。",
    "银行": "金融板块，与宏观经济高度相关，股息率高。代表：招商银行、兴业银行。",
    "券商": "金融板块，牛市弹性大，被称为'牛市旗手'。代表：中信证券。",
    "保险": "金融板块，负债端+投资端双轮驱动。代表：中国平安。",
    "房地产": "周期板块，受政策影响大。代表：万科A、保利发展。",
    "安防": "科技板块，海康威视是龙头。",
    "面板显示": "电子板块，周期性较强。代表：京东方A。",
    "锂电池": "新能源板块，宁德时代是龙头。",
    "新能源车": "汽车板块，比亚迪是龙头。",
    "光伏": "新能源板块，隆基绿能是龙头。",
    "医药": "消费+科技板块，恒瑞医药是龙头。",
    "食品饮料": "消费板块，伊利股份是龙头。",
    "家电": "消费板块，美的集团、格力电器是龙头。",
    "化工": "周期板块，万华化学是龙头。",
    "建材": "周期板块，海螺水泥是龙头。",
    "电力": "公用事业板块，长江电力是龙头。",
    "煤炭": "周期板块，中国神华是龙头。",
    "养殖": "农业板块，牧原股份是龙头。",
}


def generate_sector_question():
    """
    生成一道板块认知题。
    返回：{"symbol", "name", "correct", "options"} 或 None
    """
    # 从有行业映射的股票里随机选
    candidates = [(c, n) for c, n in STOCK_POOL if c in INDUSTRY_MAP]
    if not candidates:
        return None

    code, name = random.choice(candidates)
    correct = INDUSTRY_MAP[code]

    # 干扰项：从所有行业里排除正确答案，随机抽3个
    others = [i for i in ALL_INDUSTRIES if i != correct]
    if len(others) < 3:
        return None
    distractors = random.sample(others, 3)

    options = [correct] + distractors
    random.shuffle(options)

    return {
        "symbol": code, "name": name,
        "correct": correct, "options": options,
    }


def render_sector_training():
    """渲染'板块认知'训练页面"""
    st.markdown("## 🏭 板块认知训练")
    st.markdown("""
    **训练目标**：看到一只股票，能快速说出它属于哪个行业板块。

    **玩法**：系统随机从股票池中抽一只股票，显示代码和名称，
    你从4个选项中选出它所属的行业。答错自动记录到错题本。

    **为什么重要**：A股是"板块轮动"的市场，知道股票属于哪个板块，
    才能理解它为什么涨、为什么跌。
    """)

    if "sector_q" not in st.session_state:
        st.session_state.sector_q = None
        st.session_state.sector_answered = False
        st.session_state.sector_user = None
        st.session_state.sector_score = {"correct": 0, "total": 0}

    # 出题按钮
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🎲 随机出题", type="primary", use_container_width=True, key="sector_gen"):
            q = generate_sector_question()
            if q:
                st.session_state.sector_q = q
                st.session_state.sector_answered = False
                st.session_state.sector_user = None
            else:
                st.error("题目生成失败。")
    with col2:
        if st.session_state.sector_score["total"] > 0:
            rate = st.session_state.sector_score["correct"] / st.session_state.sector_score["total"] * 100
            st.metric("正确率", f"{rate:.1f}%")
    with col3:
        st.metric("答题数", st.session_state.sector_score["total"])

    # 首次自动出题
    if st.session_state.sector_q is None:
        q = generate_sector_question()
        if q:
            st.session_state.sector_q = q
        else:
            st.warning("无法生成题目。")
            return

    q = st.session_state.sector_q
    if q is None:
        return

    # 显示题目
    st.markdown(f"### 股票：**{q['symbol']} {q['name']}**")
    st.markdown("它属于以下哪个行业？")

    # 选项
    if not st.session_state.sector_answered:
        cols = st.columns(4)
        for i, opt in enumerate(q["options"]):
            with cols[i]:
                if st.button(opt, key=f"sector_opt_{i}", use_container_width=True):
                    st.session_state.sector_user = opt
                    st.session_state.sector_answered = True
                    st.session_state.sector_score["total"] += 1
                    if opt == q["correct"]:
                        st.session_state.sector_score["correct"] += 1
                    st.rerun()

    # 已作答
    if st.session_state.sector_answered:
        user = st.session_state.sector_user
        correct = q["correct"]

        st.markdown("---")
        if user == correct:
            st.markdown(f"""
            <div class="success-box">
            <h3>✅ 回答正确！</h3>
            <p><b>{q['name']}</b> 属于 <b>{correct}</b> 行业。</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="error-box">
            <h3>❌ 回答错误</h3>
            <p>你选了 <b>{user}</b>，正确答案是 <b>{correct}</b>。</p>
            </div>
            """, unsafe_allow_html=True)

            # 记录错题
            add_wrong(
                module="板块认知",
                question=f"{q['symbol']} {q['name']} 属于哪个行业？",
                user_answer=user,
                correct_answer=correct,
                analysis=f"{q['name']} 属于 {correct} 行业。"
                         f"你选择了 {user}。"
                         f"行业知识：{INDUSTRY_DESC.get(correct, '')}"
            )
            st.caption("📝 本题已记录到错题本")

        # 学习提示
        st.markdown("### 📚 学习提示")
        st.info(INDUSTRY_DESC.get(correct, f"{correct} 是A股市场的一个重要板块。"))

        # 同行业其他股票
        st.markdown("#### 🔗 同行业的其他股票")
        same_ind = [c for c, n in STOCK_POOL
                    if c in INDUSTRY_MAP and INDUSTRY_MAP[c] == correct and c != q["symbol"]]
        if same_ind:
            for c in same_ind:
                st.markdown(f"- {c} {get_stock_name(c)}")
        else:
            st.caption("股票池中没有同行业的其他股票。")

        # 该股票的K线
        st.markdown("### 📈 该股票近期走势")
        with st.spinner("加载K线..."):
            df = fetch_daily(q["symbol"], days=120)
            if df is not None and len(df) > 0:
                fig = plot_kline(df.tail(60), title=f"{q['symbol']} {q['name']}",
                                 show_ma=True, show_volume=True, height=450)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("K线数据加载失败。")

        # 下一题
        st.markdown("---")
        if st.button("➡️ 下一题", type="primary", key="sector_next"):
            new_q = generate_sector_question()
            if new_q:
                st.session_state.sector_q = new_q
                st.session_state.sector_answered = False
                st.session_state.sector_user = None
                st.rerun()


# ============================================================
# 模块B：买卖点判断
# ============================================================
def identify_trade_scene(df, i):
    """
    识别第i根K线所处的典型买卖点场景。
    返回：(场景名, 正确操作, 场景说明) 或 None
    """
    if i < 25:
        return None

    last = df.iloc[i]
    prev = df.iloc[i - 1]
    window = df.iloc[max(0, i - 20):i + 1]

    ma20 = window["close"].rolling(20).mean().iloc[-1] if len(window) >= 20 else last["close"]
    ma5 = window["close"].rolling(5).mean().iloc[-1] if len(window) >= 5 else last["close"]
    vol_avg = df["volume"].iloc[max(0, i - 6):i].mean() if i >= 6 else last["volume"]
    recent_high = df["high"].iloc[max(0, i - 20):i].max() if i >= 20 else last["high"]

    # 场景1：突破买入 — 放量突破20日新高
    if (last["close"] > recent_high * 1.005
            and last["volume"] > vol_avg * 1.3
            and last["close"] > last["open"]):
        return ("放量突破20日新高",
                "买入",
                "放量突破前高，说明多头强势，资金介入明确。"
                "这种突破往往打开上涨空间。")

    # 场景2：回踩买入 — 跌破MA20后阳线拉回 + 缩量
    if (last["low"] <= ma20 * 1.01
            and last["close"] > ma20
            and last["close"] > last["open"]
            and last["volume"] < vol_avg * 0.9):
        return ("回踩MA20后企稳反弹",
                "买入",
                "股价回踩20日均线获得支撑，缩量说明抛压不重，"
                "阳线说明买盘回归，是较安全的买点。")

    # 场景3：跌破卖出 — 放量跌破MA20
    if (last["close"] < ma20 * 0.99
            and last["volume"] > vol_avg * 1.3
            and last["close"] < last["open"]):
        return ("放量跌破MA20",
                "卖出",
                "放量跌破20日均线，说明空头强势，支撑失效。"
                "此时应该果断离场，不要幻想反弹。")

    # 场景4：冲高卖出 — 长上影线 + 高位
    upper = last["high"] - max(last["open"], last["close"])
    body = abs(last["close"] - last["open"])
    if (upper >= body * 1.5
            and last["high"] > recent_high * 0.98
            and last["close"] < last["open"]):
        return ("高位长上影线",
                "卖出",
                "股价冲高后被大量抛压打回，形成长上影线。"
                "说明上方压力极重，短期见顶概率大。")

    # 场景5：震荡观望 — 均线交织，量能平淡
    if (abs(last["close"] - ma20) / ma20 < 0.01
            and vol_avg > 0
            and 0.8 < last["volume"] / vol_avg < 1.2):
        return ("均线交织，量能平淡",
                "观望",
                "股价在均线附近震荡，没有明确方向。"
                "此时买入容易被套，卖出可能卖飞，最好的策略是等。")

    return None


def generate_trade_question():
    """生成一道买卖点判断题"""
    pool = STOCK_POOL.copy()
    random.shuffle(pool)

    for code, name in pool[:8]:
        df = fetch_daily(code, days=250)
        if df is None or len(df) < 80:
            continue

        # 从第50根开始找场景（保证前面有足够均线数据）
        candidates = []
        for i in range(50, len(df) - 6):
            scene = identify_trade_scene(df, i)
            if scene:
                candidates.append((i, scene))

        if not candidates:
            continue

        # 随机选一个场景
        idx, (scene_name, correct_action, scene_desc) = random.choice(candidates)

        # 展示到场景位置
        df_show = df.iloc[max(0, idx - 60):idx + 1].reset_index(drop=True)

        # 后续5天走势
        future = df.iloc[idx + 1:idx + 6].reset_index(drop=True)

        # 计算后续5天累计涨跌
        if len(future) > 0:
            base = df.iloc[idx]["close"]
            future_returns = [(row["close"] - base) / base * 100
                              for _, row in future.iterrows()]
        else:
            future_returns = []

        return {
            "symbol": code, "name": name,
            "df": df_show,
            "scene": scene_name,
            "correct": correct_action,
            "scene_desc": scene_desc,
            "future": future,
            "future_returns": future_returns,
            "base_price": df.iloc[idx]["close"],
        }
    return None


def render_trade_training():
    """渲染'买卖点判断'训练页面"""
    st.markdown("## 🎯 买卖点判断训练")
    st.markdown("""
    **训练目标**：看到K线图，能判断当前应该是"买入"、"卖出"还是"观望"。

    **玩法**：系统从历史中识别出5种典型场景，展示对应的K线图，
    你选择买/卖/观望。答完系统会展示后续5天的真实走势。

    **5种典型场景**：
    1. 放量突破20日新高 → 买入
    2. 回踩MA20后企稳反弹 → 买入
    3. 放量跌破MA20 → 卖出
    4. 高位长上影线 → 卖出
    5. 均线交织、量能平淡 → 观望
    """)

    if "trade_q" not in st.session_state:
        st.session_state.trade_q = None
        st.session_state.trade_answered = False
        st.session_state.trade_user = None
        st.session_state.trade_score = {"correct": 0, "total": 0}

    # 出题
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🎲 随机出题", type="primary", use_container_width=True, key="trade_gen"):
            with st.spinner("正在识别买卖点场景..."):
                q = generate_trade_question()
                if q:
                    st.session_state.trade_q = q
                    st.session_state.trade_answered = False
                    st.session_state.trade_user = None
                else:
                    st.error("题目生成失败，请重试。")
    with col2:
        if st.session_state.trade_score["total"] > 0:
            rate = st.session_state.trade_score["correct"] / st.session_state.trade_score["total"] * 100
            st.metric("正确率", f"{rate:.1f}%")
    with col3:
        st.metric("答题数", st.session_state.trade_score["total"])

    if st.session_state.trade_q is None:
        with st.spinner("首次加载..."):
            q = generate_trade_question()
            if q:
                st.session_state.trade_q = q
            else:
                st.warning("无法生成题目。")
                return

    q = st.session_state.trade_q
    if q is None:
        return

    # 显示K线
    st.markdown(f"### {q['name']}（{q['symbol']}）")
    st.caption(f"场景特征：**{q['scene']}**")

    fig = plot_kline(q["df"], title=f"{q['name']} 日K线",
                     show_ma=True, show_volume=True, height=500)
    st.plotly_chart(fig, use_container_width=True)

    # 选项
    if not st.session_state.trade_answered:
        st.markdown("### 你认为现在应该：")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("🟢 买入", use_container_width=True, key="trade_buy"):
                st.session_state.trade_user = "买入"
                st.session_state.trade_answered = True
                st.session_state.trade_score["total"] += 1
                if q["correct"] == "买入":
                    st.session_state.trade_score["correct"] += 1
                st.rerun()
        with c2:
            if st.button("🔴 卖出", use_container_width=True, key="trade_sell"):
                st.session_state.trade_user = "卖出"
                st.session_state.trade_answered = True
                st.session_state.trade_score["total"] += 1
                if q["correct"] == "卖出":
                    st.session_state.trade_score["correct"] += 1
                st.rerun()
        with c3:
            if st.button("⚪ 观望", use_container_width=True, key="trade_wait"):
                st.session_state.trade_user = "观望"
                st.session_state.trade_answered = True
                st.session_state.trade_score["total"] += 1
                if q["correct"] == "观望":
                    st.session_state.trade_score["correct"] += 1
                st.rerun()

    # 已作答
    if st.session_state.trade_answered:
        user = st.session_state.trade_user
        correct = q["correct"]

        st.markdown("---")
        if user == correct:
            st.markdown(f"""
            <div class="success-box">
            <h3>✅ 判断正确！</h3>
            <p>场景：<b>{q['scene']}</b> → 正确操作：<b>{correct}</b></p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="error-box">
            <h3>❌ 判断错误</h3>
            <p>你选了 <b>{user}</b>，正确答案是 <b>{correct}</b>。</p>
            </div>
            """, unsafe_allow_html=True)

            # 记录错题
            add_wrong(
                module="买卖点判断",
                question=f"{q['name']}（{q['symbol']}）场景：{q['scene']}",
                user_answer=user,
                correct_answer=correct,
                analysis=f"场景：{q['scene']}\n"
                         f"正确操作：{correct}\n"
                         f"你选了：{user}\n"
                         f"逻辑：{q['scene_desc']}"
            )
            st.caption("📝 本题已记录到错题本")

        # 场景说明
        st.markdown("### 📚 场景说明")
        st.info(q["scene_desc"])

        # 后续5天走势
        st.markdown("### 📈 后续5天真实走势")
        if len(q["future"]) > 0:
            future_df = q["future"][["date", "open", "high", "low", "close"]].copy()
            future_df["涨跌%"] = [(r["close"] - q["base_price"]) / q["base_price"] * 100
                                 for _, r in future_df.iterrows()]
            future_df["date"] = future_df["date"].dt.strftime("%Y-%m-%d")
            st.dataframe(future_df, use_container_width=True)

            # 累计涨跌
            total_ret = q["future_returns"][-1] if q["future_returns"] else 0
            if total_ret > 0:
                st.markdown(f"**5日累计涨跌**：<span class='red-text'>{total_ret:+.2f}%</span>",
                            unsafe_allow_html=True)
            else:
                st.markdown(f"**5日累计涨跌**：<span class='green-text'>{total_ret:+.2f}%</span>",
                            unsafe_allow_html=True)

            # 如果用户选错，对比逻辑
            if user != correct:
                st.markdown("### 🔍 为什么你的选择不对？")
                if user == "买入" and correct == "卖出":
                    st.warning("👉 你看到的是下跌中的'假反弹'，实际是放量跌破关键均线，应该止损离场。")
                elif user == "买入" and correct == "观望":
                    st.warning("👉 你过早介入。均线交织、量能平淡时，方向不明朗，等确认再出手。")
                elif user == "卖出" and correct == "买入":
                    st.warning("👉 你把'回踩支撑'当成了'破位下跌'。缩量回踩均线后企稳，是买点不是卖点。")
                elif user == "卖出" and correct == "观望":
                    st.warning("👉 趋势不明时不要急于卖出，可能卖在震荡区间的底部。")
                elif user == "观望" and correct == "买入":
                    st.warning("👉 你错过了明确信号。放量突破或缩量回踩都是经典的买点，不该犹豫。")
                elif user == "观望" and correct == "卖出":
                    st.warning("👉 你忽略了风险信号。放量跌破或长上影线，是明确的离场信号。")
        else:
            st.caption("后续数据不足。")

        # 下一题
        st.markdown("---")
        if st.button("➡️ 下一题", type="primary", key="trade_next"):
            with st.spinner("识别新场景..."):
                new_q = generate_trade_question()
                if new_q:
                    st.session_state.trade_q = new_q
                    st.session_state.trade_answered = False
                    st.session_state.trade_user = None
                    st.rerun()
                else:
                    st.error("新题生成失败。")


# ============================================================
# 第5段结束
# ============================================================# ============================================================
# 第6段：止损训练 + 未来趋势
# ============================================================
# 【本段做什么】
#   模块A：止损训练
#     - 展示一段真实K线，显示当前价和ATR
#     - 用户输入自己认为合理的止损价
#     - 系统根据ATR判断是否合理（合理区间：入场价 - 2ATR ~ 入场价 - 0.8ATR）
#     - 答错对比"你的止损"和"合理区间"的逻辑区别
#
#   模块B：未来趋势
#     - 展示一段K线，让用户判断未来3天涨还是跌
#     - 答完显示未来3天真实走势
#     - 逐指标复盘：MACD/RSI/KDJ/布林带/量价/均线
# ============================================================


# ============================================================
# 模块A：止损训练
# ============================================================
def generate_stop_question():
    """
    生成一道止损训练题。
    逻辑：
      1. 随机选股票，取日线
      2. 随机截取一段（≥60根）展示
      3. 计算当前价、ATR(14)
      4. 合理止损区间 = 当前价 - 2*ATR  ~  当前价 - 0.8*ATR
    """
    pool = STOCK_POOL.copy()
    random.shuffle(pool)

    for code, name in pool[:8]:
        df = fetch_daily(code, days=250)
        if df is None or len(df) < 80:
            continue

        # 截取到某个位置（保证后面还有足够数据展示）
        cut = random.randint(60, len(df) - 5)
        display = df.iloc[:cut].reset_index(drop=True)

        ind = calc_all_indicators(display, idx=len(display) - 1)
        last_close = ind["last_close"]
        atr = ind["atr"]

        if atr <= 0 or pd.isna(atr):
            continue

        return {
            "symbol": code, "name": name,
            "df": display,
            "last_close": last_close,
            "atr": atr,
            "stop_high": last_close - 0.8 * atr,   # 保守止损（窄）
            "stop_low": last_close - 2.0 * atr,    # 宽松止损（宽）
            "indicators": ind,
        }
    return None


def judge_stop(user_stop, q):
    """
    判断用户的止损价是否合理。
    返回：(是否合理, 评语)
    """
    stop_low = q["stop_low"]
    stop_high = q["stop_high"]
    last_close = q["last_close"]
    atr = q["atr"]

    # 计算用户止损距离当前价的百分比
    dist_pct = (last_close - user_stop) / last_close * 100

    if user_stop >= last_close:
        return False, "止损价高于或等于当前价，没有意义。止损应该低于当前价。"
    if user_stop < last_close * 0.8:
        return False, f"止损价太低（-{dist_pct:.1f}%），亏损会很大。除非你有特别理由，否则止损不应该超过-15%。"
    if user_stop < stop_low:
        return False, (f"止损价太宽（-{dist_pct:.1f}%）。"
                       f"合理区间应该在 {stop_low:.2f} ~ {stop_high:.2f}。"
                       f"止损太宽会导致单次亏损过大。")
    if user_stop > stop_high:
        return False, (f"止损价太窄（-{dist_pct:.1f}%）。"
                       f"合理区间应该在 {stop_low:.2f} ~ {stop_high:.2f}。"
                       f"止损太窄会被日内波动轻易扫出局。")
    return True, f"合理！止损距离当前价 -{dist_pct:.1f}%，正好在ATR合理区间内。"


def render_stop_training():
    """渲染'止损训练'页面"""
    st.markdown("## 🛡️ 止损训练")
    st.markdown("""
    **训练目标**：学会设置合理的止损价。

    **玩法**：系统展示一段K线，显示当前价，你输入自己认为合理的止损价。
    系统根据ATR（平均真实波幅）判断是否合理。

    **核心原则**：
    - 止损太窄 → 被日内正常波动扫出局
    - 止损太宽 → 单次亏损过大
    - **合理区间 = 当前价 - 2×ATR  ~  当前价 - 0.8×ATR**
    """)

    if "stop_q" not in st.session_state:
        st.session_state.stop_q = None
        st.session_state.stop_answered = False
        st.session_state.stop_user_input = None
        st.session_state.stop_score = {"correct": 0, "total": 0}

    # 出题
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🎲 随机出题", type="primary", use_container_width=True, key="stop_gen"):
            with st.spinner("正在准备题目..."):
                q = generate_stop_question()
                if q:
                    st.session_state.stop_q = q
                    st.session_state.stop_answered = False
                    st.session_state.stop_user_input = None
                else:
                    st.error("题目生成失败，请重试。")
    with col2:
        if st.session_state.stop_score["total"] > 0:
            rate = st.session_state.stop_score["correct"] / st.session_state.stop_score["total"] * 100
            st.metric("正确率", f"{rate:.1f}%")
    with col3:
        st.metric("答题数", st.session_state.stop_score["total"])

    if st.session_state.stop_q is None:
        with st.spinner("首次加载..."):
            q = generate_stop_question()
            if q:
                st.session_state.stop_q = q
            else:
                st.warning("无法生成题目。")
                return

    q = st.session_state.stop_q
    if q is None:
        return

    # 显示K线
    st.markdown(f"### {q['name']}（{q['symbol']}）")
    fig = plot_kline(q["df"].tail(60), title=f"{q['name']} 日K线（最后60根）",
                     show_ma=True, show_volume=True, height=500)
    st.plotly_chart(fig, use_container_width=True)

    # 显示当前信息
    c1, c2, c3 = st.columns(3)
    c1.metric("当前价", f"{q['last_close']:.2f}")
    c2.metric("ATR(14)", f"{q['atr']:.2f}")
    c3.metric("ATR占比", f"{q['atr'] / q['last_close'] * 100:.2f}%")

    # 输入止损价
    if not st.session_state.stop_answered:
        st.markdown("### 请输入你认为合理的止损价：")
        col1, col2 = st.columns([2, 1])
        with col1:
            user_stop = st.number_input(
                "止损价",
                value=float(round(q["last_close"] * 0.95, 2)),
                step=0.01,
                key="stop_input"
            )
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✅ 提交", type="primary", use_container_width=True, key="stop_submit"):
                st.session_state.stop_user_input = user_stop
                st.session_state.stop_answered = True
                is_ok, _ = judge_stop(user_stop, q)
                st.session_state.stop_score["total"] += 1
                if is_ok:
                    st.session_state.stop_score["correct"] += 1
                st.rerun()

    # 已作答
    if st.session_state.stop_answered:
        user_stop = st.session_state.stop_user_input
        is_ok, comment = judge_stop(user_stop, q)

        st.markdown("---")
        if is_ok:
            st.markdown(f"""
            <div class="success-box">
            <h3>✅ 止损设置合理</h3>
            <p>你的止损价：<b>{user_stop:.2f}</b>（距离当前价 -{(q['last_close'] - user_stop) / q['last_close'] * 100:.2f}%）</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="error-box">
            <h3>❌ 止损设置不合理</h3>
            <p>你的止损价：<b>{user_stop:.2f}</b></p>
            </div>
            """, unsafe_allow_html=True)

            # 记录错题
            add_wrong(
                module="止损训练",
                question=f"{q['name']}（{q['symbol']}）止损价设定",
                user_answer=f"{user_stop:.2f}",
                correct_answer=f"{q['stop_low']:.2f} ~ {q['stop_high']:.2f}",
                analysis=f"当前价：{q['last_close']:.2f}，ATR：{q['atr']:.2f}。"
                         f"合理止损区间：{q['stop_low']:.2f} ~ {q['stop_high']:.2f}。"
                         f"你设置了 {user_stop:.2f}。{comment}"
            )
            st.caption("📝 本题已记录到错题本")

        st.markdown("### 📚 详细分析")
        st.info(comment)

        # ATR教学
        st.markdown("### 🧠 为什么要用ATR？")
        st.markdown(f"""
        **ATR = 平均真实波幅**，衡量的是股票"一天平均能波动多少"。

        本股当前的ATR是 **{q['atr']:.2f}**，意味着它平均每天波动 {q['atr']:.2f} 元。

        止损价的设置原则：
        - **保守（窄）**：当前价 - 0.8×ATR = **{q['stop_high']:.2f}**
          适合：短线交易，不想亏太多，但容易被震出局。

        - **宽松（宽）**：当前价 - 2.0×ATR = **{q['stop_low']:.2f}**
          适合：中长线，能容忍较大波动，但单次亏损也大。

        - **合理区间**：{q['stop_low']:.2f} ~ {q['stop_high']:.2f}
        """)

        # 可视化：画出止损区间
        st.markdown("### 📊 止损位置可视化")
        last_close = q["last_close"]
        stop_low = q["stop_low"]
        stop_high = q["stop_high"]

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=[0, 1], y=[last_close, last_close],
            mode="lines+text", name="当前价",
            text=[f"当前价 {last_close:.2f}", ""],
            textposition="middle right",
            line=dict(color="#ffcc00", width=2)
        ))
        fig2.add_trace(go.Scatter(
            x=[0, 1], y=[stop_high, stop_high],
            mode="lines+text", name="保守止损",
            text=[f"保守止损 {stop_high:.2f}", ""],
            textposition="middle right",
            line=dict(color="#00aaff", width=2, dash="dash")
        ))
        fig2.add_trace(go.Scatter(
            x=[0, 1], y=[stop_low, stop_low],
            mode="lines+text", name="宽松止损",
            text=[f"宽松止损 {stop_low:.2f}", ""],
            textposition="middle right",
            line=dict(color="#ff88cc", width=2, dash="dash")
        ))
        fig2.add_trace(go.Scatter(
            x=[0, 1], y=[user_stop, user_stop],
            mode="lines+text", name="你的止损",
            text=[f"你的止损 {user_stop:.2f}", ""],
            textposition="middle right",
            line=dict(color="#00cc66" if is_ok else "#ff4444", width=3)
        ))
        fig2.update_layout(
            height=300, template="plotly_white",
            title="止损位置对比",
            showlegend=True,
            xaxis=dict(showticklabels=False),
            yaxis=dict(title="价格")
        )
        st.plotly_chart(fig2, use_container_width=True)

        # 下一题
        st.markdown("---")
        if st.button("➡️ 下一题", type="primary", key="stop_next"):
            with st.spinner("准备新题..."):
                new_q = generate_stop_question()
                if new_q:
                    st.session_state.stop_q = new_q
                    st.session_state.stop_answered = False
                    st.session_state.stop_user_input = None
                    st.rerun()
                else:
                    st.error("新题生成失败。")


# ============================================================
# 模块B：未来趋势
# ============================================================
def generate_trend_question():
    """
    生成一道未来趋势题。
    逻辑：
      1. 随机选股票，取日线
      2. 截取到某个位置，展示到该位置
      3. 记录未来3天的真实涨跌作为答案
      4. 计算截止到当前位置的所有指标
    """
    pool = STOCK_POOL.copy()
    random.shuffle(pool)

    for code, name in pool[:8]:
        df = fetch_daily(code, days=250)
        if df is None or len(df) < 80:
            continue

        # 截取位置：保证后面至少还有3天
        cut = random.randint(60, len(df) - 4)
        display = df.iloc[:cut + 1].reset_index(drop=True)
        future_3 = df.iloc[cut + 1:cut + 4].reset_index(drop=True)

        if len(future_3) < 3:
            continue

        current_price = display.iloc[-1]["close"]
        future_price = future_3.iloc[-1]["close"]
        direction = "涨" if future_price > current_price else "跌"
        pct = (future_price - current_price) / current_price * 100

        ind = calc_all_indicators(display, idx=len(display) - 1)

        return {
            "symbol": code, "name": name,
            "df": display,
            "future_3": future_3,
            "current_price": current_price,
            "future_price": future_price,
            "actual_direction": direction,
            "actual_pct": pct,
            "indicators": ind,
        }
    return None


def render_trend_training():
    """渲染'未来趋势'页面"""
    st.markdown("## 🔮 未来趋势判断")
    st.markdown("""
    **训练目标**：看到当前K线图和指标，判断未来3天大概率涨还是跌。

    **玩法**：系统展示一段K线图，你判断未来3天的方向。
    答完系统会展示未来3天真实走势，并逐指标复盘。

    **复盘价值**：不是猜对错，而是学会"用指标组合判断趋势"。
    """)

    if "trend_q" not in st.session_state:
        st.session_state.trend_q = None
        st.session_state.trend_answered = False
        st.session_state.trend_user = None
        st.session_state.trend_score = {"correct": 0, "total": 0}

    # 出题
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🎲 随机出题", type="primary", use_container_width=True, key="trend_gen"):
            with st.spinner("正在准备题目..."):
                q = generate_trend_question()
                if q:
                    st.session_state.trend_q = q
                    st.session_state.trend_answered = False
                    st.session_state.trend_user = None
                else:
                    st.error("题目生成失败。")
    with col2:
        if st.session_state.trend_score["total"] > 0:
            rate = st.session_state.trend_score["correct"] / st.session_state.trend_score["total"] * 100
            st.metric("正确率", f"{rate:.1f}%")
    with col3:
        st.metric("答题数", st.session_state.trend_score["total"])

    if st.session_state.trend_q is None:
        with st.spinner("首次加载..."):
            q = generate_trend_question()
            if q:
                st.session_state.trend_q = q
            else:
                st.warning("无法生成题目。")
                return

    q = st.session_state.trend_q
    if q is None:
        return

    ind = q["indicators"]

    # 显示K线
    st.markdown(f"### {q['name']}（{q['symbol']}）")
    fig = plot_kline(q["df"].tail(60), title=f"{q['name']} 日K线（最后60根）",
                     show_ma=True, show_volume=True, height=500)
    st.plotly_chart(fig, use_container_width=True)

    # 显示指标概览
    st.markdown("### 📊 当前指标概览")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("均线", ind['ma_alignment'])
    c2.metric("MACD", ind['macd_status'])
    c3.metric("RSI", f"{ind['rsi']:.1f}", delta=ind['rsi_status'])
    c4.metric("量价", ind['vol_price_status'])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("KDJ-J值", f"{ind['j_val']:.1f}", delta=ind['kdj_status'])
    c2.metric("布林带", ind['boll_status'])
    c3.metric("ADX", f"{ind['adx']:.1f}")
    c4.metric("5日涨幅", f"{ind['pct_5d']:+.2f}%")

    # 答题
    if not st.session_state.trend_answered:
        st.markdown("### 请判断：未来3天大概率是——")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📈 看涨", use_container_width=True, key="trend_up"):
                st.session_state.trend_user = "涨"
                st.session_state.trend_answered = True
                st.session_state.trend_score["total"] += 1
                if q["actual_direction"] == "涨":
                    st.session_state.trend_score["correct"] += 1
                st.rerun()
        with c2:
            if st.button("📉 看跌", use_container_width=True, key="trend_down"):
                st.session_state.trend_user = "跌"
                st.session_state.trend_answered = True
                st.session_state.trend_score["total"] += 1
                if q["actual_direction"] == "跌":
                    st.session_state.trend_score["correct"] += 1
                st.rerun()

    # 已作答：复盘
    if st.session_state.trend_answered:
        user = st.session_state.trend_user
        actual = q["actual_direction"]

        st.markdown("---")
        if user == actual:
            st.markdown(f"""
            <div class="success-box">
            <h3>✅ 判断正确！</h3>
            <p>未来3天实际：<b>{actual} {abs(q['actual_pct']):.2f}%</b></p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="error-box">
            <h3>❌ 判断错误</h3>
            <p>你选了 <b>{user}</b>，实际未来3天：<b>{actual} {abs(q['actual_pct']):.2f}%</b></p>
            </div>
            """, unsafe_allow_html=True)

            add_wrong(
                module="未来趋势",
                question=f"{q['name']}（{q['symbol']}）未来3天方向",
                user_answer=user,
                correct_answer=actual,
                analysis=f"实际走势：{actual} {abs(q['actual_pct']):.2f}%。"
                         f"当时指标：均线={ind['ma_alignment']}，"
                         f"MACD={ind['macd_status']}，"
                         f"RSI={ind['rsi']:.1f}，"
                         f"量价={ind['vol_price_status']}，"
                         f"KDJ={ind['kdj_status']}，"
                         f"布林={ind['boll_status']}"
            )
            st.caption("📝 本题已记录到错题本")

        # 未来3天真实走势
        st.markdown("### 📈 未来3天真实走势")
        future_df = q["future_3"][["date", "open", "high", "low", "close"]].copy()
        future_df["涨跌%"] = [(r["close"] - q["current_price"]) / q["current_price"] * 100
                             for _, r in future_df.iterrows()]
        future_df["date"] = future_df["date"].dt.strftime("%Y-%m-%d")
        st.dataframe(future_df, use_container_width=True)

        # 逐指标复盘
        st.markdown("### 🔍 逐指标复盘")

        with st.expander("1️⃣ 均线系统", expanded=True):
            st.markdown(f"- **均线排列**：{ind['ma_alignment']}")
            st.markdown(f"- **价格位置**：{ind['price_position']}")
            st.markdown(f"- **MA5**：{ind['ma5']:.2f}  **MA20**：{ind['ma20']:.2f}  **MA60**：{ind['ma60']:.2f}")
            if "多头排列" in ind['ma_alignment']:
                st.info("👉 均线多头排列，短期趋势向上，看涨概率大。")
            elif "空头排列" in ind['ma_alignment']:
                st.warning("👉 均线空头排列，短期趋势向下，看跌概率大。")
            else:
                st.info("👉 均线交织，方向不明朗，需要其他指标确认。")

        with st.expander("2️⃣ MACD", expanded=True):
            st.markdown(f"- **状态**：{ind['macd_status']}")
            st.markdown(f"- **交叉**：{ind['macd_cross']}")
            st.markdown(f"- **MACD柱值**：{ind['macd_hist_value']:.4f}")
            if "多头增强" in ind['macd_status']:
                st.info("👉 红柱持续放大，多头动能增强，未来3天看涨。")
            elif "多头减弱" in ind['macd_status']:
                st.warning("👉 红柱开始缩短，多头动能在衰减，注意回调风险。")
            elif "空头增强" in ind['macd_status']:
                st.warning("👉 绿柱持续放大，空头动能增强，未来3天看跌。")
            elif "空头减弱" in ind['macd_status']:
                st.info("👉 绿柱开始缩短，空头动能在衰减，可能企稳。")

        with st.expander("3️⃣ RSI + KDJ"):
            st.markdown(f"- **RSI(14)**：{ind['rsi']:.1f}（{ind['rsi_status']}）")
            st.markdown(f"- **KDJ**：K={ind['k_val']:.1f} D={ind['d_val']:.1f} J={ind['j_val']:.1f}（{ind['kdj_status']}）")
            if ind['rsi'] > 70 or ind['j_val'] > 100:
                st.warning("👉 超买信号，短期回调压力大。")
            elif ind['rsi'] < 30 or ind['j_val'] < 0:
                st.info("👉 超卖信号，短期反弹需求强。")
            else:
                st.info("👉 中性区间，参考其他指标。")

        with st.expander("4️⃣ 布林带"):
            st.markdown(f"- **上轨**：{ind['boll_up']:.2f}")
            st.markdown(f"- **中轨**：{ind['boll_mid']:.2f}")
            st.markdown(f"- **下轨**：{ind['boll_low']:.2f}")
            st.markdown(f"- **当前价**：{ind['last_close']:.2f}（位置 {ind['bb_position']:.1f}%）")
            st.markdown(f"- **状态**：{ind['boll_status']}")
            if "触及上轨" in ind['boll_status']:
                st.warning("👉 触及上轨，短期有超买压力。")
            elif "触及下轨" in ind['boll_status']:
                st.info("👉 触及下轨，短期有超卖支撑。")
            else:
                st.info("👉 在中轨附近，方向由其他指标决定。")

        with st.expander("5️⃣ 量价关系"):
            st.markdown(f"- **量比**：{ind['vol_ratio']:.2f}（{ind['vol_status']}）")
            st.markdown(f"- **量价状态**：{ind['vol_price_status']}")
            if "放量上涨" in ind['vol_price_status']:
                st.info("👉 放量上涨，买盘积极，看涨。")
            elif "放量下跌" in ind['vol_price_status']:
                st.warning("👉 放量下跌，抛压重，看跌。")
            elif "缩量上涨" in ind['vol_price_status']:
                st.warning("👉 缩量上涨，追高意愿不足，谨慎。")
            elif "缩量下跌" in ind['vol_price_status']:
                st.info("👉 缩量下跌，抛压减轻，可能企稳。")

        with st.expander("6️⃣ 趋势强度（ADX）"):
            st.markdown(f"- **ADX**：{ind['adx']:.1f}")
            if ind['adx'] > 40:
                st.info("👉 ADX > 40，趋势非常强。顺趋势操作胜率高。")
            elif ind['adx'] > 25:
                st.info("👉 ADX 在25~40之间，趋势中等。可以做趋势交易。")
            else:
                st.warning("👉 ADX < 25，趋势弱，处于震荡。不建议做趋势交易。")

        # 综合判断
        st.markdown("### 🎯 综合判断")
        score = 0
        reasons = []

        if "多头排列" in ind['ma_alignment']:
            score += 1; reasons.append("+1 均线多头")
        elif "空头排列" in ind['ma_alignment']:
            score -= 1; reasons.append("-1 均线空头")

        if "多头增强" in ind['macd_status']:
            score += 1; reasons.append("+1 MACD多头增强")
        elif "空头增强" in ind['macd_status']:
            score -= 1; reasons.append("-1 MACD空头增强")

        if "放量上涨" in ind['vol_price_status']:
            score += 1; reasons.append("+1 放量上涨")
        elif "放量下跌" in ind['vol_price_status']:
            score -= 1; reasons.append("-1 放量下跌")

        if ind['rsi'] < 30:
            score += 1; reasons.append("+1 RSI超卖")
        elif ind['rsi'] > 70:
            score -= 1; reasons.append("-1 RSI超买")

        if ind['j_val'] < 0:
            score += 1; reasons.append("+1 KDJ超卖")
        elif ind['j_val'] > 100:
            score -= 1; reasons.append("-1 KDJ超买")

        for r in reasons:
            st.markdown(f"- {r}")

        if score >= 3:
            st.success(f"**综合评分：{score:+d} → 强烈看涨**")
        elif score >= 1:
            st.info(f"**综合评分：{score:+d} → 偏多**")
        elif score <= -3:
            st.error(f"**综合评分：{score:+d} → 强烈看跌**")
        elif score <= -1:
            st.warning(f"**综合评分：{score:+d} → 偏空**")
        else:
            st.info(f"**综合评分：{score:+d} → 中性观望**")

        st.markdown(f"**实际未来3天：{actual} {abs(q['actual_pct']):.2f}%**")

        # 下一题
        st.markdown("---")
        if st.button("➡️ 下一题", type="primary", key="trend_next"):
            with st.spinner("准备新题..."):
                new_q = generate_trend_question()
                if new_q:
                    st.session_state.trend_q = new_q
                    st.session_state.trend_answered = False
                    st.session_state.trend_user = None
                    st.rerun()
                else:
                    st.error("新题生成失败。")


# ============================================================
# 第6段结束
# ============================================================# ============================================================
# 第7段：仓位管理 + 大盘趋势
# ============================================================
# 【本段做什么】
#   模块A：仓位管理
#     - 输入信号强度（强/中/弱）+ 大盘环境（上涨/震荡/下跌）
#     - 系统结合"12个月周期规律"给出建议仓位
#     - 答错对比"你的选择"和"正确仓位"的逻辑
#
#   模块B：大盘趋势
#     - 展示上证指数K线
#     - 判断当前大盘是"上涨/震荡/下跌"
#     - 结合当前月份给出季节性提示
#
# 【12个月周期规律（A股历史统计）】
#   1月：极弱（年初资金面紧张 + 年报预告雷）
#   2月：极强（春节红包行情 + 资金回流）
#   4月：极弱（年报+一季报密集披露，业绩地雷）
#   5月：极强（红五月 + 政策预期）
#   10月：极弱（三季报 + 长假效应）
#   11月：极强（年底估值切换 + 基金排名）
#   其他月份：正常偏震荡
# ============================================================

# 每月季节性权重（正数=偏强，负数=偏弱，0=中性）
MONTH_BIAS = {
    1: -2,   # 极弱
    2: +2,   # 极强
    3:  0,   # 中性
    4: -2,   # 极弱
    5: +2,   # 极强
    6:  0,
    7:  0,
    8:  0,
    9:  0,
    10: -2,  # 极弱
    11: +2,  # 极强
    12:  0,
}

# 每月季节性描述
MONTH_DESC = {
    1:  "1月通常极弱：年初资金紧张，机构调仓，叠加年报预告雷。建议防守。",
    2:  "2月通常极强：春节后资金回流，红包行情，是全年胜率最高的月份之一。",
    3:  "3月震荡：两会行情有政策预期，但资金面不宽裕。",
    4:  "4月通常极弱：年报+一季报密集披露，业绩地雷频发。建议规避高估值。",
    5:  "5月通常极强：红五月行情，政策预期强，资金活跃。",
    6:  "6月震荡：年中资金面偏紧（半年末考核），但7月往往有翻身行情。",
    7:  "7月震荡：半年报预告开始，业绩好的公司开始表现。",
    8:  "8月震荡：中报密集披露，业绩为王。",
    9:  "9月震荡：国庆前资金偏谨慎。",
    10: "10月通常极弱：三季报披露+长假效应，资金观望。",
    11: "11月通常极强：年底估值切换，基金排名战，做多意愿强。",
    12: "12月震荡：年末资金面偏紧，但为明年春季行情布局。",
}


# ============================================================
# 模块A：仓位管理
# ============================================================
def calc_position_advice(signal_strength, market_env, month=None):
    """
    根据信号强度 + 大盘环境 + 月份，计算建议仓位。

    参数：
        signal_strength: "强" / "中" / "弱"
        market_env: "上涨" / "震荡" / "下跌"
        month: 月份（1-12），默认取当前月份

    返回：
        dict: {
            "base": 基础仓位区间,
            "adjusted": 调整后仓位区间,
            "reason": 详细理由,
            "stop_loss": 建议止损比例,
        }
    """
    if month is None:
        month = datetime.now().month

    # ---------- 第一步：根据信号强度和市场环境，确定基础仓位 ----------
    # 矩阵（信号强度 × 市场环境）
    base_matrix = {
        ("强", "上涨"): "5-7成",
        ("强", "震荡"): "3-5成",
        ("强", "下跌"): "1-3成",
        ("中", "上涨"): "3-5成",
        ("中", "震荡"): "2-4成",
        ("中", "下跌"): "0-2成",
        ("弱", "上涨"): "2-3成",
        ("弱", "震荡"): "1-2成",
        ("弱", "下跌"): "0-1成",
    }
    base = base_matrix.get((signal_strength, market_env), "1-2成")

    # ---------- 第二步：根据月份季节性调整 ----------
    bias = MONTH_BIAS.get(month, 0)
    reason_parts = [f"基础仓位（信号{signal_strength}+大盘{market_env}）：{base}"]

    if bias == +2:
        # 极强月份，可以加仓
        adjusted = _shift_position(base, +1)
        reason_parts.append(f"当前{month}月为极强月份，可加仓。")
    elif bias == -2:
        # 极弱月份，需要减仓
        adjusted = _shift_position(base, -1)
        reason_parts.append(f"当前{month}月为极弱月份，需减仓防守。")
    else:
        adjusted = base
        reason_parts.append(f"当前{month}月为中性月份，仓位不变。")

    # ---------- 第三步：建议止损比例 ----------
    # 仓位越重，止损可以越宽；仓位越轻，止损越严格
    if "5-7" in adjusted or "3-5" in adjusted:
        stop_loss = "5-8%"
    elif "2-4" in adjusted or "2-3" in adjusted:
        stop_loss = "4-6%"
    else:
        stop_loss = "3-5%"

    return {
        "base": base,
        "adjusted": adjusted,
        "month": month,
        "month_bias": bias,
        "reason": " ".join(reason_parts),
        "stop_loss": stop_loss,
    }


def _shift_position(position_str, levels):
    """
    将仓位区间按levels移动。
    例如："3-5成" 加1级 → "5-7成"
          "3-5成" 减1级 → "1-2成"
    """
    # 解析出数字
    import re
    nums = re.findall(r'\d+', position_str)
    if len(nums) < 2:
        return position_str
    low, high = int(nums[0]), int(nums[1])

    # 每级约2成
    step = 2 * levels
    low = max(0, min(10, low + step))
    high = max(0, min(10, high + step))

    if low == high:
        return f"{low}成"
    return f"{low}-{high}成"


def generate_position_question():
    """生成一道仓位管理题"""
    signal = random.choice(["强", "中", "弱"])
    market = random.choice(["上涨", "震荡", "下跌"])

    advice = calc_position_advice(signal, market)

    # 生成4个选项（包含正确答案）
    all_options = ["0-1成", "1-2成", "2-4成", "3-5成", "5-7成", "7-9成"]
    correct = advice["adjusted"]

    # 确保正确答案在选项里，再加3个干扰项
    distractors = [o for o in all_options if o != correct]
    random.shuffle(distractors)
    options = [correct] + distractors[:3]
    random.shuffle(options)

    return {
        "signal": signal,
        "market": market,
        "correct": correct,
        "options": options,
        "advice": advice,
    }


def render_position_training():
    """渲染'仓位管理'页面"""
    st.markdown("## 💰 仓位管理训练")
    st.markdown("""
    **训练目标**：根据信号强度、大盘环境、当前月份，选择合理的仓位。

    **核心逻辑**：
    1. **信号强度**：强信号 → 仓位重；弱信号 → 仓位轻
    2. **大盘环境**：牛市场 → 仓位重；熊市 → 仓位轻
    3. **月份季节性**：极强月份可加仓，极弱月份要减仓

    **12个月周期规律**（A股历史统计）：
    - 🔴 极弱月：1月、4月、10月 → 减仓防守
    - 🟢 极强月：2月、5月、11月 → 可加仓进攻
    - ⚪ 中性月：3、6、7、8、9、12月 → 正常仓位
    """)

    if "pos_q" not in st.session_state:
        st.session_state.pos_q = None
        st.session_state.pos_answered = False
        st.session_state.pos_user = None
        st.session_state.pos_score = {"correct": 0, "total": 0}

    # 出题
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🎲 随机出题", type="primary", use_container_width=True, key="pos_gen"):
            q = generate_position_question()
            st.session_state.pos_q = q
            st.session_state.pos_answered = False
            st.session_state.pos_user = None
    with col2:
        if st.session_state.pos_score["total"] > 0:
            rate = st.session_state.pos_score["correct"] / st.session_state.pos_score["total"] * 100
            st.metric("正确率", f"{rate:.1f}%")
    with col3:
        st.metric("答题数", st.session_state.pos_score["total"])

    # 首次自动出题
    if st.session_state.pos_q is None:
        st.session_state.pos_q = generate_position_question()

    q = st.session_state.pos_q
    if q is None:
        return

    advice = q["advice"]

    # 显示场景
    st.markdown("### 📋 当前场景")
    c1, c2, c3 = st.columns(3)
    c1.metric("信号强度", q["signal"])
    c2.metric("大盘环境", q["market"])
    c3.metric("当前月份", f"{advice['month']}月")

    # 月份提示
    month = advice["month"]
    month_desc = MONTH_DESC.get(month, "")
    if MONTH_BIAS.get(month, 0) == +2:
        st.success(f"🟢 **{month}月季节性**：{month_desc}")
    elif MONTH_BIAS.get(month, 0) == -2:
        st.error(f"🔴 **{month}月季节性**：{month_desc}")
    else:
        st.info(f"⚪ **{month}月季节性**：{month_desc}")

    # 选项
    if not st.session_state.pos_answered:
        st.markdown("### 你认为合理的仓位是：")
        cols = st.columns(4)
        for i, opt in enumerate(q["options"]):
            with cols[i]:
                if st.button(opt, key=f"pos_opt_{i}", use_container_width=True):
                    st.session_state.pos_user = opt
                    st.session_state.pos_answered = True
                    st.session_state.pos_score["total"] += 1
                    if opt == q["correct"]:
                        st.session_state.pos_score["correct"] += 1
                    st.rerun()

    # 已作答
    if st.session_state.pos_answered:
        user = st.session_state.pos_user
        correct = q["correct"]

        st.markdown("---")
        if user == correct:
            st.markdown(f"""
            <div class="success-box">
            <h3>✅ 回答正确！</h3>
            <p>建议仓位：<b>{correct}</b></p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="error-box">
            <h3>❌ 回答错误</h3>
            <p>你选了 <b>{user}</b>，正确答案是 <b>{correct}</b>。</p>
            </div>
            """, unsafe_allow_html=True)

            add_wrong(
                module="仓位管理",
                question=f"信号{q['signal']} + 大盘{q['market']} + {advice['month']}月",
                user_answer=user,
                correct_answer=correct,
                analysis=f"基础仓位（信号{q['signal']}+大盘{q['market']}）：{advice['base']}。"
                         f"经{advice['month']}月季节性调整（月偏{bias:+d}）后：{correct}。"
                         f"{MONTH_DESC.get(advice['month'], '')}"
                         f"建议止损：{advice['stop_loss']}"
            )
            st.caption("📝 本题已记录到错题本")

        # 详细逻辑
        st.markdown("### 📚 计算逻辑")
        st.markdown(f"""
        **第一步：基础仓位**（信号{q['signal']} + 大盘{q['market']}）
        → **{advice['base']}**

        **第二步：季节性调整**
        - {advice['month']}月季节性权重：**{advice['month_bias']:+d}**（+2极强，-2极弱，0中性）
        - 调整后仓位：**{correct}**

        **第三步：建议止损比例**
        - 当前建议止损：**{advice['stop_loss']}**
        """)

        st.info(f"💡 **{advice['month']}月操作提示**：{MONTH_DESC.get(advice['month'], '')}")

        # 12个月周期速查表
        with st.expander("📅 查看12个月周期规律速查表", expanded=False):
            month_data = []
            for m in range(1, 13):
                bias = MONTH_BIAS.get(m, 0)
                if bias == +2:
                    tag = "🟢 极强"
                elif bias == -2:
                    tag = "🔴 极弱"
                else:
                    tag = "⚪ 中性"
                month_data.append({"月份": f"{m}月", "季节性": tag, "说明": MONTH_DESC.get(m, "")})
            st.dataframe(pd.DataFrame(month_data), use_container_width=True)

        # 下一题
        st.markdown("---")
        if st.button("➡️ 下一题", type="primary", key="pos_next"):
            st.session_state.pos_q = generate_position_question()
            st.session_state.pos_answered = False
            st.session_state.pos_user = None
            st.rerun()


# ============================================================
# 模块B：大盘趋势
# ============================================================
def judge_market_state(df_index):
    """
    根据指数数据判断当前大盘状态。
    返回：(状态, 详细分析)
    """
    if df_index is None or len(df_index) < 60:
        return "数据不足", {}

    ind = calc_all_indicators(df_index, idx=len(df_index) - 1)

    last_close = ind["last_close"]
    ma20 = ind["ma20"]
    ma60 = ind["ma60"]
    vol_ratio = ind["vol_ratio"]
    macd_status = ind["macd_status"]
    pct_20d = (last_close - df_index["close"].iloc[-21]) / df_index["close"].iloc[-21] * 100

    # 判断逻辑
    score = 0
    reasons = []

    # 均线位置
    if last_close > ma20 * 1.02:
        score += 2
        reasons.append(f"指数在MA20上方（{last_close:.2f} > {ma20:.2f}）+2")
    elif last_close < ma20 * 0.98:
        score -= 2
        reasons.append(f"指数在MA20下方（{last_close:.2f} < {ma20:.2f}）-2")

    # MA20与MA60的关系
    if ma20 > ma60 * 1.01:
        score += 1
        reasons.append(f"MA20 > MA60（中期向上）+1")
    elif ma20 < ma60 * 0.99:
        score -= 1
        reasons.append(f"MA20 < MA60（中期向下）-1")

    # MACD
    if "多头增强" in macd_status:
        score += 1
        reasons.append("MACD多头增强 +1")
    elif "空头增强" in macd_status:
        score -= 1
        reasons.append("MACD空头增强 -1")

    # 20日涨跌
    if pct_20d > 5:
        score += 1
        reasons.append(f"20日涨幅 {pct_20d:+.2f}% +1")
    elif pct_20d < -5:
        score -= 1
        reasons.append(f"20日跌幅 {pct_20d:+.2f}% -1")

    # 量能
    if vol_ratio > 1.3:
        if last_close > df_index["close"].iloc[-2]:
            score += 1
            reasons.append(f"放量上涨（量比{vol_ratio:.2f}）+1")
        else:
            score -= 1
            reasons.append(f"放量下跌（量比{vol_ratio:.2f}）-1")

    # 判定状态
    if score >= 3:
        state = "上涨"
    elif score <= -3:
        state = "下跌"
    else:
        state = "震荡"

    return state, {
        "score": score,
        "reasons": reasons,
        "ind": ind,
        "pct_20d": pct_20d,
    }


def render_market_trend():
    """渲染'大盘趋势'页面"""
    st.markdown("## 🌍 大盘趋势判断")
    st.markdown("""
    **训练目标**：判断当前大盘处于上涨、震荡还是下跌。

    **玩法**：系统展示上证指数的近期K线，你判断当前大盘状态。
    系统会结合均线、MACD、量能、20日涨跌综合分析。

    **为什么重要**：大盘决定80%个股的方向。
    大盘不好时，个股再强也容易被拖累。
    """)

    # 指数选择
    index_options = {
        "上证指数": "000001",
        "深证成指": "399001",
        "创业板指": "399006",
    }
    selected_index = st.selectbox("选择指数", list(index_options.keys()), key="market_idx")

    index_code = index_options[selected_index]

    if "market_q" not in st.session_state:
        st.session_state.market_q = None
        st.session_state.market_answered = False
        st.session_state.market_user = None
        st.session_state.market_score = {"correct": 0, "total": 0}

    # 出题
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🎲 随机出题", type="primary", use_container_width=True, key="market_gen"):
            with st.spinner("加载大盘数据..."):
                df = fetch_market_index(index_code, days=250)
                if df is None or len(df) < 80:
                    st.error("大盘数据加载失败，请检查网络。")
                else:
                    # 随机截取一段
                    cut = random.randint(60, len(df) - 5)
                    display = df.iloc[:cut + 1].reset_index(drop=True)
                    state, detail = judge_market_state(display)

                    st.session_state.market_q = {
                        "df": display,
                        "index_name": selected_index,
                        "state": state,
                        "detail": detail,
                    }
                    st.session_state.market_answered = False
                    st.session_state.market_user = None
    with col2:
        if st.session_state.market_score["total"] > 0:
            rate = st.session_state.market_score["correct"] / st.session_state.market_score["total"] * 100
            st.metric("正确率", f"{rate:.1f}%")
    with col3:
        st.metric("答题数", st.session_state.market_score["total"])

    # 首次自动出题
    if st.session_state.market_q is None:
        with st.spinner("首次加载大盘数据..."):
            df = fetch_market_index(index_code, days=250)
            if df is not None and len(df) >= 80:
                cut = random.randint(60, len(df) - 5)
                display = df.iloc[:cut + 1].reset_index(drop=True)
                state, detail = judge_market_state(display)
                st.session_state.market_q = {
                    "df": display, "index_name": selected_index,
                    "state": state, "detail": detail,
                }
            else:
                st.warning("大盘数据加载失败。")
                return

    q = st.session_state.market_q
    if q is None:
        return

    # 显示K线
    st.markdown(f"### {q['index_name']}（截止到当前位置）")
    fig = plot_kline(q["df"].tail(120), title=f"{q['index_name']}",
                     show_ma=True, show_volume=True, height=500)
    st.plotly_chart(fig, use_container_width=True)

    # 当前指标
    ind = q["detail"]["ind"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("当前点位", f"{ind['last_close']:.2f}", delta=f"{ind['pct_change']:+.2f}%")
    c2.metric("MA20", f"{ind['ma20']:.2f}")
    c3.metric("MA60", f"{ind['ma60']:.2f}")
    c4.metric("20日涨跌", f"{q['detail']['pct_20d']:+.2f}%")

    # 选项
    if not st.session_state.market_answered:
        st.markdown("### 你认为当前大盘处于：")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("📈 上涨", use_container_width=True, key="mkt_up"):
                st.session_state.market_user = "上涨"
                st.session_state.market_answered = True
                st.session_state.market_score["total"] += 1
                if q["state"] == "上涨":
                    st.session_state.market_score["correct"] += 1
                st.rerun()
        with c2:
            if st.button("➡️ 震荡", use_container_width=True, key="mkt_flat"):
                st.session_state.market_user = "震荡"
                st.session_state.market_answered = True
                st.session_state.market_score["total"] += 1
                if q["state"] == "震荡":
                    st.session_state.market_score["correct"] += 1
                st.rerun()
        with c3:
            if st.button("📉 下跌", use_container_width=True, key="mkt_down"):
                st.session_state.market_user = "下跌"
                st.session_state.market_answered = True
                st.session_state.market_score["total"] += 1
                if q["state"] == "下跌":
                    st.session_state.market_score["correct"] += 1
                st.rerun()

    # 已作答
    if st.session_state.market_answered:
        user = st.session_state.market_user
        correct = q["state"]
        detail = q["detail"]

        st.markdown("---")
        if user == correct:
            st.markdown(f"""
            <div class="success-box">
            <h3>✅ 判断正确！</h3>
            <p>当前大盘：<b>{correct}</b></p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="error-box">
            <h3>❌ 判断错误</h3>
            <p>你选了 <b>{user}</b>，正确答案是 <b>{correct}</b>。</p>
            </div>
            """, unsafe_allow_html=True)

            add_wrong(
                module="大盘趋势",
                question=f"{q['index_name']} 状态判断",
                user_answer=user,
                correct_answer=correct,
                analysis=f"综合评分：{detail['score']:+d}。"
                         f"评分理由：{'; '.join(detail['reasons'])}"
            )
            st.caption("📝 本题已记录到错题本")

        # 详细分析
        st.markdown("### 📊 综合评分明细")
        st.markdown(f"**总分：{detail['score']:+d}**（≥+3 上涨，≤-3 下跌，之间 震荡）")
        for r in detail["reasons"]:
            st.markdown(f"- {r}")

        # 当前月份季节提示
        month = datetime.now().month
        bias = MONTH_BIAS.get(month, 0)
        st.markdown("### 📅 当前月份季节性提示")
        if bias == +2:
            st.success(f"🟢 **{month}月**（极强月份）：{MONTH_DESC.get(month, '')}")
        elif bias == -2:
            st.error(f"🔴 **{month}月**（极弱月份）：{MONTH_DESC.get(month, '')}")
        else:
            st.info(f"⚪ **{month}月**（中性月份）：{MONTH_DESC.get(month, '')}")

        # 对应仓位建议
        if correct == "上涨":
            st.info("📌 **上涨市操作建议**：可积极做多，仓位5-7成。重点关注强势板块龙头。")
        elif correct == "下跌":
            st.warning("📌 **下跌市操作建议**：防守为主，仓位0-2成。不要盲目抄底，等趋势明朗。")
        else:
            st.info("📌 **震荡市操作建议**：高抛低吸，仓位3-5成。不追涨不杀跌，做区间波段。")

        # 下一题
        st.markdown("---")
        if st.button("➡️ 下一题", type="primary", key="market_next"):
            with st.spinner("加载新题..."):
                df = fetch_market_index(index_code, days=250)
                if df is not None and len(df) >= 80:
                    cut = random.randint(60, len(df) - 5)
                    display = df.iloc[:cut + 1].reset_index(drop=True)
                    state, detail = judge_market_state(display)
                    st.session_state.market_q = {
                        "df": display, "index_name": selected_index,
                        "state": state, "detail": detail,
                    }
                    st.session_state.market_answered = False
                    st.session_state.market_user = None
                    st.rerun()
                else:
                    st.error("新题生成失败。")


# ============================================================
# 第7段结束
# ============================================================# ============================================================
# 第8段：模拟盘（完整版）
# ============================================================
# 【本段做什么】
#   1. 真实价格买卖（用 fetch_daily 的日线）
#   2. 逐日推进：点"下一天"按钮，价格按日线走
#   3. 完整扣费：
#        买入：佣金（万2.5，最低5元）+ 过户费（万0.1）
#        卖出：佣金 + 印花税（千1）+ 过户费
#   4. 显示账号寿命（还能交易多少次）
#   5. 持仓盈亏实时显示
#   6. 交易记录完整保存
#
# 【A股手续费标准（2024年）】
#   佣金：万分之2.5，最低5元，买卖双向
#   印花税：千分之1，仅卖出
#   过户费：万分之0.1，买卖双向（沪深统一）
# ============================================================


# ------------------------------------------------------------
# 手续费计算
# ------------------------------------------------------------
COMMISSION_RATE = 0.00025   # 佣金：万分之2.5
COMMISSION_MIN = 5.0        # 佣金最低5元
STAMP_TAX_RATE = 0.001      # 印花税：千分之1（仅卖出）
TRANSFER_FEE_RATE = 0.00001 # 过户费：万分之0.1


def calc_buy_fee(amount):
    """
    计算买入总费用。
    返回：(佣金, 过户费, 总费用)
    """
    commission = max(amount * COMMISSION_RATE, COMMISSION_MIN)
    transfer_fee = amount * TRANSFER_FEE_RATE
    return commission, transfer_fee, commission + transfer_fee


def calc_sell_fee(amount):
    """
    计算卖出总费用。
    返回：(佣金, 印花税, 过户费, 总费用)
    """
    commission = max(amount * COMMISSION_RATE, COMMISSION_MIN)
    stamp_tax = amount * STAMP_TAX_RATE
    transfer_fee = amount * TRANSFER_FEE_RATE
    return commission, stamp_tax, transfer_fee, commission + stamp_tax + transfer_fee


# ------------------------------------------------------------
# 初始化模拟盘状态
# ------------------------------------------------------------
INIT_CASH = 1000000.0       # 初始资金100万
INIT_TRADE_LIMIT = 200      # 初始可交易次数（账号寿命）


def init_sim_state():
    """初始化模拟盘所需的 session_state"""
    if "sim_initialized" not in st.session_state:
        st.session_state.sim_initialized = True
        st.session_state.sim_cash = INIT_CASH
        st.session_state.sim_holdings = {}       # {code: {"shares", "avg_cost", "buy_date"}}
        st.session_state.sim_history = []        # 交易记录列表
        st.session_state.sim_trade_count = 0     # 已交易次数
        st.session_state.sim_trade_limit = INIT_TRADE_LIMIT
        st.session_state.sim_day_offset = 0      # 当前推进到第几天（相对今天往前推）
        st.session_state.sim_current_date = None # 当前模拟日期
        st.session_state.sim_price_cache = {}    # {code: {date_str: close}} 缓存


def get_sim_price(code, offset=0):
    """
    获取模拟盘当前可用的价格。
    offset=0 表示当前模拟日期，正数表示往前推进。
    返回：当前价格（float）或 None
    """
    df = fetch_daily(code, days=250)
    if df is None or len(df) == 0:
        return None, None

    # 从最后一根往前推
    idx = len(df) - 1 - offset
    if idx < 0:
        return None, None
    return float(df.iloc[idx]["close"]), df.iloc[idx]["date"]


# ------------------------------------------------------------
# 买卖操作
# ------------------------------------------------------------
def sim_buy(code, name, price, shares):
    """
    模拟买入。
    返回：(成功, 消息)
    """
    amount = price * shares
    commission, transfer_fee, total_fee = calc_buy_fee(amount)
    total_cost = amount + total_fee

    if total_cost > st.session_state.sim_cash:
        return False, f"资金不足。需要 ¥{total_cost:,.2f}，可用 ¥{st.session_state.sim_cash:,.2f}"

    # 扣现金
    st.session_state.sim_cash -= total_cost

    # 更新持仓
    h = st.session_state.sim_holdings.get(code, {"shares": 0, "avg_cost": 0, "buy_date": None})
    old_shares = h["shares"]
    old_cost = h["avg_cost"] * old_shares
    new_shares = old_shares + shares
    # 成本价含手续费
    h["avg_cost"] = (old_cost + total_cost) / new_shares
    h["shares"] = new_shares
    h["buy_date"] = datetime.now().strftime("%Y-%m-%d")
    st.session_state.sim_holdings[code] = h

    # 记录交易
    st.session_state.sim_history.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "action": "买入",
        "code": code, "name": name,
        "price": price, "shares": shares,
        "amount": amount,
        "fee": total_fee,
        "detail": f"佣金{commission:.2f} + 过户费{transfer_fee:.2f}",
    })
    st.session_state.sim_trade_count += 1

    return True, f"✅ 买入 {name} {shares}股 @ {price:.2f}，总费用 ¥{total_fee:.2f}"


def sim_sell(code, name, price, shares):
    """
    模拟卖出。
    返回：(成功, 消息, 盈亏)
    """
    h = st.session_state.sim_holdings.get(code)
    if not h or h["shares"] < shares:
        return False, "持仓不足", 0

    amount = price * shares
    commission, stamp_tax, transfer_fee, total_fee = calc_sell_fee(amount)
    net_income = amount - total_fee

    # 计算盈亏
    cost = h["avg_cost"] * shares
    profit = net_income - cost

    # 加现金
    st.session_state.sim_cash += net_income

    # 更新持仓
    h["shares"] -= shares
    if h["shares"] == 0:
        del st.session_state.sim_holdings[code]
    else:
        st.session_state.sim_holdings[code] = h

    # 记录交易
    st.session_state.sim_history.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "action": "卖出",
        "code": code, "name": name,
        "price": price, "shares": shares,
        "amount": amount,
        "fee": total_fee,
        "profit": profit,
        "detail": f"佣金{commission:.2f} + 印花税{stamp_tax:.2f} + 过户费{transfer_fee:.2f}",
    })
    st.session_state.sim_trade_count += 1

    return True, f"✅ 卖出 {name} {shares}股 @ {price:.2f}，净收入 ¥{net_income:.2f}", profit


# ------------------------------------------------------------
# 计算总资产
# ------------------------------------------------------------
def calc_total_assets():
    """
    计算当前总资产（现金 + 持仓市值）。
    持仓市值按当前模拟日期价格计算。
    """
    total = st.session_state.sim_cash
    holdings_detail = []

    for code, h in st.session_state.sim_holdings.items():
        price, _ = get_sim_price(code, offset=st.session_state.sim_day_offset)
        if price is None:
            price = h["avg_cost"]
        market_value = price * h["shares"]
        total += market_value

        profit = (price - h["avg_cost"]) * h["shares"]
        profit_pct = (price - h["avg_cost"]) / h["avg_cost"] * 100 if h["avg_cost"] > 0 else 0

        holdings_detail.append({
            "code": code,
            "name": get_stock_name(code),
            "shares": h["shares"],
            "avg_cost": h["avg_cost"],
            "price": price,
            "market_value": market_value,
            "profit": profit,
            "profit_pct": profit_pct,
        })

    return total, holdings_detail


# ------------------------------------------------------------
# 渲染模拟盘页面
# ------------------------------------------------------------
def render_simulation():
    """渲染模拟盘页面"""
    init_sim_state()

    st.markdown("## 💼 模拟盘")
    st.markdown("""
    **训练目标**：用虚拟资金练习完整交易，检验前面训练的综合成果。

    **规则**：
    - 初始资金 **¥1,000,000**
    - 交易规则与A股一致：
      - 佣金：万分之2.5，最低5元（买卖双向）
      - 印花税：千分之1（仅卖出）
      - 过户费：万分之0.1（买卖双向）
    - 账号寿命：初始可交易 **200次**，用完需重置
    - 逐日推进：点"下一天"按钮，价格按真实日线走
    """)

    # ---------- 顶部：账号状态 ----------
    st.markdown("### 📊 账号状态")
    total, holdings_detail = calc_total_assets()
    profit_total = total - INIT_CASH
    profit_pct = profit_total / INIT_CASH * 100

    remaining = st.session_state.sim_trade_limit - st.session_state.sim_trade_count
    life_pct = remaining / st.session_state.sim_trade_limit * 100

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("现金", f"¥{st.session_state.sim_cash:,.0f}")
    c2.metric("总资产", f"¥{total:,.0f}",
              delta=f"{profit_total:+,.0f} ({profit_pct:+.2f}%)")
    c3.metric("持仓数", f"{len(st.session_state.sim_holdings)} 只")
    c4.metric("账号寿命", f"{remaining} 次",
              delta=f"已用 {st.session_state.sim_trade_count} 次")

    # 寿命进度条
    if life_pct > 50:
        st.progress(life_pct / 100, text=f"账号寿命：{remaining}/{st.session_state.sim_trade_limit} 次（健康）")
    elif life_pct > 20:
        st.progress(life_pct / 100, text=f"⚠️ 账号寿命：{remaining}/{st.session_state.sim_trade_limit} 次（偏少）")
    else:
        st.progress(life_pct / 100, text=f"🔴 账号寿命：{remaining}/{st.session_state.sim_trade_limit} 次（即将耗尽）")

    # ---------- 逐日推进 ----------
    st.markdown("---")
    st.markdown("### ⏩ 逐日推进")
    st.caption("点下面的按钮，模拟盘会往前推进一天（价格按真实日线走）。")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("▶️ 下一天", use_container_width=True, key="sim_next_day"):
            st.session_state.sim_day_offset += 1
            st.rerun()
    with col2:
        if st.button("⏪ 上一天", use_container_width=True, key="sim_prev_day"):
            if st.session_state.sim_day_offset > 0:
                st.session_state.sim_day_offset -= 1
                st.rerun()
    with col3:
        if st.button("🔄 重置模拟盘", use_container_width=True, key="sim_reset"):
            st.session_state.sim_cash = INIT_CASH
            st.session_state.sim_holdings = {}
            st.session_state.sim_history = []
            st.session_state.sim_trade_count = 0
            st.session_state.sim_trade_limit = INIT_TRADE_LIMIT
            st.session_state.sim_day_offset = 0
            st.rerun()

    st.info(f"📅 当前模拟日期：今天往前 **{st.session_state.sim_day_offset}** 个交易日")

    # ---------- 买入区 ----------
    st.markdown("---")
    st.markdown("### 🟢 买入")

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        buy_code = st.selectbox(
            "选择股票",
            options=[c for c, _ in STOCK_POOL],
            format_func=lambda x: f"{x} {get_stock_name(x)}",
            key="sim_buy_code"
        )
    with c2:
        buy_price, _ = get_sim_price(buy_code, offset=st.session_state.sim_day_offset)
        if buy_price is None:
            buy_price = 10.0
        buy_price_input = st.number_input(
            "买入价", value=float(round(buy_price, 2)),
            step=0.01, key="sim_buy_price"
        )
    with c3:
        buy_shares = st.number_input(
            "股数（100的倍数）", value=100, step=100,
            min_value=100, key="sim_buy_shares"
        )
    with c4:
        st.markdown("<br>", unsafe_allow_html=True)
        buy_btn = st.button("买入", type="primary", use_container_width=True, key="sim_do_buy")

    # 预估费用
    amount = buy_price_input * buy_shares
    comm, trans, total_fee = calc_buy_fee(amount)
    st.caption(f"预估费用：佣金¥{comm:.2f} + 过户费¥{trans:.2f} = **¥{total_fee:.2f}**，总花费 ¥{amount + total_fee:,.2f}")

    if buy_btn:
        ok, msg = sim_buy(buy_code, get_stock_name(buy_code), buy_price_input, buy_shares)
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

    # ---------- 卖出区 ----------
    st.markdown("---")
    st.markdown("### 🔴 卖出")

    if st.session_state.sim_holdings:
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        with c1:
            sell_code = st.selectbox(
                "选择持仓",
                options=list(st.session_state.sim_holdings.keys()),
                format_func=lambda x: f"{x} {get_stock_name(x)}",
                key="sim_sell_code"
            )
        with c2:
            sell_price, _ = get_sim_price(sell_code, offset=st.session_state.sim_day_offset)
            if sell_price is None:
                sell_price = st.session_state.sim_holdings[sell_code]["avg_cost"]
            sell_price_input = st.number_input(
                "卖出价", value=float(round(sell_price, 2)),
                step=0.01, key="sim_sell_price"
            )
        with c3:
            max_shares = st.session_state.sim_holdings[sell_code]["shares"]
            sell_shares = st.number_input(
                "股数", value=max_shares, min_value=1,
                max_value=max_shares, step=100, key="sim_sell_shares"
            )
        with c4:
            st.markdown("<br>", unsafe_allow_html=True)
            sell_btn = st.button("卖出", type="primary", use_container_width=True, key="sim_do_sell")

        # 预估卖出费用
        s_amount = sell_price_input * sell_shares
        s_comm, s_stamp, s_trans, s_total = calc_sell_fee(s_amount)
        st.caption(f"预估费用：佣金¥{s_comm:.2f} + 印花税¥{s_stamp:.2f} + 过户费¥{s_trans:.2f} = **¥{s_total:.2f}**，净收入 ¥{s_amount - s_total:,.2f}")

        if sell_btn:
            ok, msg, profit = sim_sell(sell_code, get_stock_name(sell_code),
                                       sell_price_input, sell_shares)
            if ok:
                st.success(f"{msg}，盈亏 {profit:+,.2f}")
                st.rerun()
            else:
                st.error(msg)
    else:
        st.info("暂无持仓，无法卖出。")

    # ---------- 持仓展示 ----------
    st.markdown("---")
    st.markdown("### 📋 当前持仓")

    if holdings_detail:
        df_hold = pd.DataFrame(holdings_detail)
        df_hold["avg_cost"] = df_hold["avg_cost"].round(3)
        df_hold["price"] = df_hold["price"].round(2)
        df_hold["market_value"] = df_hold["market_value"].round(2)
        df_hold["profit"] = df_hold["profit"].round(2)
        df_hold["profit_pct"] = df_hold["profit_pct"].round(2)

        # 重命名列
        df_show = df_hold.rename(columns={
            "code": "代码", "name": "名称", "shares": "持仓",
            "avg_cost": "成本价", "price": "现价",
            "market_value": "市值", "profit": "盈亏", "profit_pct": "盈亏%"
        })

        # 用颜色标记盈亏
        st.dataframe(
            df_show[["代码", "名称", "持仓", "成本价", "现价", "市值", "盈亏", "盈亏%"]],
            use_container_width=True
        )
    else:
        st.info("暂无持仓。")

    # ---------- 交易记录 ----------
    st.markdown("---")
    st.markdown("### 📜 交易记录")

    if st.session_state.sim_history:
        # 只显示最近30条
        recent = list(reversed(st.session_state.sim_history[-30:]))
        for r in recent:
            if r["action"] == "买入":
                st.markdown(
                    f"🔴 **{r['time']}** 买入 **{r['name']}**({r['code']}) "
                    f"{r['shares']}股 @ {r['price']:.2f}，费用 ¥{r['fee']:.2f}"
                )
            else:
                profit = r.get("profit", 0)
                color = "red-text" if profit > 0 else "green-text" if profit < 0 else ""
                st.markdown(
                    f"🟢 **{r['time']}** 卖出 **{r['name']}**({r['code']}) "
                    f"{r['shares']}股 @ {r['price']:.2f}，费用 ¥{r['fee']:.2f}，"
                    f"盈亏 <span class='{color}'>{profit:+.2f}</span>",
                    unsafe_allow_html=True
                )
    else:
        st.info("暂无交易记录。")

    # ---------- 账号寿命说明 ----------
    with st.expander("💡 什么是账号寿命？", expanded=False):
        st.markdown(f"""
        **账号寿命 = 初始可交易次数 - 已使用次数**

        - 初始可交易次数：**{INIT_TRADE_LIMIT} 次**
        - 每次买入或卖出消耗 1 次
        - 用完需点"重置模拟盘"重新开始

        **为什么要限制？**
        1. 训练"交易机会有限"的意识，避免乱交易
        2. 训练"每笔交易都要慎重"的心态
        3. 真实交易中，频繁交易会被手续费吃光利润

        **当前状态**：
        - 已用：{st.session_state.sim_trade_count} 次
        - 剩余：{st.session_state.sim_trade_limit - st.session_state.sim_trade_count} 次
        """)

    # ---------- 手续费说明 ----------
    with st.expander("💰 手续费计算详解", expanded=False):
        st.markdown(f"""
        **A股实际手续费标准**：

        | 费用类型 | 费率 | 收取方向 | 备注 |
        |---------|------|---------|------|
        | 佣金 | 万分之2.5 | 买卖双向 | 最低5元 |
        | 印花税 | 千分之1 | 仅卖出 | 国家税收 |
        | 过户费 | 万分之0.1 | 买卖双向 | 沪深统一 |

        **举例**：买入 ¥10,000 股票
        - 佣金：10,000 × 0.00025 = ¥2.5 → 按最低 ¥5 收
        - 过户费：10,000 × 0.00001 = ¥0.1
        - **买入总费用：¥5.1**

        **举例**：卖出 ¥10,000 股票
        - 佣金：¥5（最低）
        - 印花税：10,000 × 0.001 = ¥10
        - 过户费：¥0.1
        - **卖出总费用：¥15.1**

        **注意**：一买一卖，¥20,000 的交易额，光手续费就 ¥20.2。频繁交易是散户亏钱的重要原因之一。
        """)


# ============================================================
# 第8段结束
# ============================================================# ============================================================
# 第9段：错题本 + 个股分析（技术面）
# ============================================================
# 【本段做什么】
#   模块A：错题本
#     - 从SQLite读取所有错题
#     - 按模块统计数量
#     - 按模块筛选查看
#     - 导出CSV
#     - 清空（按模块/全部）
#
#   模块B：个股分析（技术面）
#     - 输入股票代码，输出技术面综合评分
#     - 短线（5-10天）：看均线、MACD、量价、RSI
#     - 中线（1-3月）：看MA20/MA60、周线趋势、ADX
#     - 长线（半年以上）：看MA60/MA120、历史位置
#     - 支撑位/压力位：用近期高低点识别
#     - ATR止损建议
# ============================================================


# ============================================================
# 模块A：错题本
# ============================================================
def render_wrong_book():
    """渲染'错题本'页面"""
    st.markdown("## 📝 错题本")
    st.markdown("""
    **用途**：所有训练模块答错的题都会自动记录到这里。
    按模块分类查看，重点复习自己的薄弱环节。
    """)

    # ---------- 统计概览 ----------
    stats = get_wrong_stats()

    if stats.empty:
        st.info("🎉 目前没有错题。继续保持！")
        return

    total = int(stats["count"].sum())
    st.markdown(f"### 📊 总计 {total} 道错题")

    # 按模块显示统计
    cols = st.columns(min(5, len(stats)))
    for i, row in stats.iterrows():
        with cols[i % len(cols)]:
            st.metric(row["module"], f"{int(row['count'])} 道")

    # 条形图（用原生st.bar_chart避免额外依赖）
    st.markdown("#### 各模块错题分布")
    chart_df = stats.set_index("module")[["count"]]
    st.bar_chart(chart_df, height=250)

    # ---------- 筛选 ----------
    st.markdown("---")
    st.markdown("### 🔍 筛选查看")

    modules = ["全部"] + list(stats["module"])
    selected_module = st.selectbox("选择模块", modules, key="wrong_filter")

    # ---------- 错题列表 ----------
    df_wrong = get_wrong_list(
        module=None if selected_module == "全部" else selected_module,
        limit=500
    )

    if df_wrong.empty:
        st.info("该模块下没有错题。")
        return

    st.markdown(f"#### 共 {len(df_wrong)} 条记录（按时间倒序）")

    # 逐条展示
    for _, row in df_wrong.iterrows():
        title = f"[{row['module']}] {row['question'][:50]} — {row['timestamp']}"
        with st.expander(title, expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**❌ 你的答案**")
                st.markdown(f"`{row['user_answer']}`")
            with c2:
                st.markdown(f"**✅ 正确答案**")
                st.markdown(f"`{row['correct_answer']}`")

            if row["analysis"] and str(row["analysis"]).strip():
                st.markdown("**📚 详细分析**")
                st.markdown(row["analysis"])

            st.caption(f"记录时间：{row['timestamp']}")

    # ---------- 导出和清空 ----------
    st.markdown("---")
    st.markdown("### 🛠️ 操作")

    c1, c2, c3 = st.columns(3)

    with c1:
        # 导出CSV
        csv = df_wrong.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "📥 导出当前筛选结果为CSV",
            data=csv,
            file_name=f"错题_{selected_module}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with c2:
        if st.button("🗑️ 清空当前模块", use_container_width=True, key="wrong_clear_module"):
            if selected_module == "全部":
                st.warning("请先选择一个具体模块（不能选'全部'）。")
            else:
                clear_wrong(selected_module)
                st.success(f"已清空【{selected_module}】的错题。")
                st.rerun()

    with c3:
        # 二次确认的清空全部
        if "confirm_clear_all" not in st.session_state:
            st.session_state.confirm_clear_all = False

        if not st.session_state.confirm_clear_all:
            if st.button("⚠️ 清空全部错题", use_container_width=True, key="wrong_clear_all_1"):
                st.session_state.confirm_clear_all = True
                st.rerun()
        else:
            st.warning("确定要清空全部错题吗？此操作不可恢复。")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 确定清空", use_container_width=True, key="wrong_confirm"):
                    clear_wrong()
                    st.session_state.confirm_clear_all = False
                    st.success("已清空全部错题。")
                    st.rerun()
            with c2:
                if st.button("❌ 取消", use_container_width=True, key="wrong_cancel"):
                    st.session_state.confirm_clear_all = False
                    st.rerun()


# ============================================================
# 模块B：个股分析（技术面）
# ============================================================
def find_support_resistance(df, lookback=60):
    """
    识别支撑位和压力位。
    方法：在最近lookback根K线中，找出被反复触及的价格区域。
    
    返回：(支撑位列表, 压力位列表) 每个位置是 (价格, 触及次数)
    """
    if df is None or len(df) < 20:
        return [], []

    window = df.tail(lookback).copy()
    current_price = window.iloc[-1]["close"]

    # 收集所有低点和高点
    lows = window["low"].values
    highs = window["high"].values

    # 用聚类思路：把价格按1%的区间分箱，统计出现次数
    def cluster(prices, current):
        bins = {}
        for p in prices:
            if p <= 0:
                continue
            key = round(p / current * 100)  # 以当前价为基准，按1%分箱
            bins.setdefault(key, []).append(p)
        result = []
        for key, vals in bins.items():
            if len(vals) >= 2:  # 至少触及2次
                result.append((sum(vals) / len(vals), len(vals)))
        result.sort(key=lambda x: -x[1])
        return result[:5]

    all_supports = cluster(lows, current_price)
    all_resistances = cluster(highs, current_price)

    # 支撑位：价格低于当前价的；压力位：价格高于当前价的
    supports = sorted([s for s in all_supports if s[0] < current_price * 0.995],
                      key=lambda x: -x[0])
    resistances = sorted([r for r in all_resistances if r[0] > current_price * 1.005],
                         key=lambda x: x[0])

    return supports, resistances


def score_technical(df):
    """
    对个股做技术面综合评分。
    返回：dict 含 short_score, mid_score, long_score, details
    """
    if df is None or len(df) < 60:
        return None

    ind = calc_all_indicators(df, idx=len(df) - 1)
    last_close = ind["last_close"]

    details = {"short": [], "mid": [], "long": []}

    # ========== 短线评分（5-10天）==========
    short_score = 0

    # 1. 价格位置 vs MA5
    if ind["last_close"] > ind["ma5"]:
        short_score += 1
        details["short"].append("+1 价格站上MA5（短期偏强）")
    else:
        short_score -= 1
        details["short"].append("-1 价格跌破MA5（短期偏弱）")

    # 2. MACD状态
    if "多头增强" in ind["macd_status"]:
        short_score += 2
        details["short"].append("+2 MACD多头增强（红柱放大）")
    elif "多头减弱" in ind["macd_status"]:
        short_score += 1
        details["short"].append("+1 MACD多头减弱（红柱缩小）")
    elif "空头增强" in ind["macd_status"]:
        short_score -= 2
        details["short"].append("-2 MACD空头增强（绿柱放大）")
    else:
        short_score -= 1
        details["short"].append("-1 MACD空头减弱（绿柱缩小）")

    # 3. 量价
    if "放量上涨" in ind["vol_price_status"]:
        short_score += 2
        details["short"].append("+2 放量上涨（买盘积极）")
    elif "缩量上涨" in ind["vol_price_status"]:
        short_score += 1
        details["short"].append("+1 缩量上涨（追高意愿不足）")
    elif "放量下跌" in ind["vol_price_status"]:
        short_score -= 2
        details["short"].append("-2 放量下跌（抛压重）")
    elif "缩量下跌" in ind["vol_price_status"]:
        short_score -= 1
        details["short"].append("-1 缩量下跌（抛压减轻）")

    # 4. RSI
    if ind["rsi"] > 70:
        short_score -= 1
        details["short"].append("-1 RSI超买（短期回调风险）")
    elif ind["rsi"] < 30:
        short_score += 1
        details["short"].append("+1 RSI超卖（短期反弹机会）")

    # 5. KDJ-J值
    if ind["j_val"] > 100:
        short_score -= 1
        details["short"].append("-1 KDJ-J超买")
    elif ind["j_val"] < 0:
        short_score += 1
        details["short"].append("+1 KDJ-J超卖")

    # 6. 5日涨幅（避免追高）
    if ind["pct_5d"] > 8:
        short_score -= 1
        details["short"].append(f"-1 5日涨幅{ind['pct_5d']:.1f}%（短期过热）")
    elif ind["pct_5d"] < -8:
        short_score += 1
        details["short"].append(f"+1 5日跌幅{ind['pct_5d']:.1f}%（短期超跌）")

    # ========== 中线评分（1-3月）==========
    mid_score = 0

    # 1. 均线排列
    if "多头排列" in ind["ma_alignment"]:
        mid_score += 2
        details["mid"].append("+2 均线多头排列（中期强势）")
    elif "空头排列" in ind["ma_alignment"]:
        mid_score -= 2
        details["mid"].append("-2 均线空头排列（中期弱势）")
    else:
        details["mid"].append("0 均线交织（中期震荡）")

    # 2. MA20 vs MA60
    if ind["ma20"] > ind["ma60"]:
        mid_score += 1
        details["mid"].append("+1 MA20 > MA60（中期向上）")
    else:
        mid_score -= 1
        details["mid"].append("-1 MA20 < MA60（中期向下）")

    # 3. ADX（趋势强度）
    if ind["adx"] > 40:
        if ind["ma20"] > ind["ma60"]:
            mid_score += 2
            details["mid"].append(f"+2 ADX={ind['adx']:.1f}，强上涨趋势")
        else:
            mid_score -= 2
            details["mid"].append(f"-2 ADX={ind['adx']:.1f}，强下跌趋势")
    elif ind["adx"] > 25:
        if ind["ma20"] > ind["ma60"]:
            mid_score += 1
            details["mid"].append(f"+1 ADX={ind['adx']:.1f}，中等上涨趋势")
        else:
            mid_score -= 1
            details["mid"].append(f"-1 ADX={ind['adx']:.1f}，中等下跌趋势")
    else:
        details["mid"].append(f"0 ADX={ind['adx']:.1f}，趋势弱（震荡市）")

    # 4. 20日涨幅
    if len(df) >= 21:
        pct_20 = (last_close - df["close"].iloc[-21]) / df["close"].iloc[-21] * 100
        if pct_20 > 15:
            mid_score -= 1
            details["mid"].append(f"-1 20日涨幅{pct_20:.1f}%（中期过热）")
        elif pct_20 < -15:
            mid_score += 1
            details["mid"].append(f"+1 20日跌幅{pct_20:.1f}%（中期超跌）")

    # 5. 布林带位置
    if "触及下轨" in ind["boll_status"]:
        mid_score += 1
        details["mid"].append("+1 触及布林下轨（中期支撑）")
    elif "触及上轨" in ind["boll_status"]:
        mid_score -= 1
        details["mid"].append("-1 触及布林上轨（中期压力）")

    # ========== 长线评分（半年以上）==========
    long_score = 0

    # 1. 价格 vs MA60 / MA120
    if len(df) >= 120:
        ma120 = df["close"].rolling(120).mean().iloc[-1]
    else:
        ma120 = ind["ma60"]

    if last_close > ind["ma60"] > ma120:
        long_score += 2
        details["long"].append("+2 价格 > MA60 > MA120（长期上升通道）")
    elif last_close > ind["ma60"]:
        long_score += 1
        details["long"].append("+1 价格站上MA60（长期偏强）")
    elif last_close < ind["ma60"] < ma120:
        long_score -= 2
        details["long"].append("-2 价格 < MA60 < MA120（长期下降通道）")
    else:
        long_score -= 1
        details["long"].append("-1 价格跌破MA60（长期偏弱）")

    # 2. 历史位置（250日分位）
    if len(df) >= 60:
        year_high = df["high"].tail(250).max()
        year_low = df["low"].tail(250).min()
        rng = year_high - year_low
        if rng > 0:
            pos_pct = (last_close - year_low) / rng * 100
            if pos_pct > 80:
                long_score -= 1
                details["long"].append(f"-1 处于近1年高位（{pos_pct:.0f}%分位）")
            elif pos_pct < 20:
                long_score += 1
                details["long"].append(f"+1 处于近1年低位（{pos_pct:.0f}%分位）")
            else:
                details["long"].append(f"0 处于近1年中位（{pos_pct:.0f}%分位）")

    # 3. 长期波动率（ATR占比）
    atr_pct = ind["atr"] / last_close * 100
    if atr_pct > 5:
        details["long"].append(f"-1 波动率高（ATR占比{atr_pct:.1f}%，长期风险大）")
        long_score -= 1
    elif atr_pct < 2:
        details["long"].append(f"+1 波动率低（ATR占比{atr_pct:.1f}%，长期稳健）")
        long_score += 1

    return {
        "short_score": short_score,
        "mid_score": mid_score,
        "long_score": long_score,
        "details": details,
        "ind": ind,
        "last_close": last_close,
        "atr": ind["atr"],
    }


def render_stock_analysis():
    """渲染'个股分析（技术面）'页面"""
    st.markdown("## 📈 个股分析（技术面）")
    st.markdown("""
    **用途**：输入股票代码，系统从技术面给出短/中/长线三档评分。

    **评分说明**：
    - **短线（5-10天）**：看MA5、MACD、量价、RSI、KDJ
    - **中线（1-3月）**：看MA20/MA60、ADX、布林带
    - **长线（半年以上）**：看MA60/MA120、历史分位、波动率

    **每档评分**：
    - ≥+4：强烈看多 | +1~+3：偏多 | 0：中性 | -1~-3：偏空 | ≤-4：强烈看空
    """)

    # 输入区
    c1, c2 = st.columns([2, 1])
    with c1:
        code_input = st.text_input(
            "输入6位股票代码（如 600519 贵州茅台）",
            value="600519",
            key="analysis_code"
        )
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        analyze_btn = st.button("🔍 开始分析", type="primary", use_container_width=True,
                                key="analysis_btn")

    if analyze_btn:
        code_input = code_input.strip()
        if not code_input.isdigit() or len(code_input) != 6:
            st.error("请输入6位数字股票代码。")
            return

        with st.spinner(f"正在分析 {code_input}..."):
            df = fetch_daily(code_input, days=250)
            if df is None or len(df) < 60:
                st.error(f"无法获取 {code_input} 的数据，请检查代码是否正确或稍后重试。")
                return

            result = score_technical(df)
            if result is None:
                st.error("数据不足，无法分析。")
                return

            st.session_state.analysis_result = {
                "code": code_input,
                "name": get_stock_name(code_input),
                "df": df,
                "result": result,
            }

    # 显示结果
    if "analysis_result" not in st.session_state:
        st.info("👆 输入股票代码，点击'开始分析'。")
        return

    data = st.session_state.analysis_result
    df = data["df"]
    result = data["result"]
    ind = result["ind"]
    code = data["code"]
    name = data["name"]

    # ---------- K线图 ----------
    st.markdown(f"### {code} {name}")
    fig = plot_kline(df.tail(120), title=f"{code} {name}",
                     show_ma=True, show_volume=True, height=500)
    st.plotly_chart(fig, use_container_width=True)

    # ---------- 当前基础数据 ----------
    st.markdown("### 📊 基础数据")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("当前价", f"{result['last_close']:.2f}",
              delta=f"{ind['pct_change']:+.2f}%")
    c2.metric("ATR(14)", f"{result['atr']:.2f}",
              delta=f"{result['atr'] / result['last_close'] * 100:.2f}%")
    c3.metric("MA20", f"{ind['ma20']:.2f}")
    c4.metric("MA60", f"{ind['ma60']:.2f}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("均线排列", ind["ma_alignment"])
    c2.metric("MACD", ind["macd_status"], delta=ind["macd_cross"])
    c3.metric("RSI", f"{ind['rsi']:.1f}", delta=ind["rsi_status"])
    c4.metric("量价", ind["vol_price_status"])

    # ---------- 三档评分 ----------
    st.markdown("---")
    st.markdown("### 🎯 三档评分")

    def score_to_label(s):
        if s >= 4:
            return "强烈看多", "success"
        elif s >= 1:
            return "偏多", "info"
        elif s == 0:
            return "中性", "info"
        elif s >= -3:
            return "偏空", "warning"
        else:
            return "强烈看空", "error"

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("#### 📈 短线（5-10天）")
        label, _ = score_to_label(result["short_score"])
        st.metric("短线评分", f"{result['short_score']:+d}", delta=label)
        for d in result["details"]["short"]:
            st.markdown(f"- {d}")

    with c2:
        st.markdown("#### 📊 中线（1-3月）")
        label, _ = score_to_label(result["mid_score"])
        st.metric("中线评分", f"{result['mid_score']:+d}", delta=label)
        for d in result["details"]["mid"]:
            st.markdown(f"- {d}")

    with c3:
        st.markdown("#### 🏛️ 长线（半年以上）")
        label, _ = score_to_label(result["long_score"])
        st.metric("长线评分", f"{result['long_score']:+d}", delta=label)
        for d in result["details"]["long"]:
            st.markdown(f"- {d}")

    # ---------- 综合建议 ----------
    st.markdown("---")
    st.markdown("### 💡 综合建议")

    short_s = result["short_score"]
    mid_s = result["mid_score"]
    long_s = result["long_score"]

    if short_s >= 3 and mid_s >= 3:
        st.success("🚀 **短线+中线共振看多**：可以考虑积极介入，止损设近5日低点下方。")
    elif short_s >= 2 and mid_s <= -2:
        st.warning("⚠️ **短线反弹但中线弱势**：只适合快进快出，不要恋战。")
    elif short_s <= -2 and mid_s >= 2:
        st.info("📉 **短线回调但中线向好**：可能是上车机会，等短线企稳信号再买。")
    elif short_s <= -3 and mid_s <= -3:
        st.error("🔻 **短中线共振看空**：建议规避，持仓的考虑止损。")
    else:
        st.info("⚪ **信号不明确**：建议观望，等方向明朗再操作。")

    if long_s >= 3:
        st.success("🏛️ **长线趋势向上**：适合作为底仓长期持有。")
    elif long_s <= -3:
        st.error("🏛️ **长线趋势向下**：不适合长线持有，短线参与也要快进快出。")

    # ---------- 支撑压力位 ----------
    st.markdown("---")
    st.markdown("### 📍 支撑位与压力位")

    supports, resistances = find_support_resistance(df, lookback=60)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🔵 支撑位（下方买盘）")
        if supports:
            for price, count in supports[:3]:
                dist = (price - result["last_close"]) / result["last_close"] * 100
                st.markdown(f"- **¥{price:.2f}**（触及{count}次，距现价 {dist:+.2f}%）")
        else:
            st.caption("近期未识别出明显支撑位。")

    with c2:
        st.markdown("#### 🔴 压力位（上方卖盘）")
        if resistances:
            for price, count in resistances[:3]:
                dist = (price - result["last_close"]) / result["last_close"] * 100
                st.markdown(f"- **¥{price:.2f}**（触及{count}次，距现价 {dist:+.2f}%）")
        else:
            st.caption("近期未识别出明显压力位。")

    # ---------- ATR止损建议 ----------
    st.markdown("---")
    st.markdown("### 🛡️ ATR止损建议")

    last_close = result["last_close"]
    atr = result["atr"]

    # 三种止损
    stop_tight = last_close - 0.8 * atr
    stop_normal = last_close - 1.5 * atr
    stop_loose = last_close - 2.0 * atr

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("保守止损（0.8×ATR）", f"{stop_tight:.2f}",
                  delta=f"{(stop_tight - last_close) / last_close * 100:.2f}%")
        st.caption("适合短线，保护严格，但易被震出局。")
    with c2:
        st.metric("标准止损（1.5×ATR）", f"{stop_normal:.2f}",
                  delta=f"{(stop_normal - last_close) / last_close * 100:.2f}%")
        st.caption("适合大多数情况，平衡保护和容错。")
    with c3:
        st.metric("宽松止损（2.0×ATR）", f"{stop_loose:.2f}",
                  delta=f"{(stop_loose - last_close) / last_close * 100:.2f}%")
        st.caption("适合中长线，容错大但单次亏损也大。")

    # 可视化止损位
    st.markdown("#### 📊 止损位置可视化")
    fig2 = go.Figure()
    levels = [
        ("当前价", last_close, "#ffcc00", 2),
        ("保守止损", stop_tight, "#00aaff", 2),
        ("标准止损", stop_normal, "#ff88cc", 2),
        ("宽松止损", stop_loose, "#ff4444", 2),
    ]
    for name_, price_, color_, width_ in levels:
        fig2.add_hline(y=price_, line_color=color_, line_width=width_,
                       annotation_text=f"{name_} {price_:.2f}",
                       annotation_position="right")
    fig2.update_layout(
        height=300, template="plotly_white",
        title="止损价位参考",
        yaxis_title="价格",
        xaxis=dict(showticklabels=False),
        showlegend=False,
    )
    st.plotly_chart(fig2, use_container_width=True)


# ============================================================
# 第9段结束
# ============================================================# ============================================================
# 第10段：个股分析（基本面）
# ============================================================
# 【本段做什么】
#   1. 获取个股估值数据：PE（市盈率）、PB（市净率）
#   2. 获取盈利数据：ROE（净资产收益率）
#   3. 行业平均对比
#   4. 基本面打分（0-10分）
#   5. 与技术面结合，给出最终建议
#
# 【数据来源】
#   优先同花顺API，失败自动切AkShare。
#   AkShare的 stock_a_indicator_lg 提供PE/PB；
#   stock_financial_analysis_indicator 提供ROE等财务指标。
#
# 【基本面评分逻辑】
#   PE：越低越好（但要排除亏损股）
#   PB：越低越好（但金融股PB天然低）
#   ROE：越高越好（>15%优秀，>20%极佳）
#   综合成0-10分
# ============================================================

# 行业平均PE参考值（A股历史大致水平，仅用于快速对比）
INDUSTRY_PE_REF = {
    "白酒": 30, "银行": 6, "券商": 20, "保险": 12,
    "房地产": 10, "安防": 25, "面板显示": 20,
    "锂电池": 30, "新能源车": 25, "光伏": 25,
    "医药": 30, "食品饮料": 25, "家电": 15,
    "化工": 15, "建材": 12, "电力": 18,
    "煤炭": 10, "养殖": 15,
}

INDUSTRY_PB_REF = {
    "白酒": 6, "银行": 0.8, "券商": 1.5, "保险": 1.2,
    "房地产": 1.0, "安防": 3, "面板显示": 1.5,
    "锂电池": 3, "新能源车": 3, "光伏": 3,
    "医药": 4, "食品饮料": 3, "家电": 2,
    "化工": 2, "建材": 1.5, "电力": 1.5,
    "煤炭": 1.2, "养殖": 2.5,
}


# ------------------------------------------------------------
# 获取基本面数据
# ------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fundamentals(code: str):
    """
    获取个股基本面数据。
    返回：dict 或 None
        {
            "pe": 市盈率, "pb": 市净率, "roe": 净资产收益率,
            "total_mv": 总市值, "name": 股票名称, "industry": 行业,
        }
    """
    result = {
        "pe": None, "pb": None, "roe": None,
        "total_mv": None, "industry": get_industry(code),
        "name": get_stock_name(code),
    }

    # ---------- 方案A：AkShare 获取估值 ----------
    try:
        import akshare as ak

        # 1) 实时估值（PE、PB、市值）
        try:
            df_spot = ak.stock_zh_a_spot_em()
            row = df_spot[df_spot["代码"] == code]
            if not row.empty:
                row = row.iloc[0]
                result["name"] = str(row.get("名称", result["name"]))
                result["pe"] = safe_float(row.get("市盈率-动态", None))
                result["pb"] = safe_float(row.get("市净率", None))
                result["total_mv"] = safe_float(row.get("总市值", None))
        except Exception:
            pass

        # 2) ROE（从财务指标获取最近一期）
        try:
            df_fin = ak.stock_financial_analysis_indicator(symbol=code, start_year="2023")
            if df_fin is not None and not df_fin.empty:
                # 找ROE列
                roe_col = None
                for col in df_fin.columns:
                    if "净资产收益率" in str(col):
                        roe_col = col
                        break
                if roe_col:
                    latest = df_fin.iloc[0][roe_col]
                    result["roe"] = safe_float(latest)
        except Exception:
            pass

    except ImportError:
        pass

    # 如果PE和PB都拿不到，返回None
    if result["pe"] is None and result["pb"] is None:
        return None

    return result


# ------------------------------------------------------------
# 基本面评分
# ------------------------------------------------------------
def score_fundamentals(fund: dict):
    """
    对基本面打分（0-10分）。
    返回：dict 含 total_score, details
    """
    if fund is None:
        return None

    score = 0
    max_score = 0
    details = []

    pe = fund.get("pe")
    pb = fund.get("pb")
    roe = fund.get("roe")
    industry = fund.get("industry", "未知")

    # ---------- PE评分（0-3分）----------
    max_score += 3
    if pe is not None and pe > 0:
        pe_ref = INDUSTRY_PE_REF.get(industry, 20)
        if pe < pe_ref * 0.6:
            score += 3
            details.append(f"+3 PE={pe:.1f}，显著低于行业参考{pe_ref}（低估）")
        elif pe < pe_ref * 1.0:
            score += 2
            details.append(f"+2 PE={pe:.1f}，低于行业参考{pe_ref}（合理偏低）")
        elif pe < pe_ref * 1.5:
            score += 1
            details.append(f"+1 PE={pe:.1f}，略高于行业参考{pe_ref}（合理）")
        else:
            details.append(f"+0 PE={pe:.1f}，显著高于行业参考{pe_ref}（高估）")
    elif pe is not None and pe <= 0:
        details.append("+0 PE为负，公司亏损（基本面风险）")
    else:
        details.append("+0 PE数据缺失")

    # ---------- PB评分（0-3分）----------
    max_score += 3
    if pb is not None and pb > 0:
        pb_ref = INDUSTRY_PB_REF.get(industry, 2)
        if pb < pb_ref * 0.6:
            score += 3
            details.append(f"+3 PB={pb:.2f}，显著低于行业参考{pb_ref}（低估）")
        elif pb < pb_ref * 1.0:
            score += 2
            details.append(f"+2 PB={pb:.2f}，低于行业参考{pb_ref}（合理偏低）")
        elif pb < pb_ref * 1.5:
            score += 1
            details.append(f"+1 PB={pb:.2f}，略高于行业参考{pb_ref}（合理）")
        else:
            details.append(f"+0 PB={pb:.2f}，显著高于行业参考{pb_ref}（高估）")
    else:
        details.append("+0 PB数据缺失")

    # ---------- ROE评分（0-4分）----------
    max_score += 4
    if roe is not None:
        if roe >= 20:
            score += 4
            details.append(f"+4 ROE={roe:.1f}%，极佳（长期赚钱能力强）")
        elif roe >= 15:
            score += 3
            details.append(f"+3 ROE={roe:.1f}%，优秀")
        elif roe >= 10:
            score += 2
            details.append(f"+2 ROE={roe:.1f}%，良好")
        elif roe >= 5:
            score += 1
            details.append(f"+1 ROE={roe:.1f}%，一般")
        else:
            details.append(f"+0 ROE={roe:.1f}%，偏低（盈利能力弱）")
    else:
        details.append("+0 ROE数据缺失")

    return {
        "total_score": score,
        "max_score": max_score,
        "details": details,
        "pe": pe, "pb": pb, "roe": roe,
        "industry": industry,
    }


def render_fundamental_analysis():
    """渲染'个股分析（基本面）'页面"""
    st.markdown("## 🏛️ 个股分析（基本面）")
    st.markdown("""
    **用途**：输入股票代码，系统从基本面给出评分。

    **三个核心指标**：
    - **PE（市盈率）**：股价 / 每股收益。越低越便宜，但太低可能反映市场不看好
    - **PB（市净率）**：股价 / 每股净资产。适合重资产行业（银行、地产）
    - **ROE（净资产收益率）**：净利润 / 净资产。**这是巴菲特最看重的指标**，>15%是优秀公司

    **评分逻辑**：PE+PB+ROE 综合成 **0-10分**，结合行业参考值判断贵贱。
    """)

    # 输入区
    c1, c2 = st.columns([2, 1])
    with c1:
        code_input = st.text_input(
            "输入6位股票代码（如 600519 贵州茅台）",
            value="600519",
            key="fund_code"
        )
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        analyze_btn = st.button("🔍 开始分析", type="primary", use_container_width=True,
                                key="fund_btn")

    if analyze_btn:
        code_input = code_input.strip()
        if not code_input.isdigit() or len(code_input) != 6:
            st.error("请输入6位数字股票代码。")
            return

        with st.spinner(f"正在获取 {code_input} 的基本面数据..."):
            fund = fetch_fundamentals(code_input)
            if fund is None:
                st.error("无法获取基本面数据。可能是网络问题，或该股票不在当前数据源覆盖范围内。")
                return
            score_result = score_fundamentals(fund)
            st.session_state.fund_result = {
                "code": code_input,
                "fund": fund,
                "score": score_result,
            }

    # 显示结果
    if "fund_result" not in st.session_state:
        st.info("👆 输入股票代码，点击'开始分析'。")
        return

    data = st.session_state.fund_result
    fund = data["fund"]
    score_result = data["score"]
    code = data["code"]

    # ---------- 顶部：基本信息 ----------
    st.markdown(f"### {code} {fund['name']}")
    st.caption(f"所属行业：**{fund['industry']}**")

    # ---------- 核心指标卡片 ----------
    st.markdown("### 📊 核心估值指标")
    c1, c2, c3, c4 = st.columns(4)

    pe = fund.get("pe")
    pb = fund.get("pb")
    roe = fund.get("roe")
    mv = fund.get("total_mv")

    with c1:
        if pe is not None:
            pe_ref = INDUSTRY_PE_REF.get(fund["industry"], 20)
            delta_str = f"行业参考{pe_ref}"
            st.metric("PE（市盈率）", f"{pe:.2f}", delta=delta_str)
        else:
            st.metric("PE（市盈率）", "无数据")

    with c2:
        if pb is not None:
            pb_ref = INDUSTRY_PB_REF.get(fund["industry"], 2)
            delta_str = f"行业参考{pb_ref}"
            st.metric("PB（市净率）", f"{pb:.2f}", delta=delta_str)
        else:
            st.metric("PB（市净率）", "无数据")

    with c3:
        if roe is not None:
            st.metric("ROE（净资产收益率）", f"{roe:.2f}%",
                      delta="优秀" if roe >= 15 else "一般" if roe >= 10 else "偏低")
        else:
            st.metric("ROE", "无数据")

    with c4:
        if mv is not None and mv > 0:
            mv_yi = mv / 1e8
            st.metric("总市值", f"{mv_yi:.0f} 亿")
        else:
            st.metric("总市值", "无数据")

    # ---------- 基本面评分 ----------
    st.markdown("---")
    st.markdown("### 🎯 基本面评分")

    total = score_result["total_score"]
    max_s = score_result["max_score"]

    if max_s > 0:
        pct = total / max_s * 100
    else:
        pct = 0

    # 显示分数
    c1, c2 = st.columns([1, 3])
    with c1:
        st.metric("基本面评分", f"{total}/{max_s}", delta=f"{pct:.0f}%")

    with c2:
        if pct >= 80:
            st.success("🌟 **优秀**：基本面非常扎实，适合长期持有。")
        elif pct >= 60:
            st.info("✅ **良好**：基本面稳健，可以配置。")
        elif pct >= 40:
            st.warning("⚪ **一般**：基本面普通，需要谨慎。")
        else:
            st.error("⚠️ **较差**：基本面偏弱，不建议长期持有。")

    # 评分明细
    st.markdown("#### 📋 评分明细")
    for d in score_result["details"]:
        st.markdown(f"- {d}")

    # ---------- 行业对比 ----------
    st.markdown("---")
    st.markdown("### 🏭 行业对比")

    industry = fund["industry"]
    if industry in INDUSTRY_PE_REF:
        pe_ref = INDUSTRY_PE_REF[industry]
        pb_ref = INDUSTRY_PB_REF.get(industry, 2)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**PE对比**")
            st.markdown(f"- 本股PE：{pe:.2f}" if pe else "- 本股PE：无数据")
            st.markdown(f"- {industry}行业参考PE：{pe_ref}")
            if pe and pe > 0:
                if pe < pe_ref:
                    st.info(f"👉 本股PE低于行业参考，估值相对便宜。")
                else:
                    st.warning(f"👉 本股PE高于行业参考，估值相对偏贵。")

        with c2:
            st.markdown(f"**PB对比**")
            st.markdown(f"- 本股PB：{pb:.2f}" if pb else "- 本股PB：无数据")
            st.markdown(f"- {industry}行业参考PB：{pb_ref}")
            if pb and pb > 0:
                if pb < pb_ref:
                    st.info(f"👉 本股PB低于行业参考，估值相对便宜。")
                else:
                    st.warning(f"👉 本股PB高于行业参考，估值相对偏贵。")

        st.caption("💡 行业参考值是A股历史大致水平，仅供参考，不作为投资依据。")
    else:
        st.caption(f"暂未收录 {industry} 行业的参考数据。")

    # ---------- 与技术面结合 ----------
    st.markdown("---")
    st.markdown("### 🔗 技术面 + 基本面 综合")

    if "analysis_result" in st.session_state:
        tech = st.session_state.analysis_result
        if tech["code"] == code:
            tech_res = tech["result"]
            short_s = tech_res["short_score"]
            mid_s = tech_res["mid_score"]
            long_s = tech_res["long_score"]
            fund_pct = pct

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("短线", f"{short_s:+d}")
            c2.metric("中线", f"{mid_s:+d}")
            c3.metric("长线", f"{long_s:+d}")
            c4.metric("基本面", f"{fund_pct:.0f}%")

            # 综合判断
            st.markdown("#### 🎯 综合建议")
            tech_good = (short_s + mid_s) >= 3
            fund_good = fund_pct >= 60

            if tech_good and fund_good:
                st.success("🌟 **技术面+基本面双优**：这是最理想的标的，适合中长期持有。")
            elif tech_good and not fund_good:
                st.warning("⚠️ **技术面强但基本面弱**：只适合短线快进快出，不要长期持有。")
            elif not tech_good and fund_good:
                st.info("📈 **基本面好但技术面弱**：可能是价值洼地，适合分批建仓，等趋势转好。")
            else:
                st.error("🔻 **技术面+基本面双弱**：建议规避。")
        else:
            st.info("💡 请先在第9段'个股分析（技术面）'里分析同一只股票，才能看到综合对比。")
    else:
        st.info("💡 先在第9段'个股分析（技术面）'里分析同一只股票，就能在这里看到技术面+基本面的综合对比。")

    # ---------- 风险提示 ----------
    st.markdown("---")
    with st.expander("⚠️ 基本面分析的局限（必读）", expanded=False):
        st.markdown("""
        **基本面分析的常见陷阱**：

        1. **PE低≠便宜**：周期股（煤炭、钢铁）在盈利顶点时PE很低，但往往是卖点。
        2. **PE高≠贵**：成长股（新能源、医药）PE高是因为市场预期未来高增长。
        3. **PB不能跨行业比**：银行PB<1是常态，白酒PB>5也正常。
        4. **ROE要看持续性**：一年ROE高没意义，要看5年以上的平均水平。
        5. **财报有滞后性**：你现在看到的ROE是过去的数据，不代表未来。
        6. **财务造假风险**：数据再好看，也要警惕康美药业、瑞幸咖啡这样的案例。

        **结论**：基本面是"选股"的重要参考，但**必须结合技术面择时**。
        """)

    # ---------- 数据来源说明 ----------
    st.caption("📌 数据来源：AkShare（东方财富公开数据）。PE/PB为实时估值，ROE为最近一期财报数据。")


# ============================================================
# 第10段结束
# ============================================================# ============================================================
# 第11段：主入口 + 页面导航
# ============================================================
# 【本段做什么】
#   1. 用 st.sidebar 做一个菜单，切换11个模块
#   2. 在 sidebar 显示各模块成绩
#   3. 顶部显示欢迎信息和免责声明
#   4. 统一入口，手机/电脑都能用
#
# 【为什么用 sidebar 菜单而不是 tabs】
#   - 手机上 tabs 会挤成一团，不好点
#   - sidebar 在手机上折叠后是一个汉堡菜单，体验好
#   - sidebar 可以固定显示成绩统计
# ============================================================


def render_sidebar():
    """渲染侧边栏菜单和成绩统计"""
    with st.sidebar:
        st.markdown("# ⚔️ K线训练器")
        st.markdown("*股市肌肉记忆训练*")
        st.markdown("---")

        # ---------- 菜单 ----------
        st.markdown("### 📋 选择训练模块")
        menu_options = [
            "📊 形态识别",
            "⚡ 分时实战",
            "🏭 板块认知",
            "🎯 买卖点判断",
            "🛡️ 止损训练",
            "🔮 未来趋势",
            "💰 仓位管理",
            "🌍 大盘趋势",
            "💼 模拟盘",
            "📝 错题本",
            "📈 个股分析",
        ]

        selected = st.radio(
            "选择训练模块",
            menu_options,
            label_visibility="collapsed",
            key="main_menu"
        )

        st.markdown("---")

        # ---------- 成绩统计 ----------
        st.markdown("### 📊 我的成绩")

        # 各模块的成绩保存在 session_state 里
        score_mapping = [
            ("形态识别", "pat_score"),
            ("分时实战", "intra_score"),
            ("板块认知", "sector_score"),
            ("买卖点判断", "trade_score"),
            ("止损训练", "stop_score"),
            ("未来趋势", "trend_score"),
            ("仓位管理", "pos_score"),
            ("大盘趋势", "market_score"),
        ]

        any_score = False
        total_correct = 0
        total_answered = 0

        for label, key in score_mapping:
            sc = st.session_state.get(key)
            if sc and sc.get("total", 0) > 0:
                any_score = True
                rate = sc["correct"] / sc["total"] * 100
                total_correct += sc["correct"]
                total_answered += sc["total"]
                # 用颜色标记正确率
                if rate >= 70:
                    emoji = "🟢"
                elif rate >= 50:
                    emoji = "🟡"
                else:
                    emoji = "🔴"
                st.markdown(f"{emoji} **{label}**：{sc['correct']}/{sc['total']}（{rate:.0f}%）")

        if not any_score:
            st.caption("还没有答题记录，快去训练吧！")
        else:
            st.markdown("---")
            overall = total_correct / total_answered * 100 if total_answered > 0 else 0
            st.metric("总正确率", f"{overall:.1f}%",
                      delta=f"共 {total_answered} 题")

        # ---------- 错题数 ----------
        st.markdown("---")
        try:
            stats = get_wrong_stats()
            if not stats.empty:
                total_wrong = int(stats["count"].sum())
                st.metric("📝 错题总数", f"{total_wrong} 道")
            else:
                st.caption("📝 暂无错题")
        except Exception:
            st.caption("📝 错题本加载中...")

        # ---------- 底部信息 ----------
        st.markdown("---")
        st.caption("⚠️ 本工具仅供学习训练，不构成投资建议。")
        st.caption(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    return selected


def render_welcome():
    """欢迎页：显示使用说明"""
    st.markdown("# ⚔️ 欢迎使用K线肌肉训练器")
    st.markdown("""
    这是一个专为A股投资者设计的**实战训练工具**。

    ---

    ### 🎯 训练模块介绍

    | 模块 | 训练目标 |
    |------|---------|
    | 📊 **形态识别** | 从历史K线中识别真实形态，建立"看图识形"的肌肉记忆 |
    | ⚡ **分时实战** | 判断下一根5分钟K线涨跌，训练盘感 |
    | 🏭 **板块认知** | 看代码识别所属行业，理解板块轮动 |
    | 🎯 **买卖点判断** | 识别典型买卖场景，知道什么时候该出手 |
    | 🛡️ **止损训练** | 学会用ATR设置合理止损 |
    | 🔮 **未来趋势** | 判断未来3天方向，逐指标复盘 |
    | 💰 **仓位管理** | 结合信号强度、大盘环境、月份季节性定仓位 |
    | 🌍 **大盘趋势** | 判断大盘状态，理解"大盘决定80%个股" |
    | 💼 **模拟盘** | 用虚拟资金完整练习交易，含真实手续费 |
    | 📝 **错题本** | 自动记录所有错题，按模块统计 |
    | 📈 **个股分析** | 技术面+基本面综合评分 |

    ---

    ### 💡 使用建议

    1. **新手顺序**：形态识别 → 分时实战 → 买卖点判断 → 止损训练 → 仓位管理
    2. **进阶顺序**：未来趋势 → 大盘趋势 → 板块认知 → 个股分析 → 模拟盘
    3. **日常习惯**：每天做10-20题，重点复盘错题本
    4. **最重要**：**每天都要过一遍错题本**，直到全部答对为止

    ---

    ### 📌 核心原则

    - ✅ **只练真实出现过的形态**（系统自动从历史K线中检测）
    - ✅ **答错自动记录到错题本**（SQLite持久化，刷新不丢）
    - ✅ **红涨绿跌**（符合A股习惯）
    - ✅ **数据来源**：同花顺API为主，AkShare为备用

    ---

    ⚠️ **免责声明**：本工具仅供学习训练，所有分析不构成投资建议。
    股市有风险，投资需谨慎。

    ---

    👈 **从左侧菜单选择一个模块开始训练吧！**
    """)


def main():
    """主入口函数"""
    # 先初始化错误本数据库（第1段里已经init_db，这里再保险一次）
    try:
        init_db()
    except Exception:
        pass

    # 渲染侧边栏，获取用户选择
    selected = render_sidebar()

    # 根据选择路由到对应模块
    if selected == "📊 形态识别":
        render_pattern_training()
    elif selected == "⚡ 分时实战":
        render_intraday_training()
    elif selected == "🏭 板块认知":
        render_sector_training()
    elif selected == "🎯 买卖点判断":
        render_trade_training()
    elif selected == "🛡️ 止损训练":
        render_stop_training()
    elif selected == "🔮 未来趋势":
        render_trend_training()
    elif selected == "💰 仓位管理":
        render_position_training()
    elif selected == "🌍 大盘趋势":
        render_market_trend()
    elif selected == "💼 模拟盘":
        render_simulation()
    elif selected == "📝 错题本":
        render_wrong_book()
    elif selected == "📈 个股分析":
        # 个股分析有两个子页面：技术面 + 基本面，用tab展示
        st.markdown("## 📈 个股分析")
        sub_tab1, sub_tab2 = st.tabs(["技术面分析", "基本面分析"])
        with sub_tab1:
            render_stock_analysis()
        with sub_tab2:
            render_fundamental_analysis()
    else:
        render_welcome()


# ============================================================
# 程序入口
# ============================================================
if __name__ == "__main__":
    main()


# ============================================================
# 第11段结束
# ============================================================
