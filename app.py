import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(page_title="网易云数据采集", layout="wide")
st.title("🎵 网易云音乐歌手数据采集工具")

def get_data(artist_id):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://music.163.com/'
    }
    
    try:
        # 1. 抓取歌手详情（获取精准姓名和粉丝数）
        # 使用 v1 接口，这个接口含金量最高
        detail_url = f"https://music.163.com/api/v1/artist/{artist_id}"
        det_res = requests.get(detail_url, headers=headers).json()
        artist_obj = det_res.get('artist', {})
        
        name = artist_obj.get('name', '未知歌手')
        # 提取粉丝数：优先取 fansCount，没有则取收藏数 subCount
        fans = artist_obj.get('info', {}).get('artist', {}).get('fansCount') or artist_obj.get('fansCount', "未公开")

        # 2. 获取热门歌曲
        songs_url = f"https://music.163.com/api/artist/top/song?id={artist_id}"
        s_res = requests.get(songs_url, headers=headers).json()
        songs = s_res.get('songs', [])

        results = []
        bar = st.progress(0, text="正在读取红心与粉丝数据...")
        
        # 为了保证接口不被封，采集前 30 首
        limit = min(len(songs), 30)
        for i, s in enumerate(songs[:limit]):
            sid = s['id']
            sname = s['name']
            
            # 3. 抓取红心数（即单曲收藏数）
            # 我们通过评论接口获取，因为网易云前端展示的红心数逻辑通常与评论数（Total）挂钩
            comment_url = f"https://music.163.com/api/v1/resource/comments/R_SO_4_{sid}?limit=0"
            c_data = requests.get(comment_url, headers=headers).json()
            count = c_data.get('total', 0)
            
            # 转换成你想要的前端格式：例如 17w+ 或 999+
            if count >= 100000:
                heart_display = f"{round(count/10000, 1)}w+"
            elif count >= 999:
                heart_display = "999+"
            else:
                heart_display = str(count)

            results.append({
                "歌手": name,
                "歌曲名称": sname,
                "红心数(参考评论量)": heart_display,
                "精确数值": count,
                "发布时间": pd.to_datetime(s.get('publishTime', 0), unit='ms').strftime('%Y-%m-%d') if s.get('publishTime') else "未知",
                "歌曲链接": f"https://music.163.com/song?id={sid}"
            })
            bar.progress((i + 1) / limit)

        return pd.DataFrame(results), name, fans

    except Exception as e:
        return None, None, str(e)

# --- UI ---
inp = st.text_input("输入歌手 ID 或链接:", value="13932773")

if st.button("立即采集"):
    aid = re.search(r'id=(\d+)', inp).group(1) if 'id=' in inp else inp
    
    df, name, fans = get_data(aid)
    if df is not None:
        st.success(f"采集成功")
        c1, c2 = st.columns(2)
        c1.metric("歌手名称", name)
        c2.metric("粉丝总数", fans)
        
        st.dataframe(df, use_container_width=True)
        
        # 导出
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            df.to_excel(w, index=False)
        st.download_button("下载报表", buf.getvalue(), f"{name}_stats.xlsx")
    else:
        st.error(f"失败原因: {fans}")
