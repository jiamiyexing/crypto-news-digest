import os
import requests
import feedparser
from openai import OpenAI

# ================= 配置区域 =================
RSS_FEEDS = {
    "crypto_news": [
        "https://rss.odaily.news/rss/newsflash",
        "https://rsshub.app/foresightnews/news",
        "https://www.coindesk.com/arc/outboundfeeds/rss/"
    ],
    "bitcoin_news": [
        "https://cointelegraph.com/rss/tag/bitcoin"
    ],
    "macro_finance": [
        "https://www.reutersagency.com/feed/",
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://finance.yahoo.com/news/rssindex"
    ],
    # 换用更稳定的国内热点源（微博热搜）和金融源（华尔街见闻）
    "cn_news": [
        "https://rsshub.app/weibo/search/hot",
        "https://rsshub.app/36kr/newsflashes"
    ],
    "cn_finance": [
        "https://rsshub.app/wallstreetcn/news/global",
        "https://rsshub.app/cls/telegraph"
    ],
    "twitter_hot": []
}

PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
# ============================================

def fetch_rss_entries(urls, limit_per_feed=3):
    entries = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit_per_feed]:
                entries.append(f"【{feed.feed.get('title', '未知来源')}】{entry.title}\n{entry.get('summary', '')}")
        except Exception as e:
            print(f"⚠️ RSS 抓取失败 -> {url} | 错误: {e}")
    return entries

def get_market_data():
    data_str = ""
    try:
        price_url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true"
        resp = requests.get(price_url, timeout=10).json()
        
        btc_price = resp['bitcoin']['usd']
        btc_change = resp['bitcoin']['usd_24h_change']
        eth_price = resp['ethereum']['usd']
        eth_change = resp['ethereum']['usd_24h_change']
        sol_price = resp['solana']['usd']
        sol_change = resp['solana']['usd_24h_change']
        
        fng_url = "https://api.alternative.me/fng/"
        fng_resp = requests.get(fng_url, timeout=10).json()
        fng_value = fng_resp['data'][0]['value']
        fng_class = fng_resp['data'][0]['value_classification']
        
        # 把纯净的数据传给 AI
        data_str = f"""
        当前数据：
        BTC: ${btc_price:,.2f} ({btc_change:.2f}%)
        ETH: ${eth_price:,.2f} ({eth_change:.2f}%)
        SOL: ${sol_price:,.2f} ({sol_change:.2f}%)
        加密恐慌与贪婪指数: {fng_value} ({fng_class})
        """
    except Exception as e:
        print(f"⚠️ 行情数据获取失败: {e}")
        data_str = "【实时行情数据】获取失败。"
    return data_str

def summarize_with_deepseek(crypto, btc, macro, cn_news, cn_finance, market_data):
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    
    prompt = f"""
    请根据以下今日资讯和实时数据，生成一份全球化的加密与宏观金融日报。

    {market_data}

    【加密货币综合新闻】
    {chr(10).join(crypto)}

    【比特币专项新闻】
    {chr(10).join(btc)}

    【美国及国际宏观新闻（含美股）】
    {chr(10).join(macro)}

    【国内综合新闻】
    {chr(10).join(cn_news)}

    【国内金融新闻】
    {chr(10).join(cn_finance)}

    要求生成以下七个板块（用 `### ` 作为标题）：
    
    ### 一、市场行情与情绪
    请结合上面提供的实时数据，用一段自然、连贯的分析语言总结当前市场。**必须**在段落中自然地提及比特币价格、以太坊价格以及加密恐慌与贪婪指数的具体数值和分类。不要生硬地罗列。
    
    ### 二、比特币（BTC）专属动态
    结合价格走势与专项新闻，深度分析BTC当前的支撑/压力位及核心动向。
    
    ### 三、推特热门与加密大事件
    提取推特上可能引发热议的事件（黑客攻击、大佬喊话、重大监管等）。
    
    ### 四、美股与国际宏观
    剔除纯地缘政治废话。**必须明确列出**美股三大股指（道指、纳指、标普）的动向（若新闻未披露具体数据，请说明），以及美联储/宏观数据的重要信息。
    
    ### 五、国内重要新闻（严格限制5条）
    从【国内综合新闻】中，提炼出前一天国内最重要的 5 条新闻。要求客观、精炼。
    
    ### 六、国内金融动态
    从【国内金融新闻】中，提取关于A股、央行、汇率、房地产或重要监管政策的核心信息。
    
    ### 七、空投与项目进度
    挖掘加密新闻中的空投、TGE、融资项目（项目简介、最新进度，未披露的信息直接注明）。

    语言要专业、连贯、有洞察力。绝对不要编造没有提及的事实。
    """
    
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "system", "content": "你是顶级的跨国金融与加密分析师。"}, {"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4000  # 放开字数限制
    )
    return response.choices[0].message.content

def push_wechat(title, content):
    requests.post("https://www.pushplus.plus/send", json={"token": PUSHPLUS_TOKEN, "title": title, "content": content, "template": "markdown"}, timeout=30)

def main():
    print("正在获取实时行情数据...")
    market_data = get_market_data()
    
    print("正在抓取全球及国内新闻...")
    crypto = fetch_rss_entries(RSS_FEEDS["crypto_news"])
    btc = fetch_rss_entries(RSS_FEEDS["bitcoin_news"])
    macro = fetch_rss_entries(RSS_FEEDS["macro_finance"])
    cn_news = fetch_rss_entries(RSS_FEEDS["cn_news"])
    cn_finance = fetch_rss_entries(RSS_FEEDS["cn_finance"])
    
    if not crypto and not macro and not btc and not cn_news:
        print("未抓取到任何新闻，退出。")
        return
    
    print(f"抓取完毕：加密 {len(crypto)}，BTC {len(btc)}，国际宏观 {len(macro)}，国内综合 {len(cn_news)}，国内金融 {len(cn_finance)}。")
    print("正在调用 DeepSeek 进行七板块结构化总结...")
    summary = summarize_with_deepseek(crypto, btc, macro, cn_news, cn_finance, market_data)
    
    print("正在推送到微信...")
    push_wechat("每日全球金融与加密早报", summary)
    print("✅ 推送成功！")

if __name__ == "__main__":
    main()
