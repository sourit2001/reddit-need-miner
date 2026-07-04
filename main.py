import feedparser
import requests
import os
import json
import hashlib
import re
import time
import random
from datetime import datetime
from urllib.parse import urlparse, quote_plus
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

# 热度过滤阈值配置
RSS_MIN_ENGAGEMENT = int(os.environ.get("RSS_MIN_ENGAGEMENT", 8))
RSS_MIN_UPVOTES = int(os.environ.get("RSS_MIN_UPVOTES", 3))
SEARCH_MIN_ENGAGEMENT = int(os.environ.get("SEARCH_MIN_ENGAGEMENT", 2))
SENT_POSTS_KEEP = int(os.environ.get("SENT_POSTS_KEEP", 5000))
HOT_COMMENTS = int(os.environ.get("HOT_COMMENTS", 30))
HOT_ENGAGEMENT = int(os.environ.get("HOT_ENGAGEMENT", 80))
ACTIVE_COMMENTS = int(os.environ.get("ACTIVE_COMMENTS", 10))
ACTIVE_ENGAGEMENT = int(os.environ.get("ACTIVE_ENGAGEMENT", 25))
RSS_ENTRY_LIMIT = int(os.environ.get("RSS_ENTRY_LIMIT", 12))
SEARCH_RESULT_LIMIT = int(os.environ.get("SEARCH_RESULT_LIMIT", 8))
REDDIT_429_COOLDOWN = int(os.environ.get("REDDIT_429_COOLDOWN", 180))
SOURCE_SLEEP_MIN = float(os.environ.get("SOURCE_SLEEP_MIN", 4))
SOURCE_SLEEP_MAX = float(os.environ.get("SOURCE_SLEEP_MAX", 9))
REQUEST_SLEEP_MIN = float(os.environ.get("REQUEST_SLEEP_MIN", 0.8))
REQUEST_SLEEP_MAX = float(os.environ.get("REQUEST_SLEEP_MAX", 2.5))
FETCH_POST_STATS = os.environ.get("FETCH_POST_STATS", "0") == "1"
FETCH_COMMENTS = os.environ.get("FETCH_COMMENTS", "0") == "1"
ENABLE_SEARCH_BROWSER = os.environ.get("ENABLE_SEARCH_BROWSER", "0") == "1"
ENABLE_SEARCH_JSON_FALLBACK = os.environ.get("ENABLE_SEARCH_JSON_FALLBACK", "0") == "1"


NEED_SOURCES = [
    # 1. 场景社区 RSS：优先找小生意、效率工具、表格/自动化和行业工作流痛点。
    {"name": "r/smallbusiness (Hot)", "url": "https://www.reddit.com/r/smallbusiness/hot/.rss", "type": "rss"},
    {"name": "r/Entrepreneur (Hot)", "url": "https://www.reddit.com/r/Entrepreneur/hot/.rss", "type": "rss"},
    {"name": "r/startups (Hot)", "url": "https://www.reddit.com/r/startups/hot/.rss", "type": "rss"},
    {"name": "r/SaaS (Hot)", "url": "https://www.reddit.com/r/SaaS/hot/.rss", "type": "rss"},
    {"name": "r/productivity (Hot)", "url": "https://www.reddit.com/r/productivity/hot/.rss", "type": "rss"},
    {"name": "r/Notion (Hot)", "url": "https://www.reddit.com/r/Notion/hot/.rss", "type": "rss"},
    {"name": "r/Airtable (Hot)", "url": "https://www.reddit.com/r/Airtable/hot/.rss", "type": "rss"},
    {"name": "r/zapier (Hot)", "url": "https://www.reddit.com/r/zapier/hot/.rss", "type": "rss"},
    {"name": "r/excel (Hot)", "url": "https://www.reddit.com/r/excel/hot/.rss", "type": "rss"},
    {"name": "r/googlesheets (Hot)", "url": "https://www.reddit.com/r/googlesheets/hot/.rss", "type": "rss"},
    {"name": "r/marketing (Hot)", "url": "https://www.reddit.com/r/marketing/hot/.rss", "type": "rss"},
    {"name": "r/sales (Hot)", "url": "https://www.reddit.com/r/sales/hot/.rss", "type": "rss"},
    {"name": "r/realtors (Hot)", "url": "https://www.reddit.com/r/realtors/hot/.rss", "type": "rss"},
    {"name": "r/Recruiting (Hot)", "url": "https://www.reddit.com/r/Recruiting/hot/.rss", "type": "rss"},
    {"name": "r/accounting (Hot)", "url": "https://www.reddit.com/r/accounting/hot/.rss", "type": "rss"},
    {"name": "r/SEO (Hot)", "url": "https://www.reddit.com/r/SEO/hot/.rss", "type": "rss"},
    {"name": "r/bigseo (Hot)", "url": "https://www.reddit.com/r/bigseo/hot/.rss", "type": "rss"},
    {"name": "r/TechSEO (Hot)", "url": "https://www.reddit.com/r/TechSEO/hot/.rss", "type": "rss"},
    {"name": "r/OpenAI (Hot)", "url": "https://www.reddit.com/r/OpenAI/hot/.rss", "type": "rss"},
    {"name": "r/ClaudeAI (Hot)", "url": "https://www.reddit.com/r/ClaudeAI/hot/.rss", "type": "rss"},
    {"name": "r/LocalLLaMA (Hot)", "url": "https://www.reddit.com/r/LocalLLaMA/hot/.rss", "type": "rss"},
    {"name": "r/ecommerce (Hot)", "url": "https://www.reddit.com/r/ecommerce/hot/.rss", "type": "rss"},

    # 本地音频资料库方向：音乐、有声书、播客、课程录音、语音笔记、语言学习和自托管媒体。
    {"name": "r/musichoarder (Hot)", "url": "https://www.reddit.com/r/musichoarder/hot/.rss", "type": "rss"},
    {"name": "r/audiobooks (Hot)", "url": "https://www.reddit.com/r/audiobooks/hot/.rss", "type": "rss"},
    {"name": "r/podcasts (Hot)", "url": "https://www.reddit.com/r/podcasts/hot/.rss", "type": "rss"},
    {"name": "r/selfhosted (Hot)", "url": "https://www.reddit.com/r/selfhosted/hot/.rss", "type": "rss"},
    {"name": "r/DataHoarder (Hot)", "url": "https://www.reddit.com/r/DataHoarder/hot/.rss", "type": "rss"},
    {"name": "r/foobar2000 (Hot)", "url": "https://www.reddit.com/r/foobar2000/hot/.rss", "type": "rss"},
    {"name": "r/navidrome (Hot)", "url": "https://www.reddit.com/r/navidrome/hot/.rss", "type": "rss"},
    {"name": "r/jellyfin (Hot)", "url": "https://www.reddit.com/r/jellyfin/hot/.rss", "type": "rss"},
    {"name": "r/ObsidianMD (Hot)", "url": "https://www.reddit.com/r/ObsidianMD/hot/.rss", "type": "rss"},
    {"name": "r/languagelearning (Hot)", "url": "https://www.reddit.com/r/languagelearning/hot/.rss", "type": "rss"},
    {"name": "r/headphones (Hot)", "url": "https://www.reddit.com/r/headphones/hot/.rss", "type": "rss"},
    {"name": "r/audiophile (Hot)", "url": "https://www.reddit.com/r/audiophile/hot/.rss", "type": "rss"},

    # 2. 高意图通用搜索：找还没明确说“找程序员”，但正在抱怨手工流程的人。
    {"name": "Search: Tool Request", "query": "is there a tool for", "type": "search"},
    {"name": "Search: Looking For Software", "query": "looking for software", "type": "search"},
    {"name": "Search: Alternative", "query": "alternative to", "type": "search"},
    {"name": "Search: Switch From", "query": "switch from", "type": "search"},
    {"name": "Search: Stopped Using", "query": "stopped using", "type": "search"},
    {"name": "Search: Too Expensive", "query": "too expensive tool", "type": "search"},
    {"name": "Search: Automate Pain", "query": "how to automate", "type": "search"},
    {"name": "Search: Manual Workflow", "query": "manual process spreadsheet", "type": "search"},
    {"name": "Search: Copy Paste Pain", "query": "copy paste spreadsheet workflow", "type": "search"},
    {"name": "Search: Repetitive Work", "query": "repetitive task automate", "type": "search"},
    {"name": "Search: Dashboard Need", "query": "need a dashboard to track", "type": "search"},
    {"name": "Search: Alert Need", "query": "need alerts when", "type": "search"},
    {"name": "Search: Workflow Tracking", "query": "how do you keep track of", "type": "search"},

    # 3. 更适合独立小软件的方向：AI/API 成本、SEO/GSC、销售跟进、表格/PDF、轻量监控。
    {"name": "AI Cost: Token Usage", "query": "token usage monitor", "type": "search"},
    {"name": "AI Cost: API Bill", "query": "OpenAI bill unexpected", "type": "search"},
    {"name": "AI Cost: Claude API", "query": "Claude API cost", "type": "search"},
    {"name": "AI Cost: LLM Cost", "query": "LLM cost tracking", "type": "search"},
    {"name": "SEO: GSC Indexing", "query": "Google Search Console indexing issue", "type": "search"},
    {"name": "SEO: GSC Manual", "query": "Google Search Console manual export", "type": "search"},
    {"name": "SEO: Ahrefs Alternative", "query": "Ahrefs alternative too expensive", "type": "search"},
    {"name": "SEO: Semrush Alternative", "query": "Semrush alternative too expensive", "type": "search"},
    {"name": "Docs: PDF Extraction", "query": "extract data from PDF tool", "type": "search"},
    {"name": "Docs: Excel Manual", "query": "Excel manual process automate", "type": "search"},
    {"name": "Docs: Google Sheets Manual", "query": "Google Sheets manual process automate", "type": "search"},
    {"name": "Sales: Follow Up", "query": "forgot to follow up with leads", "type": "search"},
    {"name": "Sales: CRM Too Complex", "query": "CRM too complicated small business", "type": "search"},
    {"name": "Recruiting: Candidate Tracking", "query": "track candidates spreadsheet", "type": "search"},
    {"name": "Real Estate: Lead Tracking", "query": "realtor lead tracking spreadsheet", "type": "search"},
    {"name": "Accounting: Receipt Workflow", "query": "receipt tracking spreadsheet automate", "type": "search"},
    {"name": "Small Business: Follow Up", "query": "missed calls follow up customers", "type": "search"},
    {"name": "Small Business: Manual Scheduling", "query": "manual scheduling customers spreadsheet", "type": "search"},
    {"name": "DevTools: Monitoring Alternative", "query": "Datadog alternative too expensive", "type": "search"},
    {"name": "DevTools: Webhook Debugging", "query": "webhook debugging tool", "type": "search"},

    # 4. 本地音频播放器/资料库高意图搜索：不只音乐，也覆盖有声书、播客、录音、转写和语言学习。
    {"name": "Audio: Local Player", "query": "local audio player", "type": "search"},
    {"name": "Audio: Local Files Player", "query": "audio player local files", "type": "search"},
    {"name": "Audio: Library Management", "query": "audio library management", "type": "search"},
    {"name": "Audio: Timestamp Notes", "query": "audio timestamp notes", "type": "search"},
    {"name": "Audio: Bookmarks", "query": "audio player bookmarks", "type": "search"},
    {"name": "Audio: Transcription", "query": "transcribe local audio files", "type": "search"},
    {"name": "Audio: Voice Memo Search", "query": "voice memo transcription search", "type": "search"},
    {"name": "Audio: Audiobook Local Files", "query": "audiobook player local files", "type": "search"},
    {"name": "Audio: Audiobook Bookmarks", "query": "audiobook player bookmarks notes", "type": "search"},
    {"name": "Audio: Audible Alternative", "query": "Audible alternative local files", "type": "search"},
    {"name": "Audio: Podcast Local Files", "query": "podcast app local files", "type": "search"},
    {"name": "Audio: Podcast Offline", "query": "podcast app offline downloads", "type": "search"},
    {"name": "Audio: Skip Silence", "query": "skip silence podcast player", "type": "search"},
    {"name": "Audio: Language AB Repeat", "query": "AB repeat audio player language learning", "type": "search"},
    {"name": "Audio: Slow Playback", "query": "slow down audio without changing pitch language learning", "type": "search"},
    {"name": "Audio: Foobar Alternative", "query": "foobar2000 alternative", "type": "search"},
    {"name": "Audio: Plexamp Alternative", "query": "Plexamp alternative", "type": "search"},
    {"name": "Audio: Navidrome Client", "query": "Navidrome client", "type": "search"},
    {"name": "Audio: Subsonic Client", "query": "Subsonic client music player", "type": "search"}
]

DATA_FILE = "sent_posts.json"
reddit_cooldown_until = 0

def print_source_summary():
    rss_count = sum(1 for source in NEED_SOURCES if source.get("type") == "rss")
    search_count = sum(1 for source in NEED_SOURCES if source.get("type") == "search")
    print(
        "Loaded scan config: "
        f"{rss_count} subreddits/RSS sources, {search_count} search keywords. "
        f"Limits: RSS {RSS_ENTRY_LIMIT}/source, search {SEARCH_RESULT_LIMIT}/keyword. "
        f"Post stats={'on' if FETCH_POST_STATS else 'off'}, comments={'on' if FETCH_COMMENTS else 'off'}, "
        f"browser search={'on' if ENABLE_SEARCH_BROWSER else 'off'}."
    )

def polite_sleep(min_seconds=REQUEST_SLEEP_MIN, max_seconds=REQUEST_SLEEP_MAX):
    if max_seconds <= 0:
        return
    time.sleep(random.uniform(max(0, min_seconds), max(min_seconds, max_seconds)))

def reddit_get(url, headers, timeout=20, optional=False):
    """Centralized Reddit request wrapper with a process-wide 429 cooldown."""
    global reddit_cooldown_until
    now = time.time()
    if optional and now < reddit_cooldown_until:
        remaining = int(reddit_cooldown_until - now)
        print(f"    Optional Reddit request skipped during 429 cooldown ({remaining}s left).")
        return None

    polite_sleep()
    resp = requests.get(url, headers=headers, timeout=timeout)
    if resp.status_code == 429:
        reddit_cooldown_until = time.time() + REDDIT_429_COOLDOWN
        print(f"    Reddit HTTP 429. Optional Reddit requests paused for {REDDIT_429_COOLDOWN}s.")
    return resp

def load_sent_posts():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try: return json.load(f)
            except: return []
    return []

def save_sent_posts(sent_list):
    with open(DATA_FILE, 'w') as f:
        json.dump(list(dict.fromkeys(sent_list))[-SENT_POSTS_KEEP:], f)

def get_post_id(entry):
    """Return a stable Reddit post id across RSS/search/www/old URL variants."""
    link = get_entry_link(entry)
    parsed = urlparse(link.split('?')[0])
    path_parts = [part for part in parsed.path.strip('/').split('/') if part]

    if 'comments' in path_parts:
        comments_idx = path_parts.index('comments')
        if len(path_parts) > comments_idx + 1:
            return f"reddit_{path_parts[comments_idx + 1]}"

    raw_id = entry.get('id') or entry.get('guid') or link
    return hashlib.md5(str(raw_id).encode('utf-8')).hexdigest()

def get_entry_title(entry):
    if isinstance(entry, dict):
        return entry.get("title", "Untitled")
    return getattr(entry, "title", None) or entry.get("title", "Untitled")

def get_entry_link(entry):
    if isinstance(entry, dict):
        return entry.get("link", "") or ""
    return getattr(entry, "link", None) or entry.get("link", "") or ""

def get_entry_summary(entry):
    if isinstance(entry, dict):
        return entry.get("summary") or entry.get("description") or ""
    return entry.get("summary", entry.get("description", ""))

def clean_html(raw_html):
    if not raw_html: return ""
    cleaner = re.compile('<.*?>')
    return re.sub(cleaner, '', raw_html).strip()

def extract_tagged_section(tag, text):
    pattern = rf"\[{tag}\]\s*(.*?)(?=\s*\[|$)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""

def parse_score(score_text, full_content=""):
    """Parse the model score as a 0-100 integer, avoiding list numbers like '1. 85'."""
    candidates = re.findall(r"(?<!\d)(100|[1-9]?\d)(?!\d)", score_text or "")
    if not candidates and full_content:
        score_match = re.search(r"\[评分\]\s*(?:潜力评分[:：]?)?\s*(100|[1-9]?\d)", full_content, re.IGNORECASE)
        if score_match:
            candidates = [score_match.group(1)]

    if not candidates:
        return 0

    numbers = [int(candidate) for candidate in candidates]
    meaningful = [number for number in numbers if number > 10]
    if meaningful:
        return max(0, min(100, meaningful[0]))
    return max(0, min(100, numbers[-1]))

def fetch_post_stats(link, headers):
    """从 Reddit 单帖 JSON 补充讨论热度信息。失败时返回空 dict，不阻断主流程。"""
    if not link:
        return {}

    json_url = link.split('?')[0].rstrip('/') + ".json"
    json_headers = headers.copy()
    json_headers['Accept'] = 'application/json'

    try:
        resp = reddit_get(json_url, headers=json_headers, timeout=12, optional=True)
        if resp is None:
            return {}
        if resp.status_code == 403 and "www.reddit.com" in json_url:
            resp = reddit_get(json_url.replace("www.reddit.com", "old.reddit.com"), headers=json_headers, timeout=12, optional=True)
            if resp is None:
                return {}
        if resp.status_code != 200:
            print(f"    Stats fetch skipped for HTTP {resp.status_code}")
            return {}

        payload = resp.json()
        post_data = payload[0].get('data', {}).get('children', [])[0].get('data', {})
        upvotes = post_data.get('ups')
        comments = post_data.get('num_comments')
        upvote_ratio = post_data.get('upvote_ratio')
        engagement = None
        if isinstance(upvotes, int) and isinstance(comments, int):
            engagement = upvotes + comments
        heat = "普通"
        if (isinstance(comments, int) and comments >= HOT_COMMENTS) or (isinstance(engagement, int) and engagement >= HOT_ENGAGEMENT):
            heat = "热帖"
        elif (isinstance(comments, int) and comments >= ACTIVE_COMMENTS) or (isinstance(engagement, int) and engagement >= ACTIVE_ENGAGEMENT):
            heat = "讨论中"

        return {
            "upvotes": upvotes,
            "comments": comments,
            "upvote_ratio": upvote_ratio,
            "engagement": engagement,
            "heat": heat,
            "subreddit": post_data.get('subreddit_name_prefixed') or post_data.get('subreddit'),
            "created_utc": post_data.get('created_utc'),
        }
    except Exception as e:
        print(f"    Stats fetch failed: {e}")
        return {}

def format_post_stats(post_stats):
    if not post_stats:
        return "讨论数据：暂无"

    upvotes = post_stats.get("upvotes")
    comments = post_stats.get("comments")
    engagement = post_stats.get("engagement")
    upvote_ratio = post_stats.get("upvote_ratio")
    subreddit = post_stats.get("subreddit")
    heat = post_stats.get("heat")

    parts = []
    if subreddit:
        parts.append(f"社区 {subreddit}")
    if heat:
        parts.append(f"热度 {heat}")
    if upvotes is not None:
        parts.append(f"点赞 {upvotes}")
    if comments is not None:
        parts.append(f"评论 {comments}")
    if engagement is not None:
        parts.append(f"讨论度 {engagement}")
    if upvote_ratio is not None:
        parts.append(f"赞同率 {round(upvote_ratio * 100)}%")

    return "讨论数据：" + " / ".join(parts) if parts else "讨论数据：暂无"

def analyze_needs(text, title, needs_translation=True):
    text = clean_html(text)
    if not text or len(text) < 10:
        text = f"Title: {title}\n(No content, analyze by title)"
    
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}
    
    # 动态构建 Prompt，根据需要选择是否翻译
    translation_prompt = "[翻译]\n内容\n" if needs_translation else ""
    
    payload = {
        "model": "deepseek-v4-flash",
        "messages": [
            {
                "role": "system", 
                "content": (
                    "你是一个给个人开发者找产品机会的 Reddit 需求分析助手。请用简单、具体、好懂的中文分析帖子，不要写投资报告腔。\n"
                    "目标：只筛选个人开发者能做的小产品、插件、自动化脚本、轻量 SaaS 或信息工具。\n\n"
                    "先判断这个帖子是否值得个人开发者做：\n"
                    "- 如果需求太泛、太依赖线下资源、需要大团队/牌照/重运营、或只是闲聊，评分要低。\n"
                    "- 如果用户已经在手动凑合、现有工具太贵/太复杂/不好用、可以用现成 API 或简单工作流解决，评分要高。\n\n"
                    "打分必须使用 0-100 分制，不是 0-10、1-5 或等级分。\n"
                    "打分标准（总分=A*0.35+B*0.25+C*0.25+D*0.15，每项也是 0-100 分）：\n"
                    "A. 场景清晰度：能否说清楚谁在什么情况下遇到什么麻烦？\n"
                    "B. 方法可落地：个人开发者能否用脚本、浏览器插件、AI 工作流、Notion/Slack/表格/邮件等集成做出 MVP？\n"
                    "C. 当前工具缺口：现有工具是否太贵、太复杂、缺少某个关键功能，或用户仍在手动处理？\n"
                    "D. 付费/使用意愿：用户是否表现出急、烦、反复遇到、愿意换工具或愿意付费？\n\n"
                    "分数校准：\n"
                    "- 0-20：没有明确需求、纯闲聊、新闻、教程、展示、求赞、灌水。\n"
                    "- 21-45：有问题但不适合个人开发者做产品，或证据很弱。\n"
                    "- 46-64：有具体痛点，可以记录观察，但机会还不够强。\n"
                    "- 65-79：明确可做的个人开发者机会，值得同步。\n"
                    "- 80-100：痛点强、工具缺口明显、MVP 很清楚、可能有人付费。\n\n"
                    "写作要求：\n"
                    "- 用短句，不要用抽象词堆砌。\n"
                    "- 每点都要尽量落到一个具体用户、具体动作、具体问题。\n"
                    "- 不确定时直接写“帖子里没有足够证据”，不要脑补。\n"
                    "- 必须明确说出“个人开发者可以做什么第一版”。\n\n"
                    "请严格按此格式输出：\n"
                    f"{translation_prompt}"
                    "[分析]\n"
                    "1. 场景：谁在什么情况下遇到什么问题？\n"
                    "2. 方法：个人开发者可以做什么第一版？怎么帮用户少做哪一步？\n"
                    "3. 当前工具评估：用户现在可能用什么工具/土办法？这些工具哪里不够好？\n"
                    "4. 可做性判断：为什么适合或不适合个人开发者做？\n"
                    "5. 一句话机会：用一句大白话说明这个产品机会。\n"
                    "[精选评论]\n内容\n"
                    "[评分]\n"
                    "只输出一个 0-100 的整数，例如 72。不要写编号、不要写“分”、不要写“/100”。\n"
                    "[打分理由]\n一句话说明为什么这个分数适合个人开发者\n"
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
            if resp.status_code != 200:
                print(f"AI Attempt {attempt} HTTP {resp.status_code}: {resp.text[:500]}")
                continue
            res_json = resp.json()
            full_content = res_json['choices'][0]['message']['content'].strip()

            trans = extract_tagged_section("翻译", full_content) if needs_translation else "原文搬运"
            comm = extract_tagged_section("精选评论", full_content)
            ans = extract_tagged_section("分析", full_content)
            score_s = extract_tagged_section("评分", full_content)
            cat = extract_tagged_section("分类", full_content)
            reason = extract_tagged_section("打分理由", full_content)

            # 强力兜底
            if not ans and len(full_content) > 20:
                ans = full_content
            
            score = parse_score(score_s, full_content)
            if score == 0 and not score_s:
                print(f"AI score parse warning: missing [评分] section. Raw output: {full_content[:500]}")
            
            return trans or "无内容", comm or "无内容", ans or "解析失败", score, cat or "其他", reason or "无理由"
        except Exception as e:
            print(f"AI Attempt {attempt} Error: {e}")
    return "超时", "超时", "API调用失败", 0, "其他", "API错误"

def send_to_feishu(title, link, source, translation, comments_summary, analysis, score, category, reason, post_stats=None):
    stats_text = format_post_stats(post_stats)
    content = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"🚀 [{score}分|{category}] {source}",
                    "content": [
                        [{"tag": "text", "text": f"项目: {title}\n"}],
                        [{"tag": "text", "text": f"{stats_text}\n"}],
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

def save_to_obsidian(title, link, source, translation, comments_summary, analysis, score, category, reason, post_stats=None):
    """将挖掘内容保存为 Obsidian 兼容的 Markdown 文件"""
    # 强制优先使用 iCloud 路径，如果环境变量没拿到，探测默认 Mac 路径
    i_cloud_path = OBSIDIAN_PATH or "/Users/lizhu/Library/Mobile Documents/iCloud~md~obsidian/Documents/my ai work/reddit"
    
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
reddit_upvotes: {post_stats.get("upvotes") if post_stats else "null"}
reddit_comments: {post_stats.get("comments") if post_stats else "null"}
reddit_engagement: {post_stats.get("engagement") if post_stats else "null"}
date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
tags: [reddit-need, {category.lower()}]
---

# {title}

**项目**: {title}
**讨论数据**: {format_post_stats(post_stats).replace("讨论数据：", "")}
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

def send_to_bitable(title, link, source, translation, comments_summary, analysis, score, category, reason, post_stats=None):
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
        "讨论数据": format_post_stats(post_stats),
        "点赞数": post_stats.get("upvotes") if post_stats else None,
        "评论数": post_stats.get("comments") if post_stats else None,
        "讨论度": post_stats.get("engagement") if post_stats else None,
        "赞同率": post_stats.get("upvote_ratio") if post_stats else None,
        "Subreddit": post_stats.get("subreddit") if post_stats else None,
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
            if v is None:
                continue
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
    print_source_summary()
    sent_posts = load_sent_posts()
    new_sent_list = list(sent_posts)
    seen_post_ids = set(sent_posts)
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
                resp = reddit_get(source_info['url'], headers=headers, timeout=20)
                if resp.status_code == 200:
                    feed = feedparser.parse(resp.content)
                    entries_to_process = feed.entries[:RSS_ENTRY_LIMIT]
                else:
                    print(f"  Warning: HTTP {resp.status_code} for {source_info['name']}")
                    if resp.status_code == 429:
                        print(f"  Detected Rate Limiting (429). Waiting {REDDIT_429_COOLDOWN}s before next source...")
                        time.sleep(REDDIT_429_COOLDOWN)
            else:
                scraped = []
                query = quote_plus(source_info['query'])

                # Search RSS is lighter than browser scraping and JSON API, so use it first.
                try:
                    rss_url = f"https://www.reddit.com/search.rss?q={query}&sort=relevance&t=month"
                    r_resp = reddit_get(rss_url, headers=headers, timeout=15)
                    if r_resp.status_code == 200:
                        f = feedparser.parse(r_resp.content)
                        for entry in f.entries[:SEARCH_RESULT_LIMIT]:
                            scraped.append({"title": entry.title, "link": entry.link, "entry": entry})
                    else:
                        print(f"  Search RSS failed (HTTP {r_resp.status_code}).")
                except Exception as e:
                    print(f"  Search RSS failed: {e}")

                # Optional browser fallback. Disabled by default because it often triggers Reddit blocks in CI.
                if not scraped and ENABLE_SEARCH_BROWSER:
                    scraped = scrape_reddit_search(source_info['query'], time_range='month', limit=SEARCH_RESULT_LIMIT)
                
                # Optional JSON fallback. Disabled by default because GitHub Actions IPs frequently receive 403.
                if not scraped and ENABLE_SEARCH_JSON_FALLBACK:
                    print(f"  Falling back to JSON API for {source_info['name']}...")
                    try:
                        json_headers = headers.copy()
                        
                        search_url = f"https://www.reddit.com/search.json?q={query}&sort=relevance&t=month"
                        s_resp = reddit_get(search_url, headers=json_headers, timeout=15, optional=True)
                        
                        if s_resp is not None and s_resp.status_code == 403:
                            search_url = f"https://old.reddit.com/search.json?q={query}&sort=relevance&t=month"
                            s_resp = reddit_get(search_url, headers=headers, timeout=15, optional=True)

                        if s_resp is not None and s_resp.status_code == 200:
                            data = s_resp.json()
                            for child in data.get('data', {}).get('children', []):
                                post = child.get('data', {})
                                scraped.append({"title": post.get('title'), "link": f"https://www.reddit.com{post.get('permalink')}"})
                        elif s_resp is not None:
                            print(f"  JSON API failed (HTTP {s_resp.status_code}).")
                    except Exception as e:
                        print(f"  JSON Fallback failed: {e}")

                # 转换成兼容的格式
                for item in scraped:
                    if item.get("entry"):
                        entries_to_process.append(item["entry"])
                        continue
                    entries_to_process.append(item)
            
            print(f"  Processing {len(entries_to_process)} entries.")
            
            for entry in entries_to_process:
                title = get_entry_title(entry)
                link = get_entry_link(entry)
                if not link:
                    print(f"    Skipping entry without link: {title[:60]}")
                    continue

                post_id = get_post_id(entry)
                if post_id not in seen_post_ids:
                    post_stats = fetch_post_stats(link, headers) if FETCH_POST_STATS else {}
                    
                    # --- 🚀 前置热度过滤逻辑 ---
                    should_filter = False
                    filter_reason = ""
                    if post_stats:
                        upvotes = post_stats.get("upvotes", 0) or 0
                        comments = post_stats.get("comments", 0) or 0
                        engagement = post_stats.get("engagement", 0) or 0
                        
                        if source_info.get('type') == 'rss':
                            # 对于场景社区 RSS，执行严格过滤
                            if engagement < RSS_MIN_ENGAGEMENT or upvotes < RSS_MIN_UPVOTES:
                                should_filter = True
                                filter_reason = f"点赞数 {upvotes}，评论数 {comments}，讨论度 {engagement} < 门槛 (点赞 {RSS_MIN_UPVOTES}, 讨论度 {RSS_MIN_ENGAGEMENT})"
                        else:
                            # 对于高意图搜索，执行温和过滤
                            if engagement < SEARCH_MIN_ENGAGEMENT:
                                should_filter = True
                                filter_reason = f"点赞数 {upvotes}，评论数 {comments}，讨论度 {engagement} < 门槛 (讨论度 {SEARCH_MIN_ENGAGEMENT})"
                    
                    if should_filter:
                        print(f"    ⏩ [热度不足] 过滤帖子: \"{title[:40]}...\"。原因: {filter_reason}。直接跳过，并记入已处理列表。")
                        new_sent_list.append(post_id)
                        seen_post_ids.add(post_id)
                        continue
                    # ----------------------------

                    full_content, comments = "", ""
                    stats_text = format_post_stats(post_stats)
                    full_content = clean_html(get_entry_summary(entry))

                    if FETCH_COMMENTS:
                        post_rss_url = link.split('?')[0].rstrip('/') + ".rss"
                        try:
                            p_resp = reddit_get(post_rss_url, headers=headers, timeout=15, optional=True)
                            if p_resp is not None and p_resp.status_code == 200:
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
                            elif p_resp is not None:
                                print(f"    Failed to fetch comments for {title[:30]}, status: {p_resp.status_code}")
                        except Exception as e:
                            print(f"    Deep scan error: {e}")

                    if not full_content:
                        full_content = clean_html(get_entry_summary(entry))

                    print(f"  Analyzing: {title} ({stats_text}, Content Len: {len(full_content)})")
                    analysis_input = f"Title: {title}\nLink: {link}\n{stats_text}\n{full_content}\nComments: {comments or 'Not fetched'}"
                    trans, comm, ans, score, cat, rs = analyze_needs(analysis_input, title)
                    
                    # 仅在评分大于等于 55 时才推送，过滤无关或低质量贴子
                    if score >= 55:
                        print(f"    🚀 高分商机 ({score})，正在推送至飞书...")
                        try: send_to_feishu(title, link, source_info['name'], trans, comm, ans, score, cat, rs, post_stats)
                        except Exception as e: print(f"    ⚠️ Feishu sync failed: {e}")
                        
                        try: send_to_bitable(title, link, source_info['name'], trans, comm, ans, score, cat, rs, post_stats)
                        except Exception as e: print(f"    ⚠️ Bitable sync failed: {e}")
                        # 个人帖子不写 Obsidian，只有汇总报告（由 analyzer.py 生成）才同步
                    else:
                        print(f"    ⏩ 评分较低 ({score})，跳过同步，记录已处理。")
                    
                    new_sent_list.append(post_id)
                    seen_post_ids.add(post_id)
            
            # 每处理完一个源休息一下，降低被封频次
            polite_sleep(SOURCE_SLEEP_MIN, SOURCE_SLEEP_MAX)
        except Exception as e: 
            print(f"  Error processing source {source_info['name']}: {e}")
    save_sent_posts(new_sent_list)

if __name__ == "__main__":
    main()
