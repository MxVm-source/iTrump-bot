import os, re
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from telegram import Bot

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
bot = Bot(token=TELEGRAM_TOKEN)

analyzer = SentimentIntensityAnalyzer()

KEYWORDS = {
    "Fed": (["\bfed\b","\bpowell\b","\bfomc\b","rate hike","rate cut","\binflation\b","\bcpi\b","\bppi\b"], 1.0),
    "Geopolitics": (["\bchina\b","\brussia\b","\biran\b","\bisrael\b","\btaiwan\b","\bwar\b","sanction","missile","attack"], 0.9),
    "Energy": (["\bopec\b","\bspr\b","\boil\b","\bbarrel\b","\bgasoline\b","\bdiesel\b","\brefinery\b","\bsaudi\b"], 0.8),
    "Trade": (["tariff","\btrade\b","\bimport\b","\bexport\b","\bban\b","\bquota\b","\bwto\b","decouple"], 0.9),
    "Fiscal": (["tax cut","cut taxes","\btax\b","stimulus","\bspending\b","deficit","shutdown","budget","debt ceiling"], 0.7),
    "Crypto/Reg": (["\bsec\b","\bcftc\b","\betf\b","approve","approval","bitcoin","\bbtc\b","ethereum","\beth\b","crypto"], 0.95),
    "Big Tech": (["apple","amazon","google","alphabet","microsoft","openai","nvidia","tesla","antitrust"], 0.6),
    "Immigration/Border": (["\bborder\b","\bvisa\b","immigration"], 0.4),
}
ALWAYS_ALERT = ["tariff","sanction","opec","spr","rate cut","rate hike","shutdown","sec","bitcoin","\bbtc\b","etf","\bban\b","china trade"]

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
    exclam = text.count("!")
    caps_tokens = len(re.findall(r"\b[A-Z]{4,}\b", text))
    percents = len(re.findall(r"\b\d{1,3}%\b", text))
    immed = len(re.findall(r"\b(now|today|immediately|right now|this week|tonight)\b", t))
    score += 0.05*exclam + 0.05*min(caps_tokens,4) + 0.08*percents + 0.06*immed
    score = max(0.0, min(1.0, score))
    must = any(re.search(pat, t, flags=re.I) for pat in ALWAYS_ALERT)
    return (max(score, 0.6) if must else score), tags, must

def fin_sentiment(text):
    vs = analyzer.polarity_scores(text)
    comp = vs["compound"]
    if comp >= 0.2:
        label, conf = "Bullish", comp
    elif comp <= -0.2:
        label, conf = "Bearish", -comp
    else:
        label, conf = "Neutral", 1-abs(comp)
    t = text.lower()
    if any(k in t for k in ["cut taxes","lower rates","approve etf","ceasefire","stimulus"]):
        label, conf = "Bullish", max(conf, 0.65)
    if any(k in t for k in ["raise tariffs","sanction","war","attack","hike rates","opec cut","embargo","shutdown","ban"]):
        label, conf = "Bearish", max(conf, 0.65)
    return label, round(float(conf), 2)

def classify_post(text):
    impact, tags, forced = market_impact_score(text)
    sent, conf = fin_sentiment(text)
    return {"impact_score": round(impact, 2), "sentiment": sent, "sent_conf": conf, "tags": tags, "must": forced}

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
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
