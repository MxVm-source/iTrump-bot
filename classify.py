import os
import re
import asyncio
import logging
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from telegram import Bot
from telegram.error import ChatMigrated, Forbidden, TelegramError

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
bot = Bot(token=TELEGRAM_TOKEN)

analyzer = SentimentIntensityAnalyzer()

# --- Relevance detectors ---
CRYPTO_TERMS = [
    r"\bbitcoin\b", r"\bbtc\b", r"\bethereum\b", r"\beth\b",
    r"\bcrypto\b", r"\bstablecoin\b", r"\betf\b", r"\bspot etf\b",
    r"\bsec\b", r"\bcftc\b", r"\bcoinbase\b", r"\bbinance\b",
    r"\bminer(s)?\b", r"\bhalving\b", r"\bhashrate\b"
]

FINANCE_TERMS = [
    # Monetary policy & inflation
    r"\bfed(?:eral reserve)?\b", r"\bfomc\b", r"\bpowell\b", r"\brate(?:s| hike| cut)\b",
    r"\binflation\b", r"\bcpi\b", r"\bppi\b",
    # Fiscal & taxes
    r"\btax(?:es|ation)?\b", r"\btax (?:cut|hike|increase|reform)\b", r"\bstimulus\b", r"\bdeficit\b",
    r"\bshutdown\b", r"\bbudget\b", r"\bdebt ceiling\b",
    # Trade & regulation
    r"\btariff(s)?\b", r"\bsanction(s)?\b", r"\bimport\b", r"\bexport\b", r"\bquota\b", r"\bban\b", r"\bwto\b",
    # Energy / oil
    r"\bopec\b", r"\bspr\b", r"\boil\b", r"\bbarrel\b", r"\bsaudi\b", r"\bproduction cut\b",
    # Big tech / markets
    r"\bsec\b", r"\bcftc\b", r"\bftc\b", r"\bdoj\b", r"\bantitrust\b",
    r"\bapple\b|\bamazon\b|\bgoogle\b|\balphabet\b|\bmicrosoft\b|\bnvidia\b|\btesla\b",
    # Geopolitics with market impact
    r"\bchina\b", r"\brussia\b", r"\biran\b", r"\bisrael\b", r"\bukraine\b", r"\btaiwan\b",
    r"\bwar\b", r"\bescalation\b", r"\bmissile\b", r"\bconflict\b", r"\bstrike\b"
]

def is_crypto_related(text: str, tags: list[str]) -> bool:
    if any(tag.lower().startswith("crypto") for tag in tags):
        return True
    t = text.lower()
    return any(re.search(p, t, flags=re.I) for p in CRYPTO_TERMS)

def is_financial_related(text: str, tags: list[str]) -> bool:
    if any(tag in tags for tag in ["Fed", "Geopolitics", "Energy", "Trade", "Fiscal", "Crypto/Reg", "Big Tech"]):
        return True
    t = text.lower()
    return any(re.search(p, t, flags=re.I) for p in FINANCE_TERMS)

# --- Impact scoring (keywords + urgency) ---
KEYWORDS = {
    "Fed": ([r"\bfed\b", r"\bpowell\b", r"\bfomc\b", "rate hike", "rate cut", r"\binflation\b", r"\bcpi\b", r"\bppi\b"], 1.0),
    "Geopolitics": ([r"\bchina\b", r"\brussia\b", r"\biran\b", r"\bisrael\b", r"\btaiwan\b", r"\bwar\b", "sanction", "missile", "attack"], 0.9),
    "Energy": ([r"\bopec\b", r"\bspr\b", r"\boil\b", r"\bbarrel\b", r"\bgasoline\b", r"\bdiesel\b", r"\brefinery\b", r"\bsaudi\b"], 0.8),
    "Trade": (["tariff", r"\btrade\b", r"\bimport\b", r"\bexport\b", r"\bban\b", r"\bquota\b", r"\bwto\b", "decouple"], 0.9),
    "Fiscal": (["tax cut", "cut taxes", r"\btax\b", "stimulus", r"\bspending\b", "deficit", "shutdown", "budget", "debt ceiling"], 0.7),
    "Crypto/Reg": ([r"\bsec\b", r"\bcftc\b", r"\betf\b", "approve", "approval", "bitcoin", r"\bbtc\b", "ethereum", r"\beth\b", "crypto"], 0.95),
    "Big Tech": (["apple","amazon","google","alphabet","microsoft","openai","nvidia","tesla","antitrust"], 0.6),
}

ALWAYS_ALERT = ["tariff","sanction","opec","spr","rate cut","rate hike","shutdown","sec","bitcoin",r"\bbtc\b","etf",r"\bban\b","china trade"]

def _regex_hits(text, patterns):
    return sum(1 for pat in patterns if re.search(pat, text, flags=re.I))

def market_impact_score(text):
    t = text.lower()
    score = 0.0
    tags = []
    for tag, (patterns, w) in KEYWORDS.items():
        hits = _regex_hits(t, patterns)
        if hits:
            tags.append(tag)
            score += min(1.0, 0.2*hits) * w

    # urgency cues
    exclam = text.count("!")
    caps_tokens = len(re.findall(r"\b[A-Z]{4,}\b", text))
    percents = len(re.findall(r"\b\d{1,3}%\b", text))
    immed = len(re.findall(r"\b(now|today|immediately|right now|this week|tonight)\b", t))
    score += 0.05*exclam + 0.05*min(caps_tokens,4) + 0.08*percents + 0.06*immed

    score = max(0.0, min(1.0, score))
    must = any(re.search(pat, t, flags=re.I) for pat in ALWAYS_ALERT)
    return (max(score, 0.6) if must else score), tags, must

# --- Sentiment (Lite) + finance overrides ---
def fin_sentiment(text):
    vs = analyzer.polarity_scores(text)
    comp = vs["compound"]
    if comp >= 0.2:
        label, conf = "Bullish", comp
    elif comp <= -0.2:
        label, conf = "Bearish", -comp
    else:
        label, conf = "Neutral", 1-abs(comp)
    tl = text.lower()
    if any(k in tl for k in ["cut taxes","lower rates","approve etf","ceasefire","stimulus"]):
        label, conf = "Bullish", max(conf, 0.65)
    if any(k in tl for k in ["raise tariffs","sanction","war","attack","hike rates","opec cut","embargo","shutdown","ban"]):
        label, conf = "Bearish", max(conf, 0.65)
    return label, round(float(conf), 2)

def classify_post(text):
    impact, tags, forced = market_impact_score(text)
    sent, conf = fin_sentiment(text)
    crypto = is_crypto_related(text, tags)
    finance = is_financial_related(text, tags) or crypto
    logging.info(f"[CLASSIFY] Impact={impact:.2f}, Sentiment={sent} ({conf}), Tags={tags}, Crypto={crypto}, Finance={finance}, Must={forced}")
    return {
        "impact_score": round(impact, 2),
        "sentiment": sent,
        "sent_conf": conf,
        "tags": tags,
        "must": forced,
        "is_crypto": crypto,
        "is_finance": finance
    }

def send_alert(post_url, text, meta):
    impact = meta["impact_score"]
    sent = meta["sentiment"]
    conf = meta["sent_conf"]
    tags = ", ".join(meta["tags"]) or "—"

    if impact >= 0.9:
        impact_emoji, impact_level = "🔥","VERY HIGH"
    elif impact >= 0.75:
        impact_emoji, impact_level = "🚨","HIGH"
    elif impact >= 0.60:
        impact_emoji, impact_level = "⚠️","MEDIUM"
    else:
        impact_emoji, impact_level = "💤","LOW"

    sent_emoji = {"Bullish":"🟢📈","Bearish":"🔴📉","Neutral":"⚪🤝"}[sent]

    msg = (f"🍊 iTrump | {impact_emoji} Market Impact: {impact_level} ({impact}) | "
           f"Sentiment: {sent_emoji} {sent} ({conf})\n"
           f"📎 Tags: {tags}\n\n{text.strip()}\n\nLink: {post_url}")

    logging.info(f"[ALERT] Sending message with impact={impact}, sentiment={sent}")
    try:
        asyncio.run(bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg))
    except ChatMigrated as e:
        new_id = e.new_chat_id
        logging.warning(f"[ALERT] Chat migrated -> retrying with new id {new_id}")
        asyncio.run(bot.send_message(chat_id=new_id, text=msg))
        logging.warning(f"UPDATE TELEGRAM_CHAT_ID in Render to: {new_id}")
    except Forbidden:
        logging.error("Bot is not allowed to message this chat. Add the bot to the group/supergroup.")
    except TelegramError as te:
        logging.exception(f"Telegram error sending alert: {te}")
