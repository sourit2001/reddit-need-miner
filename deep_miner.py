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
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    AI_API_KEY
)

# 深度挖掘专用配置 (从环境变量读取，确保与 main.py 隔离)
DEEP_BITABLE_APP_TOKEN = os.environ.get("DEEP_BITABLE_APP_TOKEN")
DEEP_BITABLE_TABLE_ID = os.environ.get("DEEP_BITABLE_TABLE_ID")

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
        json.dump(sent_list[-1000:], f)

def send_to_deep_bitable(keyword, title, link, source, translation, comments_summary, analysis, score, category, reason):
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
        "捕获时间": int(datetime.now().timestamp() * 1000) # 你的表里这一列是“日期”，必须传毫秒时间戳
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
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

    for kw in keywords:
        print(f"\n🔍 Deep Mining for: {kw}...")
        # 针对每个词，搜索 Reddit 的 Relevance (相关度) 和 Top (热门)
        # 这样能挖出历史上最有价值的痛点，而不只是最近的抱怨
        search_urls = [
            f"https://www.reddit.com/search.rss?q={kw.replace(' ', '+')}&sort=relevance&t=year",
            f"https://www.reddit.com/search.rss?q={kw.replace(' ', '+')}&sort=top&t=all"
        ]

        for search_url in search_urls:
            try:
                resp = requests.get(search_url, headers=headers, timeout=20)
                if resp.status_code != 200: continue
                    
                feed = feedparser.parse(resp.content)
                print(f"  Found {len(feed.entries)} potential posts...")
                
                # 深度挖掘每个词取前 10 个最相关的
                for entry in feed.entries[:10]:
                    post_id = get_post_id(entry)
                    if post_id in sent_posts: continue

                    print(f"  📝 Analyzing: {entry.title}")
                    
                    # 深度抓取评论：尝试拉取 rss 获取更多评论
                    post_rss_url = entry.link.split('?')[0].rstrip('/') + ".rss"
                    full_content, comments = "", ""
                    try:
                        p_resp = requests.get(post_rss_url, headers=headers, timeout=15)
                        if p_resp.status_code == 200:
                            p_feed = feedparser.parse(p_resp.content)
                            if p_feed.entries:
                                main_post = p_feed.entries[0]
                                full_content = clean_html(main_post.get('summary', main_post.get('description', '')))
                                # 深度挖掘取前 10 条评论（比 main.py 的 5 条更多）
                                for c in p_feed.entries[1:11]:
                                    body = clean_html(c.get('summary', ''))
                                    if body: comments += f"- {body[:400]}\n"
                    except: pass
                    
                    if not full_content:
                        full_content = clean_html(entry.get('summary', entry.get('description', '')))

                    # 调用 AI 分析
                    trans, comm, ans, score, cat, rs = analyze_needs(
                        f"Keyword: {kw}\nTitle: {entry.title}\n{full_content}\nComments: {comments}", 
                        entry.title
                    )
                    
                    # 同步到飞书
                    print(f"  📤 Syncing to Bitable (Score: {score})...")
                    b_resp = send_to_deep_bitable(kw, entry.title, entry.link, "Reddit Deep Miner", trans, comm, ans, score, cat, rs)
                    
                    if b_resp and b_resp.status_code == 200:
                        new_sent_list.append(post_id)
                        save_sent_deep(new_sent_list)
                    else:
                        print(f"  ❌ Sync failed: {b_resp.text if b_resp else 'No Response'}")
                    
                    # 避免触发频率限制
                    time.sleep(1)

            except Exception as e:
                print(f"  Error searching {kw}: {e}")

    print("\n✅ Deep Mining task completed!")

if __name__ == "__main__":
    run_deep_miner()
