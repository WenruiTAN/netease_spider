import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(page_title="网易云数据采集", layout="wide")
st.title("🎵 网易云音乐歌手数据采集工具")

def get_basic_stats(artist_id):
    # 模拟基础浏览器 Header
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://music.163.com/'
    }
    
    try:
        # 1. 获取歌手姓名
        artist_url = f"https://music.163.com/api/v1/artist/{artist_id}"
        artist_res = requests.get(artist_url, headers=headers, timeout=10).json()
        artist_name = artist_res.get('artist', {}).get('name', '未知歌手')

        # 2. 获取热门歌曲（包含专辑信息和时间）
        songs_url = f"https://music.163.com/api/artist/top/song?id={artist_id}"
        songs_res = requests.get(songs_url, headers=headers, timeout=10).json()
        songs = songs_res.get('songs', [])
        
        if not songs:
            return None, artist_name, "该歌手暂无歌曲数据。"

        final_list = []
        progress_text = st.empty()
        progress_bar = st.progress(0)
        
        # 采集前 50 首热门歌曲
        max_scan = min(len(songs), 50)
        
        for i, song in enumerate(songs[:max_scan]):
            s_id = song['id']
            s_name = song['name']
            # 获取专辑名称
            album_name = song.get('al', {}).get('name', '未知专辑')
            # 获取发布时间（毫秒转日期）
            pub_time = pd.to_datetime(song.get('publishTime', 0), unit='ms').strftime('%Y-%m-%d') if song.get('publishTime') else "未知"
            
            # 3. 单独获取评论数
            comment_api = f"https://music.163.com/api/v1/resource/comments/R_SO_4_{s_id}?limit=0"
            try:
                c_data = requests.get(comment_api, headers=headers, timeout=5).json()
                comment_total = c_data.get('total', 0)
            except:
                comment_total = 0

            final_list.append({
                "歌曲名称": s_name,
                "所属专辑": album_name,
                "发布时间": pub_time,
                "评论总数": comment_total,
                "歌曲链接": f"https://music.163.com/#/song?id={s_id}"
            })
            
            # 更新进度
            progress_bar.progress((i + 1) / max_scan)
            progress_text.text(f"正在采集第 {i+1}/{max_scan} 首: {s_name}")

        df = pd.DataFrame(final_list)
        return df, artist_name, None

    except Exception as e:
        return None, None, f"发生错误: {str(e)}"

# --- UI 界面 ---
url_input = st.text_input("请输入歌手 ID (例如 13932773):", value="13932773")

if st.button("开始采集"):
    # 提取 ID
    match = re.search(r'id=(\d+)', url_input)
    artist_id = match.group(1) if match else url_input.strip()
    
    if not artist_id.isdigit():
        st.warning("请输入有效的数字 ID。")
    else:
        with st.spinner('数据同步中...'):
            df, name, error = get_basic_stats(artist_id)
            
        if df is not None:
            st.success(f"✅ 已完成歌手【{name}】的数据采集")
            
            # 显示表格
            st.dataframe(df, use_container_width=True)
            
            # 导出 Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            st.download_button(
                label="📥 下载 Excel 数据报表",
                data=buffer.getvalue(),
                file_name=f"{name}_歌曲清单.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.error(error)
