import os
import re
import hashlib
import requests
import textwrap
import asyncio
import random
import math
import feedparser
from datetime import datetime, timedelta, timezone
from telegram import Bot
from telegram.constants import ParseMode
from PIL import Image, ImageDraw, ImageFont

import arabic_reshaper
from bidi.algorithm import get_display

# ١. وەرگرتنی زانیارییە هەستیارەکان لە Environment Variables
BOT = os.getenv("BOT_TOKEN")
CH = os.getenv("CHANNEL_ID", "@kurdish_short_news")
FID = os.getenv("FB_PAGE_ID") or os.getenv("FB_ID")
FTOK = os.getenv("FB_PAGE_TOKEN") or os.getenv("FB_TOKEN")

FEEDS = {
    "G AI": "https://news.google.com/rss/search?q=artificial+intelligence+when:1d&hl=en-US&gl=US&ceid=US:en",
    "G ChatGPT": "https://news.google.com/rss/search?q=ChatGPT+when:1d&hl=en-US&gl=US&ceid=US:en",
    "G Gemini": "https://news.google.com/rss/search?q=Gemini+AI+when:1d&hl=en-US&gl=US&ceid=US:en",
    "TechCrunch": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "TheVerge": "https://www.theverge.com/rss/ai/index.xml",
    "Wired": "https://www.wired.com/feed/tag/ai/latest/rss"
}

def cl(t):
    if not t:
        return ""
    t = re.sub(r'<[^<]+?>', '', t)
    return re.sub(r'\s+', ' ', t).strip()[:500]

def tr_mem(txt, src='en', tgt='ckb'):
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get", 
            params={"q": txt[:350], "langpair": f"{src}|{tgt}"}, 
            timeout=8
        )
        d = r.json()
        if d.get('responseStatus') == 200:
            t = d['responseData']['translatedText']
            if t and len(t) > 8 and '[MYMEMORY' not in t and t.lower() != txt.lower()[:20]:
                return t
    except Exception:
        pass
    return None

def to_ku(txt, src='en'):
    txt = cl(txt)
    if not txt:
        return txt
    for s, t in [(src, 'ckb'), ('en', 'ckb'), (src, 'ku'), ('en', 'ku')]:
        r = tr_mem(txt, s, t)
        if r:
            return r
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source=src, target='ckb').translate(txt[:350])
    except Exception:
        pass
    return txt

def fresh(e, h=24):
    try:
        if hasattr(e, 'published_parsed') and e.published_parsed:
            pub = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - pub) <= timedelta(hours=h)
        return True
    except Exception:
        return True

def is_ai(t):
    """لە کاتی تێستدا True ڕاگیراوە بۆ ئەوەی هەموو هەواڵێک تێپەڕێت"""
    return True

def reshape_ku(text):
    """بۆ بەستنەوەی پیتە کوردییەکان و ڕاستکردنەوەی چەپ/ڕاست (RTL)"""
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

def create_beautiful_background(W, H):
    img = Image.new('RGB', (W, H), (4, 6, 22))
    draw = ImageDraw.Draw(img, 'RGBA')
    for y in range(H):
        r = int(4 + y * 0.02 + math.sin(y * 0.01) * 2)
        g = int(6 + y * 0.025)
        b = int(22 + y * 0.06 + math.sin(y * 0.008) * 5)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    for _ in range(150):
        x = random.randint(-50, W + 50)
        y = random.randint(-50, H + 50)
        s = random.randint(6, 45)
        alpha = random.randint(20, 90)
        c = random.choice([(100, 80, 255), (80, 130, 255), (140, 90, 255), (70, 200, 255), (110, 90, 230), (60, 180, 220)])
        draw.ellipse([x - s, y - s, x + s, y + s], fill=(c[0], c[1], c[2], alpha))
    return img

def card(title, summary, out="card.jpg"):
    W, H = 1080, 1080
    base = create_beautiful_background(W, H)
    img = base.copy()
    draw = ImageDraw.Draw(img, 'RGBA')

    try:
        LAYOUT = ImageFont.Layout.RAQM
    except Exception:
        LAYOUT = None

    def find_font(names):
        dirs = ["/usr/share/fonts/truetype/noto", "/usr/share/fonts/opentype/noto", "/usr/share/fonts/truetype/dejavu", "./", "./fonts"]
        for d in dirs:
            for n in names:
                p = os.path.join(d, n)
                if os.path.exists(p):
                    return p
        return None

    def load(p, size):
        try:
            return ImageFont.truetype(p, size, layout_engine=LAYOUT) if LAYOUT else ImageFont.truetype(p, size)
        except Exception:
            return ImageFont.load_default()

    en_bold = find_font(["DejaVuSans-Bold.ttf"]) or "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    en_reg = find_font(["DejaVuSans.ttf"]) or "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ku_bold = find_font(["NotoKufiArabic-Bold.ttf", "NotoNaskhArabic-Bold.ttf", "Vazirmatn-Bold.ttf"]) or en_bold
    ku_reg = find_font(["NotoKufiArabic-Regular.ttf", "NotoNaskhArabic-Regular.ttf", "Vazirmatn-Regular.ttf"]) or en_reg

    fb_en = load(en_bold, 46)
    fs_en = load(en_reg, 22)
    fb_ku = load(ku_bold, 52)
    fr_ku = load(ku_reg, 32)

    # دیزاینی لۆگۆ
    x, y = 45, 40
    draw.ellipse([x, y, x + 100, y + 100], fill=(255, 108, 20))
    draw.text((x + 28, y + 22), "AI", fill="white", font=fb_en)
    draw.text((x + 130, y + 18), "AI NEWS", fill="white", font=fs_en)
    draw.text((x + 130, y + 44), "KURDISH", fill="white", font=fs_en)

    # دیزاینی کارت (Glass effect)
    cw, ch = 880, 680
    cx, cy = (W - cw) // 2, (H - ch) // 2 + 40
    glass = Image.new('RGBA', (cw, ch), (18, 22, 48, 210))
    mask = Image.new('L', (cw, ch), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw, ch], radius=32, fill=255)
    glass.putalpha(mask)
    img.paste(glass, (cx, cy), glass)
    draw = ImageDraw.Draw(img, 'RGBA')

    # ١. دابەشکردنی دەقی ناونیشان (Title Wrap)
    title_clean = title[:130].strip()
    wr = textwrap.wrap(title_clean, width=28)[:4]
    
    sy = cy + 70
    for i, line in enumerate(wr):
        if not line.strip():
            continue
        
        # ۲. بەستنەوە و ڕاستکردنەوەی پیتەکان بۆ ئەم دێڕە
        shaped_line = reshape_ku(line)
        
        try:
            bbox = draw.textbbox((0, 0), shaped_line, font=fb_ku)
            tw = bbox[2] - bbox[0]
        except Exception:
            tw = len(shaped_line) * 20
            
        x_center = W // 2 - tw // 2
        y_pos = sy + i * 75
        draw.text((x_center, y_pos), shaped_line, fill="white", font=fb_ku)

    # ۳. دابەشکردنی پوختەی هەواڵ (Summary Wrap)
    if summary:
        summary_clean = summary[:120].strip()
        sw = textwrap.wrap(summary_clean, width=38)[:2]
        sy2 = sy + len(wr) * 75 + 30
        
        for j, line in enumerate(sw):
            if not line.strip():
                continue
            
            shaped_summary_line = reshape_ku(line)
            
            try:
                bbox = draw.textbbox((0, 0), shaped_summary_line, font=fr_ku)
                tw = bbox[2] - bbox[0]
            except Exception:
                tw = len(shaped_summary_line) * 12
                
            x_center = W // 2 - tw // 2
            draw.text((x_center, sy2 + j * 42), shaped_summary_line, fill=(220, 225, 255), font=fr_ku)

    # Footer
    ly = cy + ch - 100
    draw.line([cx + 60, ly, cx + cw - 60, ly], fill=(100, 180, 255, 120), width=1)
    draw.text((W // 2 - 80, ly + 20), "AI News Kurdish", fill=(130, 190, 255), font=fs_en)
    
    img.save(out, quality=95)
    return out

def fb_post(msg, link="", img_path=None):
    if not FTOK:
        return False
    try:
        cap = f"{msg}\n\n🔗 {link}" if link else msg
        if img_path and os.path.exists(img_path):
            with open(img_path, 'rb') as f:
                r = requests.post(
                    "https://graph.facebook.com/v18.0/me/photos", 
                    data={"caption": cap, "access_token": FTOK}, 
                    files={'source': f}, 
                    timeout=30
                )
                return "id" in r.json() or "post_id" in r.json()
    except Exception:
        pass
    return False

async def main():
    if not BOT:
        print("❌ کێشە: BOT_TOKEN لە Environment Variables نەدۆزرایەوە!")
        return

    print("🚀 بۆتەکە دەستی بە کارکردن کرد...")
    bot = Bot(token=BOT)
    
    sent = set()
    try:
        with open("sent.txt", "r", encoding="utf-8") as f:
            sent = set(l.strip() for l in f if l.strip())
        print(f"📁 ژمارەی هەواڵە پێشتر نێردراوەکان: {len(sent)}")
    except Exception as e:
        print(f"⚠️ فایلی sent.txt نەدۆزرایەوە یان بەتاڵە: {e}")

    coll = []
    seen = set()
    
    for name, url in FEEDS.items():
        try:
            print(f"🔍 پشکنین بۆ feedی: {name} ...")
            feed = feedparser.parse(url)
            print(f"📊 ژمارەی بابەتە دۆزراوەکان لە {name}: {len(feed.entries)}")
            
            for e in feed.entries[:8]:
                t = cl(getattr(e, 'title', ''))
                s = cl(getattr(e, 'summary', '') or getattr(e, 'description', ''))
                lk = getattr(e, 'link', '')
                
                if not t or not lk:
                    continue
                if lk in seen:
                    continue
                seen.add(lk)
                
                if not fresh(e, 24):
                    print(f"  - ڕەتکرایەوە (کۆنە): {t[:30]}...")
                    continue
                
                h = hashlib.md5(lk.encode()).hexdigest()[:10]
                if h in sent:
                    print(f"  - ڕەتکرایەوە (پێشتر نێردراوە): {t[:30]}...")
                    continue
                
                pt = ""
                if hasattr(e, 'published_parsed') and e.published_parsed:
                    pt = datetime(*e.published_parsed[:6], tzinfo=timezone.utc).strftime("%H:%M")
                
                coll.append({"title": t, "summary": s, "link": lk, "source": name, "hash": h, "time": pt})
        except Exception as err:
            print(f"❌ کێشە لە خوێندنەوەی {name}: {err}")

    print(f"✅ کۆی گشتی هەواڵە گونجاوەکان: {len(coll)}")

    if not coll:
        print("⚠️ هیچ هەواڵێکی نوێ بۆ ناردن نەدۆزرایەوە!")
        return

    sel = coll[:3]
    for it in sel:
        print(f"🔄 وەرگێڕانی: {it['title'][:40]}...")
        kt = to_ku(it['title'])
        ks = to_ku(it['summary'][:160]) if it['summary'] else ""
        
        cp = f"c_{it['hash']}.jpg"
        try:
            card(kt, ks, cp)
            print("🎨 وێنەی کارتەکە بە تەواوی دروستکرا.")
        except Exception as e:
            print(f"❌ کێشە لە دروستکردنی وێنە: {e}")
            cp = None

        tg_msg = f"🔥 <b>{kt}</b>\n\n{ks}\n\n⏰ {it['time']} UTC | {it['source']}\n🔗 <a href='{it['link']}'>خوێندنەوەی تەواو</a>\n\n#ژیری_دەستکرد #AI"
        
        # ناردن بۆ تێگرام
        try:
            print(f"📤 ناردن بۆ کەناڵی تێگرام: {CH} ...")
            if cp and os.path.exists(cp):
                with open(cp, 'rb') as ph:
                    await bot.send_photo(chat_id=CH, photo=ph, caption=tg_msg, parse_mode=ParseMode.HTML)
            else:
                await bot.send_message(chat_id=CH, text=tg_msg, parse_mode=ParseMode.HTML)
            print("🎉 بە سەرکەوتوویی بۆ تێگرام نێردرا!")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"❌ کێشە لە ناردن بۆ تێگرام: {e}")

        # ناردن بۆ فەیسبووک
        if FTOK:
            try:
                fb_msg = f"🔥 {kt}\n\n{ks}\n\n⏰ {it['time']} UTC | {it['source']}\n\n#ژیری_دەستکرد #AI"
                if fb_post(fb_msg, it['link'], cp):
                    print("🎉 بە سەرکەوتوویی بۆ فەیسبووک نێردرا!")
            except Exception as e:
                print(f"❌ کێشە لە ناردن بۆ فەیسبووک: {e}")

        # سڕینەوەی وێنە کاتییەکە
        if cp and os.path.exists(cp):
            os.remove(cp)

    # تۆمارکردنی ئایدی هەواڵە نێردراوەکان
    try:
        allh = sent.union(set([x['hash'] for x in sel]))
        with open("sent.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(list(allh)[-500:]))
        print("💾 فایلی sent.txt نوێکرایەوە.")
    except Exception as e:
        print(f"❌ کێشە لە ڕەوانەکردنی sent.txt: {e}")

if __name__ == "__main__":
    asyncio.run(main())
