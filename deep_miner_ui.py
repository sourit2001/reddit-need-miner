import streamlit as st
import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv

# 加载本地 .env 环境变量
load_dotenv()
import feedparser
import requests
from deep_miner import (
    load_keywords, 
    load_sent_deep, 
    save_sent_deep, 
    send_to_deep_bitable,
    get_post_id
)
from main import analyze_needs, clean_html, AI_API_KEY, FEISHU_APP_ID

# 页面配置
st.set_page_config(page_title="Reddit Deep Miner", page_icon="🔍", layout="wide")

# 加载自定义 CSS 提升视觉效果
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #6366f1; color: white; border: none; }
    .stTextArea>div>div>textarea { background-color: #1e293b; color: white; border: 1px solid #475569; }
    .stAlert { border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 侧边栏：状态面板
st.sidebar.title("💎 深度挖掘配置")
st.sidebar.info("本程序在本地运行，不占用 GitHub Actions 额度。")

# 获取环境变量显示状态
has_keys = all([AI_API_KEY, FEISHU_APP_ID])
if has_keys:
    st.sidebar.success("✅ API 密钥已就绪")
else:
    st.sidebar.error("❌ 缺少环境变量 (DeepSeek/Feishu)")
    st.sidebar.warning("请确保终端已 export 相关 KEY 再运行 streamlit")

# 主界面
st.title("🚀 Reddit 需求深度挖掘控制台")
st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 投放关键词")
    input_keywords = st.text_area("输入关键词 (逗号分隔):", 
                                 placeholder="例如: Claude API cost, SaaS audit, automation tool pain",
                                 height=150)
    
    fetch_num = st.slider("每个词抓取数量 (Relevance + Top):", 5, 20, 10)

with col2:
    st.subheader("2. 挖掘状态预览")
    status_container = st.empty()
    log_container = st.container()

# 运行按钮
if st.button("✨ 开启本地挖掘引擎"):
    if not input_keywords:
        st.error("请输入至少一个关键词")
    elif not has_keys:
        st.error("系统环境未配置，请检查 API Key")
    else:
        keywords = [k.strip() for k in input_keywords.split(",") if k.strip()]
        sent_posts = load_sent_deep()
        new_sent_list = list(sent_posts)
        
        progress_bar = st.progress(0)
        total_steps = len(keywords)
        current_step = 0

        with log_container:
            for kw in keywords:
                current_step += 1
                st.write(f"🔍 **正在深入搜索: {kw}...**")
                
                search_urls = [
                    f"https://www.reddit.com/search.rss?q={kw.replace(' ', '+')}&sort=relevance&t=year",
                    f"https://www.reddit.com/search.rss?q={kw.replace(' ', '+')}&sort=top&t=all"
                ]

                results_found = 0
                for search_url in search_urls:
                    try:
                        resp = requests.get(search_url, timeout=15)
                        feed = feedparser.parse(resp.content)
                        
                        for entry in feed.entries[:fetch_num // 2]:
                            post_id = get_post_id(entry)
                            if post_id in sent_posts:
                                st.text(f"  ⏭️ 跳过已处理: {entry.title[:40]}...")
                                continue

                            st.write(f"  ⏳ 正在 AI 分析: {entry.title}")
                            
                            # 深度抓取
                            post_rss_url = entry.link.split('?')[0].rstrip('/') + ".rss"
                            full_content, comments = "", ""
                            try:
                                p_resp = requests.get(post_rss_url, timeout=10)
                                p_feed = feedparser.parse(p_resp.content)
                                if p_feed.entries:
                                    main_post = p_feed.entries[0]
                                    full_content = clean_html(main_post.get('summary', ''))
                                    for c in p_feed.entries[1:6]:
                                        body = clean_html(c.get('summary', ''))
                                        if body: comments += f"- {body[:200]}\n"
                            except: pass

                            # AI 分析
                            trans, comm, ans, score, cat, rs = analyze_needs(
                                f"Keyword: {kw}\nTitle: {entry.title}\n{full_content}\nComments: {comments}", 
                                entry.title
                            )

                            # 推送
                            st.text(f"  📤 同步飞书 (相关性: {score})...")
                            b_resp = send_to_deep_bitable(kw, entry.title, entry.link, "reddit-deep-miner", trans, comm, ans, score, cat, rs)
                            
                            if b_resp and b_resp.status_code == 200:
                                new_sent_list.append(post_id)
                                results_found += 1
                            
                            time.sleep(0.5)
                    except Exception as e:
                        st.error(f"挖掘异常: {e}")

                st.success(f"✅ {kw} 挖掘完成，新增 {results_found} 条记录！")
                progress_bar.progress(current_step / total_steps)
            
            save_sent_deep(new_sent_list)
            st.balloons()
            st.success("🎉 所有深度挖掘任务已圆满结束！请前往飞书查看。")
