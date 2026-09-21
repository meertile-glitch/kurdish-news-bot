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

# پشتیوانی کردنی LinkPreviewOptions بۆ وەشانە نوێیەکانی تێلیگرام
try:
    from telegram import LinkPreviewOptions
    HAS_LINK_PREVIEW = True
except ImportError:
    HAS_LINK_PREVIEW = False

# GitHub Secrets / Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@kurdish_short_news")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ڕێکخستنی Gemini API
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# سەرچاوەی هەواڵەکە (TechCrunch AI)
TECHCRUNCH_AI_FEED = "https://techcrunch.com/category/artificial-intelligence/feed/"


def clean_text(t):
    """پاککردنەوەی دەق لە تەگی ناپێویست."""
    if not t:
        return ""
    t = re.sub(r'<[^<]+?>', '', t)
    t = t.replace('_', ' ').replace('[', ' ').replace(']', ' ')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def news_editor_agent(title, summary, link):
    """
    ئەمە ئاجێنتەکەیە: هەڵسەنگاندن بۆ هەواڵەکە دەکات، بڕیار دەدات بڵاوی بکاتەوە یان نا،
    وە دەقە ئینگلیزییەکە وەردەگێڕێتە سەر زمانی کوردیی سۆرانیی زۆر پاراو و ڕۆژنامەوانی.
    """
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY missing, bypassing AI agent processing.")
        return {
            "should_publish": True,
            "reason": "No API key provided, default publish.",
            "telegram_caption": f"⚡️ <b>{title}</b>\n\n{summary}",
            "facebook_caption": f"⚡️ {title}\n\n{summary}"
        }

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""
تو ئاجێنتێکی سەرنووسەری ژیر و شارەزای بەشی تەکنەلۆجیای. 
ئەرکت هەڵسەنگاندن و وەرگێڕانی ئەم هەواڵەی خوارەوەیە بۆ زمانی کوردیی سۆرانیی زۆر پاراو، ڕوان، و ڕۆژنامەوانی:

سەردێڕی ئینگلیزی: {title}
کورتەی ئینگلیزی: {summary}
لینک: {link}

مەرج و یاسا تووندەکان:
1. بە هیچ شێوەیەک زمانی ئینگلیزی بەکارنەهێنیت لە بەشی telegram_caption و facebook_caption، هەموو دەقەکان پێویستە بە زمانی کوردیی سۆرانیی پاراو بن.
2. وەرگێڕانی وشەبەوشە مەکە؛ لە مانای دەقە ئینگلیزییەکە تێبگە و بە داڕشتنی ڕۆژنامەوانیی کوردی سەرتاپای بنووسەرەوە.
3. زاراوە تەکنەلۆجییە ناسراوەکان (وەک AI, LLM, OpenAI, Cloud) وەکو خۆیان بە پیت یان بە کوردی بنووسە.
4. ئەگەر هەواڵەکە گرنگییەکی ئەوتۆی نەبوو یان بابەتێکی زۆر لاوەکی بوو، should_publish بکە بە false.

تکایە تەنها بە شێوازی JSON بەم شێوازە وەڵام بدەرەوە:
{{
  "should_publish": true,
  "reason": "هۆکاری بڕیارەکەت بە کوردی لە یەک ڕستەدا",
  "telegram_caption": "⚡️ <b>[سەردێڕی هەواڵ بە کوردیی پاراو]</b>\\n\\n[کورتەی هەواڵ لە ۱ یان ۲ ڕستەدا بە کوردیی سۆرانیی زۆر ڕوان]",
  "facebook_caption": "⚡️ [سەردێڕی هەواڵ بە کوردی]\\n\\n[ڕوونکرنەوەی تێروتەسەلی هەواڵەکە بە زمانی کوردیی سۆرانیی زۆر پاراو]"
}}
"""

        response = model.generate_content(
            prompt, 
            generation_config={"response_mime_type": "application/json"}
        )
        
        decision = json.loads(response.text)
        return decision

    except Exception as e:
        print(f"❌ Agent Evaluation Error: {e}")
        return {
            "should_publish": True,
            "reason": "Error during AI response, defaulting to publish.",
            "telegram_caption": f"⚡️ <b>{title}</b>\n\n{summary}",
            "facebook_caption": f"⚡️ {title}\n\n{summary}"
        }


def post_to_facebook(caption, link):
    """بڵاوکردنەوە لەسەر پەڕەی فەیسبووک بە لەگەڵ بەستەر بۆ پێشاندانی وێنە."""
    if not FB_PAGE_TOKEN or not FB_PAGE_ID:
        print("⚠️ Facebook credentials missing, skipping Facebook post.")
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
        res = r.json()
        if "id" in res:
            print(f"✅ Published on Facebook ID: {res['id']}")
            return True
        else:
            print(f"❌ Facebook API Error: {res}")
            return False
    except Exception as e:
        print(f"❌ Facebook Exception: {e}")
        return False


def get_sent_hashes():
    """خوێندنەوەی لیستی ئەو هەواڵانەی پێشتر نێردراون."""
    if not os.path.exists("sent.txt"):
        return set()
    with open("sent.txt", "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_sent_hash(news_hash):
    """تۆمارکردنی ئایدی هەواڵە نێردراوەکان."""
    hashes = get_sent_hashes()
    hashes.add(news_hash)
    with open("sent.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(list(hashes)[-300:]))


async def check_and_publish_news(bot):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Agent checking TechCrunch AI...")
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

            print(f"\n🧠 Agent is evaluating news item: {title}")

            # 1. بڕیاردانی ئاجێنت لەسەر شیاوی و وەرگێڕانی هەواڵەکە
            decision = news_editor_agent(title, summary, link)

            # 2. جێبەجێکردنی بڕیارەکە
            if not decision.get("should_publish", False):
                print(f"🛑 Agent Rejected this news: {decision.get('reason')}")
                save_sent_hash(news_hash)
                continue

            print(f"✅ Agent Approved: {decision.get('reason')}")

            # ئامادەکردنی دەقی تێلیگرام
            tg_text = (
                f"{decision.get('telegram_caption')}\n\n"
                f"📰 سەرچاوە: TechCrunch AI\n"
                f"🔗 خوێندنەوەی تەواوی بابەتەکە:\n{link}\n\n"
                f"#ژیری_دەستکرد #TechCrunch #AI"
            )

            # ناردن بۆ تێلیگرام
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

            # ناردن بۆ فەیسبووک
            fb_text = f"{decision.get('facebook_caption')}\n\n#ژیری_دەستکرد #AI #TechCrunch"
            post_to_facebook(fb_text, link)

            save_sent_hash(news_hash)
            print(f"🚀 Successfully published by Agent: {title}")
            await asyncio.sleep(2)

    except Exception as e:
        print(f"❌ Error during processing: {e}")


async def main():
    bot = Bot(token=BOT_TOKEN)
    await check_and_publish_news(bot)


if __name__ == "__main__":
    asyncio.run(main())
