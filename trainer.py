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
st.title("⚔️ K线形态 + 分时实战训练器")
st.caption("形态识别练眼力 | 分时实战练盘感 | 每天30分钟，把纪律刻进骨头里")

# ============================================================
# 你的同花顺 API Key
# ============================================================
API_KEY = "sk-fuyao-poRiDItUZBZc8QGg-P-H2lj0HhAGg4PN"

# ============================================================
# 股票池
# ============================================================
STOCK_POOL = [
    "600519", "000858", "600036", "000002", "002415",
    "600276", "000651", "601318", "600030", "000725",
    "600900", "601166", "600887", "600309", "600585",
    "000333", "000568", "002594", "300750", "600809"
]

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
    start_date = end_date - timedelta(days=150)
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
# 2. 模拟分时数据生成器（多天拼接版 - 方案B）
# ============================================================
def generate_intraday_from_multiple_days(daily_df, num_days=7, bars_per_day=48):
    """
    从日线数据中随机选取连续 num_days 天，拼接生成分时K线序列。
    返回 DataFrame，包含 time（跨天）、open、high、low、close、volume。
    """
    if len(daily_df) < num_days:
        return None
    
    # 随机选择起点（确保有足够数据）
    max_start = len(daily_df) - num_days
    start_idx = random.randint(0, max_start)
    selected = daily_df.iloc[start_idx:start_idx + num_days].copy()
    
    all_times = []
    all_opens = []
    all_highs = []
    all_lows = []
    all_closes = []
    all_volumes = []
    
    # 生成基础时间
    base_time = datetime.strptime("09:30", "%H:%M").time()
    
    # 遍历每一天
    prev_close = None
    for day_idx, (_, day) in enumerate(selected.iterrows()):
        open_price = day["open"]
        high_price = day["high"]
        low_price = day["low"]
        close_price = day["close"]
        volume = day["volume"]
        
        # 如果前一天有收盘价，把今天的开盘价对齐（模拟跳空或连续）
        if prev_close is not None:
            # 保留真实跳空（用实际开盘价）
            pass
        
        # 生成这一天的48根K线
        np.random.seed(random.randint(0, 10000) + day_idx * 100)
        steps = np.random.normal(0, 0.2, bars_per_day)
        prices = np.cumsum(steps)
        prices = prices - prices[0] + open_price
        
        # 缩放
        min_p = np.min(prices)
        max_p = np.max(prices)
        range_p = max_p - min_p
        if range_p == 0:
            range_p = 0.01
        target_range = high_price - low_price
        scale = target_range / range_p
        prices_scaled = low_price + (prices - min_p) * scale
        
        # 强制收盘价
        end_diff = close_price - prices_scaled[-1]
        if bars_per_day > 1:
            adjustment = np.linspace(0, end_diff, bars_per_day)
            prices_scaled = prices_scaled + adjustment
        
        # 构造OHLC
        opens = [prices_scaled[0]]
        for i in range(1, bars_per_day):
            opens.append(prices_scaled[i-1])
        closes = prices_scaled.tolist()
        
        highs = []
        lows = []
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
        
        # 成交量
        returns = np.diff(closes, prepend=opens[0])
        vol_base = volume / bars_per_day
        vols = []
        for r in returns:
            if r > 0:
                vol = vol_base * (1 + abs(r)*8) * random.uniform(0.7, 1.3)
            else:
                vol = vol_base * (1 - abs(r)*8) * random.uniform(0.7, 1.3)
            vols.append(max(vol, 30000))
        
        # 调整成交量总和
        vol_sum = sum(vols)
        if vol_sum > 0:
            scale_vol = volume / vol_sum
            vols = [v * scale_vol for v in vols]
        
        # 生成时间标签（显示第几天 + 时间）
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
        
        prev_close = close_price
    
    df = pd.DataFrame({
        "time": all_times,
        "open": all_opens,
        "high": all_highs,
        "low": all_lows,
        "close": all_closes,
        "volume": all_volumes
    })
    return df

# ============================================================
# 3. 形态题库（20种）
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
# 4. 绘图函数（支持显示跨天）
# ============================================================
def plot_kline(df, title, is_intraday=False):
    if is_intraday:
        x_vals = df["time"].tolist()
        # 如果x轴标签太多，只显示部分
        if len(x_vals) > 60:
            step = len(x_vals) // 30
            tick_vals = x_vals[::step]
        else:
            tick_vals = x_vals[::5]
        
        fig = go.Figure(data=[go.Candlestick(
            x=x_vals,
            open=df["open"], high=df["high"], low=df["low"], close=df["close"]
        )])
        # 均价线
        avg_price = (df["high"] + df["low"] + df["close"]) / 3
        fig.add_trace(go.Scatter(x=x_vals, y=avg_price, mode='lines', name='均价线', line=dict(color='orange', width=1)))
        # MA5
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
        fig.update_layout(title=title, height=450, template="plotly_dark", xaxis_rangeslider_visible=False)
    return fig

# ============================================================
# 5. 指标计算函数（包含MACD，数据量充足时计算）
# ============================================================
def calculate_all_indicators(df, current_idx):
    """
    计算当前截取位置的所有技术指标
    """
    slice_df = df.iloc[:current_idx+1].copy()
    last = slice_df.iloc[-1]
    
    # 1. MA5
    ma5 = slice_df["close"].rolling(5).mean().iloc[-1] if len(slice_df) >= 5 else last["close"]
    
    # 2. 均价线
    avg_prices = (slice_df["open"] + slice_df["high"] + slice_df["low"] + slice_df["close"]) / 4
    cum_amount = (avg_prices * slice_df["volume"]).cumsum()
    cum_volume = slice_df["volume"].cumsum()
    avg_price_line = cum_amount / cum_volume
    current_avg_price = avg_price_line.iloc[-1]
    
    # 3. 量比
    vol_avg = slice_df["volume"].iloc[-6:-1].mean() if len(slice_df) >= 6 else slice_df["volume"].mean()
    vol_ratio = last["volume"] / vol_avg if vol_avg > 0 else 1
    
    # 4. MACD（现在数据量充足，可以稳定计算）
    if len(slice_df) >= 30:  # 降低到30根即可计算，因为数据量现在充足了
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
        macd_value = 0
        macd_signal_value = 0
        macd_hist_value = 0
        macd_cross = "数据不足"
    
    # 5. RSI（14周期）
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
    
    # 6. 价格区间位置
    day_high = slice_df["high"].max()
    day_low = slice_df["low"].min()
    price_range = day_high - day_low
    if price_range > 0:
        price_position_pct = (last["close"] - day_low) / price_range * 100
    else:
        price_position_pct = 50
    price_zone = "高位区" if price_position_pct > 70 else "低位区" if price_position_pct < 30 else "中位区"
    
    # 7. 乖离率
    if ma5 > 0:
        bias = (last["close"] - ma5) / ma5 * 100
        bias_status = "超买" if bias > 2 else "超卖" if bias < -2 else "正常"
    else:
        bias = 0
        bias_status = "正常"
    
    # 8. 价格位置判断
    if last["close"] > ma5 * 1.005:
        price_position = "高于MA5 (偏强)"
    elif last["close"] < ma5 * 0.995:
        price_position = "低于MA5 (偏弱)"
    else:
        price_position = "接近MA5 (中性)"
    
    # 9. 均价线位置
    if last["close"] > current_avg_price * 1.002:
        avg_position = "高于均价线 (偏强)"
    elif last["close"] < current_avg_price * 0.998:
        avg_position = "低于均价线 (偏弱)"
    else:
        avg_position = "接近均价线 (中性)"
    
    # 10. 涨跌幅
    first_open = slice_df["open"].iloc[0]
    pct_change = (last["close"] - first_open) / first_open * 100
    
    # 11. 换手率（模拟）
    if len(slice_df) >= 20:
        circulation = slice_df["volume"].rolling(20).mean().iloc[-1] * 100
    else:
        circulation = slice_df["volume"].mean() * 100
    turnover = last["volume"] / circulation * 100 if circulation > 0 else 0
    turnover = min(turnover, 50)
    
    # 12. 量价状态
    if len(slice_df) >= 2:
        prev_close = slice_df["close"].iloc[-2]
        if vol_ratio > 1.5:
            if last["close"] > prev_close:
                vol_price_status = "放量上涨（强势）"
            else:
                vol_price_status = "放量下跌（弱势）"
        elif vol_ratio < 0.8:
            if last["close"] > prev_close:
                vol_price_status = "缩量上涨（谨慎）"
            else:
                vol_price_status = "缩量下跌（企稳）"
        else:
            vol_price_status = "量价正常"
    else:
        vol_price_status = "数据不足"
    
    # 13. 短期趋势
    if len(slice_df) >= 3:
        recent_3 = slice_df["close"].iloc[-3:]
        short_trend = "上涨" if recent_3.iloc[-1] > recent_3.iloc[0] else "下跌"
    else:
        short_trend = "震荡"
    
    return {
        "last_close": last["close"],
        "ma5": ma5,
        "price_position": price_position,
        "current_avg_price": current_avg_price,
        "avg_position": avg_position,
        "vol_ratio": vol_ratio,
        "vol_status": "放量" if vol_ratio > 1.5 else "缩量" if vol_ratio < 0.8 else "正常",
        "vol_price_status": vol_price_status,
        "macd_value": macd_value,
        "macd_signal_value": macd_signal_value,
        "macd_hist_value": macd_hist_value,
        "macd_status": macd_status,
        "macd_cross": macd_cross,
        "rsi": rsi,
        "rsi_status": rsi_status,
        "price_position_pct": price_position_pct,
        "price_zone": price_zone,
        "bias": bias,
        "bias_status": bias_status,
        "short_trend": short_trend,
        "turnover": turnover,
        "pct_change": pct_change,
        "first_open": first_open,
        "last_volume": last["volume"],
        "vol_avg": vol_avg,
        "prev_close": slice_df["close"].iloc[-2] if len(slice_df) >= 2 else last["close"],
        "day_high": day_high,
        "day_low": day_low
    }

# ============================================================
# 6. 主程序
# ============================================================
def main():
    st.sidebar.header("📊 我的成绩")
    if "score_pattern" not in st.session_state:
        st.session_state.score_pattern = {"correct": 0, "total": 0}
    if "score_intra" not in st.session_state:
        st.session_state.score_intra = {"correct": 0, "total": 0}
    
    if "q_pattern_answered" not in st.session_state:
        st.session_state.q_pattern_answered = False
    if "current_pattern_q" not in st.session_state:
        st.session_state.current_pattern_q = None
    
    if "q_intra_answered" not in st.session_state:
        st.session_state.q_intra_answered = False
    if "current_intra_q" not in st.session_state:
        st.session_state.current_intra_q = None
    if "intra_user_choice" not in st.session_state:
        st.session_state.intra_user_choice = None

    tab1, tab2 = st.tabs(["📊 形态识别", "⚡ 分时实战"])

    # ---------- 形态识别 ----------
    with tab1:
        st.subheader("任务：看K线，选形态名称（共20种）")
        with st.expander("📖 形态速查表", expanded=False):
            for name, data in PATTERN_DATA.items():
                st.markdown(f"**{name}**：{data['meaning']}  (提示：{data['hint']})")
        
        if st.button("🎲 随机出题 (形态)", use_container_width=True):
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
                            "df": df.tail(30),
                            "name": symbol,
                            "correct": correct,
                            "options": options,
                            "meaning": PATTERN_DATA[correct]["meaning"],
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
                if st.button("继续下一题 (形态)"):
                    st.session_state.current_pattern_q = None
                    st.session_state.q_pattern_answered = False
                    st.rerun()
        
        if st.session_state.score_pattern["total"] > 0:
            rate = st.session_state.score_pattern["correct"] / st.session_state.score_pattern["total"] * 100
            st.sidebar.metric("形态正确率", f"{rate:.1f}%")
            st.sidebar.metric("形态总题", st.session_state.score_pattern["total"])

    # ---------- 分时实战（方案B：多天拼接） ----------
    with tab2:
        st.subheader("任务：看分时图，判断下一根5分钟K线涨跌")
        st.caption("多天拼接数据 | 包含完整MACD指标 | 训练趋势判断能力")
        
        with st.expander("📖 指标学习专区", expanded=False):
            st.markdown("""
            ## 三因子评分法

            | 因子 | 看多条件 | 看空条件 |
            |------|----------|----------|
            | **趋势 (MA5)** | 价格 > MA5 | 价格 < MA5 |
            | **量能** | 放量上涨 | 放量下跌 |
            | **动能 (MACD)** | 柱>0且变长 | 柱<0且变长 |

            **得分≥2 → 偏多，得分≤-2 → 偏空，中间 → 观望。**
            """)

        if st.button("🎲 随机出题 (分时)", use_container_width=True):
            with st.spinner("生成多天分时数据..."):
                random.shuffle(STOCK_POOL)
                found = False
                for symbol in STOCK_POOL:
                    df_daily = fetch_daily(symbol)
                    if df_daily is not None and len(df_daily) >= 20:
                        # 随机选择5-10天拼接
                        num_days = random.randint(5, 10)
                        df_intra = generate_intraday_from_multiple_days(df_daily, num_days=num_days)
                        if df_intra is None or len(df_intra) < 60:
                            continue
                        
                        # 随机截取连续100根
                        total_len = len(df_intra)
                        if total_len < 100:
                            continue
                        cut_end = random.randint(60, total_len - 5)
                        cut_start = cut_end - 100
                        display_df = df_intra.iloc[cut_start:cut_end].copy().reset_index(drop=True)
                        next_idx = cut_end
                        if next_idx >= total_len:
                            continue
                        next_row = df_intra.iloc[next_idx]
                        actual_direction = "涨" if next_row["close"] > display_df.iloc[-1]["close"] else "跌"
                        
                        # 计算指标（当前截取位置 = 最后一根）
                        indicators = calculate_all_indicators(display_df, len(display_df)-1)
                        
                        st.session_state.current_intra_q = {
                            "df": display_df,
                            "full_df": df_intra,
                            "cut_idx": len(display_df)-1,
                            "symbol": symbol,
                            "date_range": f"{df_daily['date'].iloc[0].strftime('%Y-%m-%d')} ~ {df_daily['date'].iloc[-1].strftime('%Y-%m-%d')}",
                            "actual_direction": actual_direction,
                            "next_row": next_row,
                            "indicators": indicators
                        }
                        st.session_state.q_intra_answered = False
                        st.session_state.intra_user_choice = None
                        found = True
                        break
                if not found:
                    st.error("⚠️ 生成失败，请重试")

        q = st.session_state.current_intra_q
        if q:
            ind = q["indicators"]
            
            fig = plot_kline(q["df"], f"{q['symbol']} 分时图 (截取至第{len(q['df'])}根)", is_intraday=True)
            fig.add_vline(x=q['df']['time'].iloc[-1], line_width=2, line_dash="dash", line_color="yellow")
            st.plotly_chart(fig, use_container_width=True)

            # ---- 指标面板 ----
            st.markdown("---")
            st.markdown("### 📊 当前指标面板")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("当前价", f"{ind['last_close']:.2f}", delta=f"{ind['pct_change']:.2f}%")
                st.caption(f"MA5: {ind['ma5']:.2f} | {ind['price_position']}")
            with col2:
                st.metric("量比", f"{ind['vol_ratio']:.2f}", delta=ind['vol_status'])
                st.caption(f"换手率: {ind['turnover']:.2f}%")
            with col3:
                st.metric("RSI", f"{ind['rsi']:.1f}", delta=ind['rsi_status'])
                st.caption(f"乖离率: {ind['bias']:.2f}%")
            with col4:
                st.metric("MACD柱", f"{ind['macd_hist_value']:.3f}", delta=ind['macd_status'])
                st.caption(f"{ind['macd_cross']}")

            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**MACD线**: {ind['macd_value']:.3f}")
                st.markdown(f"**信号线**: {ind['macd_signal_value']:.3f}")
                st.markdown(f"**柱状线**: {ind['macd_hist_value']:.3f} ({ind['macd_status']})")
            with col2:
                st.markdown(f"**短期趋势**: {ind['short_trend']}")
                st.markdown(f"**价格区间**: {ind['price_position_pct']:.1f}% ({ind['price_zone']})")
                st.markdown(f"**均价线**: {ind['avg_position']}")

            # ---- 三因子评分 ----
            st.markdown("---")
            st.markdown("### 🎯 三因子共振评分")
            
            score_trend = 1 if "高于" in ind['price_position'] else -1 if "低于" in ind['price_position'] else 0
            score_volume = 1 if ind['vol_price_status'] == "放量上涨（强势）" else -1 if ind['vol_price_status'] == "放量下跌（弱势）" else 0
            score_macd = 1 if ind['macd_status'] == "多头增强" else -1 if ind['macd_status'] == "空头增强" else 0
            total_score = score_trend + score_volume + score_macd
            
            st.markdown(f"| 因子 | 信号 | 得分 |")
            st.markdown(f"|------|------|------|")
            st.markdown(f"| **趋势 (MA5)** | {ind['price_position']} | {score_trend:+d} |")
            st.markdown(f"| **量能** | {ind['vol_price_status']} | {score_volume:+d} |")
            st.markdown(f"| **动能 (MACD)** | {ind['macd_status']} | {score_macd:+d} |")
            st.markdown(f"| **总分** | | **{total_score:+d}** |")
            
            if total_score >= 2:
                st.success("🔵 **偏多** — 趋势、量能、动能一致看多")
            elif total_score <= -2:
                st.error("🔴 **偏空** — 趋势、量能、动能一致看空")
            else:
                st.warning("🟡 **中性** — 信号矛盾，方向不明")

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

                st.markdown("---")
                st.markdown("### 📖 完整复盘")

                st.markdown("#### 1. MACD状态")
                st.markdown(f"- MACD线: {ind['macd_value']:.3f} | 信号线: {ind['macd_signal_value']:.3f}")
                st.markdown(f"- 柱状线: {ind['macd_hist_value']:.3f} → **{ind['macd_status']}**")
                st.markdown(f"- 交叉信号: {ind['macd_cross']}")
                with st.expander("🤔 怎么看MACD？"):
                    st.markdown("""
                    - **柱>0且变长** → 多头增强，偏多
                    - **柱<0且变长** → 空头增强，偏空
                    - **金叉**（线上穿信号线）→ 偏多
                    - **死叉**（线下穿信号线）→ 偏空
                    """)

                st.markdown("#### 2. 其他指标")
                st.markdown(f"- **MA5**: {ind['price_position']}")
                st.markdown(f"- **量价**: {ind['vol_price_status']}")
                st.markdown(f"- **RSI**: {ind['rsi']:.1f} ({ind['rsi_status']})")
                st.markdown(f"- **短期趋势**: {ind['short_trend']}")

                st.markdown("#### 3. 评分回顾")
                st.markdown(f"**三因子总分: {total_score:+d}** — {'偏多' if total_score >= 2 else '偏空' if total_score <= -2 else '中性'}")

                st.markdown("#### 4. 实际结果")
                st.markdown(f"- 下一根K线开盘 {q['next_row']['open']:.2f}，收盘 {q['next_row']['close']:.2f}")
                st.markdown(f"- **实际方向: {actual}**")
                
                if user_choice == actual:
                    st.success("✅ 判断正确！")
                else:
                    st.error("❌ 判断错误")

                if st.button("继续下一题 (分时)"):
                    st.session_state.current_intra_q = None
                    st.session_state.q_intra_answered = False
                    st.rerun()

        if st.session_state.score_intra["total"] > 0:
            rate = st.session_state.score_intra["correct"] / st.session_state.score_intra["total"] * 100
            st.sidebar.metric("分时正确率", f"{rate:.1f}%")
            st.sidebar.metric("分时总题", st.session_state.score_intra["total"])

if __name__ == "__main__":
    main()
