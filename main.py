import os
import requests
import feedparser
from openai import OpenAI

# ================= 配置区域 =================
RSS_FEEDS = {
    "crypto_news": [
        "https://rss.odaily.news/rss/newsflash",
        "https://rsshub.app/foresightnews/news", 
    ],
    "macro_finance": [
        "https://rsshub.dicomp.net/jin10",
    ],
    "twitter_hot": [
        # 暂留空，AI 会从加密新闻中寻找推特热点
    ]
}

PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
# ============================================

def fetch_rss_entries(urls, limit_per_feed=5):
    """从多个 RSS 源抓取最新条目"""
    entries = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit_per_feed]:
                entries.append(f"【{feed.feed.get('title', '未知来源')}】{entry.title}\n{entry.get('summary', '')}")
        except Exception as e:
            print(f"RSS 抓取失败 {url}: {e}")
    return entries

def summarize_with_deepseek(crypto_entries, macro_entries, twitter_entries):
    """调用 DeepSeek 进行结构化总结"""
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    
    prompt = f"""
    请根据以下今日资讯，生成一份结构化的加密与宏观日报。

    【加密货币新闻】
    {chr(10).join(crypto_entries[:10])}

    【推特热门事件】
    {chr(10).join(twitter_entries[:5]) if twitter_entries else "暂无独立推特源，请从上述加密新闻中提取可能引发推特热议的事件（如马斯克、CZ、V神等的动态）。"}

    【宏观金融新闻】
    {chr(10).join(macro_entries[:10])}

    【空投与项目进度】
    请从上述加密新闻中，**深度挖掘**涉及空投、TGE、融资或重大进展的项目。
    尽力列出以下信息：
    1. 项目简介（它是做什么的）
    2. 融资情况（金额、投资方）
    3. 团队背景
    4. 项目最新进度（如发任务、即将空投等）
    ⚠️ 注意：如果新闻原文中根本没有提及“融资、团队、投资方”等信息，请直接写明“新闻未披露”，**绝对不要编造**。

    要求：
    1. 严格按照四个板块输出，每个板块用 `### ` 作为标题。
    2. 语言精炼，提取核心增量信息，不要废话。
    3. 全文不超过 1500 字。
    """
    
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "system", "content": "你是专业的加密与宏观金融分析师。"}, {"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content

def push_wechat(title, content):
    requests.post("https://www.pushplus.plus/send", json={"token": PUSHPLUS_TOKEN, "title": title, "content": content, "template": "markdown"}, timeout=30)

def main():
    print("正在抓取新闻...")
    crypto = fetch_rss_entries(RSS_FEEDS["crypto_news"])
    macro = fetch_rss_entries(RSS_FEEDS["macro_finance"])
    twitter = fetch_rss_entries(RSS_FEEDS.get("twitter_hot", []))
    
    if not crypto and not macro:
        print("未抓取到任何新闻，退出。")
        return
    
    print(f"抓取到 {len(crypto)} 条加密新闻，{len(macro)} 条宏观新闻。")
    print("正在调用 DeepSeek 进行总结...")
    summary = summarize_with_deepseek(crypto, macro, twitter)
    
    print("正在推送到微信...")
    push_wechat("每日加密与宏观简报", summary)
    print("✅ 推送成功！")

if __name__ == "__main__":
    main()
