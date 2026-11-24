"""Post new MapleStory Classic World (isMSCW == true) news to a Discord webhook.
 
Usage:
    export DISCORD_WEBHOOK="https://discord.com/api/webhooks/..."
    python maple_news_to_discord.py
 
Run it every 10-15 minutes (cron, GitHub Actions, etc.).
The first run only records existing posts and posts nothing.
"""
import json
import os
import re
import sys
import time
 
import requests
 
API = "https://g.nexonstatic.com/maplestory/cms/v1/news"
WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
STATE_FILE = os.environ.get("STATE_FILE", "seen_ids.json")
 
ARTICLE_URL = "https://www.nexon.com/maplestory/news/{category}/{id}/{slug}"
IMAGE_BASE = "https://g.nexonstatic.com"
 
HEADERS = {"User-Agent": "Mozilla/5.0 (maple-news-discord-bot)"}
 
CATEGORY_COLORS = {
    "maintenance": 0xE67E22,
    "update": 0x2ECC71,
    "sale": 0xF1C40F,
    "events": 0x9B59B6,
    "community": 0x3498DB,
    "general": 0x95A5A6,
}
 
 
def slugify(title):
    """'Scheduled Maintenance - November 24, 2026' -> 'scheduled-maintenance-november-24-2026'"""
    title = title.lower().replace("\u2019", "").replace("'", "")  # drop apostrophes
    return re.sub(r"[^a-z0-9]+", "-", title).strip("-")
 
 
def load_seen():
    try:
        with open(STATE_FILE) as f:
            return set(json.load(f))
    except FileNotFoundError:
        return None  # first run
 
 
def save_seen(ids):
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(ids), f)
 
 
def post_to_discord(article):
    embed = {
        "title": article["name"][:256],
        "url": ARTICLE_URL.format(
            category=article["category"],
            id=article["id"],
            slug=slugify(article["name"]),
        ),
        "description": (article.get("summary") or "").strip()[:2000],
        "color": CATEGORY_COLORS.get(article.get("category"), 0x95A5A6),
        "timestamp": article["liveDate"],
        "footer": {"text": f"MapleStory Classic World • {article['category']}"},
    }
    if article.get("imageThumbnail"):
        embed["image"] = {"url": IMAGE_BASE + article["imageThumbnail"]}
 
    r = requests.post(WEBHOOK, json={"embeds": [embed]}, timeout=30)
    if r.status_code == 429:  # rate limited
        time.sleep(float(r.json().get("retry_after", 2)))
        r = requests.post(WEBHOOK, json={"embeds": [embed]}, timeout=30)
    r.raise_for_status()
 
 
def main():
    if not WEBHOOK:
        sys.exit("Set the DISCORD_WEBHOOK environment variable.")
 
    resp = requests.get(API, headers=HEADERS, timeout=30)
    resp.raise_for_status()
 
    # `is True` skips items where isMSCW is false, null, or missing
    mscw = [a for a in resp.json() if a.get("isMSCW") is True]
    current_ids = {a["id"] for a in mscw}
 
    seen = load_seen()
    if seen is None:
        save_seen(current_ids)
        print(f"First run: recorded {len(current_ids)} existing posts, posted nothing.")
        return
 
    new = [a for a in mscw if a["id"] not in seen]
    new.sort(key=lambda a: a["liveDate"])  # oldest first
 
    for a in new:
        post_to_discord(a)
        seen.add(a["id"])
        save_seen(seen)  # save as we go so a crash doesn't cause reposts
        time.sleep(1)
 
    print(f"Posted {len(new)} new post(s).")
 
 
if __name__ == "__main__":
    main()
 