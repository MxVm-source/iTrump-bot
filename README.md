# 🍊 iTrump — Finance-Focused Alert Bot (Render Worker, Lite Build)

Watches Trump's Truth Social feed and alerts only on **financially significant** posts (Fed/rates, taxes, tariffs/sanctions, shutdowns/stimulus, OPEC/oil, major geopolitics, Big Tech/SEC/ETF/crypto). Includes:
- Finance/crypto relevance gating
- Skip Neutral sentiment unless impact is huge
- Impact threshold filter
- Telegram send via asyncio (v21+)
- De-dupe with cooldown + persistence
- ChatMigrated handling

## Build
pip install --upgrade pip && pip install -r requirements.txt
## Run
python main.py

## Env Vars
TELEGRAM_TOKEN=<your bot token>
TELEGRAM_CHAT_ID=-1003151813176
IMPACT_THRESHOLD=0.70
FINANCE_ONLY=1
CRYPTO_ONLY=0
REQUIRE_NON_NEUTRAL=1
MIN_SENT_CONF=0.65
NEUTRAL_OVERRIDE_IMPACT=0.90
DEDUP_WINDOW_MIN=60
