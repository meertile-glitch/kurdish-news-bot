import feedparser
import asyncio
import os
import re
from datetime import datetime, timedelta, timezone
from telegram import Bot
from telegram.constants import ParseMode
import logging
from deep_translator import GoogleTranslator
import hashlib
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8921906381:AAEtOy3QDFFuwNMxHWeYSA9PsLvlqxQG24I"
CHANNEL_ID = "@kurdish_short_news"
SENT_FILE = "sent.txt"

# Facebook - لە GitHub Secrets وەری دەگرێت
FB_PAGE_ID = os.getenv("FB_PAGE_ID") or os.getenv("FB_ID")  # ID ی پەیجەکەت
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN") or os.getenv("FB_TOKEN")  # Page Access Token

REAL_AI_FEEDS = {
    "Google News AI (24h)": "https://news.google.com/rss/search?q=artificial+intelligence+when:1d&hl=en-US&gl=US&ceid=US:en",
    "Google News ChatGPT (24h)": "https://news.google.com/rss/search?q=ChatGPT+OpenAI+when:1d&hl=en-US&gl=US&ceid=US:en",
    "Google News Gemini (24h)": "https://news.google.com/rss/search?q=Gemini+Google+Anthropic+Claude+when:1d&hl=en-US&gl=US&ceid=US:en",
    "Google News AI TR (24h)": "https://news.google.com/rss/search?q=yapay+zeka+when:1d&hl=tr&gl=TR&ceid=TR:tr",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai/index.xml",
    "MIT Tech Review": "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "Wired AI": "https://www.wired.com/feed/tag/ai/latest/rss",
    "BBC Technology": "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "Anadolu Tech": "https://www.aa.com.tr/tr/rss/default?cat=bilim-teknoloji",
    "Webrazzi": "https://webrazzi.com/feed/",
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def clean(t):
    if not t: return ""
    t = re.sub('<[^<]+?>', '', t)
    t = t.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    t = re.sub(r'\s+', ' ', t)
    return t.strip()

def is_fresh(entry, hours=24):
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            diff = now - pub
            return diff <= timedelta(hours=hours)
        if 'news.google.com' in getattr(entry, 'link', ''):
            return True
        return True
    except:
        return True

def to_kurdish(text, src='en'):
    if not text or len(text) < 5: return text
    try:
        text = clean(text)[:400]
        for tgt in ['ckb', 'ku']:
            try:
                tr = GoogleTranslator(source=src, target=tgt).translate(text)
                if tr and len(tr) > 5:
                    return tr
            except:
                continue
        return text
    except:
        return text

def is_ai_news(text):
    if not text: return False
    kws = ["ai", "artificial intelligence", "chatgpt", "openai", "gemini", "gpt-4", "gpt-5", "llm", "machine learning", "anthropic", "claude", "yapay zeka", "sora", "nvidia", "neural", "generative"]
    return any(k in text.lower() for k in kws)

def post_to_facebook(message, link=""):
    """ناردن بۆ Facebook Page - AI News KRD"""
    if not FB_PAGE_ID or not FB_PAGE_TOKEN:
        logging.info("Facebook credentials not set - skipping FB post")
        return False
    
    try:
        # بۆ Facebook، لینک لەگەڵ message
        fb_message = message
        if link:
            fb_message = f"{message}\n\n🔗 {link}"
        
        # Facebook Graph API
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/feed"
        data = {
            "message": fb_message,
            "access_token": FB_PAGE_TOKEN
        }
        # ئەگەر لینک هەیە وەک attachment
        if link:
            data["link"] = link
        
        resp = requests.post(url, data=data, timeout=15)
        result = resp.json()
        
        if "id" in result:
            logging.info(f"✅ Posted to Facebook: {result['id']}")
            return True
        else:
            logging.error(f"Facebook post failed: {result}")
            return False
    except Exception as e:
        logging.error(f"Facebook error: {e}")
        return False

async def main():
    bot = Bot(token=BOT_TOKEN)
    
    sent_hashes = set()
    try:
        with open(SENT_FILE, "r", encoding="utf-8") as f:
            sent_hashes = set(line.strip() for line in f if line.strip())
    except:
        pass
    
    collected = []
    seen_links = set()
    
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=24)
    
    logging.info(f"🔍 Scanning for AI news newer than {cutoff} - {len(REAL_AI_FEEDS)} sources")
    
    for name, url in REAL_AI_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                continue
            for entry in feed.entries[:10]:
                title = clean(getattr(entry, 'title', ''))
                summary = clean(getattr(entry, 'summary', '') or getattr(entry, 'description', ''))
                link = getattr(entry, 'link', '')
                
                if not title or not link: continue
                if link in seen_links: continue
                seen_links.add(link)
                
                if not is_fresh(entry, 24):
                    continue
                if not is_ai_news(f"{title} {summary}"):
                    continue
                
                link_hash = hashlib.md5(link.encode()).hexdigest()[:12]
                if link_hash in sent_hashes:
                    continue
                
                pub_str = ""
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    pub_str = pub_dt.strftime("%H:%M")
                
                is_tr = 'tr' in url.lower() or any(x in name for x in ["Anadolu", "Webrazzi"])
                
                collected.append({
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "source": name,
                    "lang": 'tr' if is_tr else 'en',
                    "hash": link_hash,
                    "time": pub_str,
                })
        except Exception as e:
            logging.error(f"{name} error: {e}")
            continue
    
    logging.info(f"📊 Found {len(collected)} FRESH AI news (last 24h)")
    
    if not collected:
        logging.info("No fresh news - will check next hour")
        return
    
    selected = collected[:3]  # تەنها 3 بۆ ئەوەی Facebook spam نەبێت
    
    translated = []
    for item in selected:
        try:
            ku_title = to_kurdish(item['title'], item['lang'])
            ku_sum = to_kurdish(item['summary'], item['lang']) if item['summary'] else ""
            translated.append({
                **item,
                "ku_title": ku_title if len(ku_title) > 10 else item['title'],
                "ku_summary": ku_sum[:180] + "..." if len(ku_sum) > 180 else ku_sum
            })
            await asyncio.sleep(0.8)
        except:
            translated.append({
                **item,
                "ku_title": item['title'],
                "ku_summary": item['summary'][:180]
            })
    
    new_hashes = []
    
    for item in translated:
        # ===== 1. Telegram =====
        try:
            flag = "🇹🇷" if item['lang'] == 'tr' else "🌍"
            time_str = f"⏰ {item['time']} UTC" if item['time'] else ""
            
            tg_text = (
                f"🔥 <b>هەواڵی نوێی ژیری دەستکرد</b>\n"
                f"{time_str} | {flag} {item['source']}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>{item['ku_title']}</b>\n\n"
                f"{item['ku_summary']}\n\n"
                f"🔗 <a href='{item['link']}'>خوێندنەوەی تەواو</a>\n\n"
                f"🕒 لە 24 کاتژمێری ڕابردوو\n"
                f"#ژیری_دەستکرد #AI"
            )
            
            await bot.send_message(chat_id=CHANNEL_ID, text=tg_text, parse_mode=ParseMode.HTML)
            logging.info(f"✅ Telegram sent: {item['ku_title'][:40]}")
            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Telegram send fail: {e}")
        
        # ===== 2. Facebook =====
        try:
            fb_text = f"🔥 {item['ku_title']}\n\n{item['ku_summary']}\n\n⏰ {item['time']} UTC | {item['source']} | لە 24 کاتژمێری ڕابردوو\n\n#ژیری_دەستکرد #AI #کوردی"
            fb_ok = post_to_facebook(fb_text, item['link'])
            if fb_ok:
                logging.info(f"✅ Facebook posted: {item['ku_title'][:30]}")
            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Facebook send fail: {e}")
        
        new_hashes.append(item['hash'])
    
    # پاشەکەوت
    try:
        all_hashes = sent_hashes.union(set(new_hashes))
        with open(SENT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(list(all_hashes)[-500:]))
    except Exception as e:
        logging.error(f"Save sent fail: {e}")
    
    logging.info(f"🎉 DONE - {len(new_hashes)} fresh AI news sent to Telegram + Facebook!")

if __name__ == "__main__":
    asyncio.run(main())
