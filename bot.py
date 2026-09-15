import feedparser
import asyncio
import os
import re
import requests
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
import logging
from deep_translator import GoogleTranslator, MyMemoryTranslator

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@kurdish_short_news")
FB_TOKEN = os.getenv("FB_TOKEN")
FB_ID = os.getenv("FB_ID")

MEGA_AI_FEEDS = {
    "MIT Technology Review AI": "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai/index.xml",
    "Wired AI": "https://www.wired.com/feed/tag/ai/latest/rss",
    "AI News": "https://www.artificialintelligence-news.com/feed/",
    "MarkTechPost": "https://www.marktechpost.com/feed/",
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def clean(t):
    if not t: return ""
    t = re.sub('<[^<]+?>', '', t)
    t = t.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    t = re.sub(r'\s+', ' ', t)
    return t.strip()[:700]

def post_to_facebook(text):
    if not FB_TOKEN or not FB_ID:
        logging.warning("⚠️ FB_TOKEN/FB_ID not set")
        return False
    try:
        clean_text = re.sub(r'<[^>]+>', '', text)[:5000]
        url = f"https://graph.facebook.com/{FB_ID}/feed"
        r = requests.post(url, data={"message": clean_text, "access_token": FB_TOKEN}, timeout=20)
        logging.info(f"FB: {r.status_code} {r.text[:300]}")
        return r.status_code == 200
    except Exception as e:
        logging.error(f"FB Error: {e}")
        return False

def to_kurdish(text, src='en'):
    if not text or len(text) < 5: return text
    try:
        text = clean(text)[:500]
        tr = MyMemoryTranslator(source="en-US", target="ckb-IQ").translate(text)
        if tr and len(tr) > 5: return tr
    except: pass
    return text

def is_ai(text):
    if not text: return False
    kws = ["ai","chatgpt","openai","gemini","gpt","llm","machine learning"]
    return any(k in text.lower() for k in kws)

async def main():
    bot = Bot(token=BOT_TOKEN)
    collected=[]
    for name,url in MEGA_AI_FEEDS.items():
        try:
            feed=feedparser.parse(url)
            for entry in feed.entries[:3]:
                title=clean(getattr(entry,'title',''))
                summary=clean(getattr(entry,'summary',''))
                link=getattr(entry,'link','')
                if not title or not link: continue
                if is_ai(f"{title} {summary}"):
                    collected.append({"title":title,"summary":summary,"link":link,"source":name})
                if len(collected)>=3: break
        except: continue
        if len(collected)>=3: break

    for i,item in enumerate(collected,1):
        ku_title=to_kurdish(item['title'])
        ku_sum=to_kurdish(item['summary'])[:200]
        text_tg=f"<b>{i}. {ku_title}</b>\n\n{ku_sum}\n\n🔗 <a href='{item['link']}'>خوێندنەوەی تەواو</a>\n#{item['source']}"
        try:
            await bot.send_message(chat_id=CHANNEL_ID, text=text_tg, parse_mode=ParseMode.HTML)
            post_to_facebook(f"{i}. {ku_title}\n\n{ku_sum}\n\n{ item['link'] }")
            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Send fail: {e}")

if __name__=="__main__":
    asyncio.run(main())
