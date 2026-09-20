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
from PIL import Image, ImageDraw, ImageFont, features

BOT = os.getenv("BOT_TOKEN") or "8921906381:AAEtOy3QDFFuwNMxHWeYSA9PsLvlqxQG24I"
CH = os.getenv("CHANNEL_ID") or "@kurdish_short_news"
FID = os.getenv("FB_PAGE_ID") or os.getenv("FB_ID")
FTOK = os.getenv("FB_PAGE_TOKEN") or os.getenv("FB_TOKEN")

# ONLY AI SOURCES + TWITTER/X - NO MIXED NEWS
FEEDS = {
    "Google AI": "https://news.google.com/rss/search?q=artificial+intelligence+AI+when:1d&hl=en-US&gl=US&ceid=US:en",
    "ChatGPT": "https://news.google.com/rss/search?q=ChatGPT+OpenAI+when:1d&hl=en-US&gl=US&ceid=US:en",
    "Gemini": "https://news.google.com/rss/search?q=Google+Gemini+AI+when:1d&hl=en-US&gl=US&ceid=US:en",
    "GPT-6 Astra": "https://news.google.com/rss/search?q=GPT-6+Astra+OpenAI+when:7d&hl=en-US&gl=US&ceid=US:en",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "TheVerge AI": "https://www.theverge.com/rss/ai/index.xml",
    "Wired AI": "https://www.wired.com/feed/tag/ai/latest/rss",
    "ArsTechnica AI": "https://feeds.arstechnica.com/civis/68"
}

# TWITTER/X SOURCES - ALL AI ACCOUNTS USER REQUESTED - Nitter RSS
TWITTER_FEEDS = {
    # User requested accounts from screenshots
    "ChatGPT": "https://nitter.poast.org/ChatGPT/rss",
    "ChatGPT Alt": "https://nitter.privacydev.net/ChatGPT/rss",
    "Claude AI": "https://nitter.poast.org/claudeai/rss",
    "Claude AI Alt": "https://nitter.privacydev.net/claudeai/rss",
    "Google AI Studio": "https://nitter.poast.org/GoogleAIStudio/rss",
    "Google AI Studio Alt": "https://nitter.privacydev.net/GoogleAIStudio/rss",
    # Previous accounts
    "OpenAI": "https://nitter.poast.org/OpenAI/rss",
    "OpenAI Alt": "https://nitter.privacydev.net/OpenAI/rss",
    "Sam Altman": "https://nitter.poast.org/sama/rss",
    "Google DeepMind": "https://nitter.poast.org/GoogleDeepMind/rss",
    "Anthropic AI": "https://nitter.poast.org/AnthropicAI/rss",
    # Google search fallbacks for reliability
    "GPT-6 Astra Search": "https://news.google.com/rss/search?q=GPT-6+Astra+OpenAI+ChatGPT+when:2d&hl=en-US&gl=US&ceid=US:en",
    "Gemini 3.8 Flash Search": "https://news.google.com/rss/search?q=Gemini+3.8+Flash+Google+AI+when:2d&hl=en-US&gl=US&ceid=US:en",
    "Claude Opus 5 Search": "https://news.google.com/rss/search?q=Claude+Opus+5+Anthropic+when:2d&hl=en-US&gl=US&ceid=US:en",
}

def fetch_twitter_news():
    """Fetch tweets from ALL AI accounts as news - ChatGPT, Claude, Gemini, OpenAI"""
    tweets = []
    for name, url in TWITTER_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:4]:
                t = cl(getattr(e, 'title', ''))
                lk = getattr(e, 'link', '')
                # Convert Nitter link to X.com link
                lk = lk.replace('nitter.poast.org', 'x.com').replace('nitter.privacydev.net', 'x.com')
                if not t or not lk:
                    continue
                # Only AI tweets
                if not is_ai_strict(t):
                    continue
                # Skip pure retweets
                if t.startswith('RT @') and len(t) < 100:
                    continue
                # Important keywords - GPT-6 Astra, Gemini 3.8, Claude Opus 5
                is_important = any(x in t.lower() for x in ['gpt-6', 'astra', 'gemini 3.8', 'claude opus 5', 'opus 5', 'new star', 'meets gpt'])
                h = hashlib.md5(lk.encode()).hexdigest()[:10]
                tweets.append({
                    "title": t,
                    "summary": t[:200],
                    "link": lk,
                    "source": name,
                    "lang": "en",
                    "hash": h,
                    "time": datetime.now(timezone.utc).strftime("%H:%M"),
                    "is_tweet": True,
                    "is_important": is_important
                })
                print(f"Tweet found: {name} - {t[:80]}")
        except Exception as e:
            print(f"Twitter fetch error {name}: {e}")
            continue
    # Sort important first - GPT-6 Astra, Gemini 3.8 Flash, Claude Opus 5 on top
    tweets.sort(key=lambda x: x.get('is_important', False), reverse=True)
    return tweets[:8]


def cl(t):
    if not t:
        return ""
    t = re.sub('<[^<]+?>', '', t)
    return re.sub(r'\s+', ' ', t).strip()[:500]

def tr_mem(txt, src='en', tgt='ckb'):
    try:
        r = requests.get("https://api.mymemory.translated.net/get", params={"q": txt[:350], "langpair": f"{src}|{tgt}"}, timeout=8)
        d = r.json()
        if d.get('responseStatus') == 200:
            t = d['responseData']['translatedText']
            if t and len(t) > 8 and '[MYMEMORY' not in t and t.lower() != txt.lower()[:20]:
                return t
    except:
        pass
    return None

def to_ku(txt, src='en'):
    txt = cl(txt)
    if not txt:
        return txt
    if any(x in txt.lower() for x in [' ve ', ' bir ', ' için']):
        src = 'tr'
    for s, t in [(src, 'ckb'), ('en', 'ckb'), ('tr', 'ckb'), (src, 'ku'), ('en', 'ku')]:
        r = tr_mem(txt, s, t)
        if r:
            return r
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source=src, target='ckb').translate(txt[:350])
    except:
        pass
    return txt

def fresh(e, h=24):
    try:
        if hasattr(e, 'published_parsed') and e.published_parsed:
            pub = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - pub) <= timedelta(hours=h)
        return True
    except:
        return True

def is_ai_strict(t):
    """STRICT AI filter - ONLY AI news, includes GPT-6 Astra, excludes mixed"""
    if not t:
        return False
    text = t.lower()
    # Must contain AI keywords - now includes GPT-6 Astra, Gemini 3.8, Claude Opus 5
    must_have = ["ai", "artificial intelligence", "chatgpt", "openai", "gemini", "gemini 3.8", "flash", "gpt-4", "gpt-5", "gpt-6", "astra", "sora", "dall-e", "llm", "machine learning", "deep learning", "neural network", "anthropic", "claude", "claude opus", "opus 5", "nvidia ai", "generative ai", "stable diffusion", "midjourney", "grok", "deepmind", "new star enters the chat"]
    # Exclude non-AI topics that cause mixed news
    exclude = ["weapon", "gun license", "وەزارەتی ناوخۆ", "چەک", "مۆڵەتی چەک", "وەرگرتنەوەی مۆڵەت", "turkey general", "politics", "football", "earthquake", "بوومەلەرزە"]
    # Check exclude first
    for ex in exclude:
        if ex in text:
            print(f"EXCLUDED (non-AI): {t[:80]} - contains {ex}")
            return False
    # Must have at least one AI keyword
    for kw in must_have:
        if kw in text:
            return True
    return False

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
        if s > 20 and random.random() > 0.6:
            draw.ellipse([x - s // 3, y - s // 3, x + s // 3, y + s // 3], fill=(200, 180, 255, alpha + 30))
    for _ in range(45):
        x = random.randint(0, W // 3)
        y = random.randint(0, H)
        w = random.randint(60, 180)
        draw.rectangle([x, y, x + w, y + 2], fill=(50, 75, 140, 80))
        draw.rectangle([x, y, x + 2, y + random.randint(60, 180)], fill=(50, 75, 140, 80))
        if random.random() > 0.4:
            draw.ellipse([x + w - 3, y - 3, x + w + 3, y + 3], fill=(80, 110, 200, 100))
    for _ in range(60):
        x = random.randint(0, W)
        y = random.randint(int(H * 0.65), H)
        w = random.randint(70, 220)
        draw.rectangle([x, y, x + w, y + 1], fill=(40, 65, 120, 70))
    cx_sphere = int(W * 0.82)
    cy_sphere = int(H * 0.25)
    radius = 380
    points = []
    for _ in range(280):
        theta = random.uniform(0, 2 * math.pi)
        phi = random.uniform(0, math.pi * 0.85)
        r = radius * (0.88 + random.random() * 0.22)
        x = cx_sphere + r * math.sin(phi) * math.cos(theta)
        y = cy_sphere + r * math.sin(phi) * math.sin(theta) * 0.7
        z = r * math.cos(phi)
        if z > -radius * 0.4:
            points.append((x, y, z))
    for i, (x1, y1, z1) in enumerate(points):
        for j in range(i + 1, len(points)):
            x2, y2, z2 = points[j]
            dist = math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
            if dist < 130 and z1 > -60 and z2 > -60:
                alpha = int(160 - dist * 0.7)
                if alpha > 20:
                    if dist < 60:
                        draw.line([(x1, y1), (x2, y2)], fill=(150, 120, 255, alpha), width=1)
                    else:
                        draw.line([(x1, y1), (x2, y2)], fill=(100, 140, 255, alpha), width=1)
    for x, y, z in points:
        if z > -60:
            s = 5 if z > 100 else 4
            if z > 180:
                s = 6
            draw.ellipse([x - s, y - s, x + s, y + s], fill=(240, 220, 255, 255))
            draw.ellipse([x - s * 2, y - s * 2, x + s * 2, y + s * 2], fill=(140, 120, 255, 90))
            draw.ellipse([x - s * 3.5, y - s * 3.5, x + s * 3.5, y + s * 3.5], fill=(100, 80, 200, 35))
            draw.ellipse([x - s * 5, y - s * 5, x + s * 5, y + s * 5], fill=(80, 60, 180, 15))
            if z > 120 and random.random() > 0.5:
                draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(255, 255, 255, 255))
    return img

def card(title, summary, out="card.jpg"):
    W, H = 1080, 1080
    print(f"RAQM={features.check('raqm')} HarfBuzz={features.check('harfbuzz')}")
    base = create_beautiful_background(W, H)
    print(f"Using CODE beautiful AI tech background")
    img = base.copy()
    draw = ImageDraw.Draw(img, 'RGBA')
    try:
        LAYOUT = ImageFont.Layout.RAQM
    except:
        LAYOUT = None

    def find_font(names):
        for d in ["/usr/share/fonts/truetype/noto", "/usr/share/fonts/opentype/noto", "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/google-droid-sans-fonts", "/usr/share/fonts", "./", "./fonts", "/tmp/fonts"]:
            for n in names:
                p = os.path.join(d, n)
                if os.path.exists(p):
                    return p
        return None

    def load(p, size):
        try:
            if LAYOUT:
                return ImageFont.truetype(p, size, layout_engine=LAYOUT)
            else:
                return ImageFont.truetype(p, size)
        except:
            return ImageFont.load_default()

    en_bold = find_font(["DejaVuSans-Bold.ttf", "DejaVuSans.ttf"]) or "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    en_reg = find_font(["DejaVuSans.ttf"]) or "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ku_bold_candidates = ["Vazirmatn-Bold.ttf", "Vazirmatn-Medium.ttf", "NotoNaskhArabic-Bold.ttf", "NotoKufiArabic-Bold.ttf"]
    ku_reg_candidates = ["Vazirmatn-Regular.ttf", "NotoNaskhArabic-Regular.ttf", "NotoKufiArabic-Regular.ttf"]
    ku_bold = find_font(ku_bold_candidates)
    ku_reg = find_font(ku_reg_candidates)
    print(f"Kurdish font: {ku_bold}")

    fb_en = load(en_bold, 48)
    fs_en = load(en_reg, 22)
    fb_ku = load(ku_bold, 50) if ku_bold else fb_en
    fr_ku = load(ku_reg, 30) if ku_reg else fs_en

    x, y = 45, 40
    draw.ellipse([x, y, x + 100, y + 100], fill=(255, 108, 20))
    draw.text((x+28, y+22), "AI", fill="white", font=fb_en)
    draw.text((x+130, y+18), "AI NEWS", fill="white", font=fs_en)
    draw.text((x+130, y+44), "KURDISH", fill="white", font=fs_en)

    cw, ch = 880, 680
    cx, cy = (W - cw) // 2, (H - ch) // 2 + 40
    try:
        from PIL import ImageFilter
        bg_crop = img.crop((cx, cy, cx + cw, cy + ch)).filter(ImageFilter.GaussianBlur(12))
        img.paste(bg_crop, (cx, cy))
    except:
        pass
    glass = Image.new('RGBA', (cw, ch), (18, 22, 48, 210))
    mask = Image.new('L', (cw, ch), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw, ch], radius=32, fill=255)
    glass.putalpha(mask)
    img.paste(glass, (cx, cy), glass)
    draw = ImageDraw.Draw(img, 'RGBA')
    for i in range(3):
        alpha = 220 - i * 50
        draw.rounded_rectangle([cx - i, cy - i, cx + cw + i, cy + ch + i], radius=32 + i, outline=(140 + i * 10, 95, 255, alpha), width=1)

    def reshape_kurdish(text):
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except:
            return text

    tl = title[:130].strip()
    words = tl.split()
    lines = []
    cur = ""
    for w in words:
        test = cur + " " + w if cur else w
        if len(test) > 20:
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    wr = lines[:4]

    sy = cy + 60
    for i, l in enumerate(wr):
        if not l.strip():
            continue
        l_disp = reshape_kurdish(l)
        try:
            bbox = draw.textbbox((0, 0), l_disp, font=fb_ku)
            tw = bbox[2] - bbox[0]
        except:
            tw = len(l) * 18
        x_center = W // 2 - tw // 2
        y_pos = sy + i * 78
        draw.text((x_center + 3, y_pos + 3), l_disp, fill=(0, 0, 0, 200), font=fb_ku)
        for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text((x_center + dx, y_pos + dy), l_disp, fill=(100, 70, 200, 180), font=fb_ku)
        draw.text((x_center, y_pos), l_disp, fill="white", font=fb_ku)

    if summary:
        sm = summary[:120].strip()
        words_s = sm.split()
        sw = []
        cur_s = ""
        for w in words_s:
            test = cur_s + " " + w if cur_s else w
            if len(test) > 30:
                if cur_s:
                    sw.append(cur_s)
                cur_s = w
            else:
                cur_s = test
        if cur_s:
            sw.append(cur_s)
        sw = sw[:2]
        sy2 = sy + len(wr) * 78 + 30
        for j, l in enumerate(sw):
            if not l.strip():
                continue
            l_disp = reshape_kurdish(l)
            try:
                bbox = draw.textbbox((0, 0), l_disp, font=fr_ku)
                tw = bbox[2] - bbox[0]
            except:
                tw = len(l) * 12
            draw.text((W // 2 - tw // 2 + 1, sy2 + j * 44 + 1), l_disp, fill=(0, 0, 0, 150), font=fr_ku)
            draw.text((W // 2 - tw // 2, sy2 + j * 44), l_disp, fill=(220, 225, 255), font=fr_ku)

    ly = cy + ch - 130
    draw.line([cx + 60, ly, cx + cw - 60, ly], fill=(100, 180, 255, 120), width=1)
    b = "AI News Kurdish"
    try:
        tw = draw.textbbox((0, 0), b, font=fs_en)[2]
    except:
        tw = len(b) * 8
    draw.text((W // 2 - tw // 2, ly + 35), b, fill=(130, 190, 255), font=fs_en)
    draw.text((35, H - 45), "ai.news.krd", fill=(100, 180, 255), font=fs_en)
    img.save(out, quality=95)
    return out

def fb_post(msg, link="", img_path=None):
    try:
        cap = f"{msg}\n\n🔗 {link}" if link else msg
        if img_path and os.path.exists(img_path):
            with open(img_path, 'rb') as f:
                r = requests.post(f"https://graph.facebook.com/v18.0/me/photos", data={"caption": cap, "access_token": FTOK}, files={'source': f}, timeout=30)
                d = r.json()
                if "id" in d or "post_id" in d:
                    return True
        for ep in [f"https://graph.facebook.com/v18.0/me/feed", f"https://graph.facebook.com/v18.0/{FID}/feed"]:
            r = requests.post(ep, data={"message": cap, "access_token": FTOK, "link": link}, timeout=20)
            if "id" in r.json():
                return True
        return False
    except:
        return False

async def main():
    bot = Bot(token=BOT)
    sent = set()
    try:
        with open("sent.txt", "r", encoding="utf-8") as f:
            sent = set(l.strip() for l in f if l.strip())
    except:
        pass
    coll = []
    seen = set()
    # 1. Fetch Twitter/X first - GPT-6 Astra is priority
    try:
        twitter_news = fetch_twitter_news()
        for tw in twitter_news:
            if tw['link'] not in seen and tw['hash'] not in sent:
                coll.append(tw)
                seen.add(tw['link'])
                print(f"Added tweet: {tw['title'][:60]}")
    except Exception as e:
        print(f"Twitter fetch failed: {e}")
    # 2. Fetch RSS feeds
    for name, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:8]:
                t = cl(getattr(e, 'title', ''))
                s = cl(getattr(e, 'summary', '') or getattr(e, 'description', ''))
                lk = getattr(e, 'link', '')
                if not t or not lk or lk in seen:
                    continue
                seen.add(lk)
                if not fresh(e, 24):
                    continue
                if not is_ai_strict(f"{t} {s}"):
                    continue
                h = hashlib.md5(lk.encode()).hexdigest()[:10]
                if h in sent:
                    continue
                pt = ""
                if hasattr(e, 'published_parsed') and e.published_parsed:
                    pt = datetime(*e.published_parsed[:6], tzinfo=timezone.utc).strftime("%H:%M")
                coll.append({"title": t, "summary": s, "link": lk, "source": name, "lang": 'tr' if 'tr' in url.lower() else 'en', "hash": h, "time": pt})
        except Exception as e:
            print(f"Feed error {name}: {e}")
            continue
    print(f"Found {len(coll)} AI-only news items")
    if not coll:
        print("No AI news found - all filtered as non-AI")
        return
    sel = coll[:3]
    trans = []
    for it in sel:
        try:
            kt = to_ku(it['title'], it['lang'])
            sum_raw = it['summary'][:160] if it['summary'] else ""
            if sum_raw and sum_raw[:35].lower() != it['title'][:35].lower():
                ks = to_ku(sum_raw, it['lang'])
            else:
                ks = ""
            trans.append({**it, "ku_title": kt[:140], "ku_summary": ks[:110]})
        except:
            trans.append({**it, "ku_title": it['title'][:140], "ku_summary": ""})
    for it in trans:
        cp = f"c_{it['hash']}.jpg"
        try:
            card(it['ku_title'], it['ku_summary'], cp)
        except Exception as e:
            print(f"Card error: {e}")
            import traceback
            traceback.print_exc()
            cp = None
        try:
            tg = f"🔥 <b>{it['ku_title']}</b>\n\n{it['ku_summary']}\n\n⏰ {it['time']} UTC | {it['source']}\n🔗 <a href='{it['link']}'>خوێندنەوەی تەواو</a>\n\n#ژیری_دەستکرد #AI"
            if cp and os.path.exists(cp):
                with open(cp, 'rb') as ph:
                    await bot.send_photo(chat_id=CH, photo=ph, caption=tg, parse_mode=ParseMode.HTML)
            else:
                await bot.send_message(chat_id=CH, text=tg, parse_mode=ParseMode.HTML)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"TG error {e}")
        try:
            fb = f"🔥 {it['ku_title']}\n\n{it['ku_summary']}\n\n⏰ {it['time']} UTC | {it['source']}\n\n#ژیری_دەستکرد #AI"
            fb_post(fb, it['link'], cp)
            await asyncio.sleep(2)
        except:
            pass
        try:
            if cp and os.path.exists(cp):
                os.remove(cp)
        except:
            pass
    try:
        allh = sent.union(set([x['hash'] for x in trans]))
        with open("sent.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(list(allh)[-500:]))
    except:
        pass

if __name__ == "__main__":
    asyncio.run(main())
