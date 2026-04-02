import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(page_title="网易云深度助手", layout="wide")

# --- 初始化 Session State (保持不变) ---
if 'df_songs' not in st.session_state:
    st.session_state.df_songs = None
if 'df_albums' not in st.session_state:
    st.session_state.df_albums = None
if 'artist_name' not in st.session_state:
    st.session_state.artist_name = ""

# --- 核心采集函数 (保持不变) ---
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

# --- 页面 UI 调整部分 ---

# 1. 标题始终居中
st.markdown("<h1 style='text-align: center;'>🎵 网易云音乐歌手数据采集</h1>", unsafe_allow_html=True)

# 2. 创建居中布局：左右 25% 留白，中间 50% 放置搜索和说明
left_col, mid_col, right_col = st.columns([1, 2, 1])

with mid_col:
    # 判断：如果没有数据，显示说明
    if st.session_state.df_songs is None:
        st.info("""
        ### 📖 使用说明 & 功能
        1. **如何操作**：在下方输入框粘贴**歌手主页链接**或直接输入**歌手 ID**。
        2. **采集内容**：
            - **歌曲清单**：获取热门歌曲信息及评论数。
            - **专辑汇总**：获取歌手专辑详情、**真实收藏数**等。
        3. **数据导出**：采集完成后可下载双 Sheet Excel 报表。
        """)

    # 输入区和按钮
    inp = st.text_input("请输入歌手 ID 或主页链接:", placeholder="例如: 13932773")
    btn_click = st.button("🚀 开始全维度采集", use_container_width=True)

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

# 3. 采集完成后的结果显示（表格通常需要较宽，所以跳出 mid_col 使用全宽或稍窄布局）
if st.session_state.df_songs is not None:
    # 结果区域稍微宽一点，比例设为 [0.5, 9, 0.5] 几乎占据全宽但两边有呼吸感
    _, res_col, _ = st.columns([0.1, 0.8, 0.1])
    
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
            file_name=f"{st.session_state.artist_name}_全维度报表.xlsx",
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
