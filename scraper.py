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
        # 使用更写实的浏览器配置
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800},
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.google.com/'
            }
        )
        page = context.new_page()
        
        try:
            print(f"📡 Scaper: Navigating to {search_url}")
            # 增加对 Reddit 全屏弹窗的处理
            page.goto(search_url, timeout=60000)
            
            # 🔄 1. 处理可能的 Cookie 或年龄确认弹窗
            try:
                # 尝试点击 "Accept all" 按钮 (常见于欧盟或新版 UI)
                accept_btn = page.locator('button:has-text("Accept all"), button:has-text("Agree")')
                if accept_btn.count() > 0:
                    accept_btn.first.click()
                    time.sleep(1)
            except: pass

            # 检查是否遇到了人机验证
            if "Verify you are human" in page.content():
                print("⚠️ Scraper: Detected 'Verify you are human' block page.")
                return results 
            
            # 🔄 2. 等待内容加载 (Reddit 搜索结果可能会变动)
            # 尝试多种可能的选择器
            selectors = [
                "div[data-testid='sdui-post-unit']", 
                "shreddit-post", 
                "div.search-results-main",
                "div[data-post-click-location='title-line']"
            ]
            
            found_selector = None
            for selector in selectors:
                try:
                    page.wait_for_selector(selector, timeout=8000)
                    found_selector = selector
                    break
                except: continue
            
            if not found_selector:
                # 如果没找到特定选择器，但页面有内容，尝试继续
                if "Search results" not in page.title() and len(page.content()) < 5000:
                    print("⚠️ Scraper: Timeout waiting for results. Possibly blocked.")
                    return results
            
            # 滚动一下触发懒加载
            page.evaluate("window.scrollBy(0, 1500)")
            time.sleep(2)
            
            # 🔄 3. 提取结果
            content = page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # 针对不同版本的 UI 进行爬取
            # 方案 A: SDUI (Playwright 找到的选择器)
            posts = soup.select('div[data-testid="sdui-post-unit"]') or soup.select('shreddit-post')
            
            if not posts:
                # 方案 B: 传统选择器
                posts = soup.select('div.search-result') or soup.find_all('div', attrs={'data-testid': 'post-container'})

            for post in posts[:limit]:
                title_tag = post.find('a', id=re.compile(r'search-post-title-')) or \
                            post.find('a', href=re.compile(r'/comments/')) or \
                            post.select_one('a[slot="full-post-link"]')
                
                if title_tag and title_tag.get('href'):
                    title = title_tag.get_text().strip()
                    link = title_tag['href']
                    if not link.startswith('https'):
                        link = f"https://www.reddit.com{link}"
                    
                    # 避免重复
                    if not any(r['link'] == link for r in results):
                        results.append({"title": title, "link": link})
            
            if results:
                print(f"✅ Scraper: Found {len(results)} results using {found_selector or 'fallback'}.")
            else:
                print("⚠️ Scraper: No results extracted from page content.")
            
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
