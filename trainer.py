import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import random
import requests
from datetime import datetime, timedelta
import numpy as np

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(page_title="K线训练器", layout="wide")
st.title("⚔️ K线综合训练器")
st.caption("形态识别 | 分时实战 | 板块认知 | 买卖点 | 止损训练 | 未来趋势 | 错题本")

# ============================================================
# API Key
# ============================================================
API_KEY = st.secrets["TONGHUASHUN_API_KEY"]

# ============================================================
# 股票池
# ============================================================
STOCK_POOL = [
    "600519", "000858", "600036", "000002", "002415",
    "600276", "000651", "601318", "600030", "000725",
    "600900", "601166", "600887", "600309", "600585",
    "000333", "000568", "002594", "300750", "600809"
]

INDUSTRY_MAP = {
    "600519": "白酒", "000858": "白酒", "000568": "白酒", "600809": "白酒",
    "600036": "银行", "601166": "银行", "600030": "券商", "601318": "保险",
    "000002": "房地产", "600048": "房地产",
    "002415": "安防", "000725": "面板显示", "300750": "锂电池", "002594": "新能源车",
    "600276": "医药", "600887": "食品饮料", "000333": "家电", "000651": "家电",
    "600309": "化工", "600585": "建材", "600900": "电力"
}

ALL_INDUSTRIES = list(set(INDUSTRY_MAP.values()))

# ============================================================
# 1. 获取日线数据
# ============================================================
def fetch_daily(symbol):
    if symbol.startswith("60") or symbol.startswith("68"):
        code = symbol + ".SH"
    else:
        code = symbol + ".SZ"
    
    url = "https://fuyao.aicubes.cn/api/a-share/prices/historical"
    headers = {"X-api-key": API_KEY}
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=200)
    start_ms = int(start_date.timestamp() * 1000)
    end_ms = int(end_date.timestamp() * 1000)
    
    params = {
        "thscode": code,
        "interval": "1d",
        "start": start_ms,
        "end": end_ms,
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
                        "date_ms": "date",
                        "open_price": "open",
                        "high_price": "high",
                        "low_price": "low",
                        "close_price": "close",
                        "volume": "volume"
                    })
                    df["date"] = pd.to_datetime(df["date"], unit="ms")
                    return df[["date", "open", "high", "low", "close", "volume"]]
        return None
    except Exception as e:
        return None

# ============================================================
# 2. 模拟分时数据生成器
# ============================================================
def generate_intraday_from_multiple_days(daily_df, num_days=7, bars_per_day=48):
    if len(daily_df) < num_days:
        return None
    
    max_start = len(daily_df) - num_days
    start_idx = random.randint(0, max_start)
    selected = daily_df.iloc[start_idx:start_idx + num_days].copy()
    
    all_times, all_opens, all_highs, all_lows, all_closes, all_volumes = [], [], [], [], [], []
    base_time = datetime.strptime("09:30", "%H:%M").time()
    
    for day_idx, (_, day) in enumerate(selected.iterrows()):
        open_price = day["open"]
        high_price = day["high"]
        low_price = day["low"]
        close_price = day["close"]
        volume = day["volume"]
        
        np.random.seed(random.randint(0, 10000) + day_idx * 100)
        steps = np.random.normal(0, 0.2, bars_per_day)
        prices = np.cumsum(steps)
        prices = prices - prices[0] + open_price
        
        min_p = np.min(prices)
        max_p = np.max(prices)
        range_p = max_p - min_p
        if range_p == 0:
            range_p = 0.01
        target_range = high_price - low_price
        scale = target_range / range_p
        prices_scaled = low_price + (prices - min_p) * scale
        
        end_diff = close_price - prices_scaled[-1]
        if bars_per_day > 1:
            adjustment = np.linspace(0, end_diff, bars_per_day)
            prices_scaled = prices_scaled + adjustment
        
        opens = [prices_scaled[0]]
        for i in range(1, bars_per_day):
            opens.append(prices_scaled[i-1])
        closes = prices_scaled.tolist()
        
        highs, lows = [], []
        for i in range(bars_per_day):
            o = opens[i]
            c = closes[i]
            if o < c:
                low = o - (c - o) * random.uniform(0.3, 0.8)
                high = c + (c - o) * random.uniform(0.3, 0.8)
            else:
                high = o + (o - c) * random.uniform(0.3, 0.8)
                low = c - (o - c) * random.uniform(0.3, 0.8)
            low = max(low, low_price * 0.97)
            high = min(high, high_price * 1.03)
            lows.append(low)
            highs.append(high)
        
        returns = np.diff(closes, prepend=opens[0])
        vol_base = volume / bars_per_day
        vols = []
        for r in returns:
            if r > 0:
                vol = vol_base * (1 + abs(r)*8) * random.uniform(0.7, 1.3)
            else:
                vol = vol_base * (1 - abs(r)*8) * random.uniform(0.7, 1.3)
            vols.append(max(vol, 30000))
        
        vol_sum = sum(vols)
        if vol_sum > 0:
            scale_vol = volume / vol_sum
            vols = [v * scale_vol for v in vols]
        
        day_label = f"Day{day_idx+1}"
        times = []
        for i in range(bars_per_day):
            t = (datetime.combine(datetime.today(), base_time) + timedelta(minutes=5*i)).time()
            times.append(f"{day_label} {t.strftime('%H:%M')}")
        
        all_times.extend(times)
        all_opens.extend(opens)
        all_highs.extend(highs)
        all_lows.extend(lows)
        all_closes.extend(closes)
        all_volumes.extend(vols)
    
    df = pd.DataFrame({
        "time": all_times, "open": all_opens, "high": all_highs,
        "low": all_lows, "close": all_closes, "volume": all_volumes
    })
    return df

# ============================================================
# 3. 形态题库
# ============================================================
PATTERN_DATA = {
    "大阳线": {"meaning": "收盘远高于开盘，实体很长，买方极强", "hint": "实体很长（>3%涨幅），几乎没有上下影线", "key_features": "实体很长，上下影线很短"},
    "大阴线": {"meaning": "收盘远低于开盘，实体很长，卖方极强", "hint": "实体很长（>3%跌幅），几乎没有上下影线", "key_features": "实体很长，上下影线很短"},
    "十字星": {"meaning": "开盘收盘几乎相等，多空胶着，方向不明", "hint": "实体极小，上下影线明显", "key_features": "实体极小，上下影线明显"},
    "T字线": {"meaning": "开盘=收盘，长下影线，下方支撑强", "hint": "长下影线，无上影线或很短", "key_features": "开盘=收盘，长下影线"},
    "看涨吞没": {"meaning": "下跌末端，大阳线完全包住前一根阴线，看涨", "hint": "阴线→大阳线，阳线实体完全覆盖阴线", "key_features": "阳线覆盖阴线"},
    "看跌吞没": {"meaning": "上涨末端，大阴线完全包住前一根阳线，看跌", "hint": "阳线→大阴线，阴线实体完全覆盖阳线", "key_features": "阴线覆盖阳线"},
    "曙光初现": {"meaning": "下跌中，阳线收盘深入前阴线实体一半以上，看涨", "hint": "阴线→阳线，阳线插入阴线实体一半以上", "key_features": "阳线插入阴线一半"},
    "乌云盖顶": {"meaning": "上涨中，阴线收盘深入前阳线实体一半以上，看跌", "hint": "阳线→阴线，阴线插入阳线实体一半以上", "key_features": "阴线插入阳线一半"},
    "早晨之星": {"meaning": "下跌末端，阴线+十字+阳线，反转看涨", "hint": "阴→十字→阳", "key_features": "阴→十字→阳"},
    "黄昏之星": {"meaning": "上涨末端，阳线+十字+阴线，反转看跌", "hint": "阳→十字→阴", "key_features": "阳→十字→阴"},
    "红三兵": {"meaning": "连续三根阳线，持续看涨", "hint": "阳→阳→阳", "key_features": "三根阳线"},
    "黑三鸦": {"meaning": "连续三根阴线，持续看跌", "hint": "阴→阴→阴", "key_features": "三根阴线"},
    "上升三法": {"meaning": "上涨中，大阳+三小阴回踩+大阳创新高，看涨", "hint": "阳→阴阴阴→阳", "key_features": "回踩后创新高"},
    "下降三法": {"meaning": "下跌中，大阴+三小阳反弹+大阴创新低，看跌", "hint": "阴→阳阳阳→阴", "key_features": "反弹后创新低"},
    "锤子线": {"meaning": "下跌末端，长下影小实体，看涨", "hint": "长下影（≥实体2倍），小实体", "key_features": "长下影+小实体"},
    "射击之星": {"meaning": "上涨末端，长上影小实体，看跌", "hint": "长上影（≥实体2倍），小实体", "key_features": "长上影+小实体"},
    "倒锤子线": {"meaning": "下跌末端，长上影小实体，看涨", "hint": "长上影，小实体，出现在下跌后", "key_features": "长上影+小实体"},
    "平底": {"meaning": "多根K线最低点相同，水平支撑，看涨", "hint": "多个最低价接近相同", "key_features": "相同低点"},
    "平顶": {"meaning": "多根K线最高点相同，水平压力，看跌", "hint": "多个最高价接近相同", "key_features": "相同高点"},
    "身怀六甲": {"meaning": "大K线内包小K线，趋势可能反转", "hint": "大实体→小实体，小实体在内部", "key_features": "大包小"}
}
PATTERN_NAMES = list(PATTERN_DATA.keys())

# ============================================================
# 4. 绘图函数
# ============================================================
def plot_kline(df, title, is_intraday=False):
    if is_intraday:
        x_vals = df["time"].tolist()
        if len(x_vals) > 60:
            step = len(x_vals) // 30
            tick_vals = x_vals[::step]
        else:
            tick_vals = x_vals[::5]
        
        fig = go.Figure(data=[go.Candlestick(
            x=x_vals,
            open=df["open"], high=df["high"], low=df["low"], close=df["close"]
        )])
        avg_price = (df["high"] + df["low"] + df["close"]) / 3
        fig.add_trace(go.Scatter(x=x_vals, y=avg_price, mode='lines', name='均价线', line=dict(color='orange', width=1)))
        ma5 = df["close"].rolling(5).mean()
        fig.add_trace(go.Scatter(x=x_vals, y=ma5, mode='lines', name='MA5', line=dict(color='cyan', width=1)))
        fig.update_layout(
            title=title, height=450, template="plotly_dark", 
            xaxis_rangeslider_visible=False,
            xaxis=dict(tickvals=tick_vals, tickangle=45)
        )
    else:
        fig = go.Figure(data=[go.Candlestick(
            x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"]
        )])
        if len(df) >= 5:
            fig.add_trace(go.Scatter(x=df["date"], y=df["close"].rolling(5).mean(),
                                     mode='lines', name='MA5', line=dict(color='cyan', width=1)))
        if len(df) >= 20:
            fig.add_trace(go.Scatter(x=df["date"], y=df["close"].rolling(20).mean(),
                                     mode='lines', name='MA20', line=dict(color='purple', width=1)))
        if len(df) >= 60:
            fig.add_trace(go.Scatter(x=df["date"], y=df["close"].rolling(60).mean(),
                                     mode='lines', name='MA60', line=dict(color='yellow', width=1)))
        fig.update_layout(title=title, height=450, template="plotly_dark", xaxis_rangeslider_visible=False)
    return fig

# ============================================================
# 5. 指标计算
# ============================================================
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
    avg_price_line = cum_amount / cum_volume
    current_avg_price = avg_price_line.iloc[-1]
    
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
        macd_value = macd_line.iloc[-1]
        macd_signal_value = signal_line.iloc[-1]
        macd_hist_value = macd_hist.iloc[-1]
        if macd_line.iloc[-1] > signal_line.iloc[-1] and macd_line.iloc[-2] <= signal_line.iloc[-2]:
            macd_cross = "金叉（偏多）"
        elif macd_line.iloc[-1] < signal_line.iloc[-1] and macd_line.iloc[-2] >= signal_line.iloc[-2]:
            macd_cross = "死叉（偏空）"
        else:
            macd_cross = "无交叉"
    else:
        macd_status = "数据不足"
        macd_value = macd_signal_value = macd_hist_value = 0
        macd_cross = "数据不足"
    
    if len(slice_df) >= 15:
        delta = slice_df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1])) if loss.iloc[-1] != 0 else 100
        rsi_status = "超买区" if rsi > 70 else "超卖区" if rsi < 30 else "中性"
    else:
        rsi = 50
        rsi_status = "数据不足"
    
    day_high = slice_df["high"].max()
    day_low = slice_df["low"].min()
    price_range = day_high - day_low
    price_position_pct = (last["close"] - day_low) / price_range * 100 if price_range > 0 else 50
    price_zone = "高位区" if price_position_pct > 70 else "低位区" if price_position_pct < 30 else "中位区"
    
    bias = (last["close"] - ma5) / ma5 * 100 if ma5 > 0 else 0
    bias_status = "超买" if bias > 2 else "超卖" if bias < -2 else "正常"
    
    if last["close"] > ma5 * 1.005:
        price_position = "高于MA5 (偏强)"
    elif last["close"] < ma5 * 0.995:
        price_position = "低于MA5 (偏弱)"
    else:
        price_position = "接近MA5 (中性)"
    
    if last["close"] > current_avg_price * 1.002:
        avg_position = "高于均价线 (偏强)"
    elif last["close"] < current_avg_price * 0.998:
        avg_position = "低于均价线 (偏弱)"
    else:
        avg_position = "接近均价线 (中性)"
    
    first_open = slice_df["open"].iloc[0]
    pct_change = (last["close"] - first_open) / first_open * 100
    
    if len(slice_df) >= 20:
        circulation = slice_df["volume"].rolling(20).mean().iloc[-1] * 100
    else:
        circulation = slice_df["volume"].mean() * 100
    turnover = last["volume"] / circulation * 100 if circulation > 0 else 0
    turnover = min(turnover, 50)
    
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
    
    return {
        "last_close": last["close"], "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
        "price_position": price_position, "current_avg_price": current_avg_price,
        "avg_position": avg_position, "vol_ratio": vol_ratio,
        "vol_status": "放量" if vol_ratio > 1.5 else "缩量" if vol_ratio < 0.8 else "正常",
        "vol_price_status": vol_price_status,
        "macd_value": macd_value, "macd_signal_value": macd_signal_value,
        "macd_hist_value": macd_hist_value, "macd_status": macd_status, "macd_cross": macd_cross,
        "rsi": rsi, "rsi_status": rsi_status,
        "price_position_pct": price_position_pct, "price_zone": price_zone,
        "bias": bias, "bias_status": bias_status,
        "short_trend": short_trend, "turnover": turnover, "pct_change": pct_change,
        "first_open": first_open, "last_volume": last["volume"], "vol_avg": vol_avg,
        "prev_close": slice_df["close"].iloc[-2] if len(slice_df) >= 2 else last["close"],
        "day_high": day_high, "day_low": day_low
    }

# ============================================================
# 6. 错题本工具
# ============================================================
def init_mistakes():
    if "mistakes" not in st.session_state:
        st.session_state.mistakes = []

def record_mistake(module, question, user_answer, correct_answer, detail=""):
    st.session_state.mistakes.append({
        "module": module, "question": question,
        "user_answer": user_answer, "correct_answer": correct_answer,
        "detail": detail, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

# ============================================================
# 7. 主程序
# ============================================================
def main():
    init_mistakes()
    
    st.sidebar.header("📊 我的成绩")
    for key in ["score_pattern", "score_intra", "score_industry", "score_trade", "score_stop", "score_trend"]:
        if key not in st.session_state:
            st.session_state[key] = {"correct": 0, "total": 0}
    
    for key in ["q_pattern_answered", "q_intra_answered", "q_industry_answered", 
                "q_trade_answered", "q_stop_answered", "q_trend_answered"]:
        if key not in st.session_state:
            st.session_state[key] = False
    
    for key in ["current_pattern_q", "current_intra_q", "current_industry_q", 
                "current_trade_q", "current_stop_q", "current_trend_q"]:
        if key not in st.session_state:
            st.session_state[key] = None

    # 7个标签页
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 形态识别", "⚡ 分时实战", "🏭 板块认知", 
        "🎯 买卖点判断", "🛡️ 止损训练", "🔮 未来趋势", "📝 错题本"
    ])

    # ==========================================================
    # 标签1：形态识别
    # ==========================================================
    with tab1:
        st.subheader("任务：看K线，选形态名称（共20种）")
        with st.expander("📖 形态速查表", expanded=False):
            for name, data in PATTERN_DATA.items():
                st.markdown(f"**{name}**：{data['meaning']}  (提示：{data['hint']})")
        
        if st.button("🎲 随机出题 (形态)", use_container_width=True, key="btn_pattern"):
            with st.spinner("加载数据..."):
                random.shuffle(STOCK_POOL)
                found = False
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
                            "key_features": PATTERN_DATA[correct]["key_features"]
                        }
                        st.session_state.q_pattern_answered = False
                        found = True
                        break
                if not found:
                    st.error("⚠️ 无法获取数据")

        q = st.session_state.current_pattern_q
        if q:
            fig = plot_kline(q["df"], f"{q['name']} 日K线")
            st.plotly_chart(fig, use_container_width=True)
            
            if not st.session_state.q_pattern_answered:
                st.info(f"💡 提示：{q['hint']}")
                st.markdown("**请选择形态：**")
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
                user_choice = st.session_state.pat_user_choice
                correct = q["correct"]
                if user_choice == correct:
                    st.success(f"✅ 正确！{correct}")
                    st.markdown(f"**解释**：{q['meaning']}")
                    st.markdown(f"**关键特征**：{q['key_features']}")
                else:
                    st.error(f"❌ 错误。正确答案是 {correct}")
                    st.markdown(f"**你选的 {user_choice}**：{PATTERN_DATA[user_choice]['meaning']}")
                    st.markdown(f"**正确答案 {correct}**：{q['meaning']}")
                    st.markdown(f"🔍 关键区别：{PATTERN_DATA[user_choice]['hint']} vs {q['hint']}")
                    record_mistake("形态识别", f"{q['name']} 形态", user_choice, correct,
                                   f"关键区别：{PATTERN_DATA[user_choice]['hint']} vs {q['hint']}")
                if st.button("继续下一题 (形态)"):
                    st.session_state.current_pattern_q = None
                    st.session_state.q_pattern_answered = False
                    st.rerun()
        
        if st.session_state.score_pattern["total"] > 0:
            rate = st.session_state.score_pattern["correct"] / st.session_state.score_pattern["total"] * 100
            st.sidebar.metric("形态正确率", f"{rate:.1f}%")

    # ==========================================================
    # 标签2：分时实战
    # ==========================================================
    with tab2:
        st.subheader("任务：看分时图，判断下一根K线涨跌")
        
        with st.expander("📖 三因子评分法", expanded=False):
            st.markdown("""
            | 因子 | 看多条件 | 看空条件 |
            |------|----------|----------|
            | **趋势 (MA5)** | 价格 > MA5 | 价格 < MA5 |
            | **量能** | 放量上涨 | 放量下跌 |
            | **动能 (MACD)** | 柱>0且变长 | 柱<0且变长 |
            """)

        if st.button("🎲 随机出题 (分时)", use_container_width=True, key="btn_intra"):
            with st.spinner("生成多天分时数据..."):
                random.shuffle(STOCK_POOL)
                found = False
                for symbol in STOCK_POOL:
                    df_daily = fetch_daily(symbol)
                    if df_daily is not None and len(df_daily) >= 20:
                        num_days = random.randint(5, 10)
                        df_intra = generate_intraday_from_multiple_days(df_daily, num_days=num_days)
                        if df_intra is None or len(df_intra) < 100:
                            continue
                        total_len = len(df_intra)
                        cut_end = random.randint(60, total_len - 5)
                        cut_start = cut_end - 100
                        display_df = df_intra.iloc[cut_start:cut_end].copy().reset_index(drop=True)
                        next_idx = cut_end
                        if next_idx >= total_len:
                            continue
                        next_row = df_intra.iloc[next_idx]
                        actual_direction = "涨" if next_row["close"] > display_df.iloc[-1]["close"] else "跌"
                        indicators = calculate_all_indicators(display_df, len(display_df)-1)
                        
                        st.session_state.current_intra_q = {
                            "df": display_df, "full_df": df_intra,
                            "cut_idx": len(display_df)-1, "symbol": symbol,
                            "actual_direction": actual_direction, "next_row": next_row,
                            "indicators": indicators
                        }
                        st.session_state.q_intra_answered = False
                        found = True
                        break
                if not found:
                    st.error("⚠️ 生成失败，请重试")

        q = st.session_state.current_intra_q
        if q:
            ind = q["indicators"]
            fig = plot_kline(q["df"], f"{q['symbol']} 分时图", is_intraday=True)
            fig.add_vline(x=q['df']['time'].iloc[-1], line_width=2, line_dash="dash", line_color="yellow")
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("### 📊 指标面板")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("当前价", f"{ind['last_close']:.2f}", delta=f"{ind['pct_change']:.2f}%")
                st.caption(f"MA5: {ind['ma5']:.2f}")
            with col2:
                st.metric("量比", f"{ind['vol_ratio']:.2f}", delta=ind['vol_status'])
            with col3:
                st.metric("RSI", f"{ind['rsi']:.1f}", delta=ind['rsi_status'])
            with col4:
                st.metric("MACD柱", f"{ind['macd_hist_value']:.3f}", delta=ind['macd_status'])

            score_trend = 1 if "高于" in ind['price_position'] else -1 if "低于" in ind['price_position'] else 0
            score_volume = 1 if ind['vol_price_status'] == "放量上涨（强势）" else -1 if ind['vol_price_status'] == "放量下跌（弱势）" else 0
            score_macd = 1 if ind['macd_status'] == "多头增强" else -1 if ind['macd_status'] == "空头增强" else 0
            total_score = score_trend + score_volume + score_macd

            if not st.session_state.q_intra_answered:
                st.markdown("**下一根K线会涨还是跌？**")
                col1, col2 = st.columns(2)
                if col1.button("📈 涨", key="intra_up"):
                    st.session_state.intra_user_choice = "涨"
                    st.session_state.q_intra_answered = True
                    st.session_state.score_intra["total"] += 1
                    if q["actual_direction"] == "涨":
                        st.session_state.score_intra["correct"] += 1
                    st.rerun()
                if col2.button("📉 跌", key="intra_down"):
                    st.session_state.intra_user_choice = "跌"
                    st.session_state.q_intra_answered = True
                    st.session_state.score_intra["total"] += 1
                    if q["actual_direction"] == "跌":
                        st.session_state.score_intra["correct"] += 1
                    st.rerun()

            if st.session_state.q_intra_answered:
                user_choice = st.session_state.intra_user_choice
                actual = q["actual_direction"]
                if user_choice == actual:
                    st.success(f"✅ 正确！实际为 {actual}")
                else:
                    st.error(f"❌ 错误。你选 {user_choice}，实际为 {actual}")
                    record_mistake("分时实战", f"{q['symbol']} 分时", user_choice, actual,
                                   f"三因子：{total_score:+d}")
                
                st.markdown("### 📖 完整复盘")
                st.markdown(f"- 价格 vs MA5：{ind['price_position']}")
                st.markdown(f"- 价格 vs 均价线：{ind['avg_position']}")
                st.markdown(f"- 量价状态：{ind['vol_price_status']}")
                st.markdown(f"- MACD：{ind['macd_status']} ({ind['macd_cross']})")
                st.markdown(f"- RSI：{ind['rsi']:.1f} ({ind['rsi_status']})")
                st.markdown(f"- **三因子总分：{total_score:+d}**")
                
                if st.button("继续下一题 (分时)"):
                    st.session_state.current_intra_q = None
                    st.session_state.q_intra_answered = False
                    st.rerun()
        
        if st.session_state.score_intra["total"] > 0:
            rate = st.session_state.score_intra["correct"] / st.session_state.score_intra["total"] * 100
            st.sidebar.metric("分时正确率", f"{rate:.1f}%")

    # ==========================================================
    # 标签3：板块认知
    # ==========================================================
    with tab3:
        st.subheader("任务：看股票名称，选所属行业")
        
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
            st.markdown(f"### 股票代码：**{q['symbol']}**")
            st.markdown(f"### 它属于哪个行业？")
            
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
                user_choice = st.session_state.ind_user_choice
                if user_choice == q["correct"]:
                    st.success(f"✅ 正确！{q['symbol']} 属于 **{q['correct']}**")
                else:
                    st.error(f"❌ 错误。{q['symbol']} 属于 **{q['correct']}**")
                    record_mistake("板块认知", q['symbol'], user_choice, q['correct'])
                if st.button("继续下一题 (板块)"):
                    st.session_state.current_industry_q = None
                    st.session_state.q_industry_answered = False
                    st.rerun()
        
        if st.session_state.score_industry["total"] > 0:
            rate = st.session_state.score_industry["correct"] / st.session_state.score_industry["total"] * 100
            st.sidebar.metric("板块正确率", f"{rate:.1f}%")

    # ==========================================================
    # 标签4：买卖点判断
    # ==========================================================
    with tab4:
        st.subheader("任务：看K线图，判断当前是买点、卖点还是观望")
        
        if st.button("🎲 随机出题 (买卖点)", use_container_width=True, key="btn_trade"):
            with st.spinner("加载数据..."):
                random.shuffle(STOCK_POOL)
                found = False
                for symbol in STOCK_POOL:
                    df = fetch_daily(symbol)
                    if df is not None and len(df) >= 60:
                        cut = random.randint(40, len(df) - 5)
                        display = df.iloc[:cut].copy()
                        future = df.iloc[cut:cut+5]
                        
                        last = display.iloc[-1]
                        prev = display.iloc[-2]
                        ma20 = display["close"].rolling(20).mean().iloc[-1]
                        
                        if last["close"] > prev["high"] and last["volume"] > display["volume"].iloc[-6:-1].mean() * 1.3:
                            scene, correct_action = "突破买入", "买入"
                        elif last["low"] <= ma20 * 1.02 and last["close"] > last["open"] and last["volume"] < display["volume"].iloc[-6:-1].mean() * 0.8:
                            scene, correct_action = "回踩买入", "买入"
                        elif last["close"] < ma20 * 0.98 and last["volume"] > display["volume"].iloc[-6:-1].mean() * 1.3:
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
                        found = True
                        break
                if not found:
                    st.error("⚠️ 无法获取数据")

        q = st.session_state.current_trade_q
        if q:
            fig = plot_kline(q["df"], f"{q['symbol']} 日K线")
            st.plotly_chart(fig, use_container_width=True)
            st.info(f"📌 当前场景：**{q['scene']}**")
            
            if not st.session_state.q_trade_answered:
                col1, col2, col3 = st.columns(3)
                if col1.button("🟢 买入", key="trade_buy"):
                    st.session_state.trade_user_choice = "买入"
                    st.session_state.q_trade_answered = True
                    st.session_state.score_trade["total"] += 1
                    if q["correct_action"] == "买入":
                        st.session_state.score_trade["correct"] += 1
                    st.rerun()
                if col2.button("🔴 卖出", key="trade_sell"):
                    st.session_state.trade_user_choice = "卖出"
                    st.session_state.q_trade_answered = True
                    st.session_state.score_trade["total"] += 1
                    if q["correct_action"] == "卖出":
                        st.session_state.score_trade["correct"] += 1
                    st.rerun()
                if col3.button("⚪ 观望", key="trade_wait"):
                    st.session_state.trade_user_choice = "观望"
                    st.session_state.q_trade_answered = True
                    st.session_state.score_trade["total"] += 1
                    if q["correct_action"] == "观望":
                        st.session_state.score_trade["correct"] += 1
                    st.rerun()
            
            if st.session_state.q_trade_answered:
                user_choice = st.session_state.trade_user_choice
                if user_choice == q["correct_action"]:
                    st.success(f"✅ 正确！{q['scene']}场景下，正确操作是 **{q['correct_action']}**")
                else:
                    st.error(f"❌ 错误。{q['scene']}场景下，正确操作是 **{q['correct_action']}**")
                    record_mistake("买卖点", f"{q['symbol']} {q['scene']}", user_choice, q['correct_action'])
                
                st.markdown("### 📖 后续走势")
                st.dataframe(q["future"][["date", "open", "high", "low", "close"]])
                
                if st.button("继续下一题 (买卖点)"):
                    st.session_state.current_trade_q = None
                    st.session_state.q_trade_answered = False
                    st.rerun()
        
        if st.session_state.score_trade["total"] > 0:
            rate = st.session_state.score_trade["correct"] / st.session_state.score_trade["total"] * 100
            st.sidebar.metric("买卖点正确率", f"{rate:.1f}%")

    # ==========================================================
    # 标签5：止损训练
    # ==========================================================
    with tab5:
        st.subheader("任务：给一只股票设定止损价")
        
        if st.button("🎲 随机出题 (止损)", use_container_width=True, key="btn_stop"):
            with st.spinner("加载数据..."):
                random.shuffle(STOCK_POOL)
                found = False
                for symbol in STOCK_POOL:
                    df = fetch_daily(symbol)
                    if df is not None and len(df) >= 60:
                        cut = random.randint(40, len(df) - 5)
                        display = df.iloc[:cut].copy()
                        last_close = display.iloc[-1]["close"]
                        
                        high = display["high"]
                        low = display["low"]
                        prev_close = display["close"].shift(1)
                        tr = pd.concat([
                            high - low, (high - prev_close).abs(), (low - prev_close).abs()
                        ], axis=1).max(axis=1)
                        atr = tr.rolling(14).mean().iloc[-1]
                        
                        stop_low = last_close - 2 * atr
                        stop_high = last_close - 0.8 * atr
                        
                        st.session_state.current_stop_q = {
                            "df": display, "symbol": symbol,
                            "last_close": last_close, "atr": atr,
                            "stop_low": stop_low, "stop_high": stop_high
                        }
                        st.session_state.q_stop_answered = False
                        found = True
                        break
                if not found:
                    st.error("⚠️ 无法获取数据")

        q = st.session_state.current_stop_q
        if q:
            fig = plot_kline(q["df"], f"{q['symbol']} 日K线")
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown(f"### 当前股价：**{q['last_close']:.2f}**")
            st.markdown(f"### 假设你在此价位买入，你的止损价是多少？")
            
            if not st.session_state.q_stop_answered:
                stop_input = st.number_input("输入止损价：", value=float(round(q["last_close"] * 0.95, 2)), step=0.01)
                if st.button("提交止损价", key="submit_stop"):
                    st.session_state.stop_user_choice = stop_input
                    st.session_state.q_stop_answered = True
                    st.session_state.score_stop["total"] += 1
                    if q["stop_low"] <= stop_input <= q["stop_high"]:
                        st.session_state.score_stop["correct"] += 1
                    st.rerun()
            
            if st.session_state.q_stop_answered:
                user_stop = st.session_state.stop_user_choice
                is_reasonable = q["stop_low"] <= user_stop <= q["stop_high"]
                
                if is_reasonable:
                    st.success(f"✅ 合理！你的止损价 {user_stop:.2f} 在合理区间内")
                else:
                    st.error(f"❌ 不太合理。你的止损价 {user_stop:.2f}")
                    record_mistake("止损训练", q['symbol'], f"{user_stop:.2f}", 
                                   f"{q['stop_low']:.2f}~{q['stop_high']:.2f}")
                
                st.markdown("### 📖 分析")
                st.markdown(f"- 当前价：{q['last_close']:.2f}")
                st.markdown(f"- ATR（平均真实波幅）：{q['atr']:.2f}")
                st.markdown(f"- **合理止损区间：{q['stop_low']:.2f} ~ {q['stop_high']:.2f}**")
                
                if st.button("继续下一题 (止损)"):
                    st.session_state.current_stop_q = None
                    st.session_state.q_stop_answered = False
                    st.rerun()
        
        if st.session_state.score_stop["total"] > 0:
            rate = st.session_state.score_stop["correct"] / st.session_state.score_stop["total"] * 100
            st.sidebar.metric("止损正确率", f"{rate:.1f}%")

    # ==========================================================
    # 标签6：未来趋势判断（新增）
    # ==========================================================
    with tab6:
        st.subheader("任务：看K线图，判断未来3天是涨还是跌")
        st.caption("训练对中期趋势的判断能力")
        
        with st.expander("📖 怎么看未来趋势？", expanded=False):
            st.markdown("""
            **判断未来趋势，需要综合以下信息：**

            | 信号 | 看多条件 | 看空条件 |
            |------|----------|----------|
            | **均线排列** | 价格 > MA5 > MA20 | 价格 < MA5 < MA20 |
            | **MACD** | 柱>0且变长 | 柱<0且变长 |
            | **量价** | 放量上涨 | 放量下跌 |
            | **RSI** | < 30（超卖） | > 70（超买） |
            | **K线形态** | 底部反转形态 | 顶部反转形态 |

            **多信号共振时，趋势判断更可靠。**
            """)
        
        if st.button("🎲 随机出题 (未来趋势)", use_container_width=True, key="btn_trend"):
            with st.spinner("加载数据..."):
                random.shuffle(STOCK_POOL)
                found = False
                for symbol in STOCK_POOL:
                    df = fetch_daily(symbol)
                    if df is not None and len(df) >= 80:
                        cut = random.randint(60, len(df) - 5)
                        display = df.iloc[:cut].copy()
                        future_3 = df.iloc[cut:cut+3]
                        
                        if len(future_3) < 3:
                            continue
                        
                        # 判断未来3天涨跌
                        current_price = display.iloc[-1]["close"]
                        future_price = future_3.iloc[-1]["close"]
                        actual_direction = "涨" if future_price > current_price else "跌"
                        actual_pct = (future_price - current_price) / current_price * 100
                        
                        indicators = calculate_all_indicators(display, len(display)-1)
                        
                        st.session_state.current_trend_q = {
                            "df": display, "symbol": symbol,
                            "current_price": current_price,
                            "future_3": future_3,
                            "actual_direction": actual_direction,
                            "actual_pct": actual_pct,
                            "indicators": indicators
                        }
                        st.session_state.q_trend_answered = False
                        found = True
                        break
                if not found:
                    st.error("⚠️ 无法获取数据")

        q = st.session_state.current_trend_q
        if q:
            ind = q["indicators"]
            fig = plot_kline(q["df"], f"{q['symbol']} 日K线")
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown(f"### 当前股价：**{q['current_price']:.2f}**")
            
            # 显示当前指标
            st.markdown("### 📊 当前技术指标")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("MA5", f"{ind['ma5']:.2f}", delta=ind['price_position'])
            with col2:
                st.metric("MACD", f"{ind['macd_hist_value']:.3f}", delta=ind['macd_status'])
            with col3:
                st.metric("RSI", f"{ind['rsi']:.1f}", delta=ind['rsi_status'])
            with col4:
                st.metric("量比", f"{ind['vol_ratio']:.2f}", delta=ind['vol_status'])
            
            st.markdown(f"- 短期趋势：**{ind['short_trend']}**")
            st.markdown(f"- MACD交叉：**{ind['macd_cross']}**")
            st.markdown(f"- 量价状态：**{ind['vol_price_status']}**")
            
            if not st.session_state.q_trend_answered:
                st.markdown("### 未来3天，你认为会涨还是跌？")
                col1, col2 = st.columns(2)
                if col1.button("📈 看涨", key="trend_up"):
                    st.session_state.trend_user_choice = "涨"
                    st.session_state.q_trend_answered = True
                    st.session_state.score_trend["total"] += 1
                    if q["actual_direction"] == "涨":
                        st.session_state.score_trend["correct"] += 1
                    st.rerun()
                if col2.button("📉 看跌", key="trend_down"):
                    st.session_state.trend_user_choice = "跌"
                    st.session_state.q_trend_answered = True
                    st.session_state.score_trend["total"] += 1
                    if q["actual_direction"] == "跌":
                        st.session_state.score_trend["correct"] += 1
                    st.rerun()
            
            if st.session_state.q_trend_answered:
                user_choice = st.session_state.trend_user_choice
                actual = q["actual_direction"]
                actual_pct = q["actual_pct"]
                
                if user_choice == actual:
                    st.success(f"✅ 正确！未来3天实际 **{actual}** {abs(actual_pct):.2f}%")
                else:
                    st.error(f"❌ 错误。未来3天实际 **{actual}** {abs(actual_pct):.2f}%，你选了 {user_choice}")
                    record_mistake("未来趋势", f"{q['symbol']} 未来3天", user_choice, actual,
                                   f"实际{actual_pct:+.2f}%")
                
                st.markdown("### 📖 实际未来3天走势")
                for _, row in q["future_3"].iterrows():
                    change = (row["close"] - row["open"]) / row["open"] * 100
                    color = "🔴" if change > 0 else "🟢"
                    st.markdown(f"{color} {row['date'].strftime('%Y-%m-%d')}：开 {row['open']:.2f}，收 {row['close']:.2f}，涨跌 {change:+.2f}%")
                
                st.markdown("### 📖 复盘分析")
                st.markdown(f"- 当时 MA5：{ind['ma5']:.2f}，价格{ind['price_position']}")
                st.markdown(f"- 当时 MACD：{ind['macd_status']}")
                st.markdown(f"- 当时 RSI：{ind['rsi']:.1f}（{ind['rsi_status']}）")
                st.markdown(f"- 当时短期趋势：{ind['short_trend']}")
                
                if user_choice == actual:
                    st.info("💡 你的判断和多个指标信号一致，继续保持这种多维度分析的思路。")
                else:
                    st.info("💡 复盘一下：当时哪个指标给了你错误的信号？下次遇到类似情况要怎么修正？")
                
                if st.button("继续下一题 (未来趋势)"):
                    st.session_state.current_trend_q = None
                    st.session_state.q_trend_answered = False
                    st.rerun()
        
        if st.session_state.score_trend["total"] > 0:
            rate = st.session_state.score_trend["correct"] / st.session_state.score_trend["total"] * 100
            st.sidebar.metric("未来趋势正确率", f"{rate:.1f}%")

    # ==========================================================
    # 标签7：错题本
    # ==========================================================
    with tab7:
        st.subheader("📝 错题本")
        st.caption("自动记录所有答错的题，针对性强化薄弱环节")
        
        if len(st.session_state.mistakes) == 0:
            st.info("暂无错题。继续练习，错题会自动记录在这里。")
        else:
            st.markdown(f"### 共 {len(st.session_state.mistakes)} 道错题")
            
            modules = {}
            for m in st.session_state.mistakes:
                mod = m["module"]
                modules[mod] = modules.get(mod, 0) + 1
            
            st.markdown("#### 错题分布")
            for mod, count in sorted(modules.items(), key=lambda x: -x[1]):
                st.markdown(f"- **{mod}**：{count} 道")
            
            st.markdown("---")
            st.markdown("#### 错题列表")
            
            for i, m in enumerate(reversed(st.session_state.mistakes[-30:])):
                with st.expander(f"[{m['module']}] {m['question']} - {m['time']}"):
                    st.markdown(f"- 你的答案：**{m['user_answer']}**")
                    st.markdown(f"- 正确答案：**{m['correct_answer']}**")
                    if m.get("detail"):
                        st.markdown(f"- 解析：{m['detail']}")
            
            if st.button("清空错题本", key="clear_mistakes"):
                st.session_state.mistakes = []
                st.rerun()

if __name__ == "__main__":
    main()
