import feedparser, asyncio, os
from telegram import Bot
from telegram.constants import ParseMode
import logging
BOT_TOKEN = os.getenv("BOT_TOKEN", "8921906381:AAEtOy3QDFFuwNMxHWeYSA9PsLvlqxQG24I")
CHANNEL_ID = "@kurdish_short_news"
RSS_FEEDS = ["https://www.rudaw.net/rss","https://www.kurdistan24.net/en/rss"]
logging.basicConfig(level=logging.INFO)
async def fetch_and_send():
    bot = Bot(token=BOT_TOKEN)
    sent=set()
    try:
        with open("sent.txt","r") as f: sent=set(f.read().splitlines())
    except: pass
    for feed_url in RSS_FEEDS:
        feed=feedparser.parse(feed_url)
        for entry in feed.entries[:3]:
            if entry.link in sent: continue
            text=f"📰 <b>{entry.title}</b>\n\n🔗 <a href='{entry.link}'>خوێندنەوەی تەواو</a>"
            try:
                await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode=ParseMode.HTML)
                sent.add(entry.link)
                await asyncio.sleep(2)
            except Exception as e: print(e)
    with open("sent.txt","w") as f: f.write("\n".join(list(sent)[-100:]))
if __name__=="__main__": asyncio.run(fetch_and_send())
