import feedparser
import requests
import os
import json
import hashlib
import re
from datetime import datetime

# 环境配置
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK")
AI_API_KEY = os.environ.get("AI_API_KEY")
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
BITABLE_APP_TOKEN = os.environ.get("BITABLE_APP_TOKEN")
BITABLE_TABLE_ID = os.environ.get("BITABLE_TABLE_ID")

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
            try: return json.load(f)
            except: return []
    return []

def save_sent_posts(sent_list):
    with open(DATA_FILE, 'w') as f:
        json.dump(sent_list[-200:], f)

def get_post_id(entry):
    return hashlib.md5(entry.get('link', '').encode('utf-8')).hexdigest()

def clean_html(raw_html):
    if not raw_html: return ""
    cleaner = re.compile('<.*?>')
    return re.sub(cleaner, '', raw_html).strip()

def analyze_needs(text, title):
    text = clean_html(text)
    if not text or len(text) < 10:
        text = f"Title: {title}\n(No content, analyze by title)"
    
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个资深产品经理。请分析 Reddit 帖子。必须按此格式：\n[翻译]\n内容\n[精选评论]\n内容\n[分析]\n内容\n[评分]\n数字\n[分类]\n类别"},
            {"role": "user", "content": text[:4000]}
        ],
        "temperature": 0.3
    }
    
    for attempt in range(2):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            res_json = resp.json()
            full_content = res_json['choices'][0]['message']['content'].strip()
            print(f"DEBUG AI RAW: {full_content[:200]}...")

            def quick_extract(tag, s):
                pattern = rf"\[{tag}\]\s*(.*?)(?=\s*\[|$)"
                match = re.search(pattern, s, re.DOTALL | re.IGNORECASE)
                return match.group(1).strip() if match else ""

            trans = quick_extract("翻译", full_content)
            comm = quick_extract("精选评论", full_content)
            ans = quick_extract("分析", full_content)
            score_s = quick_extract("评分", full_content)
            cat = quick_extract("分类", full_content)

            # 强力兜底：如果解析不出任何东西
            if not trans and len(full_content) > 20:
                trans = "警告：格式解析失败，请看分析栏"
                ans = full_content
            
            try: score = int(re.search(r'\d+', score_s).group())
            except: score = 0
            
            return trans or "无内容", comm or "无内容", ans or "解析失败", score, cat or "其他"
        except Exception as e:
            print(f"AI Attempt {attempt} Error: {e}")
    return "超时", "超时", "API调用失败", 0, "其他"

def send_to_feishu(title, link, source, translation, comments_summary, analysis, score, category):
    # 注意：这里的标签和之前不同，用于确认代码是否更新成功
    content = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"� [{score}分|{category}] {source}",
                    "content": [
                        [{"tag": "text", "text": f"项目: {title}\n\n"}],
                        [{"tag": "text", "text": "【译】\n"}, {"tag": "text", "text": f"{translation}\n\n"}],
                        [{"tag": "text", "text": "【评】\n"}, {"tag": "text", "text": f"{comments_summary}\n\n"}],
                        [{"tag": "text", "text": "【析】\n"}, {"tag": "text", "text": f"{analysis}\n\n"}],
                        [{"tag": "a", "text": "� 原贴链接", "href": link}]
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

def send_to_bitable(title, link, source, translation, comments_summary, analysis, score, category):
    if not (FEISHU_APP_ID and BITABLE_APP_TOKEN): return
    token = get_tenant_access_token()
    if not token: return
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{BITABLE_TABLE_ID}/records"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    fields = {
        "标题": title, "链接": {"link": link, "text": "原帖"}, "来源": source,
        "原文翻译": translation, "精选评论": comments_summary, "需求分析": analysis,
        "潜力评分": score, "分类": category, "捕获时间": int(datetime.now().timestamp() * 1000)
    }
    requests.post(url, json={"fields": fields}, headers=headers)

def main():
    if not FEISHU_WEBHOOK_URL: return
    sent_posts = load_sent_posts()
    new_sent_list = list(sent_posts)
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

    for source_info in NEED_SOURCES:
        print(f"Scanning: {source_info['name']}...")
        try:
            resp = requests.get(source_info['url'], headers=headers, timeout=20)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:5]:
                post_id = get_post_id(entry)
                if post_id not in sent_posts:
                    post_rss_url = entry.link.split('?')[0].rstrip('/') + ".rss"
                    full_content, comments = "", ""
                    try:
                        p_resp = requests.get(post_rss_url, headers=headers, timeout=15)
                        p_feed = feedparser.parse(p_resp.content)
                        if p_feed.entries:
                            full_content = clean_html(p_feed.entries[0].summary if 'summary' in p_feed.entries[0] else p_feed.entries[0].content[0].value if 'content' in p_feed.entries[0] else "")
                            for c in p_feed.entries[1:6]:
                                body = clean_html(c.summary if 'summary' in c else "")
                                if body: comments += f"- {body[:300]}\n"
                    except: pass
                    
                    if not full_content:
                        full_content = clean_html(entry.summary if 'summary' in entry else entry.description if 'description' in entry else "")

                    print(f"Analyzing: {entry.title} (Len: {len(full_content)})")
                    trans, comm, ans, score, cat = analyze_needs(f"Title: {entry.title}\n{full_content}\nComments: {comments}", entry.title)
                    
                    send_to_feishu(entry.title, entry.link, source_info['name'], trans, comm, ans, score, cat)
                    send_to_bitable(entry.title, entry.link, source_info['name'], trans, comm, ans, score, cat)
                    new_sent_list.append(post_id)
        except Exception as e: print(f"Error: {e}")
    save_sent_posts(new_sent_list)

if __name__ == "__main__":
    main()
