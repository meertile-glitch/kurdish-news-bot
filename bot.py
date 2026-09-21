import os
import re
import hashlib
import requests
import asyncio
import feedparser
from datetime import datetime
from telegram import Bot, LinkPreviewOptions
from telegram.constants import ParseMode
from groq import Groq  # Meta Llama API Client

# Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@kurdish_short_news")
FB_PAGE_ID = os.getenv("FB_PAGE_ID", "")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN", "")

# Meta Llama API Key (from Groq / Meta API provider)
META_LLAMA_API_KEY = os.getenv("META_LLAMA_API_KEY", "YOUR_META_LLAMA_API_KEY")
llama_client = Groq(api_key=META_LLAMA_API_KEY)

# TechCrunch AI RSS Feed
TECHCRUNCH_AI_FEED = "https://techcrunch.com/category/artificial-intelligence/feed/"
CHECK_INTERVAL_SECONDS = 300  # 5 minutes check loop


def clean_text(t):
    """Clean HTML tags and unnecessary whitespace."""
    if not t:
        return ""
    t = re.sub(r'<[^<]+?>', '', t)
    t = t.replace('_', ' ').replace('[', ' ').replace(']', ' ')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def translate_news_llama(title, summary):
    """
    Translates news into natural, fluent, and journalistic Central Kurdish (Sorani)
    using Meta Llama 3 AI Model.
    """
    try:
        prompt = f"""
تو وەرگێڕ و ڕۆژنامەنووسێکی شارەزای بەشی تەکنەلۆجیا و ژیریی دەستکردی (AI). 
تکایە ئەم هەواڵەی خوارەوەی TechCrunch وەربگێڕە سەر زمانی کوردیی سۆرانیی زۆر پاراو، ڕوان، و مانابەخش.

یاساکانی وەرگێڕان:
1. وەرگێڕانی وشەبەوشە مەکە؛ لە مانای سەرەکی تێبگە و بە داڕشتنی ئاسایی و ڕۆژنامەوانیی کوردی بنووسەرەوە.
2. زاراوە تەکنەلۆجییە ناسراوەکان (وەک AI, Model, Cloud, App) بە شێوازێکی سروشتی بەکاربهێنە.
3. ئەنجامەکە تەنها لە دوو دێڕدا بدەرەوە بەم شێوازەی خوارەوە:

سەردێڕ: [سەردێڕی هەواڵەکە بە کوردیی پاراو]
کورتە: [کورتەی هەواڵەکە بە کوردیی پاراو لە ۱ یان ۲ ڕستەدا]

هەواڵەکە:
سەردێڕی ئینگلیزی: {title}
کورتەی ئینگلیزی: {summary}
        """

        response = llama_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        text = response.choices[0].message.content.strip()

        ku_title, ku_summary = title, summary
        for line in text.split('\n'):
            if line.startswith("سەردێڕ:"):
                ku_title = line.replace("سەردێڕ:", "").strip()
            elif line.startswith("کورتە:"):
                ku_summary = line.replace("کورتە:", "").strip()

        return ku_title, ku_summary

    except Exception as e:
        print(f"Meta Llama Translation Error: {e}")
        return title, summary


def post_to_facebook(caption, link):
    """Post text news with full preview link to Facebook Page."""
    if not FB_PAGE_TOKEN or not FB_PAGE_ID:
        return False
    try:
        full_message = f"{caption}\n\n🔗 خوێندنەوەی تەواوی بابەتەکە:\n{link}"
        r = requests.post(
            f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/feed",
            data={
                "message": full_message,
                "link": link,  # Fetch preview image on Facebook
                "access_token": FB_PAGE_TOKEN
            },
            timeout=20
        )
        return "id" in r.json()
    except Exception as e:
        print(f"Facebook Post Error: {e}")
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
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking TechCrunch AI...")
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

            print(f"New news item found: {title}")

            # Translate news using Meta Llama API
            ku_title, ku_summary = translate_news_llama(title, summary)

            # Format Telegram Text
            tg_text = (
                f"⚡️ <b>{ku_title}</b>\n\n"
                f"{ku_summary}\n\n"
                f"📰 سەرچاوە: TechCrunch AI\n"
                f"🔗 خوێندنەوەی تەواوی بابەتەکە:\n{link}\n\n"
                f"#ژیری_دەستکرد #TechCrunch #AI"
            )

            # Send to Telegram with explicit Link Preview (Large Media/Image Enabled)
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

            # Send to Facebook
            fb_text = f"⚡️ {ku_title}\n\n{ku_summary}\n\n#ژیری_دەستکرد #AI #TechCrunch"
            post_to_facebook(fb_text, link)

            save_sent_hash(news_hash)
            print(f"Successfully published: {title}")
            await asyncio.sleep(3)

    except Exception as e:
        print(f"Error during feed processing: {e}")


async def main():
    bot = Bot(token=BOT_TOKEN)
    print("Bot running with Link Preview / Image support...")
    while True:
        await check_and_publish_news(bot)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
