import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(page_title="网易云音乐数据采集", layout="wide")

st.title("🎵 网易云音乐歌手数据采集工具 (轻量云端版)")

def get_artist_info(artist_id):
    # 模拟手机端 User-Agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/04.1',
        'Referer': 'https://music.163.com/'
    }
    
    # 接口1：获取歌手热门歌曲和基本信息
    url = f"https://music.163.com/api/artist/top/song?id={artist_id}"
    res = requests.get(url, headers=headers)
    data = res.json()
    
    if data.get('code') != 200:
        return None, "未找到歌手信息，请检查 ID 是否正确。"
    
    songs = data.get('songs', [])
    artist_name = songs[0]['ar'][0]['name'] if songs else "未知歌手"
    
    # 接口2：获取每首歌的评论数 (通过歌曲列表循环)
    final_data = []
    progress_bar = st.progress(0)
    
    # 为了演示速度，默认取前15首
    count = min(len(songs), 15)
    for i, song in enumerate(songs[:count]):
        s_id = song['id']
        s_name = song['name']
        
        # 获取评论总数
        comment_url = f"https://music.163.com/api/v1/resource/comments/R_SO_4_{s_id}?limit=0"
        c_res = requests.get(comment_url, headers=headers).json()
        total_comments = c_res.get('total', 0)
        
        final_data.append({
            "歌手": artist_name,
            "歌曲名称": s_name,
            "歌曲ID": s_id,
            "评论数": total_comments,
            "链接": f"https://music.163.com/#/song?id={s_id}"
        })
        progress_bar.progress((i + 1) / count)
        
    return pd.DataFrame(final_data), None

# --- UI 部分 ---
url_input = st.text_input("请输入歌手主页链接或 ID:", placeholder="例如: https://music.163.com/#/artist?id=2116")

if st.button("立即获取"):
    # 提取 ID (兼容链接和纯数字)
    artist_id = re.search(r'id=(\d+)', url_input)
    artist_id = artist_id.group(1) if artist_id else url_input
    
    if not artist_id.isdigit():
        st.error("请输入有效的歌手链接或数字 ID")
    else:
        with st.spinner('正在从云端接口同步数据...'):
            df, error = get_artist_info(artist_id)
            if error:
                st.error(error)
            else:
                st.success("数据获取成功！")
                st.dataframe(df, use_container_width=True)
                
                # Excel 导出
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button(
                    label="📥 下载数据报告",
                    data=output.getvalue(),
                    file_name=f"artist_{artist_id}_data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
