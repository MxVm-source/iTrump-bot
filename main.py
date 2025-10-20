import os, time
from scraper import fetch_trump_posts
from classify import classify_post, send_alert, is_crypto_related, is_financial_related

CRYPTO_ONLY = os.environ.get("CRYPTO_ONLY", "0") == "1"          # default OFF now (finance-wide)
FINANCE_ONLY = os.environ.get("FINANCE_ONLY", "1") == "1"        # default ON -> require finance relevance
REQUIRE_NON_NEUTRAL = os.environ.get("REQUIRE_NON_NEUTRAL", "1") == "1"  # skip neutral by default
MIN_SENT_CONF = float(os.environ.get("MIN_SENT_CONF", "0.65"))   # bullish/bearish min confidence
NEUTRAL_OVERRIDE_IMPACT = float(os.environ.get("NEUTRAL_OVERRIDE_IMPACT", "0.90"))  # neutral allowed only if huge

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
