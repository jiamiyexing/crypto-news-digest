import os
import requests
import feedparser
from openai import OpenAI

# ================= 配置区域 =================
RSS_FEEDS = {
    "crypto_news": [
        "https://rss.odaily.news/rss/newsflash",           # Odaily 快讯
        "https://rsshub.app/foresightnews/news",           # Foresight 快讯
        "https://www.coindesk.com/arc/outboundfeeds/rss/"  # CoinDesk 国际加密源
    ],
    "bitcoin_news": [
        "https://cointelegraph.com/rss/tag/bitcoin",       # Cointelegraph 比特币专版
    ],
    "macro_finance": [
        "https://www.reutersagency.com/feed/",             # 路透社商业
        "https://feeds.bloomberg.com/markets/news.rss",    # 彭博市场
        "https://finance.yahoo.com/news/rssindex"          # 雅虎财经
    ],
    "twitter_hot": [] # 交由 AI 从加密新闻中提取
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
    """获取免费行情和恐慌贪婪指数"""
    data_str = ""
    try:
        # 1. 获取币价（CoinGecko 免费接口）
        price_url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true"
        resp = requests.get(price_url, timeout=10).json()
        
        btc_price = resp['bitcoin']['usd']
        btc_change = resp['bitcoin']['usd_24h_change']
        eth_price = resp['ethereum']['usd']
        eth_change = resp['ethereum']['usd_24h_change']
        sol_price = resp['solana']['usd']
        sol_change = resp['solana']['usd_24h_change']
        
        # 2. 获取恐慌贪婪指数（Alternative.me 免费接口）
        fng_url = "https://api.alternative.me/fng/"
        fng_resp = requests.get(fng_url, timeout=10).json()
        fng_value = fng_resp['data'][0]['value']
        fng_class = fng_resp['data'][0]['value_classification']
        
        data_str = f"""
        【实时行情数据】
        比特币 (BTC): ${btc_price:,.2f} (24h涨跌: {btc_change:.2f}%)
        以太坊 (ETH): ${eth_price:,.2f} (24h涨跌: {eth_change:.2f}%)
        Solana (SOL): ${sol_price:,.2f} (24h涨跌: {sol_change:.2f}%)
        加密恐慌与贪婪指数: {fng_value} ({fng_class})
        """
    except Exception as e:
        print(f"⚠️ 行情数据获取失败: {e}")
        data_str = "【实时行情数据】获取失败，请仅依靠新闻判断。"
    return data_str

def summarize_with_deepseek(crypto_entries, btc_entries, macro_entries, market_data):
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    
    prompt = f"""
    请根据以下今日资讯和实时数据，生成一份专业的加密与宏观日报。

    {market_data}

    【加密货币综合新闻】
    {chr(10).join(crypto_entries)}

    【比特币专项新闻】
    {chr(10).join(btc_entries)}

    【宏观金融新闻】
    {chr(10).join(macro_entries)}

    要求生成以下五个板块（用 `### ` 作为标题）：
    
    ### 一、市场行情与情绪
    结合上面的实时数据，用一句话总结当前市场状态（如：大盘处于极度恐慌，BTC微跌，SOL逆势上涨等）。
    
    ### 二、比特币（BTC）专属动态
    结合比特币的价格走势，提取【比特币专项新闻】中的核心信息，并联动【加密货币综合新闻】中与BTC相关的内容。分析当前BTC的支撑/压力或重大事件。
    
    ### 三、推特热门与加密大事件
    从综合新闻和比特币新闻中，提取推特（X）上可能引发热议的事件（如CZ、马斯克、V神动态，或重大黑客攻击）。
    
    ### 四、美国及国际宏观金融
    **⚠️ 重点过滤：** 必须剔除纯地缘政治（如以色列内阁、欧洲福利）的废话，**只保留**与金融/美联储/利率/CPI/非农/美股/美债相关的硬核宏观新闻。
    
    ### 五、空投与项目进度
    从所有新闻中挖掘涉及空投、TGE、融资的项目。
    1. 项目简介
    2. 融资/投资方（未披露则写未披露）
    3. 最新进度（发任务/即将空投等）

    语言要精炼专业，全文不超过 1500 字。
    """
    
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "system", "content": "你是华尔街顶级的加密与宏观金融分析师。"}, {"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content

def push_wechat(title, content):
    requests.post("https://www.pushplus.plus/send", json={"token": PUSHPLUS_TOKEN, "title": title, "content": content, "template": "markdown"}, timeout=30)

def main():
    print("正在获取实时行情数据...")
    market_data = get_market_data()
    
    print("正在抓取新闻...")
    crypto = fetch_rss_entries(RSS_FEEDS["crypto_news"])
    btc = fetch_rss_entries(RSS_FEEDS["bitcoin_news"])
    macro = fetch_rss_entries(RSS_FEEDS["macro_finance"])
    
    if not crypto and not macro and not btc:
        print("未抓取到任何新闻，退出。")
        return
    
    print(f"抓取到 {len(crypto)} 条综合新闻，{len(btc)} 条BTC新闻，{len(macro)} 条宏观新闻。")
    print("正在调用 DeepSeek 进行结构化总结...")
    summary = summarize_with_deepseek(crypto, btc, macro, market_data)
    
    print("正在推送到微信...")
    push_wechat("每日加密与宏观简报", summary)
    print("✅ 推送成功！")

if __name__ == "__main__":
    main()
