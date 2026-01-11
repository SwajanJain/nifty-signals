"""Configuration for Nifty Signals trading system."""

from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = PROJECT_ROOT / ".cache"
REPORTS_DIR = PROJECT_ROOT / "reports"
STOCKS_FILE = PROJECT_ROOT / "stocks.json"

# Ensure cache directory exists
CACHE_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# Technical indicator parameters
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

EMA_SHORT = 20
EMA_MEDIUM = 50
EMA_LONG = 200

BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2

# Signal scoring thresholds
STRONG_BUY_THRESHOLD = 5
BUY_THRESHOLD = 3
SELL_THRESHOLD = -3
STRONG_SELL_THRESHOLD = -5

# Volume confirmation
VOLUME_MULTIPLIER = 1.5

# Data fetching
CACHE_EXPIRY_HOURS = 4  # Cache data for 4 hours
LOOKBACK_DAYS = 365  # 1 year of data for analysis
