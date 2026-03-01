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

def analyze_needs(text, title):
    text = clean_html(text)
    if len(text) < 10:
        text = f"Title: {title}\n(No detailed content available for this post.)"
    
    if not AI_API_KEY: return "未配置 AI 接口", "未配置 AI 接口", "未配置 AI 接口", 0, "其他"

    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个资深产品经理。请分析输入的 Reddit 帖子（即便只有标题）。\n请严格按以下标签包裹内容：\n[翻译]\n(主贴及标题翻译)\n[精选评论]\n(评论总结)\n[分析]\n(需求分析)\n[评分]\n(1-10数字)\n[分类]\n(类别名)"},
            {"role": "user", "content": text[:4000]}
        ],
        "temperature": 0.4
    }
    
    for attempt in range(2):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            content = resp.json()['choices'][0]['message']['content'].strip()
            print(f"--- AI Result Reference ---\n{content[:300]}...") 
            
            # --- 改进后的解析逻辑 ---
            def get_section(tag, s):
                import re
                # 匹配 [标签] 或 【标签】 后面的内容，直到下一个 [ 或结束
                pattern = rf"\[{tag}\](.*?)(?=\[|$)"
                match = re.search(pattern, s, re.DOTALL | re.IGNORECASE)
                if match:
                    return match.group(1).strip()
                # 备选：如果 AI 没加中括号
                pattern_alt = rf"{tag}:?(.*?)(?=\n[A-Z]|$)"
                match_alt = re.search(pattern_alt, s, re.DOTALL | re.IGNORECASE)
                return match_alt.group(1).strip() if match_alt else ""

            translation = get_section("翻译", content)
            comments_summary = get_section("精选评论", content)
            analysis = get_section("分析", content)
            score_str = get_section("评分", content)
            category = get_section("分类", content)
            
            # 如果正则全挂了，尝试暴力分割
            if not translation and "[翻译]" in content:
                parts = content.split("[")
                for p in parts:
                    if p.startswith("翻译]"): translation = p.replace("翻译]", "").strip()
                    if p.startswith("精选评论]"): comments_summary = p.replace("精选评论]", "").strip()
                    if p.startswith("分析]"): analysis = p.replace("分析]", "").strip()
                    if p.startswith("评分]"): score_str = p.replace("评分]", "").strip()
                    if p.startswith("分类]"): category = p.replace("分类]", "").strip()

            try:
                score = int(re.search(r'\d+', score_str).group()) if score_str else 0
            except:
                score = 0
                
            # 兜底：如果 AI 还是没按格式回，但返回了内容
            if not translation and len(content) > 50:
                translation = "（格式解析失败，请查看分析）"
                analysis = content
                
            return translation or "无内容", comments_summary or "无内容", analysis or content, score, category or "其他"
        except Exception as e:
            print(f"尝试 {attempt+1} 失败: {e}")
            if attempt == 1:
                return "翻译出错", "提取出错", f"API 出错: {e}", 0, "其他"
    
    return "解析失败", "解析失败", "解析失败", 0, "其他"

def send_to_feishu(title, link, source, translation, comments_summary, analysis, score, category):
    content = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"💡 [{score}分|{category}] 发现需求: {source}",
                    "content": [
                        [{"tag": "text", "text": f"📍 标题：{title}\n\n"}],
                        [{"tag": "text", "text": "📝 翻译：\n"}, {"tag": "text", "text": f"{translation}\n\n"}],
                        [{"tag": "text", "text": "💬 评论：\n"}, {"tag": "text", "text": f"{comments_summary}\n\n"}],
                        [{"tag": "text", "text": "🔍 分析：\n"}, {"tag": "text", "text": f"{analysis}\n\n"}],
                        [{"tag": "a", "text": "👉 原贴链接", "href": link}]
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
        "标题": title,
        "链接": {"link": link, "text": "原帖"},
        "来源": source,
        "原文翻译": translation,
        "精选评论": comments_summary,
        "需求分析": analysis,
        "潜力评分": score,
        "分类": category,
        "捕获时间": int(datetime.now().timestamp() * 1000)
    }
    requests.post(url, json={"fields": fields}, headers=headers)

def main():
    if not FEISHU_WEBHOOK_URL: return
    
    sent_posts = load_sent_posts()
    new_sent_list = list(sent_posts)
    
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

    for source_info in NEED_SOURCES:
        print(f"正在扫描: {source_info['name']}...")
        try:
            resp = requests.get(source_info['url'], headers=headers, timeout=20)
            feed = feedparser.parse(resp.content)
            
            for entry in feed.entries[:5]:
                post_id = get_post_id(entry)
                if post_id not in sent_posts:
                    post_rss_url = entry.link.split('?')[0].rstrip('/') + ".rss"
                    
                    # 关键修复：从帖子的独立 RSS 中抓取更详尽的数据
                    full_content = ""
                    comments_text = ""
                    try:
                        post_resp = requests.get(post_rss_url, headers=headers, timeout=15)
                        post_feed = feedparser.parse(post_resp.content)
                        
                        if post_feed.entries:
                            # 第一个 entry 是帖子主贴，通常比主 feed 更全
                            main_post_entry = post_feed.entries[0]
                            full_content = clean_html(main_post_entry.summary if 'summary' in main_post_entry else main_post_entry.content[0].value if 'content' in main_post_entry else "")
                            
                            # 剩下的 entries 是评论
                            for comment_entry in post_feed.entries[1:11]:
                                c_body = clean_html(comment_entry.summary if 'summary' in comment_entry else "")
                                if c_body:
                                    comments_text += f"\n- {c_body[:500]}"
                    except Exception as ce:
                        print(f"深度抓取失败: {ce}")

                    # 如果深度抓取都拿不到，最后再尝试主 feed 的备用字段
                    if not full_content:
                        if 'content' in entry: full_content = clean_html(entry.content[0].value)
                        elif 'summary' in entry: full_content = clean_html(entry.summary)

                    full_text_for_ai = f"Title: {entry.title}\nContent: {full_content}\nComments: {comments_text}"
                    
                    print(f"分析中: {entry.title} (内容长度: {len(full_content)})")
                    
                    analysis_data = analyze_needs(full_text_for_ai, entry.title)
                    translation, comments_summary, analysis, score, category = analysis_data
                    
                    send_to_feishu(entry.title, entry.link, source_info['name'], translation, comments_summary, analysis, score, category)
                    send_to_bitable(entry.title, entry.link, source_info['name'], translation, comments_summary, analysis, score, category)
                    
                    new_sent_list.append(post_id)
        except Exception as e:
            print(f"发生错误: {e}")

    save_sent_posts(new_sent_list)

if __name__ == "__main__":
    main()
