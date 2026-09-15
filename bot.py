import feedparser
import asyncio
import os
import re
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
import logging
from deep_translator import GoogleTranslator, MyMemoryTranslator

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@kurdish_short_news")

if not BOT_TOKEN:
    raise SystemExit(
        "❌ BOT_TOKEN دانەنراوە. پێویستە وەک ژینگە گۆڕاو (environment variable) دایبنێیت.\n"
        "نموونە: export BOT_TOKEN='یاریدەدەری_تۆکنی_تۆ'"
    )

# ===== سەرچاوە بەناوبانگ و پسپۆڕی هەواڵی AI (بەبێ گەڕانی گشتی) =====
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

def to_kurdish(text, src='en'):
    if not text or len(text) < 5: return text
    try:
        text = clean(text)
        if len(text) > 500: text = text[:500]

        # MyMemory یەکەم هەوڵ (Google لە IPـی GitHub Actions بلۆک کراوە)
        # هەر وەرگێڕێک کۆدی زمانی خۆی هەیە
        attempts = [
            ("MyMemory", MyMemoryTranslator, "en-US", ['ckb-IQ']),
            ("Google", GoogleTranslator, src, ['ckb', 'ku']),
        ]

        for engine_name, engine_cls, engine_src, targets in attempts:
            for tgt in targets:
                try:
                    tr = engine_cls(source=engine_src, target=tgt).translate(text)
                    if tr and len(tr) > 5 and tr.strip().lower() != text.strip().lower():
                        return tr
                    logging.warning(f"[{engine_name}->{tgt}] empty/unchanged result for: {text[:50]}")
                except Exception as e:
                    logging.error(f"[{engine_name}->{tgt}] failed: {type(e).__name__}: {e}")
                    continue

        logging.warning(f"All translation engines failed, falling back to original text: {text[:50]}")
        return text
    except Exception as e:
        logging.error(f"to_kurdish outer exception: {type(e).__name__}: {e}")
        return text

def is_ai(text):
    if not text: return False
    kws = ["ai", "artificial", "chatgpt", "openai", "gemini", "gpt", "llm", "machine learning", "deep learning", "neural", "yapay zeka", "midjourney", "claude", "anthropic", "sora", "dall-e", "stable diffusion", "nvidia", "robot"]
    lower = text.lower()
    return any(k in lower for k in kws)

async def main():
    bot = Bot(token=BOT_TOKEN)

    # Header - ڕۆژانە
    try:
        today_kurdish = datetime.now().strftime("%d/%m/%Y")
        header = (
            f"🌅 <b>هەواڵی ڕۆژانەی ژیری دەستکرد</b>\n"
            f"📅 {today_kurdish}\n"
            f"✅ لە سەرچاوە باوەڕپێکراوەکان\n"
            f"🔍 MIT Tech Review, TechCrunch, VentureBeat, The Verge...\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )
        await bot.send_message(chat_id=CHANNEL_ID, text=header, parse_mode=ParseMode.HTML)
        await asyncio.sleep(2)
    except Exception as e:
        logging.error(f"Header fail: {e}")

    collected = []
    seen_titles = set()

    logging.info(f"🌍 Scanning {len(MEGA_AI_FEEDS)} global sources for AI news...")

    for name, url in MEGA_AI_FEEDS.items():
        if len(collected) >= 20:
            break
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                continue

            for entry in feed.entries[:5]:
                title = clean(getattr(entry, 'title', ''))
                summary = clean(getattr(entry, 'summary', '') or getattr(entry, 'description', ''))
                link = getattr(entry, 'link', '')

                if not title or not link: continue
                if title.lower() in seen_titles: continue
                if not is_ai(f"{title} {summary}"): continue

                seen_titles.add(title.lower())

                collected.append({
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "source": name,
                    "lang": 'en'
                })

                if len(collected) >= 20:
                    break

        except Exception as e:
            logging.error(f"{name} error: {e}")
            continue

    logging.info(f"✅ Collected {len(collected)} AI news from global scan")

    if not collected:
        try:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text="🤖 ئەمڕۆ هەواڵی نوێی AI نەدۆزرایەوە - بەیانی هەوڵ دەدەمەوە!\n#ژیری_دەستکرد",
                parse_mode=ParseMode.HTML
            )
        except: pass
        return

    # هەڵبژاردنی باشترینەکان - جیاواز و نوێ
    unique = []
    for item in collected:
        if len(unique) >= 7: break
        if not any(item['title'][:20].lower() in u['title'][:20].lower() for u in unique):
            unique.append(item)

    # وەرگێڕان و ناردن
    for i, item in enumerate(unique, 1):
        try:
            ku_title = to_kurdish(item['title'], item['lang'])
            ku_sum = to_kurdish(item['summary'], item['lang']) if item['summary'] else ""

            short = ku_sum[:200] + "..." if len(ku_sum) > 200 else ku_sum
            if not short or len(short) < 20:
                short = ku_title[:180]

            flags = {
                "MIT Technology Review AI": "🎓",
                "TechCrunch AI": "🚀",
                "VentureBeat AI": "📊",
                "The Verge AI": "🔺",
                "Wired AI": "🔌",
                "AI News": "🤖",
                "MarkTechPost": "📰",
            }
            flag = flags.get(item['source'], "🌍")

            text = (
                f"<b>{i}. {ku_title}</b>\n\n"
                f"{short}\n\n"
                f"🔗 <a href='{item['link']}'>خوێندنەوەی تەواو</a> | {flag} {item['source']}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"#ژیری_دەستکرد #AI"
            )

            if len(ku_title) < 10:
                text = (
                    f"<b>{i}. {item['title']}</b>\n\n"
                    f"{item['summary'][:200]}...\n\n"
                    f"🔗 <a href='{item['link']}'>Read more</a> | {flag} {item['source']}\n"
                    f"#AI"
                )

            await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
            logging.info(f"Sent {i}/7: {ku_title[:50]}")
            await asyncio.sleep(3)

        except Exception as e:
            logging.error(f"Send {i} fail: {e}")
            await asyncio.sleep(2)

    # Footer
    try:
        footer = (
            f"✅ <b>کۆتایی هەواڵی ئەمڕۆ</b>\n"
            f"📊 {len(unique)} کورتە هەواڵ لە {len(MEGA_AI_FEEDS)} سەرچاوە\n"
            f"⏰ بەیانی 9:00 هەواڵی نوێ\n\n"
            f"🔔 چەناڵەکە Follow بکە!\n"
            f"#کوردی #تەکنەلۆژیا #ژیری_دەستکرد"
        )
        await bot.send_message(chat_id=CHANNEL_ID, text=footer, parse_mode=ParseMode.HTML)
    except:
        pass

    logging.info(f"🎉 DAILY DIGEST DONE - {len(unique)} news sent from {len(MEGA_AI_FEEDS)} sources")

if __name__ == "__main__":
    asyncio.run(main())
