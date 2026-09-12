import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import random
import requests
from datetime import datetime, timedelta
import numpy as np

st.set_page_config(page_title="K线训练器", layout="wide")
st.title("⚔️ K线综合训练器")
st.caption("形态 | 分时 | 板块 | 买卖点 | 止损 | 未来趋势 | 仓位 | 大盘 | 模拟盘 | 错题本")

API_KEY = st.secrets["TONGHUASHUN_API_KEY"]

STOCK_POOL = [
    "600519", "000858", "600036", "000002", "002415",
    "600276", "000651", "601318", "600030", "000725",
    "600900", "601166", "600887", "600309", "600585",
    "000333", "000568", "002594", "300750", "600809"
]

INDUSTRY_MAP = {
    "600519": "白酒", "000858": "白酒", "000568": "白酒", "600809": "白酒",
    "600036": "银行", "601166": "银行", "600030": "券商", "601318": "保险",
    "000002": "房地产",
    "002415": "安防", "000725": "面板显示", "300750": "锂电池", "002594": "新能源车",
    "600276": "医药", "600887": "食品饮料", "000333": "家电", "000651": "家电",
    "600309": "化工", "600585": "建材", "600900": "电力"
}
ALL_INDUSTRIES = list(set(INDUSTRY_MAP.values()))

def fetch_daily(symbol):
    if symbol.startswith("60") or symbol.startswith("68"):
        code = symbol + ".SH"
    else:
        code = symbol + ".SZ"
    url = "https://fuyao.aicubes.cn/api/a-share/prices/historical"
    headers = {"X-api-key": API_KEY}
    end_date = datetime.now()
    start_date = end_date - timedelta(days=200)
    params = {
        "thscode": code, "interval": "1d",
        "start": int(start_date.timestamp() * 1000),
        "end": int(end_date.timestamp() * 1000),
        "adjust": "forward"
    }
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("code") == 0:
                items = data.get("data", {}).get("item", [])
                if items:
                    df = pd.DataFrame(items)
                    df = df.rename(columns={
                        "date_ms": "date", "open_price": "open", "high_price": "high",
                        "low_price": "low", "close_price": "close", "volume": "volume"
                    })
                    df["date"] = pd.to_datetime(df["date"], unit="ms")
                    return df[["date", "open", "high", "low", "close", "volume"]]
        return None
    except Exception:
        return None

def generate_intraday_from_multiple_days(daily_df, num_days=7, bars_per_day=48):
    if len(daily_df) < num_days:
        return None
    max_start = len(daily_df) - num_days
    start_idx = random.randint(0, max_start)
    selected = daily_df.iloc[start_idx:start_idx + num_days].copy()
    all_times, all_opens, all_highs, all_lows, all_closes, all_volumes = [], [], [], [], [], []
    base_time = datetime.strptime("09:30", "%H:%M").time()
    for day_idx, (_, day) in enumerate(selected.iterrows()):
        op, hp, lp, cp, vol = day["open"], day["high"], day["low"], day["close"], day["volume"]
        np.random.seed(random.randint(0, 10000) + day_idx * 100)
        steps = np.random.normal(0, 0.2, bars_per_day)
        prices = np.cumsum(steps)
        prices = prices - prices[0] + op
        min_p, max_p = np.min(prices), np.max(prices)
        range_p = max_p - min_p if max_p - min_p != 0 else 0.01
        scale = (hp - lp) / range_p
        prices_scaled = lp + (prices - min_p) * scale
        end_diff = cp - prices_scaled[-1]
        if bars_per_day > 1:
            prices_scaled = prices_scaled + np.linspace(0, end_diff, bars_per_day)
        opens = [prices_scaled[0]] + [prices_scaled[i-1] for i in range(1, bars_per_day)]
        closes = prices_scaled.tolist()
        highs, lows = [], []
        for i in range(bars_per_day):
            o, c = opens[i], closes[i]
            if o < c:
                low = o - (c - o) * random.uniform(0.3, 0.8)
                high = c + (c - o) * random.uniform(0.3, 0.8)
            else:
                high = o + (o - c) * random.uniform(0.3, 0.8)
                low = c - (o - c) * random.uniform(0.3, 0.8)
            lows.append(max(low, lp * 0.97))
            highs.append(min(high, hp * 1.03))
        returns = np.diff(closes, prepend=opens[0])
        vol_base = vol / bars_per_day
        vols = []
        for r in returns:
            if r > 0:
                v = vol_base * (1 + abs(r)*8) * random.uniform(0.7, 1.3)
            else:
                v = vol_base * (1 - abs(r)*8) * random.uniform(0.7, 1.3)
            vols.append(max(v, 30000))
        vol_sum = sum(vols)
        if vol_sum > 0:
            scale_vol = vol / vol_sum
            vols = [v * scale_vol for v in vols]
        day_label = f"Day{day_idx+1}"
        times = [f"{day_label} {(datetime.combine(datetime.today(), base_time) + timedelta(minutes=5*i)).time().strftime('%H:%M')}" for i in range(bars_per_day)]
        all_times.extend(times); all_opens.extend(opens); all_highs.extend(highs)
        all_lows.extend(lows); all_closes.extend(closes); all_volumes.extend(vols)
    return pd.DataFrame({
        "time": all_times, "open": all_opens, "high": all_highs,
        "low": all_lows, "close": all_closes, "volume": all_volumes
    })

# ===== 30种形态 =====
PATTERN_DATA = {
    "大阳线": {"meaning": "收盘远高于开盘，实体很长，买方极强", "hint": "实体很长（>3%涨幅），几乎没有上下影线", "key_features": "实体很长，上下影线很短", "teaching": "低位反转，高位延续"},
    "大阴线": {"meaning": "收盘远低于开盘，实体很长，卖方极强", "hint": "实体很长（>3%跌幅），几乎没有上下影线", "key_features": "实体很长，上下影线很短", "teaching": "高位见顶，低位杀跌"},
    "十字星": {"meaning": "开盘收盘几乎相等，多空胶着", "hint": "实体极小，上下影线明显", "key_features": "实体极小", "teaching": "高位见顶，低位见底"},
    "T字线": {"meaning": "开盘=收盘，长下影线，下方支撑强", "hint": "长下影线，无上影线", "key_features": "开盘=收盘，长下影线", "teaching": "下跌末端出现，可能止跌"},
    "看涨吞没": {"meaning": "下跌末端，大阳线完全包住前阴线，看涨", "hint": "阴线→大阳线，阳线实体覆盖阴线", "key_features": "阳线覆盖阴线", "teaching": "多头完全压倒空头"},
    "看跌吞没": {"meaning": "上涨末端，大阴线完全包住前阳线，看跌", "hint": "阳线→大阴线，阴线实体覆盖阳线", "key_features": "阴线覆盖阳线", "teaching": "空头完全压倒多头"},
    "曙光初现": {"meaning": "下跌中，阳线收盘深入前阴线一半以上，看涨", "hint": "阴线→阳线，阳线插入阴线一半", "key_features": "阳线插入阴线一半", "teaching": "多头开始反击"},
    "乌云盖顶": {"meaning": "上涨中，阴线收盘深入前阳线一半以上，看跌", "hint": "阳线→阴线，阴线插入阳线一半", "key_features": "阴线插入阳线一半", "teaching": "空头开始反击"},
    "早晨之星": {"meaning": "下跌末端，阴线+十字+阳线，反转看涨", "hint": "阴→十字→阳", "key_features": "阴→十字→阳", "teaching": "经典底部反转"},
    "黄昏之星": {"meaning": "上涨末端，阳线+十字+阴线，反转看跌", "hint": "阳→十字→阴", "key_features": "阳→十字→阴", "teaching": "经典顶部反转"},
    "红三兵": {"meaning": "连续三根阳线，持续看涨", "hint": "阳→阳→阳", "key_features": "三根阳线", "teaching": "多头持续发力"},
    "黑三鸦": {"meaning": "连续三根阴线，持续看跌", "hint": "阴→阴→阴", "key_features": "三根阴线", "teaching": "空头持续发力"},
    "上升三法": {"meaning": "大阳+三小阴回踩+大阳创新高，看涨", "hint": "阳→阴阴阴→阳", "key_features": "回踩后创新高", "teaching": "洗盘后继续拉升"},
    "下降三法": {"meaning": "大阴+三小阳反弹+大阴创新低，看跌", "hint": "阴→阳阳阳→阴", "key_features": "反弹后创新低", "teaching": "诱多后继续出货"},
    "锤子线": {"meaning": "下跌末端，长下影小实体，看涨", "hint": "长下影（≥实体2倍）", "key_features": "长下影+小实体", "teaching": "下方支撑强"},
    "射击之星": {"meaning": "上涨末端，长上影小实体，看跌", "hint": "长上影（≥实体2倍）", "key_features": "长上影+小实体", "teaching": "上方压力大"},
    "倒锤子线": {"meaning": "下跌末端，长上影小实体，看涨", "hint": "长上影，小实体", "key_features": "长上影+小实体", "teaching": "多头试探性反攻"},
    "平底": {"meaning": "多根K线最低点相同，水平支撑，看涨", "hint": "多个最低价接近相同", "key_features": "相同低点", "teaching": "支撑位确认"},
    "平顶": {"meaning": "多根K线最高点相同，水平压力，看跌", "hint": "多个最高价接近相同", "key_features": "相同高点", "teaching": "压力位确认"},
    "身怀六甲": {"meaning": "大K线内包小K线，趋势可能反转", "hint": "大实体→小实体", "key_features": "大包小", "teaching": "动能衰竭"},
    "两只乌鸦": {"meaning": "高位出现两根阴线，第一根长，第二根小且跳空高开", "hint": "阳→阴→阴（第二根跳空）", "key_features": "两阴夹一阳的变形", "teaching": "高位见顶信号"},
    "三只乌鸦": {"meaning": "连续三根阴线，每根开盘在前根实体内部，收盘创新低", "hint": "阴→阴→阴（跳空下跌）", "key_features": "三根跳空阴线", "teaching": "强烈看跌"},
    "红三线": {"meaning": "连续三根小阳线，走势温和", "hint": "阳→阳→阳（实体较小）", "key_features": "三根小阳线", "teaching": "温和上涨"},
    "白三线": {"meaning": "连续三根阳线，收盘都在最高价附近", "hint": "阳→阳→阳（无上影）", "key_features": "三根光阳", "teaching": "强势持续"},
    "上升楔形": {"meaning": "价格在两条收敛向上的趋势线之间运行", "hint": "价格高点抬高，但幅度越来越小", "key_features": "收敛向上楔形", "teaching": "可能向下突破"},
    "下降楔形": {"meaning": "价格在两条收敛向下的趋势线之间运行", "hint": "价格低点降低，但幅度越来越小", "key_features": "收敛向下楔形", "teaching": "可能向上突破"},
    "圆弧底": {"meaning": "价格缓慢下滑后缓慢回升，形成圆弧形", "hint": "底部平滑圆润，无明显尖角", "key_features": "圆弧形底部", "teaching": "缓慢筑底"},
    "圆弧顶": {"meaning": "价格缓慢上升后缓慢回落，形成圆弧形", "hint": "顶部平滑圆润，无明显尖角", "key_features": "圆弧形顶部", "teaching": "缓慢筑顶"},
    "V形反转": {"meaning": "价格急速下跌后急速反弹，形成V字", "hint": "底部尖锐，快速反转", "key_features": "V字形", "teaching": "急速反转信号"},
    "岛形反转": {"meaning": "价格跳空后横盘几日，再次反向跳空", "hint": "两处跳空，中间孤岛", "key_features": "两个反向缺口", "teaching": "强烈反转信号"}
}
PATTERN_NAMES = list(PATTERN_DATA.keys())

def plot_kline(df, title, is_intraday=False):
    if is_intraday:
        x_vals = df["time"].tolist()
        tick_vals = x_vals[::len(x_vals)//30] if len(x_vals) > 60 else x_vals[::5]
        fig = go.Figure(data=[go.Candlestick(
            x=x_vals, open=df["open"], high=df["high"], low=df["low"], close=df["close"]
        )])
        avg_price = (df["high"] + df["low"] + df["close"]) / 3
        fig.add_trace(go.Scatter(x=x_vals, y=avg_price, mode='lines', name='均价线', line=dict(color='orange', width=1)))
        ma5 = df["close"].rolling(5).mean()
        fig.add_trace(go.Scatter(x=x_vals, y=ma5, mode='lines', name='MA5', line=dict(color='cyan', width=1)))
        fig.update_layout(title=title, height=450, template="plotly_dark",
                          xaxis_rangeslider_visible=False, xaxis=dict(tickvals=tick_vals, tickangle=45))
    else:
        fig = go.Figure(data=[go.Candlestick(
            x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"]
        )])
        if len(df) >= 5:
            fig.add_trace(go.Scatter(x=df["date"], y=df["close"].rolling(5).mean(), mode='lines', name='MA5', line=dict(color='cyan', width=1)))
        if len(df) >= 20:
            fig.add_trace(go.Scatter(x=df["date"], y=df["close"].rolling(20).mean(), mode='lines', name='MA20', line=dict(color='purple', width=1)))
        if len(df) >= 60:
            fig.add_trace(go.Scatter(x=df["date"], y=df["close"].rolling(60).mean(), mode='lines', name='MA60', line=dict(color='yellow', width=1)))
        fig.update_layout(title=title, height=450, template="plotly_dark", xaxis_rangeslider_visible=False)
    return fig

def calculate_all_indicators(df, current_idx):
    slice_df = df.iloc[:current_idx+1].copy()
    last = slice_df.iloc[-1]
    ma5 = slice_df["close"].rolling(5).mean().iloc[-1] if len(slice_df) >= 5 else last["close"]
    ma10 = slice_df["close"].rolling(10).mean().iloc[-1] if len(slice_df) >= 10 else ma5
    ma20 = slice_df["close"].rolling(20).mean().iloc[-1] if len(slice_df) >= 20 else ma5
    ma60 = slice_df["close"].rolling(60).mean().iloc[-1] if len(slice_df) >= 60 else ma20
    avg_prices = (slice_df["open"] + slice_df["high"] + slice_df["low"] + slice_df["close"]) / 4
    cum_amount = (avg_prices * slice_df["volume"]).cumsum()
    cum_volume = slice_df["volume"].cumsum()
    current_avg_price = (cum_amount / cum_volume).iloc[-1]
    if last["close"] > current_avg_price * 1.002:
        avg_position = "高于均价线 (偏强)"
    elif last["close"] < current_avg_price * 0.998:
        avg_position = "低于均价线 (偏弱)"
    else:
        avg_position = "接近均价线 (中性)"
    vol_avg = slice_df["volume"].iloc[-6:-1].mean() if len(slice_df) >= 6 else slice_df["volume"].mean()
    vol_ratio = last["volume"] / vol_avg if vol_avg > 0 else 1
    if len(slice_df) >= 30:
        exp1 = slice_df["close"].ewm(span=12, adjust=False).mean()
        exp2 = slice_df["close"].ewm(span=26, adjust=False).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - signal_line
        macd_status = "多头增强" if macd_hist.iloc[-1] > 0 and macd_hist.iloc[-1] > macd_hist.iloc[-2] else \
                      "多头减弱" if macd_hist.iloc[-1] > 0 else \
                      "空头增强" if macd_hist.iloc[-1] < 0 and macd_hist.iloc[-1] < macd_hist.iloc[-2] else "空头减弱"
        macd_hist_value = macd_hist.iloc[-1]
        if macd_line.iloc[-1] > signal_line.iloc[-1] and macd_line.iloc[-2] <= signal_line.iloc[-2]:
            macd_cross = "金叉（偏多）"
        elif macd_line.iloc[-1] < signal_line.iloc[-1] and macd_line.iloc[-2] >= signal_line.iloc[-2]:
            macd_cross = "死叉（偏空）"
        else:
            macd_cross = "无交叉"
    else:
        macd_status, macd_hist_value, macd_cross = "数据不足", 0, "数据不足"
    if len(slice_df) >= 15:
        delta = slice_df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1])) if loss.iloc[-1] != 0 else 100
        rsi_status = "超买区" if rsi > 70 else "超卖区" if rsi < 30 else "中性"
    else:
        rsi, rsi_status = 50, "数据不足"
    if last["close"] > ma5 * 1.005:
        price_position = "高于MA5 (偏强)"
    elif last["close"] < ma5 * 0.995:
        price_position = "低于MA5 (偏弱)"
    else:
        price_position = "接近MA5 (中性)"
    if len(slice_df) >= 2:
        prev_close = slice_df["close"].iloc[-2]
        if vol_ratio > 1.5:
            vol_price_status = "放量上涨（强势）" if last["close"] > prev_close else "放量下跌（弱势）"
        elif vol_ratio < 0.8:
            vol_price_status = "缩量上涨（谨慎）" if last["close"] > prev_close else "缩量下跌（企稳）"
        else:
            vol_price_status = "量价正常"
    else:
        vol_price_status = "数据不足"
    if len(slice_df) >= 3:
        recent_3 = slice_df["close"].iloc[-3:]
        short_trend = "上涨" if recent_3.iloc[-1] > recent_3.iloc[0] else "下跌"
    else:
        short_trend = "震荡"
    if last["close"] > ma5 and ma5 > ma20:
        ma_alignment = "多头排列（强势）"
    elif last["close"] < ma5 and ma5 < ma20:
        ma_alignment = "空头排列（弱势）"
    else:
        ma_alignment = "均线交织（震荡）"
    first_open = slice_df["open"].iloc[0]
    pct_change = (last["close"] - first_open) / first_open * 100
    return {
        "last_close": last["close"],
        "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
        "ma_alignment": ma_alignment,
        "price_position": price_position,
        "avg_position": avg_position,
        "current_avg_price": current_avg_price,
        "vol_ratio": vol_ratio,
        "vol_status": "放量" if vol_ratio > 1.5 else "缩量" if vol_ratio < 0.8 else "正常",
        "vol_price_status": vol_price_status,
        "macd_hist_value": macd_hist_value,
        "macd_status": macd_status,
        "macd_cross": macd_cross,
        "rsi": rsi, "rsi_status": rsi_status,
        "short_trend": short_trend,
        "pct_change": pct_change,
        "last_volume": last["volume"], "vol_avg": vol_avg
    }

def init_mistakes():
    if "mistakes" not in st.session_state:
        st.session_state.mistakes = []

def record_mistake(module, question, user_answer, correct_answer, detail=""):
    st.session_state.mistakes.append({
        "module": module, "question": question,
        "user_answer": user_answer, "correct_answer": correct_answer,
        "detail": detail, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
# ========== 仓位管理训练 ==========
def tab_position():
    st.subheader("任务：给定场景，选择合理仓位")
    with st.expander("📖 仓位管理教学", expanded=False):
        st.markdown("""
        ## 仓位管理是生存第一法则

        | 信号强度 | 建议仓位 |
        |---------|----------|
        | 强（多指标共振） | 5-7成 |
        | 中（部分信号） | 3-5成 |
        | 弱（信号矛盾） | 1-2成或观望 |
        | 大盘暴跌 | 0-1成 |

        **永远不要满仓，留有余地应对意外。**
        """)

    if st.button("🎲 随机出题 (仓位)", use_container_width=True, key="btn_pos"):
        strength = random.choice(["强", "中", "弱"])
        market = random.choice(["大盘上涨", "大盘震荡", "大盘暴跌"])
        if market == "大盘暴跌":
            correct = "0-1成"
        elif strength == "强" and market == "大盘上涨":
            correct = "5-7成"
        elif strength == "强":
            correct = "3-5成"
        elif strength == "中":
            correct = "3-5成"
        else:
            correct = "1-2成"
        options = ["0-1成", "1-2成", "3-5成", "5-7成"]
        st.session_state.current_pos_q = {
            "strength": strength, "market": market, "correct": correct, "options": options
        }
        st.session_state.q_pos_answered = False

    q = st.session_state.get("current_pos_q")
    if q:
        st.markdown(f"### 场景")
        st.markdown(f"- 信号强度：**{q['strength']}**")
        st.markdown(f"- 市场环境：**{q['market']}**")
        st.markdown("### 你应该用多少仓位？")
        if not st.session_state.get("q_pos_answered"):
            cols = st.columns(4)
            for i, opt in enumerate(q["options"]):
                with cols[i]:
                    if st.button(opt, key=f"pos_{i}"):
                        st.session_state.q_pos_answered = True
                        st.session_state.score_pos["total"] += 1
                        if opt == q["correct"]:
                            st.session_state.score_pos["correct"] += 1
                        st.session_state.pos_user_choice = opt
                        st.rerun()
        if st.session_state.get("q_pos_answered"):
            uc = st.session_state.pos_user_choice
            if uc == q["correct"]:
                st.success(f"✅ 正确！建议仓位 {q['correct']}")
            else:
                st.error(f"❌ 错误。正确仓位是 {q['correct']}，你选了 {uc}")
            st.markdown(f"**逻辑**：信号{q['strength']} + {q['market']} → {q['correct']}")
            if st.button("继续下一题 (仓位)"):
                st.session_state.current_pos_q = None
                st.session_state.q_pos_answered = False
                st.rerun()
    if st.session_state.score_pos["total"] > 0:
        rate = st.session_state.score_pos["correct"] / st.session_state.score_pos["total"] * 100
        st.sidebar.metric("仓位正确率", f"{rate:.1f}%")


# ========== 大盘趋势判断 ==========
def tab_market():
    st.subheader("任务：判断当前大盘处于什么状态")
    with st.expander("📖 大盘趋势教学", expanded=False):
        st.markdown("""
        ## 大盘三状态

        | 状态 | 特征 | 建议仓位 |
        |------|------|----------|
        | 上涨 | 指数在MA20上方，量能放大 | 5-7成 |
        | 震荡 | 指数在MA20附近，量能平稳 | 3-5成 |
        | 下跌 | 指数在MA20下方，量能萎缩 | 0-2成 |

        **大盘决定仓位，个股决定买卖。**
        """)

    if st.button("🎲 随机出题 (大盘)", use_container_width=True, key="btn_mkt"):
        df = fetch_daily("600519")
        if df is None or len(df) < 60:
            st.error("数据加载失败")
            return
        cut = random.randint(40, len(df) - 5)
        display = df.iloc[:cut].copy()
        ma20 = display["close"].rolling(20).mean().iloc[-1]
        last = display.iloc[-1]["close"]
        vol_ratio = display["volume"].iloc[-1] / display["volume"].iloc[-6:-1].mean()
        if last > ma20 * 1.02 and vol_ratio > 1.2:
            correct = "上涨"
        elif last < ma20 * 0.98:
            correct = "下跌"
        else:
            correct = "震荡"
        st.session_state.current_mkt_q = {
            "df": display, "correct": correct, "current": last, "ma20": ma20
        }
        st.session_state.q_mkt_answered = False

    q = st.session_state.get("current_mkt_q")
    if q:
        st.plotly_chart(plot_kline(q["df"], "大盘走势"), use_container_width=True)
        st.markdown(f"当前价：{q['current']:.2f}，MA20：{q['ma20']:.2f}")
        if not st.session_state.get("q_mkt_answered"):
            cols = st.columns(3)
            for i, opt in enumerate(["上涨", "震荡", "下跌"]):
                with cols[i]:
                    if st.button(opt, key=f"mkt_{i}"):
                        st.session_state.q_mkt_answered = True
                        st.session_state.score_mkt["total"] += 1
                        if opt == q["correct"]:
                            st.session_state.score_mkt["correct"] += 1
                        st.session_state.mkt_user_choice = opt
                        st.rerun()
        if st.session_state.get("q_mkt_answered"):
            uc = st.session_state.mkt_user_choice
            if uc == q["correct"]:
                st.success(f"✅ 正确！当前大盘：{q['correct']}")
            else:
                st.error(f"❌ 错误。正确是 {q['correct']}，你选了 {uc}")
            if st.button("继续下一题 (大盘)"):
                st.session_state.current_mkt_q = None
                st.session_state.q_mkt_answered = False
                st.rerun()
    if st.session_state.score_mkt["total"] > 0:
        rate = st.session_state.score_mkt["correct"] / st.session_state.score_mkt["total"] * 100
        st.sidebar.metric("大盘正确率", f"{rate:.1f}%")


# ========== 模拟盘 ==========
def tab_simulation():
    st.subheader("模拟盘交易")
    st.caption("用虚拟资金练习买卖，检验训练成果")

    if "sim_cash" not in st.session_state:
        st.session_state.sim_cash = 1000000.0
    if "sim_holdings" not in st.session_state:
        st.session_state.sim_holdings = {}
    if "sim_history" not in st.session_state:
        st.session_state.sim_history = []

    col1, col2 = st.columns(2)
    col1.metric("💰 现金", f"¥{st.session_state.sim_cash:,.2f}")
    total_value = st.session_state.sim_cash
    for sym, h in st.session_state.sim_holdings.items():
        total_value += h["shares"] * h["avg_price"]
    col2.metric("📊 总资产", f"¥{total_value:,.2f}")

    st.markdown("---")
    st.markdown("### 买入")
    c1, c2, c3 = st.columns(3)
    with c1:
        buy_symbol = st.selectbox("选择股票", STOCK_POOL, key="buy_sym")
    with c2:
        df = fetch_daily(buy_symbol)
        if df is not None:
            buy_price = st.number_input("买入价", value=float(df.iloc[-1]["close"]), step=0.01, key="buy_p")
        else:
            buy_price = st.number_input("买入价", value=10.0, step=0.01, key="buy_p")
    with c3:
        buy_shares = st.number_input("股数（100的倍数）", value=100, step=100, key="buy_s")

    if st.button("🟢 买入", key="do_buy"):
        cost = buy_price * buy_shares
        if cost > st.session_state.sim_cash:
            st.error("❌ 资金不足")
        else:
            st.session_state.sim_cash -= cost
            if buy_symbol in st.session_state.sim_holdings:
                h = st.session_state.sim_holdings[buy_symbol]
                total_shares = h["shares"] + buy_shares
                h["avg_price"] = (h["shares"] * h["avg_price"] + cost) / total_shares
                h["shares"] = total_shares
            else:
                st.session_state.sim_holdings[buy_symbol] = {"shares": buy_shares, "avg_price": buy_price}
            st.session_state.sim_history.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "action": "买入", "symbol": buy_symbol,
                "price": buy_price, "shares": buy_shares
            })
            st.success(f"✅ 买入 {buy_symbol} {buy_shares}股 @ {buy_price:.2f}")
            st.rerun()

    st.markdown("---")
    st.markdown("### 卖出")
    if st.session_state.sim_holdings:
        c1, c2, c3 = st.columns(3)
        with c1:
            sell_symbol = st.selectbox("选择股票", list(st.session_state.sim_holdings.keys()), key="sell_sym")
        with c2:
            h = st.session_state.sim_holdings[sell_symbol]
            sell_price = st.number_input("卖出价", value=float(h["avg_price"]), step=0.01, key="sell_p")
        with c3:
            sell_shares = st.number_input("股数", value=h["shares"], max_value=h["shares"], step=100, key="sell_s")

        if st.button("🔴 卖出", key="do_sell"):
            h = st.session_state.sim_holdings[sell_symbol]
            revenue = sell_price * sell_shares
            profit = (sell_price - h["avg_price"]) * sell_shares
            st.session_state.sim_cash += revenue
            if sell_shares >= h["shares"]:
                del st.session_state.sim_holdings[sell_symbol]
            else:
                h["shares"] -= sell_shares
            st.session_state.sim_history.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "action": "卖出", "symbol": sell_symbol,
                "price": sell_price, "shares": sell_shares, "profit": profit
            })
            st.success(f"✅ 卖出 {sell_symbol} {sell_shares}股 @ {sell_price:.2f}，盈亏 {profit:+.2f}")
            st.rerun()

    st.markdown("---")
    st.markdown("### 当前持仓")
    if st.session_state.sim_holdings:
        for sym, h in st.session_state.sim_holdings.items():
            st.markdown(f"- **{sym}**：{h['shares']}股，成本 {h['avg_price']:.2f}")
    else:
        st.info("暂无持仓")

    st.markdown("### 交易记录")
    if st.session_state.sim_history:
        for r in reversed(st.session_state.sim_history[-20:]):
            if r["action"] == "买入":
                st.markdown(f"🔴 {r['time']} 买入 {r['symbol']} {r['shares']}股 @ {r['price']:.2f}")
            else:
                st.markdown(f"🟢 {r['time']} 卖出 {r['symbol']} {r['shares']}股 @ {r['price']:.2f}，盈亏 {r['profit']:+.2f}")
    else:
        st.info("暂无记录")

    if st.button("重置模拟盘", key="reset_sim"):
        st.session_state.sim_cash = 1000000.0
        st.session_state.sim_holdings = {}
        st.session_state.sim_history = []
        st.rerun()


# ========== 个股分析 ==========
def tab_stock_analysis():
    st.subheader("📈 个股分析")
    st.caption("输入股票代码，系统自动给出综合分析和操作建议")

    col1, col2 = st.columns([2, 1])
    with col1:
        symbol_input = st.text_input("输入股票代码（6位数字）", value="600519")
    with col2:
        analyze_btn = st.button("开始分析", use_container_width=True)

    if analyze_btn:
        with st.spinner("正在分析..."):
            df = fetch_daily(symbol_input)
            if df is None or len(df) < 60:
                st.error("⚠️ 无法获取数据，请检查代码是否正确")
                return
            ind = calculate_all_indicators(df, len(df) - 1)
            st.session_state.analysis_result = {"df": df, "symbol": symbol_input, "ind": ind}

    result = st.session_state.get("analysis_result")
    if result:
        df = result["df"]
        ind = result["ind"]
        symbol = result["symbol"]

        st.plotly_chart(plot_kline(df.tail(60), f"{symbol} 近60日K线"), use_container_width=True)

        st.markdown("### 📊 基础数据")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("当前价", f"{ind['last_close']:.2f}", delta=f"{ind['pct_change']:.2f}%")
        c2.metric("MA5", f"{ind['ma5']:.2f}")
        c3.metric("MA20", f"{ind['ma20']:.2f}")
        c4.metric("MA60", f"{ind['ma60']:.2f}")

        st.markdown("### 📈 技术指标")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("均线排列", ind['ma_alignment'])
        c2.metric("MACD", ind['macd_status'], delta=ind['macd_cross'])
        c3.metric("RSI", f"{ind['rsi']:.1f}", delta=ind['rsi_status'])
        c4.metric("量价", ind['vol_price_status'])

        st.markdown("### 🎯 综合评分")
        score = 0
        details = []
        if "高于" in ind['price_position']:
            score += 1; details.append("+1 价格在MA5上方")
        elif "低于" in ind['price_position']:
            score -= 1; details.append("-1 价格在MA5下方")
        if ind['ma_alignment'] == "多头排列（强势）":
            score += 1; details.append("+1 均线多头排列")
        elif ind['ma_alignment'] == "空头排列（弱势）":
            score -= 1; details.append("-1 均线空头排列")
        if ind['macd_status'] == "多头增强":
            score += 1; details.append("+1 MACD多头增强")
        elif ind['macd_status'] == "空头增强":
            score -= 1; details.append("-1 MACD空头增强")
        if ind['vol_price_status'] == "放量上涨（强势）":
            score += 1; details.append("+1 放量上涨")
        elif ind['vol_price_status'] == "放量下跌（弱势）":
            score -= 1; details.append("-1 放量下跌")
        if ind['rsi'] < 30:
            score += 1; details.append("+1 RSI超卖")
        elif ind['rsi'] > 70:
            score -= 1; details.append("-1 RSI超买")

        for d in details:
            st.markdown(f"- {d}")
        st.markdown(f"**总分：{score:+d}**")

        st.markdown("### 💡 操作建议")
        if score >= 3:
            st.success("🔵 **强烈看多** — 多信号共振，可以考虑买入")
        elif score >= 1:
            st.info("🔵 **偏多** — 可轻仓介入，注意止损")
        elif score <= -3:
            st.error("🔴 **强烈看空** — 建议离场观望")
        elif score <= -1:
            st.warning("🟡 **偏空** — 谨慎操作，控制仓位")
        else:
            st.info("⚪ **中性** — 方向不明，建议观望")

        st.markdown("### 🛡️ 止损位建议")
        high, low = df["high"], df["low"]
        prev_close = df["close"].shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        stop_low = ind['last_close'] - 2 * atr
        stop_high = ind['last_close'] - 0.8 * atr
        st.markdown(f"- ATR：**{atr:.2f}**")
        st.markdown(f"- 合理止损区间：**{stop_low:.2f} ~ {stop_high:.2f}**")
        st.markdown(f"- 建议止损价：**{stop_high:.2f}**（较保守）或 **{stop_low:.2f}**（较宽松）")

# ========== 主程序 ==========
def main():
    init_mistakes()
    st.sidebar.header("📊 我的成绩")
    for key in ["score_pattern", "score_intra", "score_industry", "score_trade",
                "score_stop", "score_trend", "score_pos", "score_mkt"]:
        if key not in st.session_state:
            st.session_state[key] = {"correct": 0, "total": 0}
    for key in ["q_pattern_answered", "q_intra_answered", "q_industry_answered",
                "q_trade_answered", "q_stop_answered", "q_trend_answered",
                "q_pos_answered", "q_mkt_answered"]:
        if key not in st.session_state:
            st.session_state[key] = False
    for key in ["current_pattern_q", "current_intra_q", "current_industry_q",
                "current_trade_q", "current_stop_q", "current_trend_q",
                "current_pos_q", "current_mkt_q"]:
        if key not in st.session_state:
            st.session_state[key] = None

       tabs = st.tabs([
        "📊 形态", "⚡ 分时", "🏭 板块", "🎯 买卖点",
        "🛡️ 止损", "🔮 趋势", "💰 仓位", "🌍 大盘",
        "💼 模拟盘", "📝 错题本", "📈 个股分析"
    ])
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = tabs

    with tab1:
        st.subheader(f"任务：看K线，选形态名称（共{len(PATTERN_NAMES)}种）")
        with st.expander("📖 形态识别教学", expanded=False):
            st.markdown("""
            - **实体长度**：越长越强（大阳线=买方强，大阴线=卖方强）
            - **影线长度**：越长越有含义（长下影=下方支撑，长上影=上方压力）
            - **出现位置**：高位看跌，低位看涨
            """)
            for name, data in PATTERN_DATA.items():
                st.markdown(f"**{name}**：{data['meaning']} | 实战：{data['teaching']}")

        if st.button("🎲 随机出题 (形态)", use_container_width=True, key="btn_pattern"):
            with st.spinner("加载..."):
                random.shuffle(STOCK_POOL)
                for symbol in STOCK_POOL:
                    df = fetch_daily(symbol)
                    if df is not None and len(df) >= 30:
                        correct = random.choice(PATTERN_NAMES)
                        options = [correct] + random.sample([p for p in PATTERN_NAMES if p != correct], 3)
                        random.shuffle(options)
                        st.session_state.current_pattern_q = {
                            "df": df.tail(30), "name": symbol, "correct": correct,
                            "options": options, "meaning": PATTERN_DATA[correct]["meaning"],
                            "hint": PATTERN_DATA[correct]["hint"],
                            "key_features": PATTERN_DATA[correct]["key_features"],
                            "teaching": PATTERN_DATA[correct]["teaching"]
                        }
                        st.session_state.q_pattern_answered = False
                        break

        q = st.session_state.current_pattern_q
        if q:
            st.plotly_chart(plot_kline(q["df"], f"{q['name']} 日K线"), use_container_width=True)
            if not st.session_state.q_pattern_answered:
                st.info(f"💡 提示：{q['hint']}")
                cols = st.columns(4)
                for i, opt in enumerate(q["options"]):
                    with cols[i]:
                        if st.button(opt, key=f"pat_{i}"):
                            st.session_state.q_pattern_answered = True
                            st.session_state.score_pattern["total"] += 1
                            if opt == q["correct"]:
                                st.session_state.score_pattern["correct"] += 1
                            st.session_state.pat_user_choice = opt
                            st.rerun()
            if st.session_state.q_pattern_answered:
                uc = st.session_state.pat_user_choice
                if uc == q["correct"]:
                    st.success(f"✅ 正确！{q['correct']}：{q['meaning']}")
                else:
                    st.error(f"❌ 错误。正确答案是 {q['correct']}")
                    st.markdown(f"**你选的 {uc}**：{PATTERN_DATA[uc]['meaning']}")
                    st.markdown(f"**正确答案 {q['correct']}**：{q['meaning']}")
                    record_mistake("形态", f"{q['name']}", uc, q['correct'])
                if st.button("继续下一题 (形态)"):
                    st.session_state.current_pattern_q = None
                    st.session_state.q_pattern_answered = False
                    st.rerun()

    with tab2:
        st.subheader("任务：看分时图，判断下一根K线涨跌")
        if st.button("🎲 随机出题 (分时)", use_container_width=True, key="btn_intra"):
            with st.spinner("生成..."):
                random.shuffle(STOCK_POOL)
                for symbol in STOCK_POOL:
                    df_daily = fetch_daily(symbol)
                    if df_daily is not None and len(df_daily) >= 20:
                        df_intra = generate_intraday_from_multiple_days(df_daily, num_days=random.randint(5, 10))
                        if df_intra is None or len(df_intra) < 150:
                            continue
                        total_len = len(df_intra)
                        cut_end = random.randint(100, total_len - 5)
                        display_df = df_intra.iloc[cut_end-100:cut_end].copy().reset_index(drop=True)
                        if len(display_df) < 100:
                            continue
                        next_row = df_intra.iloc[cut_end]
                        actual_direction = "涨" if next_row["close"] > display_df.iloc[-1]["close"] else "跌"
                        indicators = calculate_all_indicators(display_df, len(display_df)-1)
                        st.session_state.current_intra_q = {
                            "df": display_df, "symbol": symbol,
                            "actual_direction": actual_direction, "next_row": next_row,
                            "indicators": indicators
                        }
                        st.session_state.q_intra_answered = False
                        break
        q = st.session_state.current_intra_q
        if q:
            ind = q["indicators"]
            fig = plot_kline(q["df"], f"{q['symbol']} 分时", is_intraday=True)
            fig.add_vline(x=q['df']['time'].iloc[-1], line_width=2, line_dash="dash", line_color="yellow")
            st.plotly_chart(fig, use_container_width=True)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("当前价", f"{ind['last_close']:.2f}")
            c2.metric("量比", f"{ind['vol_ratio']:.2f}", delta=ind['vol_status'])
            c3.metric("RSI", f"{ind['rsi']:.1f}", delta=ind['rsi_status'])
            c4.metric("MACD", f"{ind['macd_hist_value']:.3f}", delta=ind['macd_status'])
            if not st.session_state.q_intra_answered:
                c1, c2 = st.columns(2)
                if c1.button("📈 涨", key="intra_up"):
                    st.session_state.intra_user_choice = "涨"
                    st.session_state.q_intra_answered = True
                    st.session_state.score_intra["total"] += 1
                    if q["actual_direction"] == "涨":
                        st.session_state.score_intra["correct"] += 1
                    st.rerun()
                if c2.button("📉 跌", key="intra_down"):
                    st.session_state.intra_user_choice = "跌"
                    st.session_state.q_intra_answered = True
                    st.session_state.score_intra["total"] += 1
                    if q["actual_direction"] == "跌":
                        st.session_state.score_intra["correct"] += 1
                    st.rerun()
            if st.session_state.q_intra_answered:
                uc = st.session_state.intra_user_choice
                if uc == q["actual_direction"]:
                    st.success(f"✅ 正确！实际 {q['actual_direction']}")
                else:
                    st.error(f"❌ 错误。实际 {q['actual_direction']}")
                    record_mistake("分时", q['symbol'], uc, q['actual_direction'])
                st.markdown(f"- MA5：{ind['price_position']}")
                st.markdown(f"- 均价线：{ind['avg_position']}")
                st.markdown(f"- 量价：{ind['vol_price_status']}")
                st.markdown(f"- MACD：{ind['macd_status']} ({ind['macd_cross']})")
                if st.button("继续下一题 (分时)"):
                    st.session_state.current_intra_q = None
                    st.session_state.q_intra_answered = False
                    st.rerun()

    with tab3:
        st.subheader("任务：看股票代码，选所属行业")
        if st.button("🎲 随机出题 (板块)", use_container_width=True, key="btn_industry"):
            symbol = random.choice(list(INDUSTRY_MAP.keys()))
            correct = INDUSTRY_MAP[symbol]
            options = [correct] + random.sample([i for i in ALL_INDUSTRIES if i != correct], 3)
            random.shuffle(options)
            st.session_state.current_industry_q = {"symbol": symbol, "correct": correct, "options": options}
            st.session_state.q_industry_answered = False
            st.rerun()
        q = st.session_state.current_industry_q
        if q:
            st.markdown(f"### {q['symbol']} 属于哪个行业？")
            if not st.session_state.q_industry_answered:
                cols = st.columns(4)
                for i, opt in enumerate(q["options"]):
                    with cols[i]:
                        if st.button(opt, key=f"ind_{i}"):
                            st.session_state.q_industry_answered = True
                            st.session_state.score_industry["total"] += 1
                            if opt == q["correct"]:
                                st.session_state.score_industry["correct"] += 1
                            st.session_state.ind_user_choice = opt
                            st.rerun()
            if st.session_state.q_industry_answered:
                if st.session_state.ind_user_choice == q["correct"]:
                    st.success(f"✅ 正确！{q['symbol']} 属于 {q['correct']}")
                else:
                    st.error(f"❌ 错误。正确答案：{q['correct']}")
                    record_mistake("板块", q['symbol'], st.session_state.ind_user_choice, q['correct'])
                if st.button("继续下一题 (板块)"):
                    st.session_state.current_industry_q = None
                    st.session_state.q_industry_answered = False
                    st.rerun()

    with tab4:
        st.subheader("任务：判断买点、卖点还是观望")
        if st.button("🎲 随机出题 (买卖点)", use_container_width=True, key="btn_trade"):
            with st.spinner("加载..."):
                random.shuffle(STOCK_POOL)
                for symbol in STOCK_POOL:
                    df = fetch_daily(symbol)
                    if df is not None and len(df) >= 60:
                        cut = random.randint(40, len(df) - 5)
                        display = df.iloc[:cut].copy()
                        future = df.iloc[cut:cut+5]
                        last, prev = display.iloc[-1], display.iloc[-2]
                        ma20 = display["close"].rolling(20).mean().iloc[-1]
                        vol_mean = display["volume"].iloc[-6:-1].mean()
                        if last["close"] > prev["high"] and last["volume"] > vol_mean * 1.3:
                            scene, correct_action = "突破买入", "买入"
                        elif last["low"] <= ma20 * 1.02 and last["close"] > last["open"] and last["volume"] < vol_mean * 0.8:
                            scene, correct_action = "回踩买入", "买入"
                        elif last["close"] < ma20 * 0.98 and last["volume"] > vol_mean * 1.3:
                            scene, correct_action = "跌破卖出", "卖出"
                        elif last["close"] > display["close"].iloc[-10:].max() * 0.98 and last["high"] > last["close"] * 1.02 and last["close"] < last["open"]:
                            scene, correct_action = "冲高卖出", "卖出"
                        else:
                            scene, correct_action = "震荡观望", "观望"
                        st.session_state.current_trade_q = {
                            "df": display, "symbol": symbol, "scene": scene,
                            "correct_action": correct_action, "future": future
                        }
                        st.session_state.q_trade_answered = False
                        break
        q = st.session_state.current_trade_q
        if q:
            st.plotly_chart(plot_kline(q["df"], f"{q['symbol']} 日K线"), use_container_width=True)
            st.info(f"场景：**{q['scene']}**")
            if not st.session_state.q_trade_answered:
                c1, c2, c3 = st.columns(3)
                if c1.button("🟢 买入", key="tb"):
                    st.session_state.trade_user_choice = "买入"
                    st.session_state.q_trade_answered = True
                    st.session_state.score_trade["total"] += 1
                    if q["correct_action"] == "买入":
                        st.session_state.score_trade["correct"] += 1
                    st.rerun()
                if c2.button("🔴 卖出", key="ts"):
                    st.session_state.trade_user_choice = "卖出"
                    st.session_state.q_trade_answered = True
                    st.session_state.score_trade["total"] += 1
                    if q["correct_action"] == "卖出":
                        st.session_state.score_trade["correct"] += 1
                    st.rerun()
                if c3.button("⚪ 观望", key="tw"):
                    st.session_state.trade_user_choice = "观望"
                    st.session_state.q_trade_answered = True
                    st.session_state.score_trade["total"] += 1
                    if q["correct_action"] == "观望":
                        st.session_state.score_trade["correct"] += 1
                    st.rerun()
            if st.session_state.q_trade_answered:
                if st.session_state.trade_user_choice == q["correct_action"]:
                    st.success(f"✅ 正确！{q['scene']} → {q['correct_action']}")
                else:
                    st.error(f"❌ 错误。{q['scene']} → {q['correct_action']}")
                    record_mistake("买卖点", f"{q['symbol']} {q['scene']}", st.session_state.trade_user_choice, q['correct_action'])
                st.dataframe(q["future"][["date", "open", "high", "low", "close"]])
                if st.button("继续下一题 (买卖点)"):
                    st.session_state.current_trade_q = None
                    st.session_state.q_trade_answered = False
                    st.rerun()

    with tab5:
        st.subheader("任务：设定止损价")
        if st.button("🎲 随机出题 (止损)", use_container_width=True, key="btn_stop"):
            with st.spinner("加载..."):
                random.shuffle(STOCK_POOL)
                for symbol in STOCK_POOL:
                    df = fetch_daily(symbol)
                    if df is not None and len(df) >= 60:
                        cut = random.randint(40, len(df) - 5)
                        display = df.iloc[:cut].copy()
                        last_close = display.iloc[-1]["close"]
                        high, low = display["high"], display["low"]
                        prev_close = display["close"].shift(1)
                        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
                        atr = tr.rolling(14).mean().iloc[-1]
                        st.session_state.current_stop_q = {
                            "df": display, "symbol": symbol, "last_close": last_close, "atr": atr,
                            "stop_low": last_close - 2 * atr, "stop_high": last_close - 0.8 * atr
                        }
                        st.session_state.q_stop_answered = False
                        break
        q = st.session_state.current_stop_q
        if q:
            st.plotly_chart(plot_kline(q["df"], f"{q['symbol']}"), use_container_width=True)
            st.markdown(f"### 当前价：{q['last_close']:.2f}")
            if not st.session_state.q_stop_answered:
                stop_input = st.number_input("止损价：", value=float(round(q["last_close"] * 0.95, 2)), step=0.01)
                if st.button("提交", key="submit_stop"):
                    st.session_state.stop_user_choice = stop_input
                    st.session_state.q_stop_answered = True
                    st.session_state.score_stop["total"] += 1
                    if q["stop_low"] <= stop_input <= q["stop_high"]:
                        st.session_state.score_stop["correct"] += 1
                    st.rerun()
            if st.session_state.q_stop_answered:
                us = st.session_state.stop_user_choice
                if q["stop_low"] <= us <= q["stop_high"]:
                    st.success(f"✅ 合理！")
                else:
                    st.error(f"❌ 不合理。合理区间：{q['stop_low']:.2f} ~ {q['stop_high']:.2f}")
                    record_mistake("止损", q['symbol'], f"{us:.2f}", f"{q['stop_low']:.2f}~{q['stop_high']:.2f}")
                st.markdown(f"- ATR：{q['atr']:.2f}")
                st.markdown(f"- 合理区间：{q['stop_low']:.2f} ~ {q['stop_high']:.2f}")
                if st.button("继续下一题 (止损)"):
                    st.session_state.current_stop_q = None
                    st.session_state.q_stop_answered = False
                    st.rerun()

    with tab6:
        st.subheader("任务：判断未来3天涨跌")
        if st.button("🎲 随机出题 (趋势)", use_container_width=True, key="btn_trend"):
            with st.spinner("加载..."):
                random.shuffle(STOCK_POOL)
                for symbol in STOCK_POOL:
                    df = fetch_daily(symbol)
                    if df is not None and len(df) >= 80:
                        cut = random.randint(60, len(df) - 5)
                        display = df.iloc[:cut].copy()
                        future_3 = df.iloc[cut:cut+3]
                        if len(future_3) < 3:
                            continue
                        current_price = display.iloc[-1]["close"]
                        future_price = future_3.iloc[-1]["close"]
                        actual_direction = "涨" if future_price > current_price else "跌"
                        actual_pct = (future_price - current_price) / current_price * 100
                        indicators = calculate_all_indicators(display, len(display)-1)
                        st.session_state.current_trend_q = {
                            "df": display, "symbol": symbol, "current_price": current_price,
                            "future_3": future_3, "actual_direction": actual_direction,
                            "actual_pct": actual_pct, "indicators": indicators
                        }
                        st.session_state.q_trend_answered = False
                        break
        q = st.session_state.current_trend_q
        if q:
            ind = q["indicators"]
            st.plotly_chart(plot_kline(q["df"], f"{q['symbol']}"), use_container_width=True)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("均线", ind['ma_alignment'])
            c2.metric("MACD", ind['macd_status'])
            c3.metric("RSI", f"{ind['rsi']:.1f}")
            c4.metric("量价", ind['vol_price_status'])
            if not st.session_state.q_trend_answered:
                c1, c2 = st.columns(2)
                if c1.button("📈 看涨", key="tr_up"):
                    st.session_state.trend_user_choice = "涨"
                    st.session_state.q_trend_answered = True
                    st.session_state.score_trend["total"] += 1
                    if q["actual_direction"] == "涨":
                        st.session_state.score_trend["correct"] += 1
                    st.rerun()
                if c2.button("📉 看跌", key="tr_down"):
                    st.session_state.trend_user_choice = "跌"
                    st.session_state.q_trend_answered = True
                    st.session_state.score_trend["total"] += 1
                    if q["actual_direction"] == "跌":
                        st.session_state.score_trend["correct"] += 1
                    st.rerun()
            if st.session_state.q_trend_answered:
                uc = st.session_state.trend_user_choice
                if uc == q["actual_direction"]:
                    st.success(f"✅ 正确！实际 {q['actual_direction']} {abs(q['actual_pct']):.2f}%")
                else:
                    st.error(f"❌ 错误。实际 {q['actual_direction']} {abs(q['actual_pct']):.2f}%")
                    record_mistake("趋势", q['symbol'], uc, q['actual_direction'])
                for _, row in q["future_3"].iterrows():
                    change = (row["close"] - row["open"]) / row["open"] * 100
                    st.markdown(f"{'🔴' if change > 0 else '🟢'} {row['date'].strftime('%Y-%m-%d')}：{change:+.2f}%")
                if st.button("继续下一题 (趋势)"):
                    st.session_state.current_trend_q = None
                    st.session_state.q_trend_answered = False
                    st.rerun()

    with tab7:
        tab_position()

    with tab8:
        tab_market()

    with tab9:
        tab_simulation()

    with tab10:
        st.subheader("📝 错题本")
        if len(st.session_state.mistakes) == 0:
            st.info("暂无错题")
        else:
            st.markdown(f"### 共 {len(st.session_state.mistakes)} 道错题")
            modules = {}
            for m in st.session_state.mistakes:
                modules[m["module"]] = modules.get(m["module"], 0) + 1
            for mod, count in sorted(modules.items(), key=lambda x: -x[1]):
                st.markdown(f"- **{mod}**：{count} 道")
            st.markdown("---")
            for m in reversed(st.session_state.mistakes[-30:]):
                with st.expander(f"[{m['module']}] {m['question']} - {m['time']}"):
                    st.markdown(f"- 你选：{m['user_answer']}")
                    st.markdown(f"- 正确：{m['correct_answer']}")
                        if st.button("清空错题本"):
                st.session_state.mistakes = []
                st.rerun()

    with tab11:
        tab_stock_analysis()

    # 侧边栏成绩
    for name, key in [("形态", "score_pattern"), ("分时", "score_intra"),
                      ("板块", "score_industry"), ("买卖点", "score_trade"),
                      ("止损", "score_stop"), ("趋势", "score_trend"),
                      ("仓位", "score_pos"), ("大盘", "score_mkt")]:
        if st.session_state[key]["total"] > 0:
            rate = st.session_state[key]["correct"] / st.session_state[key]["total"] * 100
            st.sidebar.metric(f"{name}正确率", f"{rate:.1f}%")


if __name__ == "__main__":
    main()
