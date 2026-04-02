import streamlit as st
import pandas as pd
import requests
import io
import re

# 页面基础配置
st.set_page_config(page_title="网易云音乐数据采集", layout="wide")

st.title("🎵 网易云音乐歌手数据采集工具")
st.caption("直接抓取歌手热门歌曲、精确评论数及发布日期。")

def get_artist_stats(artist_id):
    # 使用移动端 Header 提高接口稳定性
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/04.1',
        'Referer': 'https://music.163.com/'
    }
    
    # 1. 获取歌手热门歌曲列表接口
    api_url = f"https://music.163.com/api/artist/top/song?id={artist_id}"
    
    try:
        res = requests.get(api_url, headers=headers, timeout=10)
        data = res.json()
        
        if data.get('code') != 200:
            return None, f"接口请求失败，错误代码: {data.get('code')}"
        
        songs = data.get('songs', [])
        if not songs:
            return None, "未找到该歌手的歌曲，请检查 ID 是否正确。"

        artist_name = songs[0]['ar'][0]['name']
        
        final_list = []
        progress_text = "正在获取歌曲评论数据..."
        my_bar = st.progress(0, text=progress_text)
        
        # 默认获取前 50 首热门歌曲
        max_songs = min(len(songs), 50)
        
        for i, song in enumerate(songs[:max_songs]):
            s_id = song['id']
            s_name = song['name']
            
            # 2. 获取每首歌的评论总数
            # 虽然前端显示 999+，但此接口通常返回精确数字
            comment_api = f"https://music.163.com/api/v1/resource/comments/R_SO_4_{s_id}?limit=0"
            try:
                c_res = requests.get(comment_api, headers=headers, timeout=5).json()
                comment_count = c_res.get('total', 0)
            except:
                comment_count = "获取失败"

            # 格式化发布日期
            pub_time = pd.to_datetime(song.get('publishTime', 0), unit='ms').strftime('%Y-%m-%d') if song.get('publishTime') else "未知"

            final_list.append({
                "歌手": artist_name,
                "歌曲名称": s_name,
                "评论总数": comment_count,
                "发布日期": pub_time,
                "歌曲链接": f"https://music.163.com/#/song?id={s_id}"
            })
            
            my_bar.progress((i + 1) / max_songs, text=f"处理中: {s_name}")

        return pd.DataFrame(final_list), None

    except Exception as e:
        return None, f"系统异常: {str(e)}"

# --- Streamlit 界面 ---
url_input = st.text_input("粘贴网易云歌手页链接或 ID:", 
                         placeholder="示例: https://music.163.com/#/artist?id=2116")

if st.button("运行采集"):
    # 正则提取 ID
    match = re.search(r'id=(\d+)', url_input)
    artist_id = match.group(1) if match else url_input.strip()
    
    if not artist_id.isdigit():
        st.warning("请输入有效的 ID 或链接。")
    else:
        with st.spinner('同步数据中...'):
            df, err = get_artist_stats(artist_id)
        
        if err:
            st.error(err)
        else:
            st.success(f"已完成歌手【{df['歌手'].iloc[0]}】的数据采集")
            
            # 结果表格
            st.dataframe(df, use_container_width=True)
            
            # 文件导出逻辑
            # Excel 导出
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            # CSV 导出 (增加编码处理防止中文乱码)
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button("📥 下载 Excel 报告", data=excel_buffer.getvalue(), 
                                 file_name=f"artist_{artist_id}.xlsx",
                                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            with col2:
                st.download_button("📥 下载 CSV 文件", data=csv_data, 
                                 file_name=f"artist_{artist_id}.csv",
                                 mime="text/csv")
