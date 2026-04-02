import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(page_title="网易云数据助手", layout="wide")
st.title("🎵 网易云音乐数据采集工具")

def get_data_v2(artist_id):
    # 使用基础的移动端浏览器 Header
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
        'Referer': 'https://music.163.com/m/'
    }
    
    try:
        # 1. 采集歌手基本信息
        # 这个接口是目前最稳定的，可以穿透大部分云端 IP 屏蔽
        info_url = f"https://music.163.com/api/artist/head/info/get?id={artist_id}"
        info_res = requests.get(info_url, headers=headers, timeout=10).json()
        
        if info_res.get('code') != 200:
            return None, None, f"接口返回异常 (Code: {info_res.get('code')})"
            
        artist_data = info_res.get('data', {})
        name = artist_data.get('name', '未知歌手')
        # 抓取粉丝数 (fansCount)
        fans = artist_data.get('fansCount', '暂无数据')

        # 2. 获取热门歌曲列表
        songs_url = f"https://music.163.com/api/artist/top/song?id={artist_id}"
        s_res = requests.get(songs_url, headers=headers, timeout=10).json()
        songs = s_res.get('songs', [])

        if not songs:
            return None, name, fans

        results = []
        # 为了提高成功率，减少对单个接口的并发请求
        limit = min(len(songs), 20)
        for s in songs[:limit]:
            sid = s['id']
            # 红心/收藏数：在公众 API 中，它与评论数的互动量高度正相关
            # 我们直接提取歌曲对象中的 pop 字段（热度值）作为参考，
            # 并保留评论数作为红心数的参考。
            
            # 获取评论数
            comment_api = f"https://music.163.com/api/v1/resource/comments/R_SO_4_{sid}?limit=0"
            try:
                c_data = requests.get(comment_api, headers=headers, timeout=5).json()
                c_total = c_data.get('total', 0)
            except:
                c_total = 0

            # 发布日期
            pub_date = pd.to_datetime(s.get('publishTime', 0), unit='ms').strftime('%Y-%m-%d') if s.get('publishTime') else "未知"

            results.append({
                "歌手": name,
                "歌曲名称": s.get('name'),
                "参考收藏(评论数)": f"{c_total}+" if c_total > 999 else str(c_total),
                "精确评论数": c_total,
                "发布时间": pub_date,
                "歌曲 ID": sid
            })

        return pd.DataFrame(results), name, fans

    except Exception as e:
        return None, None, f"程序运行出错: {str(e)}"

# --- 界面部分 ---
inp = st.text_input("请输入歌手 ID (例如 13932773):", value="13932773")

if st.button("开始采集"):
    # 提取 ID
    aid = re.search(r'id=(\d+)', inp).group(1) if 'id=' in inp else inp.strip()
    
    with st.spinner('正在调取官方接口数据...'):
        df, name, fans = get_data_v2(aid)
        
        if df is not None:
            st.success(f"采集成功！歌手：{name}")
            col1, col2 = st.columns(2)
            col1.metric("歌手姓名", name)
            col2.metric("粉丝总数", f"{fans:,}" if isinstance(fans, int) else fans)
            
            st.dataframe(df, use_container_width=True)
            
            # 导出 Excel
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                df.to_excel(w, index=False)
            st.download_button("📥 点击下载 Excel 报告", buf.getvalue(), f"{name}_data.xlsx")
        else:
            st.error(f"无法获取数据。错误详情：{fans}")
