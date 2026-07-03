import feedparser
import requests
import os
import json
import hashlib
import re
import time
from datetime import datetime
from dotenv import load_dotenv

# 加载本地 .env 环境变量
load_dotenv()
from main import (
    analyze_needs, 
    get_tenant_access_token, 
    clean_html, 
    get_post_id,
    save_to_obsidian, # 新增
    fetch_post_stats, # 用于获取帖子热度
    format_post_stats, # 用于格式化帖子热度
    SENT_POSTS_KEEP,
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    AI_API_KEY
)
from scraper import scrape_reddit_search

# 深度挖掘专用配置 (从环境变量读取，确保与 main.py 隔离)
DEEP_BITABLE_APP_TOKEN = os.environ.get("DEEP_BITABLE_APP_TOKEN")
DEEP_BITABLE_TABLE_ID = os.environ.get("DEEP_BITABLE_TABLE_ID")
DEEP_MIN_ENGAGEMENT = int(os.environ.get("DEEP_MIN_ENGAGEMENT", 3))

# 启动调试：验证 ID 是否加载正确 (只显示前4位保护隐私)
print(f"DEBUG: App ID loaded: {FEISHU_APP_ID[:4]}..." if FEISHU_APP_ID else "DEBUG: App ID NOT LOADED")
print(f"DEBUG: App Token used: {DEEP_BITABLE_APP_TOKEN[:6]}..." if DEEP_BITABLE_APP_TOKEN else "DEBUG: App Token NOT LOADED")
print(f"DEBUG: Table ID used: {DEEP_BITABLE_TABLE_ID[:6]}..." if DEEP_BITABLE_TABLE_ID else "DEBUG: Table ID NOT LOADED")

KEYWORDS_FILE = "deep_keywords.json"
SENT_DEEP_FILE = "sent_deep_posts.json"

def load_keywords():
    # 优先从环境变量读取（由 GitHub Actions 从网页端通过 inputs 传入）
    env_keywords = os.environ.get("DEEP_KEYWORDS")
    if env_keywords:
        return [k.strip() for k in env_keywords.split(",") if k.strip()]
    
    # 兜底：从本地 JSON 文件读取
    if os.path.exists(KEYWORDS_FILE):
        with open(KEYWORDS_FILE, 'r') as f:
            return json.load(f)
    return []

def load_sent_deep():
    if os.path.exists(SENT_DEEP_FILE):
        with open(SENT_DEEP_FILE, 'r') as f:
            try: return json.load(f)
            except: return []
    return []

def save_sent_deep(sent_list):
    with open(SENT_DEEP_FILE, 'w') as f:
        json.dump(list(dict.fromkeys(sent_list))[-SENT_POSTS_KEEP:], f)

def send_to_deep_bitable(keyword, title, link, source, translation, comments_summary, analysis, score, category, reason, post_stats=None):
    if not (FEISHU_APP_ID and DEEP_BITABLE_APP_TOKEN): 
        print("Error: Missing Feishu App ID or Bitable App Token")
        return None
    token = get_tenant_access_token()
    if not token: return None
    
    # 1. 先探测表格现有的列名，确保 100% 写入成功
    meta_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{DEEP_BITABLE_APP_TOKEN}/tables/{DEEP_BITABLE_TABLE_ID}/fields"
    headers = {"Authorization": f"Bearer {token}"}
    existing_fields = []
    try:
        meta_resp = requests.get(meta_url, headers=headers)
        meta_json = meta_resp.json()
        existing_fields = [f.get("field_name") for f in meta_json.get("data", {}).get("items", [])]
        if not existing_fields:
            print(f"Warning: Could not fetch fields for table {DEEP_BITABLE_TABLE_ID}. Check permissions. Response: {meta_resp.text}")
    except Exception as e:
        print(f"Warning: Field metadata error: {e}")

    # 2. 准备所有可能的字段 (精准匹配你新表的列类型)
    data_map = {
        "标题": str(title),
        "链接": {"link": link, "text": "原帖"},
        "原文翻译": str(translation),
        "精选评论": str(comments_summary),
        "需求分析": str(analysis),
        "相关性": str(score),  # 你的表里这一列是“文本”，必须传字符串
        "搜索关键词": str(keyword),
        "捕获时间": int(datetime.now().timestamp() * 1000), # 你的表里这一列是“日期”，必须传毫秒时间戳
        
        # 热度数据支持
        "讨论数据": format_post_stats(post_stats) if post_stats else "讨论数据：暂无",
        "点赞数": post_stats.get("upvotes") if post_stats else None,
        "评论数": post_stats.get("comments") if post_stats else None,
        "讨论度": post_stats.get("engagement") if post_stats else None,
        "赞同率": post_stats.get("upvote_ratio") if post_stats else None,
        "Subreddit": post_stats.get("subreddit") if post_stats else None
    }
    
    # 3. 过滤出表格中真正存在的字段
    valid_fields = {}
    for k, v in data_map.items():
        if k in existing_fields:
            valid_fields[k] = v
        else:
            print(f"  (Skipping field '{k}' as it's not in your Bitable)")

    if not valid_fields:
        print("Error: No matching fields found in Bitable! Please check your column names.")
        return None

    # 4. 执行写入
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{DEEP_BITABLE_APP_TOKEN}/tables/{DEEP_BITABLE_TABLE_ID}/records"
    headers["Content-Type"] = "application/json"
    
    resp = requests.post(url, json={"fields": valid_fields}, headers=headers)
    res_json = resp.json()
    
    # 精确判断是否成功 (根据飞书内部 code)
    if res_json.get("code") == 0:
        print(f"✅ SUCCESS: Record created! ID: {res_json.get('data', {}).get('record', {}).get('id')}")
    else:
        print(f"❌ FAILED: Feishu Error Code {res_json.get('code')}")
        print(f"   Reason: {res_json.get('msg')}")
        print(f"   Details: {res_json.get('error', {}).get('message')}")
    return resp

def run_deep_miner():
    keywords = load_keywords()
    if not keywords:
        print("No keywords found in deep_keywords.json. Please add some!")
        return

    sent_posts = load_sent_deep()
    new_sent_list = list(sent_posts)
    seen_post_ids = set(sent_posts)
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

    for kw in keywords:
        print(f"\n🔍 Deep Mining for: {kw}...")
        
        try:
            results = scrape_reddit_search(kw, time_range='month', limit=15)
            
            # 🔄 Fallback 1: JSON API
            if not results:
                print(f"  Scraper blocked. Trying JSON API for keyword: {kw}")
                try:
                    json_headers = headers.copy()
                    json_headers['User-Agent'] = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
                    
                    s_url = f"https://www.reddit.com/search.json?q={kw.replace(' ', '%20')}&sort=relevance&t=month"
                    s_resp = requests.get(s_url, headers=json_headers, timeout=15)
                    
                    if s_resp.status_code == 403:
                        s_url = f"https://old.reddit.com/search.json?q={kw.replace(' ', '%20')}&sort=relevance&t=month"
                        s_resp = requests.get(s_url, headers=headers, timeout=15)

                    if s_resp.status_code == 200:
                        data = s_resp.json()
                        for child in data.get('data', {}).get('children', []):
                            post = child.get('data', {})
                            results.append({"title": post.get('title'), "link": f"https://www.reddit.com{post.get('permalink')}"})
                except: pass

            # 🔄 Fallback 2: RSS Search
            if not results:
                print(f"  Trying RSS Search for keyword: {kw}")
                try:
                    rss_headers = headers.copy()
                    rss_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) applewebkit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
                    
                    rss_url = f"https://www.reddit.com/search.rss?q={kw.replace(' ', '%20')}&sort=relevance&t=month"
                    r_resp = requests.get(rss_url, headers=rss_headers, timeout=15)
                    if r_resp.status_code == 200:
                        f = feedparser.parse(r_resp.content)
                        for entry in f.entries[:10]:
                            results.append({"title": entry.title, "link": entry.link})
                except: pass

            
            for item in results:
                try:
                    # 同样的逻辑：抓取主贴 RSS 以获取深度内容
                    post_rss_url = item['link'].rstrip('/') + ".rss"
                    p_resp = requests.get(post_rss_url, headers=headers, timeout=10)
                    if p_resp.status_code != 200: continue
                    
                    p_feed = feedparser.parse(p_resp.content)
                    if not p_feed.entries: continue
                    
                    entry = p_feed.entries[0] # 主贴
                    post_id = get_post_id(entry)
                    if post_id in seen_post_ids: continue
                    
                    post_stats = fetch_post_stats(entry.link, headers)
                    
                    # --- 🚀 深度挖掘前置热度过滤 ---
                    should_filter = False
                    filter_reason = ""
                    if post_stats:
                        upvotes = post_stats.get("upvotes", 0) or 0
                        comments = post_stats.get("comments", 0) or 0
                        engagement = post_stats.get("engagement", 0) or 0
                        
                        if engagement < DEEP_MIN_ENGAGEMENT:
                            should_filter = True
                            filter_reason = f"点赞数 {upvotes}，评论数 {comments}，讨论度 {engagement} < 门槛 (讨论度 {DEEP_MIN_ENGAGEMENT})"
                    
                    if should_filter:
                        print(f"    ⏩ [热度不足] 过滤深度帖子: \"{entry.title[:40]}...\"。原因: {filter_reason}。直接跳过，并记入已处理列表。")
                        new_sent_list.append(post_id)
                        seen_post_ids.add(post_id)
                        save_sent_deep(new_sent_list)
                        continue
                    # ------------------------------

                    full_content = clean_html(entry.get('summary', entry.get('description', '')))
                    comments = ""
                    for c in p_feed.entries[1:10]: # 深度挖掘可以多看几条评论
                        body = clean_html(c.get('summary', ''))
                        if body: comments += f"- {body[:300]}\n"

                    print(f"  📝 Analyzing: {entry.title}")
                    
                    if not full_content:
                        full_content = clean_html(entry.get('summary', entry.get('description', '')))

                    # 调用 AI 分析
                    trans, comm, ans, score, cat, rs = analyze_needs(
                        f"Keyword: {kw}\nTitle: {entry.title}\n{full_content}\nComments: {comments}", 
                        entry.title
                    )
                    
                    # 深度挖掘通常长尾需求多，阈值设为 45 过滤完全无关的内容
                    if score >= 45:
                        print(f"  📤 Syncing (Score: {score})...")
                        
                        # 修复未定义 b_resp 的隐患，同时调用同步
                        b_resp = None
                        try: 
                            b_resp = send_to_deep_bitable(kw, entry.title, entry.link, "Reddit Deep Miner", trans, comm, ans, score, cat, rs, post_stats)
                        except Exception as e: 
                            print(f"  ⚠️ Deep Bitable sync failed: {e}")
                        
                        try: 
                            save_to_obsidian(entry.title, entry.link, "Reddit Deep Miner", trans, comm, ans, score, cat, rs, post_stats)
                        except Exception as e: 
                            print(f"  ⚠️ Obsidian sync failed: {e}")
                        
                        if b_resp and b_resp.status_code == 200:
                            new_sent_list.append(post_id)
                            seen_post_ids.add(post_id)
                            save_sent_deep(new_sent_list)
                        else:
                            print(f"  ❌ Sync failed: {b_resp.text if b_resp else 'No Response'}")
                    else:
                        print(f"  ⏩ Score {score} too low, skipping.")
                        new_sent_list.append(post_id)
                        seen_post_ids.add(post_id)
                        save_sent_deep(new_sent_list)
                    
                    # 避免触发频率限制
                    time.sleep(2)
                except Exception as e:
                    print(f"  Error processing post: {e}")

        except Exception as e:
            print(f"  Error searching {kw}: {e}")

    print("\n✅ Deep Mining task completed!")

if __name__ == "__main__":
    run_deep_miner()
