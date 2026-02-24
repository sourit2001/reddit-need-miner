import feedparser
import requests
import os
import json
import hashlib
import re
from datetime import datetime

# 从 GitHub Secrets 中获取环境变量
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK")
AI_API_KEY = os.environ.get("AI_API_KEY")

# Feishu Bitable 配置
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
BITABLE_APP_TOKEN = os.environ.get("BITABLE_APP_TOKEN")
BITABLE_TABLE_ID = os.environ.get("BITABLE_TABLE_ID")

# Reddit 需求挖掘源
NEED_SOURCES = [
    {"name": "r/SaaS", "url": "https://www.reddit.com/r/SaaS/new/.rss"},
    {"name": "r/SideProject", "url": "https://www.reddit.com/r/SideProject/new/.rss"},
    {"name": "r/Entrepreneur", "url": "https://www.reddit.com/r/Entrepreneur/new/.rss"},
    {"name": "r/Startups", "url": "https://www.reddit.com/r/Startups/new/.rss"},
    {"name": "Search: Tool request", "url": "https://www.reddit.com/search.rss?q=is+there+a+tool+for&sort=new"},
    {"name": "Search: Alternative to", "url": "https://www.reddit.com/search.rss?q=alternative+to&sort=new"}
]

DATA_FILE = "sent_posts.json"

def load_sent_posts():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return []

def save_sent_posts(sent_list):
    with open(DATA_FILE, 'w') as f:
        json.dump(sent_list[-200:], f)

def get_post_id(entry):
    return hashlib.md5(entry.get('link', '').encode('utf-8')).hexdigest()

def clean_html(raw_html):
    cleaner = re.compile('<.*?>')
    return re.sub(cleaner, '', raw_html).strip()

def analyze_needs(text):
    text = clean_html(text)
    if not text: return "无内容"
    if not AI_API_KEY: return "未配置 AI 接口"

    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个资深产品经理和需求分析专家。请分析以下 Reddit 帖子内容，提取：1. 核心痛点 (Pain Point)；2. 对现有工具的不满 (Frustration)；3. 潜在产品机会 (Opportunity)。请用简洁的中文列出。"},
            {"role": "user", "content": text[:4000]}
        ],
        "temperature": 0.5
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        return resp.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"AI 分析出错: {e}")
        return "分析失败"

def send_to_feishu(title, link, source, analysis):
    content = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"💡 发现新需求 - {source}",
                    "content": [
                        [{"tag": "text", "text": f"📍 帖子标题：{title}\n\n"}],
                        [{"tag": "text", "text": f"🔍 需求分析：\n{analysis}\n\n"}],
                        [{"tag": "a", "text": "👉 点击查看原帖链接", "href": link}]
                    ]
                }
            }
        }
    }
    requests.post(FEISHU_WEBHOOK_URL, json=content)

def get_tenant_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
    try:
        resp = requests.post(url, json=payload)
        return resp.json().get("tenant_access_token")
    except: return None

def send_to_bitable(title, link, source, analysis):
    if not (FEISHU_APP_ID and BITABLE_APP_TOKEN): return
    token = get_tenant_access_token()
    if not token: return

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{BITABLE_TABLE_ID}/records"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    fields = {
        "标题": title,
        "链接": {"link": link, "text": "原帖"},
        "来源": source,
        "需求分析": analysis,
        "捕获时间": int(datetime.now().timestamp() * 1000)
    }
    requests.post(url, json={"fields": fields}, headers=headers)

def main():
    if not FEISHU_WEBHOOK_URL: return
    
    sent_posts = load_sent_posts()
    new_sent_list = list(sent_posts)
    
    # 模拟浏览器 User-Agent，防止 Reddit 屏蔽
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

    for source_info in NEED_SOURCES:
        print(f"正在扫描: {source_info['name']}...")
        try:
            # 使用 requests 先抓取，再交给 feedparser 处理，方便设置 Headers
            resp = requests.get(source_info['url'], headers=headers, timeout=20)
            feed = feedparser.parse(resp.content)
            
            for entry in feed.entries[:5]: # 每次看最新的 5 个
                post_id = get_post_id(entry)
                if post_id not in sent_posts:
                    raw_content = entry.summary if 'summary' in entry else entry.description if 'description' in entry else ""
                    print(f"分析中: {entry.title}")
                    
                    analysis = analyze_needs(raw_content)
                    
                    send_to_feishu(entry.title, entry.link, source_info['name'], analysis)
                    send_to_bitable(entry.title, entry.link, source_info['name'], analysis)
                    
                    new_sent_list.append(post_id)
        except Exception as e:
            print(f"发生错误: {e}")

    save_sent_posts(new_sent_list)

if __name__ == "__main__":
    main()
