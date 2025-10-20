import feedparser, datetime as dt

FEED = "https://trumpstruth.org/feed"

def fetch_trump_posts(limit=10):
    d = feedparser.parse(FEED)
    posts = []
    for e in d.entries[:limit]:
        posts.append({
            "id": getattr(e, "id", getattr(e, "link", "")),
            "url": e.link,
            "text": getattr(e, "summary", getattr(e, "title", "")),
            "created_at": dt.datetime(*e.published_parsed[:6]).isoformat() if hasattr(e, "published_parsed") else dt.datetime.utcnow().isoformat()
        })
    return posts
