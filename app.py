import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(page_title="网易云深度助手", layout="wide")
st.title("🎵 网易云音乐歌手/专辑深度采集")

# 增加侧边栏说明，防止用户以为卡死了
st.sidebar.info("采集说明：\n1. 歌曲采集约需 5-10 秒\n2. 专辑深度数据采集视专辑数量而定，请耐心等待进度条走完。")

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
        msg_slot = st.empty() # 创建一个动态文本槽
        
        # 采集前 30 首（减少请求压力防止无反应）
        max_s = min(len(songs), 30)
        for i in range(max_s):
            s = songs[i]
            sid = s['id']
            msg_slot.text(f"正在处理歌曲: {s['name']}")
            
            # 歌曲评论数
            try:
                c_api = f"https://music.163.com/api/v1/resource/comments/R_SO_4_{sid}?limit=0"
                c_total = requests.get(c_api, headers=headers, timeout=5).json().get('total', 0)
            except: c_total = 0

            song_data.append({
                "歌曲名称": s['name'],
                "所属专辑": s.get('al', {}).get('name'),
                "发布时间": pd.to_datetime(s.get('publishTime', 0), unit='ms').strftime('%Y-%m-%d') if s.get('publishTime') else "未知",
                "歌曲评论数": c_total
            })

        # 3. 采集专辑列表
        msg_slot.text("正在切换至专辑列表...")
        albums_url = f"https://music.163.com/api/artist/albums/{artist_id}?limit=30"
        albums_res = requests.get(albums_url, headers=headers, timeout=10).json()
        hot_albums = albums_res.get('hotAlbums', [])

        album_results = []
        alb_progress = st.progress(0)
        
        for i, alb in enumerate(hot_albums):
            aid = alb['id']
            msg_slot.text(f"正在穿透专辑收藏数据: {alb['name']}")
            
            # 获取真实的 subCount (收藏数)
            try:
                dynamic_url = f"https://music.163.com/api/album/detail/dynamic?id={aid}"
                dyn_res = requests.get(dynamic_url, headers=headers, timeout=5).json()
                real_sub_count = dyn_res.get('subCount', 0)
            except:
                real_sub_count = 0

            # 获取专辑评论数
            try:
                alb_comm_url = f"https://music.163.com/api/v1/resource/comments/R_AL_3_{aid}?limit=0"
                alb_comm_total = requests.get(alb_comm_url, headers=headers, timeout=5).json().get('total', 0)
            except:
                alb_comm_total = 0

            album_results.append({
                "专辑名称": alb['name'],
                "发布时间": pd.to_datetime(alb.get('publishTime', 0), unit='ms').strftime('%Y-%m-%d'),
                "专辑收藏数": real_sub_count,
                "专辑自身评论数": alb_comm_total,
                "专辑内歌曲数": alb.get('size', 0)
            })
            alb_progress.progress((i + 1) / len(hot_albums))

        msg_slot.empty() # 清除动态文本
        return pd.DataFrame(song_data), pd.DataFrame(album_results), artist_name

    except Exception as e:
        return None, None, str(e)

# --- UI 逻辑 ---
inp = st.text_input("请输入歌手 ID (如 13932773):", value="13932773")

if st.button("开始采集"):
    if not inp:
        st.error("请输入 ID")
    else:
        # 清除旧的显示结果
        df_s, df_a, res = get_final_data(inp)
        if df_s is not None:
            st.success(f"完成！歌手：{res}")
            st.subheader("🎵 歌曲维度")
            st.dataframe(df_s)
            st.subheader("💿 专辑汇总")
            st.dataframe(df_a)
            
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                df_s.to_excel(writer, sheet_name="歌曲", index=False)
                df_a.to_excel(writer, sheet_name="专辑", index=False)
            st.download_button("📥 下载 Excel", buf.getvalue(), f"{res}_data.xlsx")
        else:
            st.error(f"报错详情: {res}")
