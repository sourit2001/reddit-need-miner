import feedparser
import requests
import os
import json
import hashlib
import re
from datetime import datetime
from dotenv import load_dotenv
from scraper import scrape_reddit_search

# 加载本地 .env 环境变量
load_dotenv()

# 环境配置
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK")
AI_API_KEY = os.environ.get("AI_API_KEY")
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
BITABLE_APP_TOKEN = os.environ.get("BITABLE_APP_TOKEN")
BITABLE_TABLE_ID = os.environ.get("BITABLE_TABLE_ID")
OBSIDIAN_PATH = os.environ.get("OBSIDIAN_PATH")  # 可选：本地运行时的 iCloud 路径

NEED_SOURCES = [
    # 1. 实时捕获最新需求 (RSS 效率最高)
    {"name": "r/SaaS (New)", "url": "https://www.reddit.com/r/SaaS/new/.rss", "type": "rss"},
    {"name": "r/SideProject (New)", "url": "https://www.reddit.com/r/SideProject/new/.rss", "type": "rss"},
    {"name": "r/Entrepreneur (New)", "url": "https://www.reddit.com/r/Entrepreneur/new/.rss", "type": "rss"},
    {"name": "r/Startups (New)", "url": "https://www.reddit.com/r/Startups/new/.rss", "type": "rss"},
    {"name": "r/ai_agents (New)", "url": "https://www.reddit.com/r/ai_agents/new/.rss", "type": "rss"},
    {"name": "r/SEO (New)", "url": "https://www.reddit.com/r/SEO/new/.rss", "type": "rss"},
    {"name": "r/openclaw (New)", "url": "https://www.reddit.com/r/openclaw/new/.rss", "type": "rss"},
    {"name": "r/ecommerce (New)", "url": "https://www.reddit.com/r/ecommerce/new/.rss", "type": "rss"},
    {"name": "r/ecommerce (Hot)", "url": "https://www.reddit.com/r/ecommerce/hot/.rss", "type": "rss"},
    {"name": "r/shopify (New)", "url": "https://www.reddit.com/r/shopify/new/.rss", "type": "rss"},
    {"name": "r/shopify (Hot)", "url": "https://www.reddit.com/r/shopify/hot/.rss", "type": "rss"},
    {"name": "r/SaaS (Hot)", "url": "https://www.reddit.com/r/SaaS/hot/.rss", "type": "rss"},
    
    # 3. 极速真机搜索: 解决 RSS 搜索不准的问题 (Scraper 最准确)
    {"name": "Search: Tool Request", "query": "is there a tool for", "type": "search"},
    {"name": "Search: Alternative", "query": "alternative to", "type": "search"},
    {"name": "Search: Switch From", "query": "switch from", "type": "search"},
    {"name": "Search: Stopped Using", "query": "stopped using", "type": "search"},
    {"name": "Search: Automate Pain", "query": "how to automate", "type": "search"},
    {"name": "Search: Image Editing", "query": "image editing automate", "type": "search"},
    {"name": "Search: Photo Tool", "query": "tool for batch photo editing", "type": "search"}
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

def analyze_needs(text, title, needs_translation=True):
    text = clean_html(text)
    if not text or len(text) < 10:
        text = f"Title: {title}\n(No content, analyze by title)"
    
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}
    
    # 动态构建 Prompt，根据需要选择是否翻译
    translation_prompt = "[翻译]\n内容\n" if needs_translation else ""
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system", 
                "content": (
                    "你是一个资深投资人和产品经理。请分析 Reddit 帖子并打分（0-100分）。\n"
                    "打分标准（总分=A*0.4+B*0.3+C*0.3）：\n"
                    "A. 痛点强度：用户是否有强烈的付费解决意愿？\n"
                    "B. 竞争环境：是否已有大量免费替代品？（越少分越高）\n"
                    "C. 开发难度：是否适合独立开发者快速启动？（越易分越高）\n\n"
                    "请严格按此格式输出：\n"
                    f"{translation_prompt}"
                    "[分析]\n内容（重点分析：1.具体场景 2.痛点根源 3.现有工具哪里掉链子了 4.付费商机评估）\n"
                    "[精选评论]\n内容\n"
                    "[评分]\n数字 (请拉开差距，拒绝平庸)\n"
                    "[打分理由]\n一句话解释得分点\n"
                    "[分类]\n类别"
                )
            },
            {"role": "user", "content": text[:4000]}
        ],
        "temperature": 0.4
    }
    
    for attempt in range(2):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            res_json = resp.json()
            full_content = res_json['choices'][0]['message']['content'].strip()

            def quick_extract(tag, s):
                pattern = rf"\[{tag}\]\s*(.*?)(?=\s*\[|$)"
                match = re.search(pattern, s, re.DOTALL | re.IGNORECASE)
                return match.group(1).strip() if match else ""

            trans = quick_extract("翻译", full_content) if needs_translation else "原文搬运"
            comm = quick_extract("精选评论", full_content)
            ans = quick_extract("分析", full_content)
            score_s = quick_extract("评分", full_content)
            cat = quick_extract("分类", full_content)
            reason = quick_extract("打分理由", full_content)

            # 强力兜底
            if not ans and len(full_content) > 20:
                ans = full_content
            
            try: score = int(re.search(r'\d+', score_s).group())
            except: score = 0
            
            return trans or "无内容", comm or "无内容", ans or "解析失败", score, cat or "其他", reason or "无理由"
        except Exception as e:
            print(f"AI Attempt {attempt} Error: {e}")
    return "超时", "超时", "API调用失败", 0, "其他", "API错误"

def send_to_feishu(title, link, source, translation, comments_summary, analysis, score, category, reason):
    content = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"🚀 [{score}分|{category}] {source}",
                    "content": [
                        [{"tag": "text", "text": f"项目: {title}\n"}],
                        [{"tag": "text", "text": f"理由: {reason}\n\n"}],
                        [{"tag": "text", "text": "【译】\n"}, {"tag": "text", "text": f"{translation}\n\n"}],
                        [{"tag": "text", "text": "【评】\n"}, {"tag": "text", "text": f"{comments_summary}\n\n"}],
                        [{"tag": "text", "text": "【析】\n"}, {"tag": "text", "text": f"{analysis}\n\n"}],
                        [{"tag": "a", "text": "🔗 原贴链接", "href": link}]
                    ]
                }
            }
        }
    }
    return requests.post(FEISHU_WEBHOOK_URL, json=content)

def save_to_obsidian(title, link, source, translation, comments_summary, analysis, score, category, reason):
    """将挖掘内容保存为 Obsidian 兼容的 Markdown 文件"""
    # 强制优先使用 iCloud 路径，如果环境变量没拿到，探测默认 Mac 路径
    i_cloud_path = OBSIDIAN_PATH or "/Users/lizhu/Library/Mobile Documents/iCloud~md~obsidian/Documents/my ai work/obsidian_sync"
    
    # 如果是本地运行环境（路径存在），则使用它；否则使用 GitHub Actions 默认的本地文件夹
    base_dir = i_cloud_path if os.path.isdir(os.path.dirname(i_cloud_path)) else "obsidian_sync"
    
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)
    
    # 清理文件名非法字符
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:50]
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = os.path.join(base_dir, f"[{score}分] {date_str}-{safe_title}.md")
    
    md_content = f"""---
title: "{title}"
source: "{source}"
link: "{link}"
score: {score}
category: "{category}"
date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
tags: [reddit-need, {category.lower()}]
---

# {title}

**项目**: {title}
**理由**: {reason}

---

**【译】**
{translation}

**【评】**
{comments_summary}

**【析】**
{analysis}

---
[🔗 原贴链接]({link})
"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"    ✅ 已保存至笔记: {os.path.basename(filename)}")
    except Exception as e:
        print(f"    ❌ 保存 Obsidian 失败: {e}")

def get_tenant_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
    try:
        resp = requests.post(url, json=payload)
        token = resp.json().get("tenant_access_token")
        if not token:
            print(f"Error: Token fetch failed. Response: {resp.text}")
        return token
    except Exception as e:
        print(f"Error fetching tenant_access_token: {e}")
        return None

def send_to_bitable(title, link, source, translation, comments_summary, analysis, score, category, reason):
    if not (FEISHU_APP_ID and BITABLE_APP_TOKEN): return None
    token = get_tenant_access_token()
    if not token: 
        print("Error: Could not get Feishu token for Bitable sync")
        return None
    
    # 1. 先探测表格现有的列名，避免因为缺失列导致整个插入失败
    meta_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{BITABLE_TABLE_ID}/fields"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        meta_resp = requests.get(meta_url, headers=headers)
        existing_fields = [f.get("field_name") for f in meta_resp.json().get("data", {}).get("items", [])]
    except Exception as e:
        print(f"Warning: Could not fetch Bitable metadata: {e}")
        existing_fields = []

    # 2. 准备所有可能的字段
    all_potential_fields = {
        "标题": title,
        "链接": {"link": link, "text": "原帖"},
        "来源": source,
        "原文翻译": translation,
        "精选评论": comments_summary,
        "需求分析": analysis,
        "潜力评分": score,
        "分类": category,
        "打分理由": reason,
        "捕获时间": int(datetime.now().timestamp() * 1000)
    }

    # 3. 过滤出表格中真正存在的字段
    valid_fields = {}
    if existing_fields:
        for k, v in all_potential_fields.items():
            if k in existing_fields:
                valid_fields[k] = v
            else:
                print(f"  Note: Field '{k}' not found in Bitable, skipping.")
    else:
        # 如果获取不到元数据，则尝试全量发送（兜底逻辑）
        valid_fields = all_potential_fields

    # 4. 执行写入
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{BITABLE_TABLE_ID}/records"
    headers["Content-Type"] = "application/json"
    resp = requests.post(url, json={"fields": valid_fields}, headers=headers)
    
    if resp.status_code != 200:
        print(f"Bitable Sync Failed: {resp.text}")
    return resp

def main():
    if not FEISHU_WEBHOOK_URL: return
    sent_posts = load_sent_posts()
    new_sent_list = list(sent_posts)
    # 使用更真实的现代浏览器 User-Agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
    }

    for source_info in NEED_SOURCES:
        print(f"Scanning: {source_info['name']}...")
        entries_to_process = []
        
        try:
            if source_info.get('type') == 'rss':
                resp = requests.get(source_info['url'], headers=headers, timeout=20)
                if resp.status_code == 200:
                    feed = feedparser.parse(resp.content)
                    entries_to_process = feed.entries[:25] # 增加到 25 条
                else:
                    print(f"  Warning: HTTP {resp.status_code} for {source_info['name']}")
                    if resp.status_code == 429:
                        print("  Detected Rate Limiting (429). Waiting 30s...")
                        time.sleep(30)
            else:
                # 使用真机爬虫
                scraped = scrape_reddit_search(source_info['query'], time_range='month', limit=15) # 增加到 15 条
                
                # 🔄 Fallback 1: 如果真机爬虫失败，尝试简单的 JSON 接口
                if not scraped:
                    print(f"  Scraper blocked. Falling back to JSON API for {source_info['name']}...")
                    try:
                        search_url = f"https://www.reddit.com/search.json?q={source_info['query'].replace(' ', '%20')}&sort=relevance&t=month"
                        s_resp = requests.get(search_url, headers=headers, timeout=15)
                        if s_resp.status_code == 200:
                            data = s_resp.json()
                            for child in data.get('data', {}).get('children', []):
                                post = child.get('data', {})
                                scraped.append({"title": post.get('title'), "link": f"https://www.reddit.com{post.get('permalink')}"})
                        else:
                            print(f"  JSON API also failed (HTTP {s_resp.status_code}).")
                    except Exception as e:
                        print(f"  JSON Fallback failed: {e}")

                # 🔄 Fallback 2: 如果 JSON 也失败，尝试 Search RSS (最稳健)
                if not scraped:
                    print(f"  Falling back to RSS Search for {source_info['name']}...")
                    try:
                        rss_url = f"https://www.reddit.com/search.rss?q={source_info['query'].replace(' ', '%20')}&sort=relevance&t=month"
                        r_resp = requests.get(rss_url, headers=headers, timeout=15)
                        if r_resp.status_code == 200:
                            f = feedparser.parse(r_resp.content)
                            for entry in f.entries[:8]:
                                scraped.append({"title": entry.title, "link": entry.link})
                    except Exception as e:
                        print(f"  RSS Fallback failed: {e}")

                # 转换成兼容的格式
                for item in scraped:
                    # 对于爬虫抓到的链接，我们需要去抓取它单贴的 RSS 以获取正文和评论
                    try:
                        post_rss_url = item['link'].rstrip('/') + ".rss"
                        p_resp = requests.get(post_rss_url, headers=headers, timeout=10)
                        if p_resp.status_code == 200:
                            p_feed = feedparser.parse(p_resp.content)
                            if p_feed.entries:
                                # 第一个 entry 就是主贴
                                entry = p_feed.entries[0]
                                entries_to_process.append(entry)
                    except: continue
            
            print(f"  Processing {len(entries_to_process)} entries.")
            
            for entry in entries_to_process:
                post_id = get_post_id(entry)
                if post_id not in sent_posts:
                    post_rss_url = entry.link.split('?')[0].rstrip('/') + ".rss"
                    full_content, comments = "", ""
                    try:
                        p_resp = requests.get(post_rss_url, headers=headers, timeout=15)
                        if p_resp.status_code == 200:
                            p_feed = feedparser.parse(p_resp.content)
                            if p_feed.entries:
                                main_post_entry = p_feed.entries[0]
                                summary = main_post_entry.get('summary', '')
                                content_list = main_post_entry.get('content', [])
                                if summary:
                                    full_content = clean_html(summary)
                                elif content_list and len(content_list) > 0:
                                    full_content = clean_html(content_list[0].get('value', ''))
                                
                                for c in p_feed.entries[1:6]:
                                    body = clean_html(c.get('summary', ''))
                                    if body: comments += f"- {body[:300]}\n"
                        else:
                            print(f"    Failed to fetch comments for {entry.title[:30]}, status: {p_resp.status_code}")
                    except Exception as e:
                        print(f"    Deep scan error: {e}")
                    
                    if not full_content:
                        full_content = clean_html(entry.get('summary', entry.get('description', '')))

                    print(f"  Analyzing: {entry.title} (Content Len: {len(full_content)})")
                    trans, comm, ans, score, cat, rs = analyze_needs(f"Title: {entry.title}\n{full_content}\nComments: {comments}", entry.title)
                    
                    # 仅在评分大于等于 55 时才推送，过滤无关或低质量贴子
                    if score >= 55:
                        print(f"    🚀 高分商机 ({score})，正在推送...")
                        try: send_to_feishu(entry.title, entry.link, source_info['name'], trans, comm, ans, score, cat, rs)
                        except Exception as e: print(f"    ⚠️ Feishu sync failed: {e}")
                        
                        try: send_to_bitable(entry.title, entry.link, source_info['name'], trans, comm, ans, score, cat, rs)
                        except Exception as e: print(f"    ⚠️ Bitable sync failed: {e}")
                        
                        try: save_to_obsidian(entry.title, entry.link, source_info['name'], trans, comm, ans, score, cat, rs)
                        except Exception as e: print(f"    ⚠️ Obsidian sync failed: {e}")
                        
                        if b_resp and b_resp.status_code != 200:
                            print(f"    Bitable synchronization error: {b_resp.text}")
                    else:
                        print(f"    ⏩ 评分较低 ({score})，跳过同步，记录已处理。")
                    
                    new_sent_list.append(post_id)
            
            # 每处理完一个源休息一下，降低被封频次
            time.sleep(2)
        except Exception as e: 
            print(f"  Error processing source {source_info['name']}: {e}")
    save_sent_posts(new_sent_list)

if __name__ == "__main__":
    main()
