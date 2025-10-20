import os, time, logging, json, hashlib, re
from pathlib import Path
from time import time as _now
from scraper import fetch_trump_posts
from classify import classify_post, send_alert, is_crypto_related, is_financial_related

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

# --- Env config ---
IMPACT_THRESHOLD = float(os.environ.get("IMPACT_THRESHOLD", "0.70"))
FINANCE_ONLY = os.environ.get("FINANCE_ONLY", "1") == "1"
CRYPTO_ONLY = os.environ.get("CRYPTO_ONLY", "0") == "1"
REQUIRE_NON_NEUTRAL = os.environ.get("REQUIRE_NON_NEUTRAL", "1") == "1"
MIN_SENT_CONF = float(os.environ.get("MIN_SENT_CONF", "0.65"))
NEUTRAL_OVERRIDE_IMPACT = float(os.environ.get("NEUTRAL_OVERRIDE_IMPACT", "0.90"))
DEDUP_WINDOW_MIN = int(os.environ.get("DEDUP_WINDOW_MIN", "60"))

# --- De-dup persistence ---
SEEN_FILE = Path("seen.json")

def _normalize_text(s: str) -> str:
    s = re.sub(r"https?://\S+", "", s)        # strip URLs
    s = re.sub(r"[“”\"']", "", s)              # strip quotes
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def _hash_text(s: str) -> str:
    return hashlib.sha1(_normalize_text(s).encode("utf-8")).hexdigest()

def _load_seen():
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text())
        except Exception:
            return {}
    return {}

def _save_seen(d: dict):
    try:
        SEEN_FILE.write_text(json.dumps(d))
    except Exception:
        pass

SEEN = _load_seen()  # dict: {hash: last_ts}

def _is_fresh(h: str) -> bool:
    ts = SEEN.get(h, 0)
    return (_now() - ts) > (DEDUP_WINDOW_MIN * 60)

def main():
    logging.info(f"🍊 iTrump bot started | Impact>={IMPACT_THRESHOLD} | FinanceOnly={FINANCE_ONLY} | CryptoOnly={CRYPTO_ONLY} | NonNeutral={REQUIRE_NON_NEUTRAL}")
    while True:
        posts = fetch_trump_posts(limit=10)
        for p in posts:
            pid = p.get("id") or p.get("url") or ""
            h = _hash_text(p.get("text","") + pid)

            if not _is_fresh(h):
                logging.info("[SKIP] reason=duplicate/cooldown")
                continue

            meta = classify_post(p["text"])
            is_crypto = meta.get("is_crypto", False)
            is_finance = meta.get("is_finance", False)

            passes_scope = (not FINANCE_ONLY or is_finance) and (not CRYPTO_ONLY or is_crypto)
            passes_sent = (not REQUIRE_NON_NEUTRAL) or (meta["sentiment"] != "Neutral")
            passes_conf = (meta["sentiment"] == "Neutral") or (meta["sent_conf"] >= MIN_SENT_CONF)

            # allow rare neutral if huge impact
            if meta["sentiment"] == "Neutral" and passes_scope:
                passes_sent = (meta["impact_score"] >= NEUTRAL_OVERRIDE_IMPACT)

            passes_impact = (meta["impact_score"] >= IMPACT_THRESHOLD) or meta["must"]
            should_alert = passes_scope and passes_sent and passes_conf and passes_impact

            if should_alert:
                send_alert(p["url"], p["text"], meta)
                SEEN[h] = _now()
                _save_seen(SEEN)
            else:
                logging.info(f"[SKIP] impact={meta['impact_score']} sent={meta['sentiment']} conf={meta['sent_conf']} finance={is_finance} crypto={is_crypto} tags={meta['tags']}")
                SEEN[h] = _now()  # optional: mark seen to avoid reprocessing same post
                _save_seen(SEEN)
        time.sleep(30)

if __name__ == "__main__":
    main()
