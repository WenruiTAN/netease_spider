import streamlit as st
import pandas as pd
import requests
import io
import re

# --- 1. 网页配置 ---
st.set_page_config(page_title="网易云音乐数据采集工具", layout="wide", page_icon="🎵")

# --- 2. CSS 注入 (统一审美) ---
st.markdown("""
    <style>
    /* 统一大标题样式 */
    .main-title {
        font-size: 32px !important;
        font-weight: 800 !important;
        color: #0D47A1;
        text-align: center;
        margin-bottom: 30px !important;
    }
    /* 统一二级标题样式 */
    .section-header {
        font-size: 24px !important;
        font-weight: 700 !important;
        color: #333333;
        margin-top: 20px !important;
        margin-bottom: 15px !important;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    /* 蓝色便签纸卡片 */
    .blue-note {
        background-color: #E3F2FD;
        border-left: 6px solid #2196F3;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 25px;
    }
    .blue-note p {
        color: #1565C0 !important;
        margin-bottom: 8px !important;
        font-size: 16px !important;
        line-height: 1.6 !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. 初始化 Session State (保持不变) ---
if 'df_songs' not in st.session_state:
    st.session_state.df_songs = None
if 'df_albums' not in st.session_state:
    st.session_state.df_albums = None
if 'artist_name' not in st.session_state:
    st.session_state.artist_name = ""

# --- 4. 核心采集函数 (保持不变) ---
def get_final_data(artist_id):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://music.163.com/'
    }
    try:
        artist_url = f"https://music.163.com/api/v1/artist/{artist_id}"
        artist_res = requests.get(artist_url, headers=headers, timeout=10).json()
        artist_name = artist_res.get('artist', {}).get('name', '未知歌手')

        songs_url = f"https://music.163.com/api/artist/top/song?id={artist_id}"
        songs_res = requests.get(songs_url, headers=headers, timeout=10).json()
        songs = songs_res.get('songs', [])
        
        song_data = []
        msg_slot = st.empty()
        
        max_s = min(len(songs), 50)
        for i in range(max_s):
            s = songs[i]
            sid = s['id']
            msg_slot.text(f"⏳ 正在处理歌曲: {s['name']}")
            try:
                c_api = f"https://music.163.com/api/v1/resource/comments/R_SO_4_{sid}?limit=0"
                c_total = requests.get(c_api, headers=headers, timeout=5).json().get('total', 0)
            except: c_total = 0

            song_data.append({
                "歌曲名称": s['name'],
                "所属专辑": s.get('al', {}).get('name'),
                "发布时间": pd.to_datetime(s.get('publishTime', 0), unit='ms').strftime('%Y-%m-%d') if s.get('publishTime') else "未知",
                "歌曲评论数": c_total,
                "链接": f"https://music.163.com/#/song?id={sid}"
            })

        albums_url = f"https://music.163.com/api/artist/albums/{artist_id}?limit=50"
        albums_res = requests.get(albums_url, headers=headers, timeout=10).json()
        hot_albums = albums_res.get('hotAlbums', [])

        album_results = []
        alb_progress = st.progress(0)
        for i, alb in enumerate(hot_albums):
            aid = alb['id']
            msg_slot.text(f"⏳ 正在穿透专辑收藏数据: {alb['name']}")
            try:
                dynamic_url = f"https://music.163.com/api/album/detail/dynamic?id={aid}"
                dyn_res = requests.get(dynamic_url, headers=headers, timeout=5).json()
                real_sub_count = dyn_res.get('subCount', 0)
                alb_comm_url = f"https://music.163.com/api/v1/resource/comments/R_AL_3_{aid}?limit=0"
                alb_comm_total = requests.get(alb_comm_url, headers=headers, timeout=5).json().get('total', 0)
            except:
                real_sub_count = 0
                alb_comm_total = 0

            album_results.append({
                "专辑名称": alb['name'],
                "发布时间": pd.to_datetime(alb.get('publishTime', 0), unit='ms').strftime('%Y-%m-%d'),
                "专辑内歌曲数": alb.get('size', 0),
                "专辑收藏数": real_sub_count,
                "专辑自身评论数": alb_comm_total,
                "链接": f"https://music.163.com/#/album?id={aid}"
            })
            alb_progress.progress((i + 1) / len(hot_albums))

        msg_slot.empty()
        return pd.DataFrame(song_data), pd.DataFrame(album_results), artist_name
    except Exception as e:
        return None, None, str(e)

# --- 5. 界面布局 ---

st.markdown("<h1 style='text-align: center;'>🎵 网易云音乐数据采集工具</h1>", unsafe_allow_html=True)

left_col, mid_col, right_col = st.columns([1, 2, 1])

with mid_col:
    # A. 使用说明 (蓝色便签样式)
    if st.session_state.df_songs is None:
        st.markdown("""
            <div class="blue-note">
                <div style="font-size: 20px; font-weight: bold; color: #0D47A1; margin-bottom: 10px;">📖 使用说明 & 功能</div>
                <p>1. <strong>如何操作</strong>：在下方输入框粘贴<b>歌手主页链接</b>或直接输入<b>歌手 ID</b>。</p>
                <p>2. <strong>采集内容</strong>：获取热门歌曲所属专辑、发布时间、评论数，专辑明细及收藏、评论数。</p>
                <p>3. <strong>数据导出</strong>：完成后可下载双 Sheet Excel 报表。</p>
            </div>
        """, unsafe_allow_html=True)

    # B. 输入区 (配置中心感)
    st.markdown('<div class="section-header">⚙️ 采集配置</div>', unsafe_allow_html=True)
    inp = st.text_input("请输入歌手 ID 或主页链接:", placeholder="例如: 13932773")
    btn_click = st.button("🚀 开始采集", use_container_width=True)

    if btn_click:
        aid = re.search(r'id=(\d+)', inp).group(1) if 'id=' in inp else inp.strip()
        if not aid.isdigit():
            st.error("请输入有效的数字 ID")
        else:
            with st.spinner('数据采集引擎启动中...'):
                df_s, df_a, name_res = get_final_data(aid)
                if df_s is not None:
                    st.session_state.df_songs = df_s
                    st.session_state.df_albums = df_a
                    st.session_state.artist_name = name_res
                    st.rerun()
                else:
                    st.error(f"采集出错: {name_res}")

# --- 6. 结果显示 ---
if st.session_state.df_songs is not None:
    _, res_col, _ = st.columns([0.05, 0.9, 0.05])
    
    with res_col:
        st.success(f"✅ 歌手【{st.session_state.artist_name}】的数据采集已完成")
        
        # 准备 Excel 并放置下载按钮
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            st.session_state.df_songs.to_excel(writer, sheet_name="歌曲详情", index=False)
            st.session_state.df_albums.to_excel(writer, sheet_name="专辑汇总", index=False)
        
        st.download_button(
            label="📥 下载完整 Excel 报表", 
            data=buf.getvalue(), 
            file_name=f"{st.session_state.artist_name}_数据报表.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        tab1, tab2 = st.tabs(["🎵 歌曲清单", "💿 专辑汇总"])
        with tab1:
            st.dataframe(st.session_state.df_songs, use_container_width=True)
        with tab2:
            st.dataframe(st.session_state.df_albums, use_container_width=True)
        
        if st.button("🔄 清除结果重新搜索"):
            st.session_state.df_songs = None
            st.session_state.df_albums = None
            st.rerun()
