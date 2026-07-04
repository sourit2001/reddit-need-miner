import requests
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# 加载本地 .env 环境变量
load_dotenv()

# 从环境变量获取配置
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_SUMMARY_WEBHOOK") or os.environ.get("FEISHU_WEBHOOK")
AI_API_KEY = os.environ.get("AI_API_KEY")
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
BITABLE_APP_TOKEN = os.environ.get("BITABLE_APP_TOKEN")
BITABLE_TABLE_ID = os.environ.get("BITABLE_TABLE_ID")
OBSIDIAN_PATH = os.environ.get("OBSIDIAN_PATH")
REPORT_TZ = ZoneInfo("Asia/Shanghai")

def get_tenant_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
    try:
        resp = requests.post(url, json=payload)
        return resp.json().get("tenant_access_token")
    except: return None

def fetch_bitable_records(limit=50):
    token = get_tenant_access_token()
    if not token: return []

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{BITABLE_TABLE_ID}/records"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"page_size": limit, "sort": '["捕获时间 DESC"]'}
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        return data.get("data", {}).get("items", [])
    except Exception as e:
        print(f"读取数据失败: {e}")
        return []

def extract_bitable_link(value):
    """兼容飞书多维表格链接字段的几种返回形态。"""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("link") or value.get("url") or ""
    if isinstance(value, list):
        for item in value:
            link = extract_bitable_link(item)
            if link:
                return link
    return ""

def generate_report(records):
    if not records: return "暂无新记录可分析"
    
    # 提取关键信息进行汇总
    summary_input = ""
    for idx, r in enumerate(records):
        fields = r.get("fields", {})
        title = fields.get("标题", "无标题")
        link = extract_bitable_link(fields.get("链接", ""))
        analysis = fields.get("需求分析", "无分析")
        score = fields.get("潜力评分", 0)
        
        # 提取更丰满的热度指标数据
        upvotes = fields.get("点赞数", "暂无")
        comments = fields.get("评论数", "暂无")
        subreddit = fields.get("Subreddit", "暂无")
        
        # 增加编号和标题的对应关系，让 AI 更好引用
        summary_input += (
            f"ID: {idx+1} | 标题: {title} | 评分: {score}分 | 社区: {subreddit} | 点赞: {upvotes} | 评论: {comments} | 原帖链接: {link or '无链接'} "
            f"| 内容摘要: {analysis[:300]}\n\n"
        )

    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-v4-flash",
        "messages": [
            {
                "role": "system", 
                "content": (
                    "你是一个给个人开发者整理 Reddit 产品机会的助手。请用简单、具体、好懂的中文总结，不要写宏观商业报告。\n"
                    "你的目标是筛出个人开发者能做的内容：小工具、插件、自动化脚本、轻量 SaaS、信息整理工具、AI 工作流。\n\n"
                    "请按以下角度总结：\n"
                    "1. **💡 场景**：列出 3 个最具体的用户场景。写清楚“谁、在什么时候、想完成什么、卡在哪里”。\n"
                    "2. **🛠 方法**：每个高潜机会都要写一个个人开发者可做的第一版，例如浏览器插件、表格自动化、Shopify 插件、AI 总结器、监控提醒、模板生成器等。\n"
                    "3. **🔍 当前工具评估**：说明用户现在可能用什么工具或土办法，以及这些方案为什么不够好。重点看太贵、太复杂、缺少集成、需要手动复制粘贴、结果不稳定。\n"
                    "4. **✅ 个人开发者可做性**：只推荐不依赖大团队、重销售、牌照、线下交付的机会。对不适合个人开发者的需求要明确排除。\n"
                    "5. **📌 今日优先级**：最后给出 3 个最值得先做的机会，用一句话说明为什么。\n\n"
                    "**格式要求**：\n"
                    "- 引用具体帖子时，请务必使用 Markdown 超链接格式：'ID [[帖子标题](链接URL)]'（例如：#1 [[AI Video Bot](https://www.reddit.com/r/comments/abc/)]）。\n"
                    "- 每个被引用的具体帖子下，都必须提供超链接直达链接，格式为：[🔗 点此直达原帖](链接URL)。如果同一个机会引用多个帖子，请列出每个帖子的直达链接。\n"
                    "- 请严格保证链接 URL 为输入记录中对应的 '原帖链接'，禁止胡乱编造不真实的链接。\n"
                    "- 每个机会都要包含：场景 / 方法 / 当前工具评估 / 是否适合个人开发者。\n"
                    "- 用短句和普通话表达，让非技术读者也能看懂。\n"
                    "- 请使用 Emoji 让报告排版易于在移动端（飞书/手机）阅读。"
                )
            },
            {"role": "user", "content": f"以下是最近的抓取记录：\n{summary_input}"}
        ],
        "temperature": 0.3
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        return resp.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"生成汇总报表失败: {e}"

def send_report_to_feishu(report_text):
    if not FEISHU_WEBHOOK_URL: return
    
    # 使用飞书消息卡片 (interactive) 格式发送，以便完美渲染 Markdown 加粗与超链接 []()
    card_content = {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True,
                "enable_forward": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📊 Reddit 需求挖掘 - 每日机会汇总报告"
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": report_text
                }
            ]
        }
    }
    try:
        resp = requests.post(FEISHU_WEBHOOK_URL, json=card_content)
        if resp.status_code != 200:
            print(f"发送汇总报告至飞书失败，HTTP status: {resp.status_code}, Response: {resp.text}")
    except Exception as e:
        print(f"发送汇总报告至飞书异常: {e}")

def save_report_to_obsidian(report_text):
    """将汇总报告保存至 Obsidian"""
    i_cloud_path = OBSIDIAN_PATH or "/Users/lizhu/Library/Mobile Documents/iCloud~md~obsidian/Documents/my ai work/reddit"
    base_dir = i_cloud_path if os.path.isdir(os.path.dirname(i_cloud_path)) else "obsidian_sync"

    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)
    
    now = datetime.now(REPORT_TZ)
    date_str = now.strftime("%Y-%m-%d")
    filename = os.path.join(base_dir, f"汇总报告-{date_str}.md")
    
    md_content = f"""---
title: "Reddit 需求发现每日汇总 ({date_str})"
date: {now.strftime("%Y-%m-%d %H:%M:%S")}
tags: [reddit-summary, business-insight]
---

{report_text}
"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"✅ 汇总报告已保存: {os.path.basename(filename)}")
    except Exception as e:
        print(f"❌ 保存汇总报告失败: {e}")

def main():
    print("正在从多维表格拉取数据...")
    records = fetch_bitable_records(limit=30)
    print(f"成功获取 {len(records)} 条记录，正在生成深度分析报表...")
    
    report = generate_report(records)
    print("分析完成，正在推送至飞书...")
    
    send_report_to_feishu(report)
    save_report_to_obsidian(report)
    print("全流程结束。")

if __name__ == "__main__":
    main()
