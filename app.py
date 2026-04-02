import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(page_title="网易云深度助手", layout="wide")
st.title("🎵 网易云音乐歌手/专辑全维度采集")

def get_final_data(artist_id):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://music.163.com/'
    }
    
    try:
        # 1. 获取歌手名
        artist_url = f"https://music.163.com/api/v1/artist/{artist_id}"
        artist_res = requests.get(artist_url, headers=headers).json()
        artist_name = artist_res.get('artist', {}).get('name', '未知歌手')

        # 2. 获取歌曲列表 (保持原样)
        songs_url = f"https://music.163.com/api/artist/top/song?id={artist_id}"
        songs_res = requests.get(songs_url, headers=headers).json()
        songs = songs_res.get('songs', [])
        
        song_data = []
        for s in songs[:50]:
            sid = s['id']
            # 歌曲评论数
            c_api = f"https://music.163.com/api/v1/resource/comments/R_SO_4_{sid}?limit=0"
            try:
                c_total = requests.get(c_api, headers=headers).json().get('total', 0)
            except: c_total = 0

            song_data.append({
                "歌曲名称": s['name'],
                "所属专辑": s.get('al', {}).get('name'),
                "发布时间": pd.to_datetime(s.get('publishTime', 0), unit='ms').strftime('%Y-%m-%d') if s.get('publishTime') else "未知",
                "歌曲评论数": c_total
            })

        # 3. 核心修正：获取歌手主页专辑列表
        albums_url = f"https://music.163.com/api/artist/albums/{artist_id}?limit=50"
        albums_res = requests.get(albums_url, headers=headers).json()
        hot_albums = albums_res.get('hotAlbums', [])

        album_results = []
        bar = st.progress(0, text="正在穿透采集专辑收藏数据...")
        
        for i, alb in enumerate(hot_albums):
            aid = alb['id']
            # 专辑发布时间
            a_pub_time = pd.to_datetime(alb.get('publishTime', 0), unit='ms').strftime('%Y-%m-%d')
            
            # --- 修正点：调用动态信息接口获取真实的 subCount (收藏数) ---
            # 这是一个专用的计数接口，不容易返回0
            dynamic_url = f"https://music.163.com/api/album/detail/dynamic?id={aid}"
            try:
                dyn_res = requests.get(dynamic_url, headers=headers).json()
                # 提取真实的收藏数
                real_sub_count = dyn_res.get('subCount', 0)
            except:
                real_sub_count = 0

            # 获取专辑评论数
            alb_comm_url = f"https://music.163.com/api/v1/resource/comments/R_AL_3_{aid}?limit=0"
            try:
                alb_comm_total = requests.get(alb_comm_url, headers=headers).json().get('total', 0)
            except:
                alb_comm_total = 0

            album_results.append({
                "专辑名称": alb['name'],
                "发布时间": a_pub_time,
                "专辑收藏数": real_sub_count,
                "专辑自身评论数": alb_comm_total,
                "专辑内歌曲数": alb.get('size', 0),
                "链接": f"https://music.163.com/#/album?id={aid}"
            })
            bar.progress((i + 1) / len(hot_albums))

        return pd.DataFrame(song_data), pd.DataFrame(album_results), artist_name

    except Exception as e:
        return None, None, str(e)

# --- UI 逻辑不变 ---
inp = st.text_input("输入歌手 ID (如 13932773):", value="13932773")
if st.button("开始深度采集"):
    aid = re.search(r'id=(\d+)', inp).group(1) if 'id=' in inp else inp.strip()
    df_s, df_a, name_or_err = get_final_data(aid)
    if df_s is not None:
        st.success(f"已完成歌手【{name_or_err}】数据抓取")
        st.subheader("🎵 歌曲维度数据")
        st.dataframe(df_s, use_container_width=True)
        st.subheader("💿 专辑汇总清单")
        st.dataframe(df_a, use_container_width=True)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_s.to_excel(writer, sheet_name="歌曲清单", index=False)
            df_a.to_excel(writer, sheet_name="专辑汇总", index=False)
        st.download_button("📥 下载完整报表", buf.getvalue(), f"{name_or_err}_data.xlsx")
    else:
        st.error(name_or_err)
