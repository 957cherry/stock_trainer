import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import random
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="K线训练器", layout="wide")
st.title("⚔️ K线形态训练器（同花顺数据）")

# ---------- 你的 API Key ----------
API_KEY = "sk-fuyao-poRiDItUZBZc8QGg-P-H2lj0HhAGg4PN"

# ---------- 股票池 ----------
STOCK_POOL = [
    "600519", "000858", "600036", "000002", "002415",
    "600276", "000651", "601318", "600030", "000725",
    "600900", "601166", "600887", "600309", "600585",
    "000333", "000568", "002594", "300750", "600809"
]

# ---------- 获取数据 ----------
def fetch_kline(symbol):
    if symbol.startswith("60") or symbol.startswith("68"):
        code = symbol + ".SH"
    else:
        code = symbol + ".SZ"
    
    url = "https://fuyao.aicubes.cn/api/a-share/prices/historical"
    headers = {"X-api-key": API_KEY}
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=120)
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

# ---------- 20种形态题库 ----------
PATTERN_DATA = {
    # ===== 单根K线 =====
    "大阳线": {
        "meaning": "收盘价远高于开盘价，实体很长，代表买方力量强劲，看涨",
        "hint": "看最后一根K线：实体是不是很长（几乎没有上下影线），收盘价比开盘价高很多",
        "key_features": "实体很长（>3%涨幅），上下影线很短",
        "category": "单根K线"
    },
    "大阴线": {
        "meaning": "收盘价远低于开盘价，实体很长，代表卖方力量强劲，看跌",
        "hint": "看最后一根K线：实体是不是很长（几乎没有上下影线），收盘价比开盘价低很多",
        "key_features": "实体很长（>3%跌幅），上下影线很短",
        "category": "单根K线"
    },
    "十字星": {
        "meaning": "开盘价和收盘价几乎相等，多空胶着、方向不明，趋势可能反转",
        "hint": "看最后一根K线：实体非常小，几乎是一条横线，上下影线可以长可以短",
        "key_features": "实体极小（<0.5%），上下影线明显",
        "category": "单根K线"
    },
    "T字线": {
        "meaning": "开盘价=收盘价，有长下影线，代表下方有强支撑，出现在下跌末端看涨",
        "hint": "看最后一根K线：开盘价=收盘价，有很长的下影线，没有上影线或很短",
        "key_features": "开盘=收盘，长下影线，无上影线",
        "category": "单根K线"
    },
    
    # ===== 双根K线组合 =====
    "看涨吞没": {
        "meaning": "下跌趋势中，一根大阳线完全包住前一根阴线，底部反转看涨",
        "hint": "看最后两根K线：前一根是阴线（绿色），后一根是大阳线（红色），且阳线实体完全覆盖了阴线的实体",
        "key_features": "阴线 → 大阳线（阳线实体完全包住阴线）",
        "category": "双根组合"
    },
    "看跌吞没": {
        "meaning": "上涨趋势中，一根大阴线完全包住前一根阳线，顶部反转看跌",
        "hint": "看最后两根K线：前一根是阳线（红色），后一根是大阴线（绿色），且阴线实体完全覆盖了阳线的实体",
        "key_features": "阳线 → 大阴线（阴线实体完全包住阳线）",
        "category": "双根组合"
    },
    "曙光初现": {
        "meaning": "下跌趋势中，先出现一根阴线，后出现一根大阳线，且阳线收盘价深入阴线实体一半以上，看涨",
        "hint": "看最后两根K线：前一根是阴线，后一根是大阳线，阳线的收盘价超过了前一根阴线实体的一半位置",
        "key_features": "阴线 → 阳线（阳线插入阴线实体一半以上）",
        "category": "双根组合"
    },
    "乌云盖顶": {
        "meaning": "上涨趋势中，先出现一根阳线，后出现一根大阴线，且阴线收盘价深入阳线实体一半以上，看跌",
        "hint": "看最后两根K线：前一根是阳线，后一根是大阴线，阴线的收盘价跌破了前一根阳线实体的一半位置",
        "key_features": "阳线 → 阴线（阴线插入阳线实体一半以上）",
        "category": "双根组合"
    },
    
    # ===== 三根K线组合 =====
    "早晨之星": {
        "meaning": "下跌末端，大阴线 + 十字星 + 大阳线，三根K线组成，反转看涨",
        "hint": "看最后三根K线：第一根大阴线（跌），第二根十字星（犹豫），第三根大阳线（涨）",
        "key_features": "三根组合：阴→十字→阳",
        "category": "三根组合"
    },
    "黄昏之星": {
        "meaning": "上涨末端，大阳线 + 十字星 + 大阴线，三根K线组成，反转看跌",
        "hint": "看最后三根K线：第一根大阳线（涨），第二根十字星（犹豫），第三根大阴线（跌）",
        "key_features": "三根组合：阳→十字→阴",
        "category": "三根组合"
    },
    "红三兵": {
        "meaning": "连续三根阳线，实体逐渐增大或持平，持续看涨",
        "hint": "看最后三根K线：全部是阳线（红色），实体不小，收盘价一根比一根高",
        "key_features": "阳→阳→阳（连续三根阳线）",
        "category": "三根组合"
    },
    "黑三鸦": {
        "meaning": "连续三根阴线，实体逐渐增大或持平，持续看跌",
        "hint": "看最后三根K线：全部是阴线（绿色），实体不小，收盘价一根比一根低",
        "key_features": "阴→阴→阴（连续三根阴线）",
        "category": "三根组合"
    },
    "上升三法": {
        "meaning": "上涨趋势中，一根大阳线 + 三根小阴线回踩 + 一根大阳线创新高，持续看涨",
        "hint": "看最后五根K线：第一根大阳线，中间三根小阴线（回踩不破大阳线底部），最后一根大阳线创新高",
        "key_features": "阳→阴阴阴→阳（中间三根小阴线回踩）",
        "category": "三根组合"
    },
    "下降三法": {
        "meaning": "下跌趋势中，一根大阴线 + 三根小阳线反弹 + 一根大阴线创新低，持续看跌",
        "hint": "看最后五根K线：第一根大阴线，中间三根小阳线（反弹不破大阴线顶部），最后一根大阴线创新低",
        "key_features": "阴→阳阳阳→阴（中间三根小阳线反弹）",
        "category": "三根组合"
    },
    
    # ===== 特殊形态 =====
    "锤子线": {
        "meaning": "下跌末端，长下影线（影线是实体的2倍以上），小实体，看涨",
        "hint": "看最后一根K线：有很长的下影线（至少是实体的2倍），实体很小，出现在下跌后",
        "key_features": "长下影线 + 小实体",
        "category": "特殊形态"
    },
    "射击之星": {
        "meaning": "上涨末端，长上影线（影线是实体的2倍以上），小实体，看跌",
        "hint": "看最后一根K线：有很长的上影线（至少是实体的2倍），实体很小，出现在上涨后",
        "key_features": "长上影线 + 小实体",
        "category": "特殊形态"
    },
    "倒锤子线": {
        "meaning": "下跌末端，长上影线（影线是实体的2倍以上），小实体，看涨",
        "hint": "看最后一根K线：有很长的上影线（至少是实体的2倍），实体很小，出现在下跌后",
        "key_features": "长上影线 + 小实体（出现在下跌末端）",
        "category": "特殊形态"
    },
    "平底": {
        "meaning": "两根或多根K线的最低点相同，形成水平支撑，看涨",
        "hint": "看最后几根K线：最低点是否都在同一水平线上（差不多相同）",
        "key_features": "多根K线最低价接近相同",
        "category": "特殊形态"
    },
    "平顶": {
        "meaning": "两根或多根K线的最高点相同，形成水平压力，看跌",
        "hint": "看最后几根K线：最高点是否都在同一水平线上（差不多相同）",
        "key_features": "多根K线最高价接近相同",
        "category": "特殊形态"
    },
    "身怀六甲": {
        "meaning": "一根大K线后面跟一根小K线，小K线的实体完全被大K线实体包裹，趋势可能反转",
        "hint": "看最后两根K线：前一根是大K线，后一根是小K线，小K线的实体完全在前一根的实体内部",
        "key_features": "大实体 → 小实体（被包裹在内部）",
        "category": "特殊形态"
    }
}
PATTERN_NAMES = list(PATTERN_DATA.keys())

# ---------- 绘图 ----------
def plot_kline(df, title):
    fig = go.Figure(data=[go.Candlestick(
        x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"]
    )])
    fig.update_layout(title=title, height=450, template="plotly_dark", xaxis_rangeslider_visible=False)
    return fig

# ---------- 主程序 ----------
def main():
    st.sidebar.header("📊 我的成绩")
    if "score" not in st.session_state:
        st.session_state.score = {"correct": 0, "total": 0}
    if "q_answered" not in st.session_state:
        st.session_state.q_answered = False
    if "current_q" not in st.session_state:
        st.session_state.current_q = None
    if "user_choice" not in st.session_state:
        st.session_state.user_choice = None

    tab1, tab2 = st.tabs(["📊 形态识别", "⚡ 分时实战"])

    with tab1:
        st.subheader("任务：看K线，选形态名称（共20种）")
        
        # 分类速查表
        with st.expander("📖 所有形态速查表（点开看）", expanded=False):
            categories = ["单根K线", "双根组合", "三根组合", "特殊形态"]
            for cat in categories:
                st.markdown(f"### {cat}")
                for name, data in PATTERN_DATA.items():
                    if data["category"] == cat:
                        st.markdown(f"**{name}**：{data['meaning']}")
                st.markdown("---")
        
        if st.button("🎲 随机出题", use_container_width=True):
            with st.spinner("正在加载数据..."):
                random.shuffle(STOCK_POOL)
                found = False
                for symbol in STOCK_POOL:
                    df = fetch_kline(symbol)
                    if df is not None and len(df) >= 30:
                        correct = random.choice(PATTERN_NAMES)
                        options = [correct] + random.sample([p for p in PATTERN_NAMES if p != correct], 3)
                        random.shuffle(options)
                        st.session_state.current_q = {
                            "df": df.tail(30),
                            "name": symbol,
                            "correct": correct,
                            "options": options,
                            "hint": PATTERN_DATA[correct]["hint"],
                            "meaning": PATTERN_DATA[correct]["meaning"],
                            "key_features": PATTERN_DATA[correct]["key_features"],
                            "category": PATTERN_DATA[correct]["category"]
                        }
                        st.session_state.q_answered = False
                        st.session_state.user_choice = None
                        found = True
                        break
                if not found:
                    st.error("⚠️ 无法获取数据，请检查网络或API Key")

        q = st.session_state.current_q
        if q:
            fig = plot_kline(q["df"], f"{q['name']} 日K线")
            st.plotly_chart(fig, use_container_width=True)
            
            if not st.session_state.q_answered:
                st.info(f"💡 **提示**：{q['hint']}")
            
            if not st.session_state.q_answered:
                st.markdown("**请选择你认为最符合的形态：**")
                cols = st.columns(4)
                for i, opt in enumerate(q["options"]):
                    with cols[i]:
                        if st.button(opt, key=f"q1_{i}"):
                            st.session_state.user_choice = opt
                            st.session_state.q_answered = True
                            st.session_state.score["total"] += 1
                            if opt == q["correct"]:
                                st.session_state.score["correct"] += 1
                            st.rerun()
            
            if st.session_state.q_answered:
                user_choice = st.session_state.user_choice
                correct = q["correct"]
                correct_data = PATTERN_DATA[correct]
                
                if user_choice == correct:
                    st.success(f"✅ 正确！{correct}")
                    st.markdown(f"**类别**：{correct_data['category']}")
                    st.markdown(f"**解释**：{correct_data['meaning']}")
                    st.markdown(f"**关键特征**：{correct_data['key_features']}")
                else:
                    user_data = PATTERN_DATA[user_choice]
                    st.error(f"❌ 错误。正确答案是 **{correct}**")
                    st.markdown("---")
                    st.markdown("### 📖 详细分析")
                    st.markdown(f"**你选的是：{user_choice}**（类别：{user_data['category']}）")
                    st.markdown(f"**正确答案：{correct}**（类别：{correct_data['category']}）")
                    st.markdown("")
                    st.markdown(f"**{user_choice} 的特征**：{user_data['meaning']}")
                    st.markdown(f"**{correct} 的特征**：{correct_data['meaning']}")
                    st.markdown("")
                    st.markdown(f"🔍 **关键区别**：")
                    st.markdown(f"- {user_choice}：{user_data['key_features']}")
                    st.markdown(f"- {correct}：{correct_data['key_features']}")
                    st.markdown("")
                    st.markdown(f"💡 **提示**：下次注意观察 {correct_data['hint']}")
                
                if st.button("继续下一题", use_container_width=True):
                    st.session_state.current_q = None
                    st.session_state.q_answered = False
                    st.session_state.user_choice = None
                    st.rerun()

        if st.session_state.score["total"] > 0:
            rate = st.session_state.score["correct"] / st.session_state.score["total"] * 100
            st.sidebar.metric("✅ 正确率", f"{rate:.1f}%")
            st.sidebar.metric("📝 总题数", st.session_state.score["total"])

    with tab2:
        st.subheader("分时实战 - 即将上线")

if __name__ == "__main__":
    main()
