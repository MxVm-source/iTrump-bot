import os, time
from scraper import fetch_trump_posts
from classify import classify_post, send_alert

IMPACT_THRESHOLD = float(os.environ.get("IMPACT_THRESHOLD", "0.60"))
SEEN = set()

def main():
    while True:
        posts = fetch_trump_posts(limit=10)
        for p in posts:
            pid = p.get("id") or p.get("url")
            if pid in SEEN:
                continue
            meta = classify_post(p["text"])
            if meta["impact_score"] >= IMPACT_THRESHOLD or meta["must"]:
                send_alert(p["url"], p["text"], meta)
            SEEN.add(pid)
        time.sleep(30)

if __name__ == "__main__":
    main()
