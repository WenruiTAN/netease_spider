import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(page_title="网易云音乐数据采集", layout="wide")

st.title("🎵 网易云音乐歌手数据采集工具")

def get_full_stats(artist_id):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://music.163.com/'
    }
    
    try:
        # --- 1. 获取歌手基本信息（精准歌手名 + 粉丝数） ---
        # 使用 artist 详情接口
        info_url = f"https://music.163.com/api/v1/artist/{artist_id}"
        info_res = requests.get(info_url, headers=headers, timeout=10).json()
        
        if info_res.get('code') != 200:
            return None, "无法获取歌手信息，请检查 ID 是否正确。"
            
        artist_obj = info_res.get('artist', {})
        artist_name = artist_obj.get('name', '未知歌手')
        # 粉丝数在部分接口中可能为 null，尝试多路径获取
        fans_count = artist_obj.get('fansCount') or "需网页权限查看"
        
        # --- 2. 获取热门歌曲列表 ---
        songs_url = f"https://music.163.com/api/artist/top/song?id={artist_id}"
        songs_res = requests.get(songs_url, headers=headers, timeout=10).json()
        songs = songs_res.get('songs', [])
        
        if not songs:
            return None, "该歌手暂无热门歌曲数据。"

        final_list = []
        progress_bar = st.progress(0, text="正在深度采集歌曲数据...")
        
        # 采集前 20 首以保证稳定性和红心数查询频率
        max_scan = min(len(songs), 20)
        
        for i, song in enumerate(songs[:max_scan]):
            s_id = song['id']
            s_name = song['name']
            
            # --- 3. 获取评论数 (红心数的最佳替代参考) ---
            comment_api = f"https://music.163.com/api/v1/resource/comments/R_SO_4_{s_id}?limit=0"
            try:
                c_data = requests.get(comment_api, headers=headers, timeout=5).json()
                comment_total = c_data.get('total', 0)
                # 模拟前端 999+ 显示逻辑 (如需要)
                comment_display = f"{comment_total}" if comment_total < 10000 else f"{round(comment_total/10000, 1)}w+"
            except:
                comment_display = "暂无"

            # --- 4. 尝试获取歌曲发布日期 ---
            pub_time = pd.to_datetime(song.get('publishTime', 0), unit='ms').strftime('%Y-%m-%d') if song.get('publishTime') else "未知"

            final_list.append({
                "歌手": artist_name,
                "歌曲名称": s_name,
                "评论总数": comment_total,
                "热度范围": comment_display,
                "发布日期": pub_time,
                "歌曲链接": f"https://music.163.com/#/song?id={s_id}"
            })
            progress_bar.progress((i + 1) / max_scan, text=f"已完成: {s_name}")

        df = pd.DataFrame(final_list)
        return df, artist_name, fans_count

    except Exception as e:
        return None, None, f"发生错误: {str(e)}"

# --- UI 界面 ---
url_input = st.text_input("粘贴歌手主页链接或 ID (如 13932773):")

if st.button("开始深度采集"):
    match = re.search(r'id=(\d+)', url_input)
    artist_id = match.group(1) if match else url_input.strip()
    
    if not artist_id.isdigit():
        st.warning("请输入有效的数字 ID。")
    else:
        with st.spinner('正在调取网易云 API...'):
            df, name, fans = get_full_stats(artist_id)
            
        if name:
            st.success(f"✅ 采集完成！")
            
            # 统计概览卡片
            col_a, col_b = st.columns(2)
            col_a.metric("当前歌手", name)
            col_b.metric("粉丝数", fans)
            
            # 显示表格
            st.dataframe(df, use_container_width=True)
            
            # 导出
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 下载 Excel 报告", data=buffer.getvalue(), file_name=f"{name}_data.xlsx")
        else:
            st.error(fans) # 此处 fans 变量存放了错误信息
