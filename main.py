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
    if not text: return "无内容", "无内容", "无内容", 0, "其他"
    if not AI_API_KEY: return "未配置 AI 接口", "未配置 AI 接口", "未配置 AI 接口", 0, "其他"

    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个资深产品经理和需求分析专家。请执行以下任务：\n1. 将输入的 Reddit 帖子翻译成地道的中文。\n2. 从评论区提取出最有价值的 3-5 条观点。\n3. 分析核心痛点 (Pain Point)、不满 (Frustration) 和潜在机会 (Opportunity)。\n4. 给该需求打分 (1-10分)，衡量商业潜力和开发可行性。\n5. 给需求归类 (如：SaaS, 开发者工具, 内容创作, 电商, 效率工具等)。\n\n请按以下格式严格输出：\n[翻译]\n(内容)\n[精选评论]\n(内容)\n[分析]\n(分析内容)\n[评分]\n(仅数字)\n[分类]\n(仅类别名)"},
            {"role": "user", "content": text[:4000]}
        ],
        "temperature": 0.5
    }
    
    # 增加重试机制 (最多尝试 2 次)
    for attempt in range(2):
        try:
            # 超时时间增加到 60 秒
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            content = resp.json()['choices'][0]['message']['content'].strip()
            
            translation, comments_summary, analysis = "翻译失败", "提取失败", "分析失败"
            score = 0
            category = "其他"
            
            def extract(p, s):
                import re
                match = re.search(f"\\{p}\\](.*?)(?=\\[|$)", s, re.DOTALL)
                return match.group(1).strip() if match else ""

            translation = extract("[翻译]", content)
            comments_summary = extract("[精选评论]", content)
            analysis = extract("[分析]", content)
            score_str = extract("[评分]", content)
            category = extract("[分类]", content)
            
            try:
                score = int(re.search(r'\d+', score_str).group()) if score_str else 0
            except:
                score = 0
                
            return translation, comments_summary, analysis, score, category
        except Exception as e:
            print(f"第 {attempt+1} 次 AI 分析出错: {e}")
            if attempt == 1: # 最后一次尝试也失败了
                return "翻译超时", "提取超时", f"分析失败（API连续报错）: {e}", 0, "其他"
    
    return "翻译失败", "提取失败", "分析失败", 0, "其他"

def send_to_feishu(title, link, source, translation, comments_summary, analysis, score, category):
    content = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"💡 [{score}分|{category}] 发现新需求 - {source}",
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
                    comments_text = ""
                    try:
                        post_resp = requests.get(post_rss_url, headers=headers, timeout=15)
                        post_feed = feedparser.parse(post_resp.content)
                        for comment_entry in post_feed.entries[1:11]:
                            c_body = clean_html(comment_entry.summary if 'summary' in comment_entry else "")
                            if c_body:
                                comments_text += f"\n- {c_body[:500]}"
                    except Exception as ce:
                        print(f"抓取评论出错: {ce}")

                    # 增强内容抓取：尝试更多可能的字段
                    raw_content = ""
                    if 'content' in entry:
                        raw_content = entry.content[0].value
                    elif 'summary' in entry:
                        raw_content = entry.summary
                    elif 'description' in entry:
                        raw_content = entry.description
                    
                    full_text_for_ai = f"Title: {entry.title}\nContent: {raw_content}\nComments: {comments_text}"
                    
                    print(f"分析中 (含评论): {entry.title} (内容长度: {len(raw_content)})")
                    
                    analysis_data = analyze_needs(full_text_for_ai)
                    translation, comments_summary, analysis, score, category = analysis_data
                    
                    send_to_feishu(entry.title, entry.link, source_info['name'], translation, comments_summary, analysis, score, category)
                    send_to_bitable(entry.title, entry.link, source_info['name'], translation, comments_summary, analysis, score, category)
                    
                    new_sent_list.append(post_id)
        except Exception as e:
            print(f"发生错误: {e}")

    save_sent_posts(new_sent_list)

if __name__ == "__main__":
    main()
