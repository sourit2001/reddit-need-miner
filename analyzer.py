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
        summary_input += f"{idx+1}. [{score}分] {title}: {analysis[:200]}...\n\n"

    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个商业分析师。请阅读以下从 Reddit 抓取的一批需求分析结果，执行以下任务：\n1. 总结这批内容中反映出的 3 个最核心的行业趋势。\n2. 识别出是否有多个帖子指向同一个痛点（交叉验证机会）。\n3. 从中精选出 2-3 个最具商业化价值（赚钱潜力高、技术可行性强）的开发机会，并给出具体建议。"},
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
