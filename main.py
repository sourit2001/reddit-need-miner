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
    if not text: return "无内容", "无内容", "无内容"
    if not AI_API_KEY: return "未配置 AI 接口", "未配置 AI 接口", "未配置 AI 接口"

    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个资深产品经理和需求分析专家。请执行以下任务：\n1. 将输入的 Reddit 帖子主贴内容翻译成地道的中文。\n2. 从评论区提取出最有价值的 3-5 条观点，翻译成中文。\n3. 分析帖子，提取核心痛点 (Pain Point)、对现有工具的不满 (Frustration) 以及潜在产品机会 (Opportunity)。\n\n请按以下格式严格输出：\n[翻译]\n(主贴翻译内容)\n[精选评论]\n(评论总结内容)\n[分析]\n(分析内容)"},
            {"role": "user", "content": text[:4000]}
        ],
        "temperature": 0.5
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        content = resp.json()['choices'][0]['message']['content'].strip()
        
        translation = ""
        comments_summary = ""
        analysis = ""
        
        if "[精选评论]" in content and "[分析]" in content:
            parts_1 = content.split("[精选评论]")
            translation = parts_1[0].replace("[翻译]", "").strip()
            parts_2 = parts_1[1].split("[分析]")
            comments_summary = parts_2[0].strip()
            analysis = parts_2[1].strip()
        else:
            analysis = content
            
        return translation, comments_summary, analysis
    except Exception as e:
        print(f"AI 分析出错: {e}")
        return "翻译失败", "提取失败", "分析失败"

def send_to_feishu(title, link, source, translation, comments_summary, analysis):
    content = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"💡 发现新需求 - {source}",
                    "content": [
                        [{"tag": "text", "text": f"📍 帖子标题：{title}\n\n"}],
                        [{"tag": "text", "text": "📝 原文翻译：\n"}, {"tag": "text", "text": f"{translation}\n\n"}],
                        [{"tag": "text", "text": "💬 精选评论：\n"}, {"tag": "text", "text": f"{comments_summary}\n\n"}],
                        [{"tag": "text", "text": "🔍 需求分析：\n"}, {"tag": "text", "text": f"{analysis}\n\n"}],
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

def send_to_bitable(title, link, source, translation, comments_summary, analysis):
    if not (FEISHU_APP_ID and BITABLE_APP_TOKEN): return
    token = get_tenant_access_token()
    if not token: return

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{BITABLE_TABLE_ID}/records"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    fields = {
        "标题": title,
        "链接": {"link": link, "text": "原帖"},
        "来源": source,
        "原文翻译": translation,
        "精选评论": comments_summary,
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
                    # 获取该帖子的评论 RSS
                    # Reddit 帖子 RSS 链接通常是：[原贴链接].rss
                    post_rss_url = entry.link.split('?')[0].rstrip('/') + ".rss"
                    comments_text = ""
                    try:
                        post_resp = requests.get(post_rss_url, headers=headers, timeout=15)
                        post_feed = feedparser.parse(post_resp.content)
                        # 跳过第一个 entry (那是主贴自己)，取后面 10 条作为评论
                        for comment_entry in post_feed.entries[1:11]:
                            c_body = clean_html(comment_entry.summary if 'summary' in comment_entry else "")
                            if c_body:
                                comments_text += f"\n- {c_body[:500]}" # 每条评论限制长度
                    except Exception as ce:
                        print(f"抓取评论出错: {ce}")

                    raw_content = entry.summary if 'summary' in entry else entry.description if 'description' in entry else ""
                    full_text_for_ai = f"Title: {entry.title}\nContent: {raw_content}\nComments: {comments_text}"
                    
                    print(f"分析中 (含评论): {entry.title}")
                    
                    analysis_data = analyze_needs(full_text_for_ai)
                    translation, comments_summary, analysis = analysis_data
                    
                    send_to_feishu(entry.title, entry.link, source_info['name'], translation, comments_summary, analysis)
                    send_to_bitable(entry.title, entry.link, source_info['name'], translation, comments_summary, analysis)
                    
                    new_sent_list.append(post_id)
        except Exception as e:
            print(f"发生错误: {e}")

    save_sent_posts(new_sent_list)

if __name__ == "__main__":
    main()
