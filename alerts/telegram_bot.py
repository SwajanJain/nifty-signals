"""Telegram Alert Bot for Nifty Signals.

Sends trading signals and market summaries via Telegram.
Configure via environment variables:
  TELEGRAM_BOT_TOKEN  — BotFather token
  TELEGRAM_CHAT_ID    — Your chat/group ID

Usage:
    from alerts.telegram_bot import TelegramAlerts
    bot = TelegramAlerts()
    bot.send_signal(decision_dict)
    bot.send_market_summary(summary_dict)
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

try:
    from config import TELEGRAM_CONFIG as _TELE_CFG
except ImportError:
    _TELE_CFG = {}

_CFG = {
    'enabled': False,
    'send_on': ['STRONG_BUY', 'BUY'],
    'bot_token': os.environ.get('TELEGRAM_BOT_TOKEN', ''),
    'chat_id': os.environ.get('TELEGRAM_CHAT_ID', ''),
}
_CFG.update(_TELE_CFG)
# Env vars always override config file
if os.environ.get('TELEGRAM_BOT_TOKEN'):
    _CFG['bot_token'] = os.environ['TELEGRAM_BOT_TOKEN']
if os.environ.get('TELEGRAM_CHAT_ID'):
    _CFG['chat_id'] = os.environ['TELEGRAM_CHAT_ID']


class TelegramAlerts:
    """Send formatted trading alerts via Telegram."""

    def __init__(self, bot_token: str = '', chat_id: str = ''):
        self.bot_token = bot_token or _CFG['bot_token']
        self.chat_id = chat_id or _CFG['chat_id']
        self._available = None

    @property
    def available(self) -> bool:
        """Check if Telegram sending is possible."""
        if self._available is None:
            self._available = bool(self.bot_token and self.chat_id)
            if self._available:
                try:
                    import requests  # noqa: F401
                except ImportError:
                    self._available = False
        return self._available

    # ------------------------------------------------------------------
    # Core send
    # ------------------------------------------------------------------

    def _send(self, text: str, parse_mode: str = 'HTML') -> bool:
        """Send a message via Telegram Bot API.

        Uses requests directly (no python-telegram-bot dependency needed).
        """
        if not self.available:
            print("[TelegramAlerts] Not configured — skipping send")
            return False

        import requests

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode,
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True
            print(f"[TelegramAlerts] API error {resp.status_code}: {resp.text[:200]}")
            return False
        except Exception as e:
            print(f"[TelegramAlerts] Send failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Message formatting
    # ------------------------------------------------------------------

    def format_signal_message(self, decision: Dict) -> str:
        """Format a trading signal as a Telegram message."""
        symbol = decision.get('symbol', '?')
        action = decision.get('action', '?')
        price = decision.get('price', 0)
        conviction = decision.get('conviction', '?')
        score = decision.get('conviction_score', 0)

        stop = decision.get('stop_loss', 0)
        t1 = decision.get('target_1', 0)
        t2 = decision.get('target_2', 0)
        risk_pct = decision.get('risk_pct', 0)

        # Action emoji
        emoji_map = {'STRONG_BUY': '🟢🟢', 'BUY': '🟢', 'SELL': '🔴', 'STRONG_SELL': '🔴🔴', 'HOLD': '🟡'}
        emoji = emoji_map.get(action, '⚪')

        lines = [
            f"{emoji} <b>{action}: {symbol}</b> @ ₹{price:,.1f}",
            f"",
            f"<b>Conviction:</b> {conviction} ({score}/100)",
        ]

        if stop:
            lines.append(f"<b>Stop:</b> ₹{stop:,.1f} ({risk_pct:.1f}%)")
        if t1:
            lines.append(f"<b>T1:</b> ₹{t1:,.1f}")
        if t2:
            lines.append(f"<b>T2:</b> ₹{t2:,.1f}")

        # Reasons
        reasons = decision.get('reasons', [])
        if reasons:
            lines.append("")
            lines.append("<b>Reasons:</b>")
            for r in reasons[:5]:
                lines.append(f"  • {r}")

        lines.append(f"\n<i>{datetime.now().strftime('%Y-%m-%d %H:%M IST')}</i>")
        return "\n".join(lines)

    def format_market_summary(self, summary: Dict) -> str:
        """Format a market summary as a Telegram message."""
        regime = summary.get('regime', '?')
        should_trade = summary.get('should_trade', True)
        risk_score = summary.get('global_risk_score', 0)
        top_sectors = summary.get('top_sectors', [])
        signals_count = summary.get('signals_count', 0)

        regime_emoji = {
            'STRONG_BULL': '🐂🐂', 'BULL': '🐂', 'NEUTRAL': '➡️',
            'BEAR': '🐻', 'STRONG_BEAR': '🐻🐻', 'CRASH': '💥',
        }

        lines = [
            f"📊 <b>Market Summary</b> — {datetime.now().strftime('%Y-%m-%d')}",
            f"",
            f"<b>Regime:</b> {regime_emoji.get(regime, '')} {regime}",
            f"<b>Should Trade:</b> {'✅ YES' if should_trade else '❌ NO'}",
            f"<b>Global Risk:</b> {risk_score}/5",
        ]

        if top_sectors:
            lines.append(f"<b>Top Sectors:</b> {', '.join(top_sectors[:5])}")

        lines.append(f"<b>Signals Generated:</b> {signals_count}")
        lines.append(f"\n<i>Run 'python3 main.py enhanced-scan' for details</i>")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # High-level send methods
    # ------------------------------------------------------------------

    def send_signal(self, decision: Dict) -> bool:
        """Send a trading signal if it meets the action filter."""
        action = decision.get('action', '')
        if action not in _CFG['send_on']:
            return False
        msg = self.format_signal_message(decision)
        return self._send(msg)

    def send_market_summary(self, summary: Dict) -> bool:
        """Send daily market summary."""
        msg = self.format_market_summary(summary)
        return self._send(msg)

    def send_text(self, text: str) -> bool:
        """Send raw text message."""
        return self._send(text, parse_mode='HTML')

    def send_alert(self, title: str, body: str) -> bool:
        """Send a generic alert."""
        msg = f"🔔 <b>{title}</b>\n\n{body}\n\n<i>{datetime.now().strftime('%H:%M IST')}</i>"
        return self._send(msg)
