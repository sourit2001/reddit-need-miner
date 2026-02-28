import requests
import os
import json
from datetime import datetime

# 从环境变量获取配置
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK")
AI_API_KEY = os.environ.get("AI_API_KEY")
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
BITABLE_APP_TOKEN = os.environ.get("BITABLE_APP_TOKEN")
BITABLE_TABLE_ID = os.environ.get("BITABLE_TABLE_ID")

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

def generate_report(records):
    if not records: return "暂无新记录可分析"
    
    # 提取关键信息进行汇总
    summary_input = ""
    for idx, r in enumerate(records):
        fields = r.get("fields", {})
        title = fields.get("标题", "无标题")
        analysis = fields.get("需求分析", "无分析")
        score = fields.get("潜力评分", 0)
        # 增加编号和标题的对应关系，让 AI 更好引用
        summary_input += f"ID: {idx+1} | 标题: {title} | 评分: {score}分 | 内容摘要: {analysis[:300]}\n\n"

    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个商业分析师。请阅读以下 Reddit 需求记录：\n1. 总结 3 个核心行业趋势。\n2. 识别交叉验证的痛点（多个帖子提到同一个问题）。\n3. 精选 2-3 个最具价值的机会。\n\n**重要规则**：在引用具体帖子时，请务必使用 'ID [帖子标题]' 的格式（例如：#1 [AI Video Bot]），以便用户在表格中快速查找。"},
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
    
    content = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": "📊 Reddit 需求挖掘 - 每日机会汇总报告",
                    "content": [
                        [{"tag": "text", "text": report_text}]
                    ]
                }
            }
        }
    }
    requests.post(FEISHU_WEBHOOK_URL, json=content)

def main():
    print("正在从多维表格拉取数据...")
    records = fetch_bitable_records(limit=30)
    print(f"成功获取 {len(records)} 条记录，正在生成深度分析报表...")
    
    report = generate_report(records)
    print("分析完成，正在推送至飞书...")
    
    send_report_to_feishu(report)
    print("全流程结束。")

if __name__ == "__main__":
    main()
