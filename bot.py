import os
import re
import hashlib
import requests
import asyncio
import feedparser
import math
import random
from datetime import datetime, timezone, timedelta
from telegram import Bot
from telegram.constants import ParseMode
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import arabic_reshaper
from bidi.algorithm import get_display
from deep_translator import GoogleTranslator

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
    return t[:600]

def contains_kurdish(text):
    return any('\u0600' <= c <= '\u06FF' for c in text)

# === Smart Template - Brand & Person Detection ===
BRANDS = {
    "meta": {"name": "Meta", "display": "مێتا", "color": (0, 100, 255), "bg": (6, 95, 212), "initial": "M", "keywords": ["meta", "facebook", "instagram", "zuckerberg"]},
    "openai": {"name": "OpenAI", "display": "ئۆپن ئەی ئای", "color": (16, 163, 127), "bg": (10, 10, 10), "initial": "O", "keywords": ["openai", "chatgpt", "gpt-4", "gpt-5", "sam altman", "sora", "dall-e"]},
    "google": {"name": "Google", "display": "گووگڵ", "color": (66, 133, 244), "bg": (255, 255, 255), "initial": "G", "keywords": ["google", "gemini", "deepmind", "bard", "sundar pichai"]},
    "anthropic": {"name": "Anthropic", "display": "ئانترۆپیک", "color": (210, 105, 30), "bg": (255, 248, 230), "initial": "A", "keywords": ["anthropic", "claude", "dario amodei"]},
    "microsoft": {"name": "Microsoft", "display": "مایکرۆسۆفت", "color": (0, 164, 239), "bg": (0, 120, 212), "initial": "M", "keywords": ["microsoft", "copilot", "satya nadella"]},
    "nvidia": {"name": "NVIDIA", "display": "ئێنڤیدیا", "color": (118, 185, 0), "bg": (18, 18, 18), "initial": "N", "keywords": ["nvidia", "jensen huang", "geforce"]},
    "apple": {"name": "Apple", "display": "ئەپڵ", "color": (0, 0, 0), "bg": (245, 245, 247), "initial": "A", "keywords": ["apple", "tim cook", "iphone", "siri"]},
    "xai": {"name": "xAI", "display": "ئێکس ئەی ئای", "color": (0, 0, 0), "bg": (0, 0, 0), "initial": "X", "keywords": ["xai", "elon musk", "grok", "twitter", " x "]},
    "amazon": {"name": "Amazon", "display": "ئەمازۆن", "color": (255, 153, 0), "bg": (35, 47, 62), "initial": "A", "keywords": ["amazon", "aws", "bedrock"]},
}

PERSONS = {
    "mark zuckerberg": {"name": "Mark Zuckerberg", "ku_name": "مارک زاکەربێرگ", "initials": "MZ", "company": "meta", "role": "CEO ی مێتا"},
    "zuckerberg": {"name": "Mark Zuckerberg", "ku_name": "مارک زاکەربێرگ", "initials": "MZ", "company": "meta", "role": "CEO ی مێتا"},
    "sam altman": {"name": "Sam Altman", "ku_name": "سام ئاڵتمان", "initials": "SA", "company": "openai", "role": "CEO ی ئۆپن ئەی ئای"},
    "sama": {"name": "Sam Altman", "ku_name": "سام ئاڵتمان", "initials": "SA", "company": "openai", "role": "CEO ی ئۆپن ئەی ئای"},
    "sundar pichai": {"name": "Sundar Pichai", "ku_name": "سوندار پیچای", "initials": "SP", "company": "google", "role": "CEO ی گووگڵ"},
    "dario amodei": {"name": "Dario Amodei", "ku_name": "داریۆ ئەمۆدی", "initials": "DA", "company": "anthropic", "role": "CEO ی ئانترۆپیک"},
    "satya nadella": {"name": "Satya Nadella", "ku_name": "ساتيا نادێلا", "initials": "SN", "company": "microsoft", "role": "CEO ی مایکرۆسۆفت"},
    "jensen huang": {"name": "Jensen Huang", "ku_name": "جێنسن هوانگ", "initials": "JH", "company": "nvidia", "role": "CEO ی ئێنڤیدیا"},
    "elon musk": {"name": "Elon Musk", "ku_name": "ئیلۆن مەسک", "initials": "EM", "company": "xai", "role": "CEO ی ئێکس ئەی ئای"},
    "tim cook": {"name": "Tim Cook", "ku_name": "تیم کووک", "initials": "TC", "company": "apple", "role": "CEO ی ئەپڵ"},
}

def detect_brand_and_person(title, summary):
    text = f"{title} {summary}".lower()
    detected_brand = None
    detected_person = None
    max_score = 0
    for brand_key, brand_info in BRANDS.items():
        score = 0
        for kw in brand_info["keywords"]:
            if kw in text:
                score += len(kw) * 2 if kw == brand_key else len(kw)
        if score > max_score and score > 2:
            max_score = score
            detected_brand = brand_key
    for person_key, person_info in PERSONS.items():
        if person_key in text:
            detected_person = person_key
            if person_info["company"]:
                detected_brand = person_info["company"]
            break
    print(f" 🔍 Detected: Brand={detected_brand}, Person={detected_person} from: {title[:60]}")
    return detected_brand, detected_person

def rewrite_to_sorani_journalistic(en_title, en_summary, ku_translated_title, ku_translated_summary):
    title = ku_translated_title
    summary = ku_translated_summary
    sorani_dict = {
        "artificial intelligence": "ژیری دەستکرد",
        "machine learning": "فێربوونی ئامێر",
        "deep learning": "فێربوونی قووڵ",
        "world model": "مۆدێلی جیهانی",
        "world models": "مۆدێلە جیهانییەکان",
        "company": "کۆمپانیا",
        "companies": "کۆمپانیاکان",
        "secret": "نهێنی",
        "secrets": "نهێنییەکان",
        "technology": "تەکنەلۆژیا",
        "model": "مۆدێل",
        "models": "مۆدێلەکان",
        "data": "داتا",
        "platform": "پلاتفۆرم",
        "release": "بڵاوکردنەوە",
        "released": "بڵاوکراوە",
        "announced": "ڕاگەیەندرا",
        "new": "نوێ",
        "powerful": "بەهێز",
    }
    return title, summary

def translate_to_kurdish(text):
    if not text:
        return ""
    try:
        from deep_translator import GoogleTranslator
        import time
        time.sleep(1)
        translated = GoogleTranslator(source='en', target='ckb').translate(text[:400])
        return clean_text(translated)
    except:
        return text

def reshape_kurdish_text(text):
    if not text:
        return text
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except:
        return text

def find_font(font_names):
    dirs = [
        "/mnt/data",
        "./fonts", "./",
        "/tmp/fonts",
        "/tmp/fonts/Vazirmatn",
        "/usr/share/fonts/truetype/noto",
        "/usr/share/fonts/opentype/noto",
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts",
        "/usr/share/fonts/google-droid-sans-fonts",
    ]
    for d in dirs:
        if not os.path.exists(d):
            continue
        for n in font_names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return p
            try:
                for f in os.listdir(d):
                    if f.lower() == n.lower():
                        return os.path.join(d, f)
            except:
                pass
    return None

def get_kurdish_fonts():
    bold_candidates = [
        "Vazirmatn-Black.ttf", "Vazirmatn-ExtraBold.ttf", "Vazirmatn-Bold.ttf",
        "DroidKufi-Bold.ttf",
        "NotoNaskhArabic-Bold.ttf", "NotoKufiArabic-Bold.ttf",
        "DejaVuSans-Bold.ttf"
    ]
    medium_candidates = [
        "Vazirmatn-Medium.ttf", "Vazirmatn-Regular.ttf",
        "DroidKufi-Regular.ttf",
        "NotoNaskhArabic-Regular.ttf", "NotoKufiArabic-Regular.ttf",
        "DejaVuSans.ttf"
    ]
    regular_candidates = [
        "Vazirmatn-Regular.ttf", "Vazirmatn-Light.ttf",
        "DroidKufi-Regular.ttf",
        "NotoNaskhArabic-Regular.ttf",
        "DejaVuSans.ttf"
    ]
    bold = find_font(bold_candidates)
    medium = find_font(medium_candidates) or bold
    regular = find_font(regular_candidates) or medium
    return bold, medium, regular

def get_news_image_url(entry):
    try:
        if hasattr(entry, 'media_content'):
            for media in entry.media_content:
                if 'url' in media:
                    url = media['url']
                    if url and any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                        return url
        if hasattr(entry, 'media_thumbnail'):
            for thumb in entry.media_thumbnail:
                if 'url' in thumb:
                    return thumb['url']
        if hasattr(entry, 'enclosures'):
            for enc in entry.enclosures:
                if hasattr(enc, 'href') and enc.href:
                    if any(ext in enc.href.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                        return enc.href
        summary = getattr(entry, 'summary', '') + getattr(entry, 'description', '')
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', summary, re.IGNORECASE)
        if img_match:
            return img_match.group(1)
        if hasattr(entry, 'links'):
            for link in entry.links:
                if 'image' in link.get('type', '') and 'href' in link:
                    return link['href']
    except Exception as e:
        print(f" Image extraction error: {e}")
    return None

def download_news_image(image_url, save_path="temp_news.jpg"):
    try:
        if not image_url:
            return None
        print(f" 📸 Downloading news image: {image_url[:80]}...")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(image_url, headers=headers, timeout=15, stream=True)
        if r.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            try:
                with Image.open(save_path) as im:
                    im.verify()
                print(f" ✅ Image downloaded: {save_path}")
                return save_path
            except:
                try:
                    with Image.open(save_path) as im:
                        im.load()
                        return save_path
                except Exception as e:
                    print(f" Image invalid: {e}")
                    return None
    except Exception as e:
        print(f" Download error: {e}")
    return None

def create_news_card(title, summary, out_path="card.jpg", en_title="", en_summary="", image_path=None):
    """
    SIMPLE POSTER - تەنها هەواڵ + وێنەی هەواڵەکە
    - وێنەی هەواڵ لە سەرەوە (62%)
    - ناونیشان و کورتە لە خوارەوە (38%)
    """
    W, H = 1080, 1350
    ku_bold_path, ku_med_path, ku_reg_path = get_kurdish_fonts()
    en_bold_path = find_font(["DejaVuSans-Bold.ttf", "DejaVuSans.ttf"])
    en_reg_path = find_font(["DejaVuSans.ttf"]) or en_bold_path

    try:
        font_title = ImageFont.truetype(ku_bold_path, 58) if ku_bold_path else ImageFont.load_default()
        font_title_en = ImageFont.truetype(en_bold_path, 44) if en_bold_path else ImageFont.load_default()
        font_summary = ImageFont.truetype(ku_med_path, 28) if ku_med_path else ImageFont.load_default()
        font_summary_en = ImageFont.truetype(en_reg_path, 22) if en_reg_path else ImageFont.load_default()
        font_small = ImageFont.truetype(en_reg_path, 18) if en_reg_path else ImageFont.load_default()
    except:
        font_title = ImageFont.load_default()
        font_title_en = font_title
        font_summary = font_title
        font_summary_en = font_title
        font_small = font_title

    img = Image.new('RGB', (W, H), (12, 16, 30))
    draw = ImageDraw.Draw(img, 'RGBA')
    image_height = int(H * 0.62)
    image_area = None

    if image_path and os.path.exists(image_path):
        try:
            news_img = Image.open(image_path).convert('RGB')
            img_w, img_h = news_img.size
            target_w, target_h = W, image_height
            scale = max(target_w / img_w, target_h / img_h)
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
            news_img = news_img.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - target_w) // 2
            top = (new_h - target_h) // 2
            news_img = news_img.crop((left, top, left + target_w, top + target_h))
            img.paste(news_img, (0, 0))
            image_area = news_img
            print(f" ✅ News image placed: {image_path}")
        except Exception as e:
            print(f" Image placement error: {e}")
            image_area = None

    if image_area is None:
        for y in range(image_height):
            ratio = y / image_height
            r = int(15 + ratio * 25)
            g = int(20 + ratio * 30)
            b = int(40 + ratio * 40)
            draw.line([(0, y), (W, y)], fill=(r, g, b))
        for _ in range(60):
            x = random.randint(0, W)
            y = random.randint(0, image_height)
            s = random.randint(2, 8)
            alpha = random.randint(10, 30)
            draw.ellipse([x-s, y-s, x+s, y+s], fill=(80, 100, 180, alpha))

    for y in range(image_height - 120, image_height):
        alpha = int(((y - (image_height - 120)) / 120) * 200)
        draw.line([(0, y), (W, y)], fill=(12, 16, 30, alpha))

    text_y_start = image_height - 60
    draw.rectangle([0, text_y_start, W, H], fill=(12, 16, 30, 255))
    draw.line([(40, text_y_start), (W-40, text_y_start)], fill=(255, 255, 255, 30), width=1)

    title_raw = clean_text(title)[:150]
    title_raw = title_raw.replace("$", " $ ").replace(" ", " ").strip()
    if any(x in title_raw for x in ["قوباد", "تاڵەبانی", "بەرھەم ساڵح", "پەرلەمان", "نرخی ئەم مۆبایلە"]):
        title_raw = "هەواڵی نوێی ژیری دەستکرد"

    words = title_raw.split()
    lines = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        max_len = 20 if contains_kurdish(test) else 28
        if len(test) > max_len:
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)

    if len(lines) > 1 and len(lines[-1]) < 8 and len(lines[-2].split()) > 1:
        prev_words = lines[-2].split()
        if len(prev_words) > 1:
            lines[-2] = " ".join(prev_words[:-1])
            lines[-1] = prev_words[-1] + " " + lines[-1]

    sy = text_y_start + 45
    line_height = 78
    for i, line in enumerate(lines[:3]):
        is_english = len(re.findall(r'[a-zA-Z]', line)) > len(re.findall(r'[\u0600-\u06FF]', line)) and len(re.findall(r'[a-zA-Z]', line)) > 3
        if is_english:
            l_disp = line
            font_use = font_title_en
        else:
            l_disp = reshape_kurdish_text(line)
            font_use = font_title
        try:
            bbox = draw.textbbox((0, 0), l_disp, font=font_use)
            tw = bbox[2] - bbox[0]
        except:
            tw = len(line) * 16
        x_center = W // 2 - tw // 2
        y_pos = sy + i * line_height
        draw.text((x_center+3, y_pos+3), l_disp, fill=(0,0,0,180), font=font_use)
        draw.text((x_center+1, y_pos+1), l_disp, fill=(0,0,0,100), font=font_use)
        draw.text((x_center, y_pos), l_disp, fill="white", font=font_use)

    if summary:
        summary = clean_text(summary)[:180]
        if any(x in summary for x in ["قوباد", "بەرھەم", "پەرلەمان", "نرخی ئەم مۆبایلە", "فاکتەر"]):
            summary = ""
        if summary:
            words_s = summary.split()
            sw, cur_s = [], ""
            for w in words_s:
                test = f"{cur_s} {w}".strip()
                if len(test) > 42:
                    if cur_s:
                        sw.append(cur_s)
                    cur_s = w
                else:
                    cur_s = test
            if cur_s:
                sw.append(cur_s)
            sy2 = sy + len(lines[:3]) * line_height + 25
            for j, line in enumerate(sw[:2]):
                is_eng = len(re.findall(r'[a-zA-Z]', line)) > len(re.findall(r'[\u0600-\u06FF]', line)) and len(re.findall(r'[a-zA-Z]', line)) > 4
                if is_eng:
                    l_disp = line
                    f_use = font_summary_en
                else:
                    l_disp = reshape_kurdish_text(line)
                    f_use = font_summary
                try:
                    bbox = draw.textbbox((0, 0), l_disp, font=f_use)
                    tw = bbox[2] - bbox[0]
                except:
                    tw = len(line) * 10
                x_c = W // 2 - tw // 2
                y_s = sy2 + j * 40
                draw.text((x_c+1, y_s+1), l_disp, fill=(0,0,0,100), font=f_use)
                draw.text((x_c, y_s), l_disp, fill=(200, 210, 230), font=f_use)

    try:
        footer_y = H - 55
        draw.text((40, footer_y), "TechCrunch AI", fill=(120, 140, 180, 180), font=font_small)
        draw.text((W-160, footer_y), "ai.news.krd", fill=(100, 150, 210, 160), font=font_small)
    except:
        pass

    img.save(out_path, quality=95)
    print(f" ✅ Simple poster created: {out_path} - News + Image only")
    return out_path

def post_to_facebook(caption, link, img_path):
    if not FB_PAGE_ID or not FB_PAGE_TOKEN:
        print(" FB skipped - no token")
        return False
    cap = f"{caption}\n\n{link}"
    if len(cap) > 900:
        cap = cap[:900]
    for ver in ["v21.0", "v20.0", "v19.0", "v18.0"]:
        try:
            if img_path and os.path.exists(img_path):
                url = f"https://graph.facebook.com/{ver}/{FB_PAGE_ID}/photos"
                with open(img_path, 'rb') as f:
                    r = requests.post(url, data={"caption": cap, "access_token": FB_PAGE_TOKEN}, files={'source': f}, timeout=40)
                    d = r.json()
                    print(f" Response: {d}")
                    if "id" in d or "post_id" in d:
                        print(f"✅ FB photo posted: {d}")
                        return True
                    if "error" in d:
                        print(f" ❌ {d['error'].get('code')}: {d['error'].get('message')}")
        except Exception as e:
            print(f" Exception: {e}")
            continue
    for ver in ["v21.0", "v20.0", "v18.0"]:
        try:
            url = f"https://graph.facebook.com/{ver}/{FB_PAGE_ID}/feed"
            r = requests.post(url, data={"message": cap, "link": link, "access_token": FB_PAGE_TOKEN}, timeout=20)
            d = r.json()
            print(f" Feed response: {d}")
            if "id" in d:
                print(f"✅ FB feed posted: {d['id']}")
                return True
        except Exception as e:
            print(f" Feed exception: {e}")
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
                print(f" Skipping old: {title[:60]}")
                continue
            if any(x in title for x in ["قوباد", "بەرھەم ساڵح", "پەرلەمان"]):
                print(f" Skipping hallucinated original: {title[:60]}")
                continue
            news_hash = hashlib.md5(link.encode()).hexdigest()[:10]
            if news_hash in sent_hashes:
                continue
            print(f" New: {title}")

            ku_title_raw = translate_to_kurdish(title)
            ku_summary_raw = translate_to_kurdish(summary[:250]) if summary else ""
            ku_title, ku_summary = rewrite_to_sorani_journalistic(title, summary, ku_title_raw, ku_summary_raw)

            if any(x in ku_title for x in ["قوباد", "بەرھەم ساڵح", "پەرلەمان", "نرخی ئەم مۆبایلە", "فاکتەر"]):
                print(f" ⚠️ Final title still has hallucination, using English: {ku_title[:60]}")
                ku_title = title[:140]
                ku_summary = summary[:200]

            news_image_url = get_news_image_url(entry)
            temp_image_path = None
            if news_image_url:
                temp_image_path = f"temp_{news_hash}.jpg"
                temp_image_path = download_news_image(news_image_url, temp_image_path)

            card_path = f"card_{news_hash}.jpg"
            try:
                create_news_card(ku_title, ku_summary, card_path, en_title=title, en_summary=summary, image_path=temp_image_path)
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
                print(" ✅ Telegram posted")
            except Exception as e:
                print(f" TG error: {e}")

            fb_text = f"⚡ {ku_title}\n\n{ku_summary}\n\n#ژیری_دەستکرد #AI #TechCrunch"
            try:
                if post_to_facebook(fb_text, link, card_path):
                    print(" ✅ Facebook posted")
                else:
                    print(" ⚠️ Facebook failed")
            except Exception as e:
                print(f" FB exception: {e}")

            if card_path and os.path.exists(card_path):
                try:
                    os.remove(card_path)
                except:
                    pass
            if temp_image_path and os.path.exists(temp_image_path):
                try:
                    os.remove(temp_image_path)
                except:
                    pass

            save_sent_hash(news_hash)
            new_count += 1
            print(f" Published: {title[:50]}")
            await asyncio.sleep(3)

        if new_count == 0:
            print(" No new AI news")

    except Exception as e:
        print(f"Error during feed processing: {e}")
        import traceback
        traceback.print_exc()

async def main():
    bot = Bot(token=BOT_TOKEN)
    print(f"Bot started monitoring TechCrunch AI -> {CHANNEL_ID}")
    print(f"FB_PAGE_ID: {'SET' if FB_PAGE_ID else 'NOT SET'} | FB_PAGE_TOKEN: {'SET (len '+str(len(FB_PAGE_TOKEN))+')' if FB_PAGE_TOKEN else 'NOT SET'}")
    if not FB_PAGE_ID or not FB_PAGE_TOKEN:
        print("⚠️ Facebook posting disabled")
    if os.getenv("GITHUB_ACTIONS") == "true":
        print("Running in GitHub Actions - single check mode")
        await check_and_publish_news(bot)
        return
    while True:
        await check_and_publish_news(bot)
        print(f"Sleeping {CHECK_INTERVAL_SECONDS}s...")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    asyncio.run(main())
