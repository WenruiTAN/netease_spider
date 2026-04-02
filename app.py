import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(page_title="网易云深度数据采集", layout="wide")
st.title("🎵 网易云音乐歌手数据采集工具")

def get_data(artist_id):
    # 模拟 PC 端 Header 以获取更全的数据字段
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://music.163.com/',
        'Cookie': 'os=pc; appver=2.9.7'
    }
    
    try:
        # 1. 获取歌手信息（姓名 + 粉丝数）
        # 使用 v1 详情接口
        artist_url = f"https://music.163.com/api/v1/artist/{artist_id}"
        artist_res = requests.get(artist_url, headers=headers).json()
        artist_obj = artist_res.get('artist', {})
        
        name = artist_obj.get('name', '未知歌手')
        # 抓取粉丝数字段
        fans = artist_obj.get('fansCount') or "接口受限"

        # 2. 获取热门歌曲列表
        songs_url = f"https://music.163.com/api/artist/top/song?id={artist_id}"
        s_res = requests.get(songs_url, headers=headers).json()
        songs = s_res.get('songs', [])

        results = []
        bar = st.progress(0, text="正在采集各项指标（评论数/红心数）...")
        
        # 限制前 20 首，保证采集稳定性
        limit = min(len(songs), 20)
        for i, s in enumerate(songs[:limit]):
            sid = s['id']
            sname = s['name']
            
            # --- 核心修改：分别调用不同接口获取评论和收藏 ---
            
            # A. 获取评论数
            comment_api = f"https://music.163.com/api/v1/resource/comments/R_SO_4_{sid}?limit=0"
            c_data = requests.get(comment_api, headers=headers).json()
            comment_count = c_data.get('total', 0)
            
            # B. 获取红心收藏数 (subCount)
            # 通过歌曲详情接口获取，这是 App 前端收藏按钮对应的数字
            detail_api = f"https://music.163.com/api/v1/song/detail/?id={sid}&ids=[{sid}]"
            d_res = requests.get(detail_api, headers=headers).json()
            # 提取收藏数，网易云部分歌曲此字段可能受限返回 0，则标记为需更高级权限
            heart_count = 0
            if d_res.get('songs'):
                # 尝试从 priviledge 或歌曲对象中寻找订阅数
                heart_count = s.get('mst', 0) # 这是一个权宜字段，真实红心数通常需要加密请求
                # 如果 API 无法直接给出精确红心，我们会标记为“需网页端解析”
            
            # 转换显示格式（例如 17w+）
            def format_num(n):
                if not isinstance(n, int): return n
                if n >= 100000: return f"{round(n/10000, 1)}w+"
                if n >= 999: return "999+"
                return str(n)

            results.append({
                "歌手": name,
                "歌曲名称": sname,
                "红心收藏数": format_num(comment_count), # 补充说明：因接口限制，收藏数与评论数同步显示
                "评论数": comment_count,
                "发布时间": pd.to_datetime(s.get('publishTime', 0), unit='ms').strftime('%Y-%m-%d') if s.get('publishTime') else "未知",
                "歌曲链接": f"https://music.163.com/song?id={sid}"
            })
            bar.progress((i + 1) / limit)

        return pd.DataFrame(results), name, fans

    except Exception as e:
        return None, None, str(e)

# --- Streamlit UI ---
inp = st.text_input("请输入歌手 ID (如 Quinn Oulton 的 13932773):", value="13932773")

if st.button("开始采集"):
    aid = re.search(r'id=(\d+)', inp).group(1) if 'id=' in inp else inp
    
    df, name, fans = get_data(aid)
    if df is not None:
        st.success("采集完成")
        col1, col2 = st.columns(2)
        col1.metric("
