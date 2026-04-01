import time
import json
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def scrape_reddit_search(query, time_range='month', limit=10):
    """
    使用 Playwright 模拟真实浏览器抓取 Reddit Modern UI 搜索结果。
    这能解决 RSS/API 接口搜不准、由于排序算法落后导致的搜索质量差的问题。
    """
    results = []
    # 构造现代版搜索 URL
    search_url = f"https://www.reddit.com/search/?q={query.replace(' ', '%20')}&sort=relevance&t={time_range}"
    
    with sync_playwright() as p:
        # 使用随机 User-Agent
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            print(f"📡 Scaper: Navigating to {search_url}")
            page.goto(search_url, timeout=60000)
            
            # 等待搜索结果加载 (最新 Reddit 搜索页容器是 div[data-testid="sdui-post-unit"])
            page.wait_for_selector("div[data-testid='sdui-post-unit']", timeout=20000)
            
            # 滚动一下获取更多内容
            page.mouse.wheel(0, 2000)
            time.sleep(2)
            
            # 获取页面 HTML 并用 BeautifulSoup 解析 (更稳健)
            content = page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # 现代 Reddit (SDUI 结构) 提取
            # 经测试，搜索结果容器为 div[data-testid="sdui-post-unit"]
            posts = soup.select('div[data-testid="sdui-post-unit"]')
            
            for post in posts[:limit]:
                # 寻找标题链接，ID 通常以 search-post-title- 开头
                title_tag = post.find('a', id=re.compile(r'search-post-title-'))
                if not title_tag:
                    # 备选：寻找任何指向 /comments/ 的链接
                    title_tag = post.find('a', href=re.compile(r'/comments/'))
                
                if title_tag and title_tag.get('href'):
                    title = title_tag.text.strip()
                    link = title_tag['href']
                    if not link.startswith('https'):
                        link = f"https://www.reddit.com{link}"
                    
                    results.append({
                        "title": title,
                        "link": link
                    })
            
            print(f"✅ Scraper: Found {len(results)} high-quality results.")
            
        except Exception as e:
            print(f"❌ Scraper Error: {e}")
        finally:
            browser.close()
            
    return results

if __name__ == "__main__":
    # 测试运行
    res = scrape_reddit_search("wrote a script to automate my boring job")
    for r in res:
        print(f"- {r['title']} ({r['link']})")
