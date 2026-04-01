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
from scraper import scrape_reddit_search
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

from concurrent.futures import ThreadPoolExecutor, as_completed

# ... (之前的部分保持不变)

# 运行按钮
if st.button("🚀 开启极速挖掘引擎"):
    if not input_keywords:
        st.error("请输入至少一个关键词")
    elif not has_keys:
        st.error("系统环境未配置，请检查 API Key")
    else:
        keywords = [k.strip() for k in input_keywords.split(",") if k.strip()]
        sent_posts = load_sent_deep()
        new_sent_list = list(sent_posts)
        
        st.write("### 🛰️ 正在启动并发挖掘引擎...")
        progress_bar = st.progress(0)
        
        # 收集所有待处理的任务
        all_tasks = []
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}        # 抓取阶段：使用真机爬虫
        with st.spinner("🚀 正在调用极速真机搜索引擎 (匹配网页版结果)..."):
            for kw in keywords:
                results = scrape_reddit_search(kw, time_range='month', limit=fetch_num)
                for item in results:
                    pid = get_post_id(item)
                    if pid not in sent_posts:
                        # 抓取单贴 RSS 以获取正文
                        try:
                            post_rss_url = item['link'].rstrip('/') + ".rss"
                            p_resp = requests.get(post_rss_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                            if p_resp.status_code == 200:
                                p_feed = feedparser.parse(p_resp.content)
                                if p_feed.entries:
                                    # 将原始 entry 存入任务列表
                                    all_tasks.append((kw, p_feed.entries[0], p_feed.entries[1:6]))
                        except: continue

        if not all_tasks:
            st.warning("没有发现新的、高相关的贴子。")
        else:
            st.info(f"💾 共检索到 {len(all_tasks)} 篇新需求，正在开启 5 线程并发处理...")
            
            # 使用线程池并发执行 AI 分析和推送
            def process_single_post(kw, main_post_entry, comment_entries):
                try:
                    # 获取正文和评论 (已在抓取阶段获取)
                    full_content = clean_html(main_post_entry.get('summary', main_post_entry.get('description', '')))
                    comments = ""
                    for c in comment_entries:
                        body = clean_html(c.get('summary', ''))
                        if body: comments += f"- {body[:300]}\n"
                    
                    if not full_content: full_content = "无正文"

                    # AI 分析 (手动设置为不需翻译，确保极速)
                    _, comm, ans, score, cat, rs = analyze_needs(
                        f"Keyword: {kw}\nTitle: {main_post_entry.title}\n{full_content}\nComments: {comments}", 
                        main_post_entry.title,
                        needs_translation=False
                    )

                    # 仅在评分合理时推送
                    if score >= 45:
                        send_to_deep_bitable(kw, main_post_entry.title, main_post_entry.link, "reddit-deep-miner", full_content, comm, ans, score, cat, rs)
                        return get_post_id(main_post_entry), f"{main_post_entry.title} (Score: {score})"
                    else:
                        return get_post_id(main_post_entry), f"SKIP (Score: {score}): {main_post_entry.title}"
                except Exception as e:
                    return None, str(e)

            # 进度跟踪
            completed = 0
            with ThreadPoolExecutor(max_workers=5) as executor:
                # 传入元组解包
                futures = {executor.submit(process_single_post, kw, main_ent, comm_ents): main_ent for kw, main_ent, comm_ents in all_tasks}
                for future in as_completed(futures):
                    pid, title = future.result()
                    completed += 1
                    if pid:
                        new_sent_list.append(pid)
                        st.write(f"✅ [{completed}/{len(all_tasks)}] 已完成: {title}")
                    else:
                        st.write(f"❌ 失败: {title}")
                    progress_bar.progress(completed / len(all_tasks))

            save_sent_deep(new_sent_list)
            st.balloons()
            st.success(f"🎉 挖掘大功告成！共更新 {completed} 条深度需求。")
