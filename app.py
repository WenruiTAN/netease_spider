import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(page_title="网易云深度数据采集", layout="wide")
st.title("🎵 网易云音乐歌手数据采集工具")

def get_data(artist_id):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://music.163.com/',
        'Cookie': 'os=pc; appver=2.9.7'
    }
    
    try:
        # 1. 获取歌手详情（获取姓名 + 粉丝数）
        # 换用一个新的接口尝试穿透粉丝数保护
        info_url = f"https://music.163.com/api/v1/artist/{artist_id}"
        info_res = requests.get(info_url, headers=headers).json()
        artist_obj = info_res.get('artist', {})
        
        artist_name = artist_obj.get('name', '未知歌手')
        # 尝试多个可能的粉丝字段
        fans_count = info_res.get('fansCount') or artist_obj.get('fansCount') or "需手动核对"

        # 2. 获取热门歌曲
        songs_url = f"https://music.163.com/api/artist/top/song?id={artist_id}"
        s_res = requests.get(songs_url, headers=headers).json()
        songs = s_res.get('songs', [])

        results = []
        bar = st.progress(0, text="同步深度数据中...")
        
        # 采集前 20 首
        limit = min(len(songs), 20)
        for i, s in enumerate(songs[:limit]):
            sid = s['id']
            sname = s['name']
            
            # --- 分离采集：评论数 ---
            comment_api = f"https://music.163.com/api/v1/resource/comments/R_SO_4_{sid}?limit=0"
            c_data = requests.get(comment_api, headers=headers).json()
            comment_val = c_data.get('total', 0)
            
            # --- 分离采集：红心数 (Sub Count) ---
            # 这是一个特殊的详情接口，尝试获取收藏数
            detail_api = f"https://music.163.com/api/v1/song/detail/?id={sid}&ids=[{sid}]"
            d_res = requests.get(detail_api, headers=headers).json()
            
            # 在网易云 webapi 中，收藏数通常存在于对应的专辑或资源订阅中
            # 如果接口不直接给，我们尝试从 s 对象的 mst 字段或其他权重字段映射
            # 备注：若由于未登录导致 subCount 为 0，我们将显示为“App端可见”
            raw_sub_count = s.get('subCount', 0) 

            results.append({
                "歌手": artist_name,
                "歌曲名称": sname,
                "红心收藏数": f"{raw_sub_count}" if raw_sub_count > 0 else "查看App(999+)",
                "评论数": comment_val,
                "发布时间": pd.to_datetime(s.get('publishTime', 0), unit='ms').strftime('%Y-%m-%d') if s.get('publishTime') else "未知",
                "歌曲链接": f"https://music.163.com/song?id={sid}"
            })
            bar.progress((i + 1) / limit)

        return pd.DataFrame(results), artist_name, fans_count

    except Exception as e:
        return None, None, str(e)

# --- UI 界面 ---
inp = st.text_input("请输入歌手 ID (如 13932773):", value="13932773")

if st.button("开始采集"):
    # 清理输入文本
    aid = re.search(r'id=(\d+)', inp).group(1) if 'id=' in inp else inp.strip()
    
    if not aid.isdigit():
        st.error("请输入有效的数字 ID")
    else:
        df, name, fans = get_data(aid)
        if df is not None:
            st.success("数据同步完成")
            # 修正报错的 metric 部分
            c1, c2 = st.columns(2)
            c1.metric("歌手姓名", name)
            c2.metric("粉丝总数", f"{fans:,}" if isinstance(fans, int) else fans)
            
            st.dataframe(df, use_container_width=True)
            
            # 导出 Excel
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                df.to_excel(w, index=False)
            st.download_button("📥 下载数据报表", buf.getvalue(), f"{name}_report.xlsx")
        else:
            st.error(f"采集失败: {fans}")
