import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(page_title="网易云深度数据助手", layout="wide")
st.title("🎵 网易云音乐歌手/专辑全维度采集")

def get_full_data(artist_id):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://music.163.com/'
    }
    
    try:
        # --- 1. 获取歌手基本信息 ---
        artist_url = f"https://music.163.com/api/v1/artist/{artist_id}"
        artist_res = requests.get(artist_url, headers=headers, timeout=10).json()
        artist_name = artist_res.get('artist', {}).get('name', '未知歌手')

        # --- 2. 采集歌曲维度数据 (热门50首) ---
        songs_url = f"https://music.163.com/api/artist/top/song?id={artist_id}"
        songs_res = requests.get(songs_url, headers=headers).json()
        songs = songs_res.get('songs', [])
        
        song_list = []
        for s in songs[:50]:
            sid = s['id']
            # 获取歌曲评论数
            c_api = f"https://music.163.com/api/v1/resource/comments/R_SO_4_{sid}?limit=0"
            try:
                c_total = requests.get(c_api, headers=headers, timeout=5).json().get('total', 0)
            except: c_total = 0

            song_list.append({
                "歌曲名称": s['name'],
                "所属专辑": s.get('al', {}).get('name'),
                "发布时间": pd.to_datetime(s.get('publishTime', 0), unit='ms').strftime('%Y-%m-%d') if s.get('publishTime') else "未知",
                "歌曲评论数": c_total
            })

        # --- 3. 核心修改：从歌手主页“所有专辑”入口采集 ---
        # 这个接口只返回该歌手名下的专辑，排除了他出现在别人专辑里的情况
        albums_url = f"https://music.163.com/api/artist/albums/{artist_id}?limit=50"
        albums_res = requests.get(albums_url, headers=headers).json()
        hot_albums = albums_res.get('hotAlbums', [])

        album_data = []
        bar = st.progress(0, text="正在穿透采集专辑深度指标...")
        
        for i, alb in enumerate(hot_albums):
            aid = alb['id']
            aname = alb['name']
            # 获取专辑发布时间 (直接从专辑列表获取，最准确)
            a_pub_time = pd.to_datetime(alb.get('publishTime', 0), unit='ms').strftime('%Y-%m-%d')
            # 专辑歌曲数
            a_size = alb.get('size', 0)

            # --- 获取专辑收藏数 (subCount) ---
            # 注意：必须请求专辑详情接口
            alb_detail_url = f"https://music.163.com/api/album/{aid}"
            alb_detail = requests.get(alb_detail_url, headers=headers).json()
            sub_count = alb_detail.get('album', {}).get('info', {}).get('subCount', 0)

            # --- 获取专辑自身评论数 ---
            alb_comm_url = f"https://music.163.com/api/v1/resource/comments/R_AL_3_{aid}?limit=0"
            try:
                alb_comm_total = requests.get(alb_comm_url, headers=headers).json().get('total', 0)
            except:
                alb_comm_total = 0

            album_data.append({
                "专辑名称": aname,
                "发布时间": a_pub_time,
                "专辑收藏数": sub_count,
                "专辑自身评论数": alb_comm_total,
                "专辑内歌曲数": a_size,
                "链接": f"https://music.163.com/#/album?id={aid}"
            })
            bar.progress((i + 1) / len(hot_albums))

        return pd.DataFrame(song_list), pd.DataFrame(album_data), artist_name

    except Exception as e:
        return None, None, str(e)

# --- UI 逻辑 ---
inp = st.text_input("输入歌手 ID (如 Quinn Oulton 的 13932773):", value="13932773")

if st.button("开始深度运行"):
    aid = re.search(r'id=(\d+)', inp).group(1) if 'id=' in inp else inp.strip()
    
    with st.spinner('正在执行多维数据抓取...'):
        df_s, df_a, name_or_err = get_full_data(aid)
        
        if df_s is not None:
            st.success(f"✅ 歌手【{name_or_err}】数据抓取成功")
            
            # 歌曲表
            st.subheader("🎵 歌曲维度数据")
            st.dataframe(df_s, use_container_width=True)
            
            # 专辑表
            st.subheader("💿 歌手名下专辑汇总 (已过滤合辑/客串)")
            st.dataframe(df_a, use_container_width=True)
            
            # 导出
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                df_s.to_excel(writer, sheet_name="歌曲清单", index=False)
                df_a.to_excel(writer, sheet_name="专辑汇总", index=False)
            st.download_button("📥 下载完整 Excel 报表", buf.getvalue(), f"{name_or_err}_deep_data.xlsx")
        else:
            st.error(f"失败: {name_or_err}")
