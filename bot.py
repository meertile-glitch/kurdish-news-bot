import os
import re
import hashlib
import requests
import asyncio
import feedparser
from datetime import datetime, timezone, timedelta
from telegram import Bot
from telegram.constants import ParseMode
from PIL import Image, ImageDraw, ImageFont, features, ImageFilter
import arabic_reshaper
from bidi.algorithm import get_display
from deep_translator import GoogleTranslator

# Config from Env
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@kurdish_short_news")
FB_PAGE_ID = os.getenv("FB_PAGE_ID", "") or os.getenv("FB_ID", "")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN", "") or os.getenv("FB_TOKEN", "")

TECHCRUNCH_AI_FEED = "https://techcrunch.com/category/artificial-intelligence/feed/"
CHECK_INTERVAL_SECONDS = 300

def clean_text(t):
    if not t:
        return ""
    t = re.sub(r'<[^<]+?>', '', t)
    # Remove emojis that cause [] boxes
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002500-\U00002BEF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001f926-\U0001f937"
        u"\U00010000-\U0010ffff"
        u"\u2640-\u2642"
        u"\u2600-\u2B55"
        u"\u200d"
        u"\ufe0f"
        "]+", flags=re.UNICODE)
    t = emoji_pattern.sub('', t)
    t = t.replace('_', ' ').replace('[', ' ').replace(']', ' ')
    t = t.replace('📄', '').replace('📃', '').replace('📝', '').replace('🔥', '').replace('✨', '').replace('⚡', '')
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:500]

def translate_to_kurdish(txt):
    txt = clean_text(txt)
    if not txt:
        return ""
    try:
        translated = GoogleTranslator(source='en', target='ckb').translate(txt[:400])
        return clean_text(translated)
    except Exception as e:
        print(f"Translation Error: {e}")
        return txt

def reshape_kurdish_text(text):
    try:
        reshaper = arabic_reshaper.ArabicReshaper(arabic_reshaper.config_for_true_type_font)
        reshaped = reshaper.reshape(text)
        return get_display(reshaped)
    except Exception as e:
        print(f"Reshape error: {e}")
        return text

def find_font(font_names):
    dirs = [
        "/usr/share/fonts/truetype/noto",
        "/usr/share/fonts/opentype/noto",
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts",
        "/tmp/fonts",
        "./",
        "./fonts"
    ]
    for d in dirs:
        for n in font_names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return p
    return None

def create_news_card(title, summary, out_path="card.jpg"):
    W, H = 1080, 1080
    img = Image.new('RGB', (W, H), (10, 14, 30))
    draw = ImageDraw.Draw(img, 'RGBA')
    for y in range(H):
        r = int(10 + y * 0.02)
        g = int(14 + y * 0.03)
        b = int(30 + y * 0.05)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    
    # Subtle AI network background
    import random, math
    for _ in range(80):
        x = random.randint(-20, W+20)
        y = random.randint(-20, H+20)
        s = random.randint(4, 20)
        alpha = random.randint(15, 50)
        c = random.choice([(100,80,255), (80,130,255), (70,200,255)])
        draw.ellipse([x-s, y-s, x+s, y+s], fill=(c[0], c[1], c[2], alpha))

    ku_font_path = find_font(["Vazirmatn-Bold.ttf", "Vazirmatn-Medium.ttf", "NotoNaskhArabic-Bold.ttf", "DejaVuSans-Bold.ttf"])
    ku_reg_path = find_font(["Vazirmatn-Regular.ttf", "Vazirmatn-Medium.ttf", "NotoNaskhArabic-Regular.ttf"])
    en_font_path = find_font(["DejaVuSans-Bold.ttf", "DejaVuSans.ttf"])

    fb_ku = ImageFont.truetype(ku_font_path, 52) if ku_font_path else ImageFont.load_default()
    fr_ku = ImageFont.truetype(ku_reg_path or ku_font_path, 32) if (ku_reg_path or ku_font_path) else ImageFont.load_default()
    fs_en = ImageFont.truetype(en_font_path, 22) if en_font_path else ImageFont.load_default()
    fb_en = ImageFont.truetype(en_font_path, 42) if en_font_path else ImageFont.load_default()

    # Header Badge
    draw.ellipse([45, 40, 125, 120], fill=(0, 168, 255))
    draw.text((63, 62), "AI", fill="white", font=fb_en)
    draw.text((140, 55), "TECHCRUNCH AI", fill="white", font=fs_en)
    draw.text((140, 85), "KURDISH NEWS", fill=(130, 190, 255), font=fs_en)

    # Glass Box
    cw, ch = 920, 720
    cx, cy = (W - cw) // 2, (H - ch) // 2 + 30
    try:
        glass = Image.new('RGBA', (cw, ch), (18, 24, 48, 220))
        mask = Image.new('L', (cw, ch), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw, ch], radius=28, fill=255)
        glass.putalpha(mask)
        img.paste(glass, (cx, cy), glass)
    except:
        draw.rounded_rectangle([cx, cy, cx+cw, cy+ch], radius=28, fill=(18,24,48,220))
    
    draw = ImageDraw.Draw(img, 'RGBA')
    draw.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=28, outline=(0, 168, 255, 150), width=2)

    # Title - cleaned
    title = clean_text(title).replace("_", " ").replace("[", "").replace("]", "")[:130]
    words = title.split()
    lines, cur = [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if len(test) > 22:
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)

    sy = cy + 70
    for i, line in enumerate(lines[:4]):
        l_disp = reshape_kurdish_text(line)
        try:
            bbox = draw.textbbox((0, 0), l_disp, font=fb_ku)
            tw = bbox[2] - bbox[0]
        except:
            tw = len(line) * 15
        x_center = W // 2 - tw // 2
        y_pos = sy + i * 78
        # Soft shadow + thin stroke
        draw.text((x_center+3, y_pos+3), l_disp, fill=(0,0,0,180), font=fb_ku)
        for dx, dy in [(-1,-1), (-1,1), (1,-1), (1,1), (-1,0), (1,0), (0,-1), (0,1)]:
            draw.text((x_center+dx, y_pos+dy), l_disp, fill=(0,100,180,150), font=fb_ku)
        draw.text((x_center, y_pos), l_disp, fill="white", font=fb_ku)

    # Summary
    if summary:
        summary = clean_text(summary)[:140]
        words_s = summary.split()
        sw, cur_s = [], ""
        for w in words_s:
            test = f"{cur_s} {w}".strip()
            if len(test) > 32:
                if cur_s:
                    sw.append(cur_s)
                cur_s = w
            else:
                cur_s = test
        if cur_s:
            sw.append(cur_s)
        sy2 = sy + len(lines[:4]) * 78 + 25
        for j, line in enumerate(sw[:2]):
            l_disp = reshape_kurdish_text(line)
            try:
                bbox = draw.textbbox((0, 0), l_disp, font=fr_ku)
                tw = bbox[2] - bbox[0]
            except:
                tw = len(line) * 10
            x_c = W//2 - tw//2
            draw.text((x_c+1, sy2+j*42+1), l_disp, fill=(0,0,0,120), font=fr_ku)
            draw.text((x_c, sy2+j*42), l_disp, fill=(210,220,255), font=fr_ku)

    # Footer
    ly = cy + ch - 80
    draw.line([cx + 40, ly, cx + cw - 40, ly], fill=(100, 180, 255, 100), width=1)
    try:
        tw = draw.textbbox((0,0), "TechCrunch AI • ai.news.krd", font=fs_en)[2]
    except:
        tw = 200
    draw.text((W//2 - tw//2, ly + 25), "TechCrunch AI • ai.news.krd", fill=(130, 190, 255), font=fs_en)

    img.save(out_path, quality=95)
    return out_path

def post_to_facebook(caption, link, img_path):
    if not FB_PAGE_TOKEN or not FB_PAGE_ID:
        print("❌ FB_PAGE_TOKEN or FB_PAGE_ID missing - skipping Facebook")
        return False
    cap = f"{caption}\n\n🔗 {link}" if link else caption
    print(f"📘 FB post: {cap[:80]}... ID:{FB_PAGE_ID}")
    
    for ver in ["v21.0", "v20.0", "v19.0", "v18.0"]:
        try:
            if img_path and os.path.exists(img_path):
                url = f"https://graph.facebook.com/{ver}/{FB_PAGE_ID}/photos"
                print(f"  Trying {url}")
                with open(img_path, 'rb') as f:
                    r = requests.post(url, data={"caption": cap, "access_token": FB_PAGE_TOKEN}, files={'source': f}, timeout=40)
                    d = r.json()
                    print(f"  Response: {d}")
                    if "id" in d or "post_id" in d:
                        print(f"✅ FB photo posted: {d}")
                        return True
                    if "error" in d:
                        print(f"  ❌ {d['error'].get('code')}: {d['error'].get('message')}")
        except Exception as e:
            print(f"  Exception: {e}")
            continue
    
    # Fallback feed
    for ver in ["v21.0", "v20.0", "v18.0"]:
        try:
            url = f"https://graph.facebook.com/{ver}/{FB_PAGE_ID}/feed"
            r = requests.post(url, data={"message": cap, "link": link, "access_token": FB_PAGE_TOKEN}, timeout=20)
            d = r.json()
            print(f"  Feed response: {d}")
            if "id" in d:
                print(f"✅ FB feed posted: {d['id']}")
                return True
        except Exception as e:
            print(f"  Feed exception: {e}")
            continue
    
    print("❌ All FB attempts failed")
    return False

def get_sent_hashes():
    if not os.path.exists("sent.txt"):
        return set()
    with open("sent.txt", "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_sent_hash(news_hash):
    hashes = get_sent_hashes()
    hashes.add(news_hash)
    with open("sent.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(list(hashes)[-300:]))

def is_fresh(entry, hours=24):
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            from datetime import timedelta
            pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - pub) <= timedelta(hours=hours)
        return True
    except:
        return True

async def check_and_publish_news(bot):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking TechCrunch AI...")
    try:
        feed = feedparser.parse(TECHCRUNCH_AI_FEED)
        sent_hashes = get_sent_hashes()
        new_count = 0
        for entry in reversed(feed.entries[:5]):
            title = clean_text(getattr(entry, 'title', ''))
            link = getattr(entry, 'link', '')
            summary = clean_text(getattr(entry, 'summary', ''))
            if not title or not link:
                continue
            if not is_fresh(entry, 24):
                print(f"  Skipping old: {title[:60]}")
                continue
            news_hash = hashlib.md5(link.encode()).hexdigest()[:10]
            if news_hash in sent_hashes:
                continue
            print(f"  New: {title}")

            ku_title = translate_to_kurdish(title)
            ku_summary = translate_to_kurdish(summary[:200]) if summary else ""

            card_path = f"card_{news_hash}.jpg"
            try:
                create_news_card(ku_title, ku_summary, card_path)
            except Exception as e:
                print(f"Card error: {e}")
                import traceback
                traceback.print_exc()
                card_path = None

            tg_text = (
                f"⚡ <b>{ku_title}</b>\n\n"
                f"{ku_summary}\n\n"
                f"📰 سەرچاوە: TechCrunch AI\n"
                f"🔗 <a href='{link}'>خوێندنەوەی تەواوی بابەتی سەرەکی</a>\n\n"
                f"#ژیری_دەستکرد #TechCrunch #AI"
            )

            try:
                if card_path and os.path.exists(card_path):
                    with open(card_path, 'rb') as photo:
                        await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=tg_text, parse_mode=ParseMode.HTML)
                else:
                    await bot.send_message(chat_id=CHANNEL_ID, text=tg_text, parse_mode=ParseMode.HTML)
                print("  ✅ Telegram posted")
            except Exception as e:
                print(f"  TG error: {e}")

            fb_text = f"⚡ {ku_title}\n\n{ku_summary}\n\n#ژیری_دەستکرد #AI #TechCrunch"
            try:
                if post_to_facebook(fb_text, link, card_path):
                    print("  ✅ Facebook posted")
                else:
                    print("  ⚠️ Facebook failed")
            except Exception as e:
                print(f"  FB exception: {e}")

            if card_path and os.path.exists(card_path):
                try:
                    os.remove(card_path)
                except:
                    pass

            save_sent_hash(news_hash)
            new_count += 1
            print(f"  Published: {title[:50]}")
            await asyncio.sleep(3)
        
        if new_count == 0:
            print("  No new AI news")

    except Exception as e:
        print(f"Error during feed processing: {e}")
        import traceback
        traceback.print_exc()

async def main():
    bot = Bot(token=BOT_TOKEN)
    print(f"Bot started monitoring TechCrunch AI -> {CHANNEL_ID}")
    # If running in GitHub Actions (CI), run once and exit
    if os.getenv("GITHUB_ACTIONS") == "true":
        print("Running in GitHub Actions - single check mode")
        await check_and_publish_news(bot)
        return
    # Local continuous mode
    while True:
        await check_and_publish_news(bot)
        print(f"Sleeping {CHECK_INTERVAL_SECONDS}s...")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    asyncio.run(main())
