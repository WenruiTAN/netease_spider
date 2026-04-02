import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(page_title="网易云数据助手", layout="wide")
st.title("🎵 网易云音乐歌手/专辑深度数据采集")

def get_enhanced_data(artist_id):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://music.163.com/'
    }
    
    try:
        # 1. 获取歌手基本信息
        artist_url = f"https://music.163.com/api/v1/artist/{artist_id}"
        artist_res = requests.get(artist_url, headers=headers, timeout=10).json()
        artist_name = artist_res.get('artist', {}).get('name', '未知歌手')

        # 2. 获取热门歌曲
        songs_url = f"https://music.163.com/api/artist/top/song?id={artist_id}"
        songs_res = requests.get(songs_url, headers=headers, timeout=10).json()
        songs = songs_res.get('songs', [])
        
        if not songs:
            return None, None, artist_name, "未找到歌曲数据"

        song_list = []
        album_ids = set() # 用于存储不重复的专辑 ID

        # 遍历歌曲提取基本信息
        for s in songs[:50]:
            sid = s['id']
            aid = s.get('al', {}).get('id')
            aname = s.get('al', {}).get('name')
            if aid: album_ids.add((aid, aname))
            
            # 歌曲评论数
            c_api = f"https://music.163.com/api/v1/resource/comments/R_SO_4_{sid}?limit=0"
            try:
                c_total = requests.get(c_api, headers=headers, timeout=5).json().get('total', 0)
            except:
                c_total = 0

            song_list.append({
                "歌曲名称": s['name'],
                "所属专辑": aname,
                "发布时间": pd.to_datetime(s.get('publishTime', 0), unit='ms').strftime('%Y-%m-%d') if s.get('publishTime') else "未知",
                "歌曲评论数": c_total
            })

        # 3. 核心修改：采集专辑平行数据
        album_list = []
        progress_bar = st.progress(0, text="正在同步专辑维度数据...")
        
        for i, (aid, aname) in enumerate(album_ids):
            # 获取专辑详情（含收藏数和歌曲数）
            alb_detail_url = f"https://music.163.com/api/album/{aid}"
            alb_res = requests.get(alb_detail_url, headers=headers, timeout=10).json()
            
            # 专辑收藏数 (subCount)
            sub_count = alb_res.get('album', {}).get('info', {}).get('subCount', 0)
            # 专辑歌曲数
            song_count = alb_res.get('album', {}).get('size', 0)
            
            # 获取专辑自身的评论数 (注意前缀是 R_AL_3_)
            alb_comm_url = f"https://music.163.com/api/v1/resource/comments/R_AL_3_{aid}?limit=0"
            try:
                alb_comm_total = requests.get(alb_comm_url, headers=headers, timeout=5).json().get('total', 0)
            except:
                alb_comm_total = 0

            album_list.append({
                "专辑名称": aname,
                "专辑收藏数": sub_count,
                "专辑歌曲总数": song_count,
                "专辑自身评论数": alb_comm_total,
                "专辑链接": f"https://music.163.com/#/album?id={aid}"
            })
            progress_bar.progress((i + 1) / len(album_ids))

        df_songs = pd.DataFrame(song_list)
        df_albums = pd.DataFrame(album_list)
        
        return df_songs, df_albums, artist_name, None

    except Exception as e:
        return None, None, None, str(e)

# --- UI 展示 ---
inp = st.text_input("输入歌手 ID:", value="13932773")

if st.button("运行采集"):
    aid = re.search(r'id=(\d+)', inp).group(1) if 'id=' in inp else inp.strip()
    
    with st.spinner('深度解析中...'):
        df_s, df_a, name, err = get_enhanced_data(aid)
        
        if df_s is not None:
            st.success(f"已完成歌手【{name}】的全维度采集")
            
            # 第一张表：歌曲维度
            st.subheader("📊 歌曲热度清单")
            st.dataframe(df_s, use_container_width=True)
            
            # 第二张表：专辑平行维度
            st.subheader("💿 专辑汇总清单 (平行表格)")
            st.dataframe(df_a, use_container_width=True)
            
            # 导出功能
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                df_s.to_excel(writer, sheet_name="歌曲数据", index=False)
                df_a.to_excel(writer, sheet_name="专辑数据汇总", index=False)
            
            st.download_button("📥 下载完整 Excel (含双表格)", buf.getvalue(), f"{name}_全维度数据.xlsx")
        else:
            st.error(err)
