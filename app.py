import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# ==========================================
# 0. 基础配置
# ==========================================
st.set_page_config(page_title="Today's Mood", page_icon="☁️", layout="wide")

st.markdown("""
<style>
    .stApp { background: linear-gradient(180deg, #FAFAFA 0%, #F5F5F5 100%); }
    .stForm, .css-1r6slb0, div[data-testid="stMetricValue"] {
        background-color: #FFFFFF; padding: 20px; border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04); border: 1px solid #EAEAEA;
    }
    section[data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #EAEAEA; }
    div.stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; border: none; border-radius: 8px; font-weight: 500; 
        transition: all 0.2s;
    }
    div.stButton > button:hover { opacity: 0.9; transform: scale(1.02); }
    h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; color: #333; }
</style>
""", unsafe_allow_html=True)

# 食物库
FOOD_DB_PRO = {
    "🍚 熟米饭": [116, 2.6, 25.9, 0.3],
    "🍞 全麦面包": [246, 10.6, 46.4, 1.0],
    "🍠 蒸红薯": [86, 1.57, 20.1, 0.2],
    "🌽 煮玉米": [112, 4.0, 22.8, 1.2],
    "🐔 鸡胸肉 (熟)": [165, 31.0, 0.0, 3.6],
    "🥩 牛排 (熟)": [250, 26.0, 0.0, 15.0],
    "🍤 虾仁 (熟)": [100, 21.0, 0.2, 1.1],
    "🥚 煮鸡蛋": [143, 12.0, 1.0, 10.0],
    "🥦 西兰花/绿叶菜": [35, 4.1, 4.3, 0.6],
    "🍎 苹果": [52, 0.2, 13.5, 0.2],
    "🍌 香蕉": [93, 1.4, 20.8, 0.2],
    "🥤 可乐 (330ml)": [43, 0, 10.6, 0],
    "☕ 拿铁 (无糖)": [45, 3.0, 4.0, 1.6],
    "🍔 汉堡/快餐": [250, 13.0, 25.0, 12.0],
}

ACT_MAP = {
    "🛋️ 久坐 (1.2)": 1.2,
    "🚶 轻度 (1.375)": 1.375,
    "🏃 中度 (1.55)": 1.55,
    "🏋️ 重度 (1.725)": 1.725,
    "🔥 专业 (1.9)": 1.9
}

try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except:
    st.error("❌ 数据库连接失败")
    st.stop()

# --- 辅助函数 ---
def safe_float(val): return 0.0 if val is None else float(val)
def safe_int(val): return 0 if val is None else int(val)

def calculate_targets(target_cal, weight, mode):
    p_gram = int(weight * 1.8)
    p_cal = p_gram * 4
    remain_cal = max(0, target_cal - p_cal)
    
    if "高碳" in mode:
        c_cal = remain_cal * 0.75
        f_cal = remain_cal * 0.25
    else:
        f_cal = remain_cal * 0.70
        c_cal = remain_cal * 0.30
        
    return p_gram, int(c_cal / 4), int(f_cal / 9)

# ==========================================
# 页面逻辑
# ==========================================
if 'user' not in st.session_state: st.session_state.user = None
if 'meal_tray' not in st.session_state: st.session_state.meal_tray = []

# --- A. 登录/注册 ---
if not st.session_state.user:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.write("")
        st.write("")
        st.markdown("<h1 style='text-align: center;'>Today's Mood</h1>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["登录", "注册"])
        with tab1:
            with st.form("login"):
                u = st.text_input("用户名")
                p = st.text_input("密码", type="password")
                if st.form_submit_button("登录", use_container_width=True):
                    with st.spinner("验证中..."):
                        res = supabase.table('users').select("*").eq("username", u).eq("password", p).execute()
                        if res.data:
                            st.session_state.user = res.data[0]
                            st.rerun()
                        else: st.error("错误")
        with tab2:
            with st.form("reg"):
                nu = st.text_input("新用户")
                np = st.text_input("密码", type="password")
                if st.form_submit_button("注册", use_container_width=True):
                    with st.spinner("创建中..."):
                        try:
                            supabase.table('users').insert({"username": nu, "password": np}).execute()
                            st.success("成功！请登录")
                        except: st.error("已存在")

# --- B. 引导页 ---
elif safe_float(st.session_state.user.get('height')) == 0:
    user = st.session_state.user
    st.info("👋 制定你的专属计划")
    with st.form("setup"):
        c1, c2 = st.columns(2)
        h = c1.number_input("身高", 100, 220, 160)
        w = c2.number_input("体重", 30, 200, 55)
        age = st.number_input("年龄", 10, 100, 25)
        gender = st.selectbox("性别", ["女", "男"])
        act_key = st.selectbox("活动量", list(ACT_MAP.keys()))
        deficit = st.slider("缺口 %", 0, 30, 15)
        if st.form_submit_button("生成计划"):
            supabase.table('users').update({
                "height": h, "weight": w, "age": age, "gender": gender, 
                "activity": ACT_MAP[act_key], "deficit": deficit
            }).eq("username", user['username']).execute()
            user.update({"height": h, "weight": w, "age": age, "activity": ACT_MAP[act_key], "deficit": deficit})
            st.session_state.user = user
            st.rerun()

# --- C. 主面板 ---
else:
    user = st.session_state.user
    
    # 1. 计算
    u_weight = safe_float(user.get('weight'))
    u_height = safe_float(user.get('height'))
    bmr = (10 * u_weight) + (6.25 * u_height) - (5 * safe_int(user.get('age'))) - 161
    if user.get('gender') == '男': bmr += 166
    
    # === 侧边栏 ===
    with st.sidebar:
        st.markdown(f"### 👋 {user['username']}")
        view_date = st.date_input("📅 当前查看日期", value=datetime.now())
        st.divider()
        with st.form("daily"):
            st.markdown(f"##### ⚙️ 状态校准 ({view_date.month}/{view_date.day})")
            cw = st.number_input("体重 (kg)", value=u_weight, step=0.1)
            exe = st.number_input("运动消耗", value=0, step=50)
            mode = st.radio("模式", ["高碳日", "低碳日"])
            
            if st.form_submit_button("保存 / 补录", use_container_width=True):
                with st.spinner("同步中..."):
                    supabase.table('users').update({"weight": cw}).eq("username", user['username']).execute()
                    user['weight'] = cw
                    st.session_state.user = user
                    
                    log_date_str = view_date.strftime("%Y-%m-%d")
                    now_time = datetime.now().strftime("%H:%M")
                    full_date = f"{log_date_str} {now_time}"
                    
                    tdee_now = bmr * safe_float(user.get('activity'))
                    target_now = int((tdee_now * (1 - safe_int(user.get('deficit'))/100)) + exe)
                    
                    exist_logs = supabase.table('diet_logs').select("*").eq("username", user['username']).like("date", f"{log_date_str}%").execute().data
                    
                    if exist_logs:
                        last_id = exist_logs[-1]['id']
                        # 更新时也顺便更新 mode
                        supabase.table('diet_logs').update({"weight": cw, "target": target_now, "mode": mode}).eq("id", last_id).execute()
                    else:
                        supabase.table('diet_logs').insert({
                            "username": user['username'], "date": full_date, "target": target_now, 
                            "intake": 0, "weight": cw, "deficit": target_now, "mode": mode
                        }).execute()
                    
                    st.success("已更新！")
                    time.sleep(0.5)
                    st.rerun()

        st.divider()
        if st.button("退出登录"):
            st.session_state.user = None
            st.rerun()
            
        with st.expander("高级设置"):
            if st.button("重写计划书"):
                 supabase.table('users').update({"height": 0}).eq("username", user['username']).execute()
                 user['height'] = 0
                 st.session_state.user = user
                 st.rerun()

    # === 主界面 ===
    # 动态计算目标
    tdee = bmr * safe_float(user.get('activity'))
    target_cal = int((tdee * (1 - safe_int(user.get('deficit'))/100)) + exe)
    tgt_p, tgt_c, tgt_f = calculate_targets(target_cal, u_weight, mode)
    
    query_date_str = view_date.strftime("%Y-%m-%d")
    if view_date == datetime.now().date(): display_date = "今天"
    else: display_date = f"{view_date.month}月{view_date.day}日"
    
    # 获取 DB 已记录的数据
    logs_data = supabase.table('diet_logs').select("*").eq("username", user['username']).like("date", f"{query_date_str}%").execute().data
    
    db_cal = sum([d['intake'] for d in logs_data])
    db_p = sum([d.get('protein', 0) for d in logs_data])
    db_c = sum([d.get('carbs', 0) for d in logs_data])
    db_f = sum([d.get('fat', 0) for d in logs_data])

    # 【核心升级 1】实时计算餐盘里的数据 (Tray)
    tray_cal, tray_p, tray_c, tray_f = 0, 0, 0, 0
    if st.session_state.meal_tray:
        tray_cal = sum([item['cal'] for item in st.session_state.meal_tray])
        tray_p = sum([item['p'] for item in st.session_state.meal_tray])
        tray_c = sum([item['c'] for item in st.session_state.meal_tray])
        tray_f = sum([item['f'] for item in st.session_state.meal_tray])

    # 【核心升级 1】展示总量 = 数据库已存 + 餐盘待提交
    total_show_cal = db_cal + tray_cal
    total_show_p = db_p + tray_p
    total_show_c = db_c + tray_c
    total_show_f = db_f + tray_f

    # 2. 仪表盘
    col_main, col_macros = st.columns([1, 1.5])
    with col_main:
        st.subheader(f"⚡ {display_date} 能量监控")
        remain = target_cal - total_show_cal
        color = "#28a745" if remain > 0 else "#dc3545"
        
        # 提示文案：如果有餐盘数据，显示"预览中"
        status_text = " (含餐盘)" if tray_cal > 0 else ""
        
        st.markdown(f"""
        <div style="background:#F8F9FA;padding:20px;border-radius:12px;text-align:center;border:1px solid #EEE;">
            <div style="font-size:14px;color:#888;">剩余可用{status_text}</div>
            <div style="font-size:40px;font-weight:bold;color:{color};">{remain}</div>
            <div style="font-size:12px;color:#AAA;"> / {target_cal} Kcal</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_macros:
        st.subheader("🧬 营养素进度")
        def macro_bar(label, current, target, color):
            pct = min(1.0, current / target) if target > 0 else 0
            st.markdown(f"""
            <div style="margin-bottom:8px;">
                <div style="display:flex;justify-content:space-between;font-size:14px;margin-bottom:4px;">
                    <span><b>{label}</b></span>
                    <span>{int(current)} / {target}g</span>
                </div>
                <div style="background:#EEE;height:10px;border-radius:5px;overflow:hidden;">
                    <div style="background:{color};width:{pct*100}%;height:100%;transition:width 0.3s;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        macro_bar("蛋白质", total_show_p, tgt_p, "#4EA8DE")
        macro_bar("碳水", total_show_c, tgt_c, "#80ED99")
        macro_bar("脂肪", total_show_f, tgt_f, "#FFB7B2")

    st.divider()

    # 3. 记录区
    st.subheader(f"🍽️ 记录饮食 ({display_date})")
    c_food, c_list = st.columns([1, 1.2])
    with c_food:
        with st.container():
            f_col, w_col = st.columns([2, 1])
            sel_food = f_col.selectbox("选择食物", ["🔍 自定义"] + list(FOOD_DB_PRO.keys()))
            
            p_val, c_val, f_val = 0, 0, 0
            if sel_food == "🔍 自定义":
                custom_name = st.text_input("名称", placeholder="例如：拿铁")
                cal_val = w_col.number_input("热量", 0, 2000, 0)
                with st.expander("填写营养素 (可选)"):
                    cc1, cc2, cc3 = st.columns(3)
                    p_val = cc1.number_input("蛋(g)", 0, 100, 0)
                    c_val = cc2.number_input("碳(g)", 0, 100, 0)
                    f_val = cc3.number_input("脂(g)", 0, 100, 0)
                d_name = custom_name if custom_name else "自定义"
            else:
                weight = w_col.number_input("重量(g)", 0, 2000, 100, step=10)
                base = FOOD_DB_PRO[sel_food]
                ratio = weight / 100
                cal_val = int(base[0] * ratio)
                p_val, c_val, f_val = round(base[1]*ratio, 1), round(base[2]*ratio, 1), round(base[3]*ratio, 1)
                d_name = f"{sel_food} {weight}g"
                f_col.caption(f"含: P{p_val} C{c_val} F{f_val}")

            if st.button("➕ 加入餐盘", use_container_width=True):
                if cal_val > 0:
                    st.session_state.meal_tray.append({
                        "name": d_name, "cal": cal_val, "p": p_val, "c": c_val, "f": f_val
                    })
                    st.success(f"已加入：{d_name}")
                    time.sleep(0.1) # 快速刷新
                    st.rerun()

    with c_list:
        if st.session_state.meal_tray:
            total_c = 0
            for i, item in enumerate(st.session_state.meal_tray):
                c1, c2 = st.columns([3, 1])
                c1.text(f"{i+1}. {item['name']}")
                c2.text(f"{item['cal']}")
                total_c += item['cal']
            
            st.markdown(f"<div style='text-align:right;font-weight:bold;font-size:20px;'>总计: {total_c} Kcal</div>", unsafe_allow_html=True)
            
            b1, b2 = st.columns([3, 1])
            if b1.button("✅ 确认打卡"):
                with st.spinner("打卡中..."):
                    log_date_str = view_date.strftime("%Y-%m-%d")
                    now_time = datetime.now().strftime("%H:%M")
                    full_date = f"{log_date_str} {now_time}"
                    
                    real_deficit = target_cal - act_cal - total_c
                    tp = sum([x['p'] for x in st.session_state.meal_tray])
                    tc = sum([x['c'] for x in st.session_state.meal_tray])
                    tf = sum([x['f'] for x in st.session_state.meal_tray])
                    
                    # 【核心升级 2】记录 mode
                    supabase.table('diet_logs').insert({
                        "username": user['username'], "date": full_date, "target": target_cal, 
                        "intake": total_c, "weight": u_weight, "deficit": real_deficit,
                        "protein": tp, "carbs": tc, "fat": tf, "mode": mode
                    }).execute()
                    
                    st.session_state.meal_tray = []
                    st.success(f"已记录到 {display_date}！")
                    time.sleep(1)
                    st.rerun()
            if b2.button("清空"):
                st.session_state.meal_tray = []
                st.rerun()
        else:
            st.info(f"给 {display_date} 的餐盘加点东西吧~")

    st.divider()
    
    # ==========================================
    # 4. 趋势图 (连线 + 颜色区分高低碳)
    # ==========================================
    st.subheader("📈 趋势分析")
    
    logs = supabase.table('diet_logs').select("*").eq("username", user['username']).execute().data
    
    if logs:
        df = pd.DataFrame(logs)
        df['date_obj'] = pd.to_datetime(df['date']).dt.date
        
        # 聚合时，取当天出现次数最多的 mode (或者最后一次的 mode)
        # 这里为了简单，我们取 'last'
        daily = df.groupby('date_obj').agg({
            'intake':'sum', 'weight':'last', 'deficit':'min', 
            'mode': 'last' # 获取当天的模式
        }).reset_index().sort_values('date_obj')
        
        min_date = daily['date_obj'].min()
        max_date = daily['date_obj'].max()
        default_start = max(min_date, max_date - timedelta(days=6))
        
        c_date, c_space = st.columns([1, 2])
        with c_date:
            sel_dates = st.date_input("📊 图表范围", value=(default_start, max_date), min_value=min_date, max_value=max_date)
        
        if isinstance(sel_dates, tuple) and len(sel_dates) == 2:
            start_d, end_d = sel_dates
            mask = (daily['date_obj'] >= start_d) & (daily['date_obj'] <= end_d)
            chart_df = daily.loc[mask]
        else:
            chart_df = daily

        if not chart_df.empty:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # 【核心升级 3】设置颜色映射
            # 高碳日=橙色，低碳日=蓝色
            colors = chart_df['mode'].map(lambda x: '#F4A261' if x == '高碳日' else '#2A9D8F').tolist()
            
            # 左轴：缺口 (连线 + 彩色点)
            fig.add_trace(
                go.Scatter(
                    x=chart_df['date_obj'], y=chart_df['deficit'], 
                    name="热量缺口", 
                    mode='lines+markers', # 连线+点
                    line=dict(color='#888', width=1, dash='dot'), # 线是灰色虚线
                    marker=dict(size=10, color=colors, symbol='circle', line=dict(width=2, color='white')), # 点是彩色
                    text=chart_df['mode'], # 鼠标悬停显示是高碳还是低碳
                ),
                secondary_y=False
            )
            
            fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.3, secondary_y=False)
            
            # 右轴：体重
            fig.add_trace(go.Scatter(x=chart_df['date_obj'], y=chart_df['weight'], name="体重", mode='lines+markers', line=dict(color='#E63946', width=3)), secondary_y=True)

            fig.update_layout(height=350, margin=dict(l=0,r=0,t=20,b=0), plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", y=1.1, x=1))
            fig.update_xaxes(tickformat="%m-%d", dtick="D1")
            fig.update_yaxes(title_text="缺口 (Kcal)", tickformat="d", secondary_y=False, showgrid=False)
            fig.update_yaxes(title_text="体重 (kg)", tickformat=".1f", secondary_y=True, showgrid=True, gridcolor='#EEE')
            st.plotly_chart(fig, use_container_width=True)
            
            st.caption("🟠 橙色点：高碳日 | 🔵 蓝色点：低碳日")
        else:
            st.warning("该时间段无数据")
    else:
        st.info("暂无数据")