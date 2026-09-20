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
from PIL import Image, ImageDraw, ImageFont
import textwrap
import random

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8921906381:AAEtOy3QDFFuwNMxHWeYSA9PsLvlqxQG24I"
CHANNEL_ID = os.getenv("CHANNEL_ID") or "@kurdish_short_news"
SENT_FILE = "sent.txt"
FB_PAGE_ID = os.getenv("FB_PAGE_ID") or os.getenv("FB_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN") or os.getenv("FB_TOKEN")

# Use the uploaded template as base
TEMPLATE_PATH = "template_base.jpg"  # Will be included in repo

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

def get_image_from_entry(entry):
    try:
        if hasattr(entry, 'media_content'):
            for m in entry.media_content:
                url = m.get('url')
                if url and url.startswith('http'):
                    return url
        if hasattr(entry, 'media_thumbnail'):
            for m in entry.media_thumbnail:
                url = m.get('url')
                if url and url.startswith('http'):
                    return url
        if hasattr(entry, 'enclosures'):
            for enc in entry.enclosures:
                url = enc.get('href') or enc.get('url')
                if url and url.startswith('http'):
                    return url
        summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
        if summary:
            m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary, re.I)
            if m:
                url = m.group(1)
                if url.startswith('http'):
                    return url
    except:
        pass
    return None

def is_fresh(entry, hours=24):
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            diff = now - pub
            return diff <= timedelta(hours=hours)
        return True
    except:
        return True

def to_kurdish(text, src='en'):
    if not text or len(text) < 5:
        return text
    text = clean(text)[:500]
    if any(c in text.lower() for c in [' ve ', ' bir ', ' bu ', ' için']):
        src = 'tr'
    for s, t in [(src,'ckb'), ('auto','ckb'), ('en','ku'), ('tr','ckb')]:
        try:
            tr = GoogleTranslator(source=s, target=t).translate(text)
            if tr and len(tr) > 10:
                logging.info(f"Translated {s}->{t}: {text[:30]} -> {tr[:30]}")
                return tr
        except:
            continue
    return text

def is_ai_news(text):
    if not text: return False
    kws = ["ai", "artificial intelligence", "chatgpt", "openai", "gemini", "gpt-4", "gpt-5", "llm", "machine learning", "anthropic", "claude", "yapay zeka", "sora", "nvidia", "neural", "generative"]
    return any(k in text.lower() for k in kws)

def create_ai_news_card(kurdish_title, kurdish_summary, output_path="news_card.jpg"):
    """دروستکردنی کارت بە دیزاینی AI News Kurdish - هەمان وێنەی تۆ"""
    W, H = 1080, 1080
    
    # Try to use template base if exists, else create from scratch
    if os.path.exists(TEMPLATE_PATH):
        base = Image.open(TEMPLATE_PATH).convert('RGB').resize((W,H))
    else:
        # Create dark tech background
        base = Image.new('RGB', (W,H), (7,10,30))
        draw_tmp = ImageDraw.Draw(base)
        # Add some glow dots
        for _ in range(100):
            x = random.randint(0,W)
            y = random.randint(0,H)
            r = random.randint(2,12)
            draw_tmp.ellipse([x-r,y-r,x+r,y+r], fill=(40,60,180,50))
    
    img = base.copy()
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # Load fonts
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
        font_title_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        font_kurdish = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except:
        font_title = ImageFont.load_default()
        font_title_small = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_kurdish = ImageFont.load_default()
    
    # Top left logo - orange circle
    logo_x, logo_y = 40, 35
    logo_r = 50
    draw.ellipse([logo_x, logo_y, logo_x+logo_r*2, logo_y+logo_r*2], fill=(255,108,20))
    draw.text((logo_x+22, logo_y+18), "AI", fill="white", font=font_title)
    draw.text((logo_x+125, logo_y+18), "AI NEWS", fill="white", font=font_small)
    draw.text((logo_x+125, logo_y+44), "KURDISH", fill="white", font=font_small)
    
    # Glass card - center
    card_w, card_h = 820, 720
    card_x = (W - card_w)//2
    card_y = (H - card_h)//2 + 30
    
    # Semi-transparent card
    card_overlay = Image.new('RGBA', (card_w, card_h), (25,30,75, 210))
    mask = Image.new('L', (card_w, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0,0,card_w,card_h], radius=30, fill=255)
    card_overlay.putalpha(mask)
    img.paste(card_overlay, (card_x, card_y), card_overlay)
    
    # Neon border
    draw = ImageDraw.Draw(img)
    for i in range(2):
        draw.rounded_rectangle([card_x-i, card_y-i, card_x+card_w+i, card_y+card_h+i], radius=30+i, outline=(130,90,255), width=1)
    
    # Wrap Kurdish title
    # Clean title for display
    title = kurdish_title[:120]
    # Wrap into 2-3 lines
    wrapped = textwrap.wrap(title, width=28)
    wrapped = wrapped[:3]  # Max 3 lines
    
    # Draw title lines centered
    start_y = card_y + 120
    for i, line in enumerate(wrapped):
        bbox = draw.textbbox((0,0), line, font=font_kurdish)
        tw = bbox[2]-bbox[0]
        draw.text((W//2 - tw//2, start_y + i*60), line, fill="white", font=font_kurdish)
    
    # Summary if exists (smaller)
    if kurdish_summary:
        summary = kurdish_summary[:120]
        sum_wrapped = textwrap.wrap(summary, width=38)
        sum_wrapped = sum_wrapped[:2]
        start_y2 = start_y + len(wrapped)*60 + 30
        for j, line in enumerate(sum_wrapped):
            bbox = draw.textbbox((0,0), line, font=font_small)
            tw = bbox[2]-bbox[0]
            draw.text((W//2 - tw//2, start_y2 + j*28), line, fill=(200,210,255), font=font_small)
    
    # Line separator
    line_y = card_y + card_h - 140
    draw.line([card_x+60, line_y, card_x+card_w-60, line_y], fill=(100,180,255,120), width=1)
    
    # Bottom AI News Kurdish
    bottom = "AI News Kurdish"
    bbox_b = draw.textbbox((0,0), bottom, font=font_small)
    tw_b = bbox_b[2]-bbox_b[0]
    draw.text((W//2 - tw_b//2, line_y+30), bottom, fill=(120,180,255), font=font_small)
    
    # Footer domain
    draw.text((35, H-45), "ai.news.krd", fill=(100,180,255), font=font_small)
    
    img.save(output_path, quality=95)
    return output_path

def post_to_facebook_with_image(message, link="", image_path=None):
    if not FB_PAGE_ID or not FB_PAGE_TOKEN:
        return False
    try:
        fb_message = f"{message}\n\n🔗 {link}" if link else message
        if image_path and os.path.exists(image_path):
            # Upload photo with caption
            url = f"https://graph.facebook.com/v18.0/me/photos"
            with open(image_path, 'rb') as f:
                files = {'source': f}
                data = {"caption": fb_message, "access_token": FB_PAGE_TOKEN}
                resp = requests.post(url, data=data, files=files, timeout=30)
                result = resp.json()
                logging.info(f"FB photo upload: {result}")
                if "id" in result or "post_id" in result:
                    return True
        # Fallback feed
        for endpoint in [f"https://graph.facebook.com/v18.0/me/feed", f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/feed"]:
            data = {"message": fb_message, "access_token": FB_PAGE_TOKEN, "link": link}
            resp = requests.post(endpoint, data=data, timeout=20)
            result = resp.json()
            if "id" in result:
                return True
        return False
    except Exception as e:
        logging.error(f"FB error: {e}")
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
    logging.info(f"Scanning AI news - {len(REAL_AI_FEEDS)} sources")
    for name, url in REAL_AI_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                title = clean(getattr(entry, 'title', ''))
                summary = clean(getattr(entry, 'summary', '') or getattr(entry, 'description', ''))
                link = getattr(entry, 'link', '')
                if not title or not link or link in seen_links: continue
                seen_links.add(link)
                if not is_fresh(entry, 24): continue
                if not is_ai_news(f"{title} {summary}"): continue
                link_hash = hashlib.md5(link.encode()).hexdigest()[:12]
                if link_hash in sent_hashes: continue
                image_url = get_image_from_entry(entry)
                pub_str = ""
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    pub_str = pub_dt.strftime("%H:%M")
                is_tr = 'tr' in url.lower() or "Anadolu" in name or "Webrazzi" in name
                collected.append({"title": title, "summary": summary, "link": link, "source": name, "lang": 'tr' if is_tr else 'en', "hash": link_hash, "time": pub_str, "image": image_url})
        except Exception as e:
            logging.error(f"{name} error: {e}")
            continue
    logging.info(f"Found {len(collected)} fresh AI news")
    if not collected:
        return
    selected = collected[:3]
    translated = []
    for item in selected:
        try:
            ku_title = to_kurdish(item['title'], item['lang'])
            ku_sum = to_kurdish(item['summary'], item['lang']) if item['summary'] else ""
            translated.append({**item, "ku_title": ku_title[:150], "ku_summary": ku_sum[:180]})
            await asyncio.sleep(1.2)
        except:
            translated.append({**item, "ku_title": item['title'], "ku_summary": item['summary'][:180]})
    for item in translated:
        # Create card image for this news
        card_path = f"card_{item['hash']}.jpg"
        try:
            create_ai_news_card(item['ku_title'], item['ku_summary'], card_path)
            logging.info(f"Created card: {card_path}")
        except Exception as e:
            logging.error(f"Card creation failed: {e}")
            card_path = None
        
        # Telegram with card
        try:
            flag = "🇹🇷" if item['lang'] == 'tr' else "🌍"
            time_str = f"⏰ {item['time']} UTC" if item['time'] else ""
            tg_text = (
                f"🔥 <b>{item['ku_title']}</b>\n\n"
                f"{item['ku_summary']}\n\n"
                f"{time_str} | {flag} {item['source']}\n"
                f"🔗 <a href='{item['link']}'>خوێندنەوەی تەواو</a>\n\n"
                f"#ژیری_دەستکرد #AI #کوردی"
            )
            if card_path and os.path.exists(card_path):
                with open(card_path, 'rb') as photo:
                    await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=tg_text, parse_mode=ParseMode.HTML)
            else:
                await bot.send_message(chat_id=CHANNEL_ID, text=tg_text, parse_mode=ParseMode.HTML)
            logging.info(f"Telegram sent: {item['ku_title'][:40]}")
            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Telegram fail: {e}")
        
        # Facebook with card
        try:
            fb_text = f"🔥 {item['ku_title']}\n\n{item['ku_summary']}\n\n⏰ {item['time']} UTC | {item['source']}\n\n#ژیری_دەستکرد #AI #کوردی"
            fb_ok = post_to_facebook_with_image(fb_text, item['link'], card_path)
            if fb_ok:
                logging.info(f"Facebook posted: {item['ku_title'][:30]}")
            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Facebook fail: {e}")
        
        # Cleanup card
        try:
            if card_path and os.path.exists(card_path):
                os.remove(card_path)
        except:
            pass

    try:
        all_hashes = sent_hashes.union(set([x['hash'] for x in translated]))
        with open(SENT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(list(all_hashes)[-500:]))
    except:
        pass
    logging.info(f"DONE - {len(translated)} news sent!")

if __name__ == "__main__":
    asyncio.run(main())
