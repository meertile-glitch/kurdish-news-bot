import feedparser
import asyncio
import os
import re
import requests
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
import logging
from deep_translator import GoogleTranslator

# ===== Secrets from GitHub =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@kurdishnews")
FB_TOKEN = os.getenv("FB_TOKEN")
FB_ID = os.getenv("FB_ID")

if not BOT_TOKEN:
    raise SystemExit(
        "❌ BOT_TOKEN پێویستە وەگ ژینگە گۆڕاو\n"
        "نموونە: export BOT_TOKEN='تۆکەنەکەت'"
    )

# ===== سەرچاوە AI =====
MEGA_AI_FEEDS = {
    "MIT Technology Review AI": "https://www.technologyreview.com/feed/",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "Wired AI": "https://www.wired.com/feed/tag/ai/latest/rss",
    "AI News": "https://www.artificialintelligence-news.com/feed/",
    "MarkTechPost": "https://www.marktechpost.com/feed/",
    "AI Business": "https://aibusiness.com/feed",
    "Towards AI": "https://towardsai.net/feed",
    "Analytics Vidhya": "https://www.analyticsvidhya.com/blog/feed/"
}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
translator = GoogleTranslator(source='en', target='ku')

# ===== Facebook Function =====
def post_to_facebook(text):
    if not FB_TOKEN or not FB_ID:
        print("⚠️ FB_TOKEN/FB_ID not set, skipping FB")
        return False
    try:
        # پاککردنەوەی تەگەکانی HTML بۆ Facebook
        clean = re.sub(r'<[^>]+>', '', text)
        clean = clean.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        url = f"https://graph.facebook.com/{FB_ID}/feed"
        data = {"message": clean, "access_token": FB_TOKEN}
        r = requests.post(url, data=data, timeout=20)
        print(f"✅ FB Posted: {r.status_code} - {r.text[:300]}")
        return r.status_code == 200
    except Exception as e:
        print(f"❌ FB Error: {e}")
        return False

def clean_html(raw_html):
    clean = re.sub(r'<[^>]+>', '', raw_html)
    return clean[:400] + "..." if len(clean) > 400 else clean

def translate_to_kurdish(text):
    try:
        # کورتی بکە بۆ وەرگێڕان
        short_text = text[:900]
        translated = translator.translate(short_text)
        return translated
    except Exception as e:
        print(f"Translate error: {e}")
        return text

async def fetch_and_post():
    print(f"🚀 Starting at {datetime.now()}")
    for name, url in MEGA_AI_FEEDS.items():
        try:
            print(f"Checking {name}...")
            feed = feedparser.parse(url)
            if not feed.entries:
                continue

            entry = feed.entries[0]
            title = entry.get('title', 'No title')
            link = entry.get('link', '')
            summary = clean_html(entry.get('summary', ''))

            # وەرگێڕان بۆ کوردی
            ku_title = translate_to_kurdish(title)
            ku_summary = translate_to_kurdish(summary)

            final_message = f"""🤖 <b>{ku_title}</b>

{ku_summary}

🔗 <a href="{link}">خوێندنەوەی تەواو</a>

#AI #هوشی_دەستکرد #TechNews #AINewsKRD
📰 سەرچاوە: {name}
"""

            # 1. ناردن بۆ Telegram
            try:
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=final_message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False
                )
                print(f"✅ Telegram sent: {name}")
            except Exception as e:
                print(f"Telegram error: {e}")

            # 2. ناردن بۆ Facebook
            fb_text = f"""{ku_title}

{ku_summary}

🔗 {link}

#AI #هوشی_دەستکرد #AINewsKRD
سەرچاوە: {name}"""

            post_to_facebook(fb_text)

            # تەنها یەک هەواڵ لە هەر جارێکدا - بۆ ئەوەی سپام نەبێت
            print("✅ Done, exiting after 1 post")
            return

        except Exception as e:
            print(f"Error in {name}: {e}")
            continue

    print("No news found")

if __name__ == "__main__":
    asyncio.run(fetch_and_post())
