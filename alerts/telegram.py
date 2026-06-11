"""Telegram alert sender (optional — requires TELEGRAM_TOKEN and TELEGRAM_CHAT_ID env vars)."""
import os
import logging

import httpx

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org"
_MAX_LEN = 4096  # Telegram message limit


def send_telegram(text: str, config: dict) -> None:
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.warning(
            "Telegram credentials missing (TELEGRAM_TOKEN / TELEGRAM_CHAT_ID). "
            "Set them as environment variables or GitHub Actions secrets."
        )
        return

    # Split into chunks if the digest is too long
    chunks = [text[i:i + _MAX_LEN] for i in range(0, len(text), _MAX_LEN)]
    for chunk in chunks:
        resp = httpx.post(
            f"{_API}/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"},
            timeout=15,
        )
        resp.raise_for_status()
    logger.info("Telegram digest sent (%d chunk(s))", len(chunks))
