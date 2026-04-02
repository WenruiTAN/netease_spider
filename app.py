import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(page_title="网易云深度助手", layout="wide")

# --- 初始化 Session State ---
if 'df_songs' not in st.session_state:
    st.session_state.df_songs = None
if 'df_albums' not in st.session_state:
    st.session_state.df_albums = None
if 'artist_name' not in st.session_state:
    st.session_state.artist_name = ""

# --- 核心采集函数 ---
def get_final_data(artist_id):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://music.163.com/'
    }
    try:
        # 1. 获取歌手名
        artist_url = f"https://music.163.com/api/v1/artist/{artist_id}"
        artist_res = requests.get(artist_url, headers=headers, timeout=10).json()
        artist_name = artist_res.get('artist', {}).get('name', '未知歌手')

        # 2. 获取歌曲列表
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

        # 3. 采集专辑列表
        msg_slot.text("正在切换至专辑列表...")
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

# --- 页面 UI ---
st.title("🎵 网易云音乐歌手数据采集")

# --- 判断：如果没有数据（未搜索），显示使用说明 ---
if st.session_state.df_songs is None:
    st.info("""
    ### 📖 使用说明 & 功能
    1. **如何操作**：在下方输入框粘贴**歌手主页链接**或直接输入**歌手 ID**。
    2. **采集内容**：
        - **歌曲清单**：获取热门歌曲的发布时间、所属专辑及歌曲评论数。
        - **专辑汇总**：获取歌手名下所有专辑的发布时间、歌曲数、**真实收藏数**及**专辑自身评论数**。
    3. **数据导出**：采集完成后可下载包含两个 Sheet 的完整 Excel 报表。
    """)

# --- 输入区 ---
inp = st.text_input("请输入歌手 ID 或主页链接:", placeholder="例如: 13932773")

if st.button("🚀 开始全维度采集"):
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
                # 触发重新运行以隐藏说明文字
                st.rerun()
            else:
                st.error(f"采集出错: {name_res}")

# --- 显示结果逻辑 ---
if st.session_state.df_songs is not None:
    st.success(f"✅ 歌手【{st.session_state.artist_name}】的数据采集已完成")
    
    # 准备 Excel
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        st.session_state.df_songs.to_excel(writer, sheet_name="歌曲详情", index=False)
        st.session_state.df_albums.to_excel(writer, sheet_name="专辑汇总", index=False)
    
    st.download_button(
        label="📥 下载完整 Excel 报表", 
        data=buf.getvalue(), 
        file_name=f"{st.session_state.artist_name}_全维度报表.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    tab1, tab2 = st.tabs(["🎵 歌曲清单", "💿 专辑汇总"])
    with tab1:
        st.dataframe(st.session_state.df_songs, use_container_width=True)
    with tab2:
        st.dataframe(st.session_state.df_albums, use_container_width=True)
    
    # 提供重置按钮
    if st.button("🔄 清除结果重新搜索"):
        st.session_state.df_songs = None
        st.session_state.df_albums = None
        st.rerun()
