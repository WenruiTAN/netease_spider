import streamlit as st
import subprocess
import sys

# 自动配置环境
if 'env_ready' not in st.session_state:
    with st.spinner("正在配置云端浏览器环境，请稍候..."):
        try:
            # 1. 安装 Chromium
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            # 2. 【核心补丁】让 playwright 自动安装缺失的系统依赖
            subprocess.run([sys.executable, "-m", "playwright", "install-deps"], check=True)
            st.session_state['env_ready'] = True
        except Exception as e:
            st.error(f"环境初始化失败: {e}")

import pandas as pd
import asyncio
from playwright.async_api import async_playwright

# --- 核心补丁：自动安装浏览器内核 ---
def install_playwright_browsers():
    try:
        # 尝试运行一次，看内核在不在
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        st.error(f"浏览器初始化失败: {e}")

# 在程序最开始就运行安装逻辑
if 'browser_installed' not in st.session_state:
    with st.spinner("首次运行，正在配置服务器环境（约需 30 秒）..."):
        install_playwright_browsers()
        st.session_state['browser_installed'] = True

# 设置页面配置
st.set_page_config(page_title="网易云音乐歌手数据采集器", layout="wide")

st.title("🎵 网易云音乐歌手数据采集工具")
st.caption("输入歌手主页链接，自动提取粉丝数、热门歌曲及评论数。")

# --- 爬虫逻辑 ---
async def scrape_netease_data(artist_url):
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 1. 访问歌手主页
        await page.goto(artist_url)
        
        # 网易云内容都在名为 contentFrame 的 iframe 中
        frame = page.frame_locator("#g_iframe")
        
        try:
            # 获取歌手姓名
            artist_name = await frame.locator("#artist-name").inner_text()
            # 获取粉丝数 (在主页的“粉丝”按钮处)
            # 注意：如果未登录，有时看不到精确粉丝数，只能看到大概
            fans_count = await frame.locator("#fan_count").inner_text()
        except:
            artist_name = "未知歌手"
            fans_count = "需登录查看"

        st.info(f"正在处理歌手: {artist_name} | 粉丝数: {fans_count}")

        # 2. 抓取热门歌曲列表
        # 获取歌曲行
        song_rows = await frame.locator("table.m-table tbody tr").all()
        
        data_list = []
        # 为了演示速度，这里只取前10首，你可以自行修改范围
        max_songs = 10 
        progress_bar = st.progress(0)
        
        for i, row in enumerate(song_rows[:max_songs]):
            # 获取歌曲 ID 和名称
            song_name_elem = row.locator("b")
            song_name = await song_name_elem.get_attribute("title")
            
            # 获取歌曲链接以进入详情页拿评论数
            song_link = await row.locator("td:nth-child(2) a").get_attribute("href")
            song_id = song_link.split("id=")[-1]
            full_song_url = f"https://music.163.com/#/song?id={song_id}"

            # 3. 进入歌曲详情页获取评论数 (由于 iframe 嵌套，需重新跳转或处理)
            # 这里为了性能，建议实际操作中通过 API，演示则直接跳转
            new_page = await context.new_page()
            await new_page.goto(full_song_url)
            song_frame = new_page.frame_locator("#g_iframe")
            
            try:
                # 等待评论元素加载
                comment_count_elem = song_frame.locator("span.sub.s-fc3")
                comment_text = await comment_count_elem.inner_text()
                comment_count = comment_text.replace("评论", "").strip("()")
            except:
                comment_count = "0"
            
            await new_page.close()

            data_list.append({
                "歌手": artist_name,
                "粉丝数": fans_count,
                "歌曲名称": song_name,
                "歌曲ID": song_id,
                "评论数": comment_count,
                "链接": full_song_url
            })
            
            progress_bar.progress((i + 1) / max_songs)

        await browser.close()
        return pd.DataFrame(data_list)

# --- Streamlit 前端界面 ---
url_input = st.text_input("请输入网易云音乐歌手主页 URL:", placeholder="例如: https://music.163.com/#/artist?id=12112211")

if st.button("开始运行"):
    if "artist" not in url_input:
        st.error("请输入正确的歌手主页链接（包含 artist?id=）")
    else:
        with st.spinner('正在努力爬取中，请稍候...'):
            try:
                # 运行异步爬虫
                df_result = asyncio.run(scrape_netease_data(url_input))
                
                if not df_result.empty:
                    st.success("数据采集完成！")
                    
                    # 展示表格
                    st.subheader("歌手数据概览")
                    st.dataframe(df_result, use_container_width=True)

                    # 导出 Excel
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_result.to_excel(writer, index=False, sheet_name='Sheet1')
                    
                    st.download_button(
                        label="📥 点击下载 Excel 表格",
                        data=buffer.getvalue(),
                        file_name="netease_artist_data.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("未抓取到数据，请检查链接是否有效。")
            except Exception as e:
                st.error(f"发生错误: {e}")
