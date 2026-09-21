import os
import re
import json
import hashlib
import requests
import asyncio
import feedparser
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
import google.generativeai as genai

try:
    from telegram import LinkPreviewOptions
    HAS_LINK_PREVIEW = True
except ImportError:
    HAS_LINK_PREVIEW = False

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@kurdish_short_news")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

TECHCRUNCH_AI_FEED = "https://techcrunch.com/category/artificial-intelligence/feed/"


def clean_text(t):
    if not t:
        return ""
    t = re.sub(r'<[^<]+?>', '', t)
    t = t.replace('_', ' ').replace('[', ' ').replace(']', ' ')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def news_editor_agent(title, summary, link):
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY is missing!")
        return {"should_publish": False, "reason": "No API Key"}

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
تو ئاجێنتێکی سەرنووسەری ژیر و شارەزای بەشی تەکنەلۆجیای. 
ئەرکت هەڵسەنگاندن و وەرگێڕانی ئەم هەواڵەی خوارەوەیە بۆ زمانی کوردیی سۆرانیی زۆر پاراو، ڕوان، و ڕۆژنامەوانی:

سەردێڕی ئینگلیزی: {title}
کورتەی ئینگلیزی: {summary}

یاسا ڕەهاکان:
1. بە هیچ شێوەیەک دەقی ئینگلیزی مەنێرەوە. سەرتاپای دەقەکە پێویستە کوردیی سۆرانیی زۆر پاراو بێت.
2. ئەگەر هەواڵەکە ڕیکلام بوو (وەک فرۆشتنی بلیت، داشکاندن، کۆنفرانس)، پێویستە should_publish بکەیت بە false.
3. زاراوە تەکنەلۆجییە ناسراوەکان (وەک AI, OpenAI, Cloud) پارێزراو بن.

تەنها بە JSON وەڵام بدەرەوە:
{{
  "should_publish": true,
  "reason": "هۆکار بە کوردی",
  "telegram_caption": "⚡️ <b>[سەردێڕ بە کوردی]</b>\\n\\n[کورتەی هەواڵ بە کوردیی سۆرانی]",
  "facebook_caption": "⚡️ [سەردێڕ بە کوردی]\\n\\n[شیکاری کوردی]"
}}
"""

        response = model.generate_content(
            prompt, 
            generation_config={"response_mime_type": "application/json"}
        )
        
        decision = json.loads(response.text)
        return decision

    except Exception as e:
        print(f"❌ Agent Error: {e}")
        return {"should_publish": False, "reason": "AI Error"}


def post_to_facebook(caption, link):
    if not FB_PAGE_TOKEN or not FB_PAGE_ID:
        return False
    try:
        full_message = f"{caption}\n\n🔗 خوێندنەوەی تەواوی بابەتەکە:\n{link}"
        r = requests.post(
            f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/feed",
            data={
                "message": full_message,
                "link": link,
                "access_token": FB_PAGE_TOKEN
            },
            timeout=20
        )
        return "id" in r.json()
    except Exception as e:
        print(f"❌ Facebook Exception: {e}")
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


async def check_and_publish_news(bot):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Agent checking news...")
    try:
        feed = feedparser.parse(TECHCRUNCH_AI_FEED)
        sent_hashes = get_sent_hashes()

        for entry in reversed(feed.entries[:5]):
            title = clean_text(getattr(entry, 'title', ''))
            link = getattr(entry, 'link', '')
            summary = clean_text(getattr(entry, 'summary', ''))

            if not title or not link:
                continue

            news_hash = hashlib.md5(link.encode()).hexdigest()[:10]
            if news_hash in sent_hashes:
                continue

            print(f"\n🧠 Evaluating: {title}")
            decision = news_editor_agent(title, summary, link)

            if not decision.get("should_publish", False):
                print(f"🛑 Rejected: {decision.get('reason')}")
                save_sent_hash(news_hash)
                continue

            print(f"✅ Approved: {decision.get('reason')}")

            tg_text = (
                f"{decision.get('telegram_caption')}\n\n"
                f"📰 سەرچاوە: TechCrunch AI\n"
                f"🔗 خوێندنەوەی تەواوی بابەتەکە:\n{link}\n\n"
                f"#ژیری_دەستکرد #TechCrunch #AI"
            )

            if HAS_LINK_PREVIEW:
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=tg_text,
                    parse_mode=ParseMode.HTML,
                    link_preview_options=LinkPreviewOptions(
                        is_disabled=False,
                        prefer_large_media=True,
                        show_above_text=False
                    )
                )
            else:
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=tg_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False
                )

            fb_text = f"{decision.get('facebook_caption')}\n\n#ژیری_دەستکرد #AI #TechCrunch"
            post_to_facebook(fb_text, link)

            save_sent_hash(news_hash)
            print(f"🚀 Published: {title}")
            await asyncio.sleep(2)

    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    bot = Bot(token=BOT_TOKEN)
    await check_and_publish_news(bot)


if __name__ == "__main__":
    asyncio.run(main())
