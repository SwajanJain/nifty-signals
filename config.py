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

# =============================================================================
# Data Source Configuration
# =============================================================================
# Using Yahoo Finance (yfinance) as the sole data source
# Provides 1+ year of historical data for technical analysis

DATA_SOURCE = 'yfinance'

# =============================================================================
# Data Quality Thresholds
# =============================================================================
# Controls how the system responds to data quality issues

DATA_QUALITY_CONFIG = {
    # Maximum age before data is considered stale
    'max_price_age_days': 5,             # 5 trading days
    'max_fundamentals_age_days': 7,      # 1 week

    # Quality-based position modifiers
    'excellent_modifier': 1.0,
    'good_modifier': 0.9,
    'degraded_modifier': 0.5,
    'unusable_modifier': 0.0,
}

# =============================================================================
# Known Symbol Issues
# =============================================================================
# Some stocks require special handling in yfinance

SYMBOL_NOTES = {
    'ABB': 'Uses BSE ticker (ABB.BO)',
    'MCDOWELL-N': 'Uses alternative ticker (UNITDSPR.NS)',
    'TATAMOTORS': 'No yfinance workaround - excluded from analysis',
    'ZOMATO': 'No yfinance workaround - excluded from analysis',
}

# =============================================================================
# Intelligence Layer Configuration
# =============================================================================
# AI-powered analysis settings

INTELLIGENCE_CONFIG = {
    # Agent enablement
    'sentinel_enabled': True,    # Market context assessment
    'analyst_enabled': True,     # Signal validation
    'validator_enabled': True,   # Risk and sanity checks
    'learner_enabled': True,     # Pattern recognition
    'explainer_enabled': True,   # Human-readable explanations

    # Model selection
    'default_model': 'claude-3-haiku-20240307',
    'deep_analysis_model': 'claude-3-sonnet-20240229',

    # Behavior
    'require_high_confidence': False,
    'save_audit_trail': True,
    'audit_trail_path': 'journal/ai_audit.jsonl',
}

# =============================================================================
# Risk Management Configuration
# =============================================================================
# From CLAUDE.md - Legendary trading principles

RISK_CONFIG = {
    # Portfolio limits
    'max_portfolio_heat': 6.0,       # Max 6% total risk
    'max_position_pct': 15.0,        # Max 15% per position
    'max_sector_pct': 30.0,          # Max 30% per sector
    'max_positions_per_sector': 3,

    # Liquidity
    'min_liquidity_cr': 10.0,        # Min 10 Cr ADV
    'max_adv_pct': 2.0,              # Max 2% of ADV

    # Drawdown management
    'drawdown_scale_threshold': 5.0, # Start scaling at 5% DD
    'drawdown_scale_factor': 0.5,    # Reduce by 50% after threshold

    # Conviction-based risk allocation
    'conviction_risk_allocation': {
        'A+': 2.5,  # 2.5% risk for exceptional setups
        'A': 2.0,   # 2.0% risk for high conviction
        'B': 1.0,   # 1.0% risk for standard setups
        'C': 0.5,   # 0.5% risk for lower conviction
        'D': 0.0,   # No trade
    },
}

# =============================================================================
# Regime-Based Adjustments
# =============================================================================
# Position sizing multipliers based on market regime

REGIME_CONFIG = {
    'STRONG_BULL': {'multiplier': 1.0, 'can_trade': True},
    'BULL': {'multiplier': 0.8, 'can_trade': True},
    'NEUTRAL': {'multiplier': 0.5, 'can_trade': True},
    'BEAR': {'multiplier': 0.3, 'can_trade': True},
    'STRONG_BEAR': {'multiplier': 0.2, 'can_trade': True},
    'CRASH': {'multiplier': 0.0, 'can_trade': False},
}


# =============================================================================
# Stock List Helper
# =============================================================================
def get_nifty100_symbols():
    """Get list of Nifty 100 symbols from stocks.json"""
    import json
    try:
        with open(STOCKS_FILE) as f:
            data = json.load(f)
        return [s['symbol'] for s in data.get('nifty_100', [])]
    except Exception:
        return []


# =============================================================================
# Fundamental Analysis Configuration
# =============================================================================

FUNDAMENTAL_CACHE_EXPIRY_HOURS = 168  # 7 days (data changes quarterly)
SCREENER_BASE_URL = "https://www.screener.in/company/{symbol}/consolidated/"
SCREENER_STANDALONE_URL = "https://www.screener.in/company/{symbol}/"
SCREENER_RATE_LIMIT_DELAY = 2.0  # seconds between requests
SCREENER_MAX_RETRIES = 3
SCREENER_TIMEOUT = 30

# Symbol mapping for screener.in URL encoding
SCREENER_SYMBOL_MAP = {
    # URL-encoding for special characters
    'M&M': 'M%26M',
    'L&TFH': 'L%26TFH',
    'BAJAJ-AUTO': 'BAJAJ-AUTO',
    'J&KBANK': 'J%26KBANK',
    # NSE symbol → screener.in slug (renames, different tickers)
    'AEGISCHEM': 'AEGISLOG',
    'AMARAJABAT': 'ARE%26M',
    'CENTURYTEX': 'ABREL',
    'GMRINFRA': 'GMRAIRPORT',
    'HBLPOWER': 'HBLENGINE',
    'KALPATPOWR': 'KPIL',
    'LAXMIMACH': 'LMW',
    'LTIM': 'LTM',
    'MCDOWELL-N': 'UNITDSPR',
    'MINDAIND': 'UNOMINDA',
    'MISHRA': 'MIDHANI',
    'MMFIN': 'M%26MFIN',
    'NMDCSTEEL': 'NSLNISP',
    'ONE97': 'PAYTM',
    'SUVENPHAR': 'COHANCE',
    'SWANENERGY': 'SWANCORP',
    'TATAMOTORS': 'TMCV',
    'ZOMATO': 'ETERNAL',
}

FUNDAMENTAL_SCORE_WEIGHTS = {
    'valuation': 20,
    'profitability': 25,
    'growth': 25,
    'financial_health': 15,
    'quality': 15,
}

SCREEN_THRESHOLDS = {
    'value': {
        'max_pe': 15,
        'max_pb': 2.0,
        'max_de': 0.5,
        'min_market_cap_cr': 5000,
        'min_years_profit': 5,
    },
    'growth': {
        'min_eps_growth': 20,
        'min_rev_growth': 15,
        'max_peg': 1.5,
    },
    'quality': {
        'min_roce': 15,
        'min_rev_growth': 10,
        'max_de': 0.5,
        'min_promoter_holding': 30,
        'min_years_consistent': 5,
    },
    'garp': {
        'max_peg': 1.5,
        'min_earnings_growth': 15,
        'min_roe': 15,
        'max_pe': 30,
    },
    'dividend': {
        'min_yield': 2.0,
        'min_years_dividend': 4,
        'min_payout': 20,
        'max_payout': 60,
    },
}

# Banking/finance sectors that need special fundamental treatment
BANKING_SECTORS = {'Banking', 'Finance', 'Insurance', 'Financial Services'}


def get_nifty500_symbols():
    """Get list of Nifty 500 symbols from stocks.json."""
    import json
    try:
        with open(STOCKS_FILE) as f:
            data = json.load(f)
        return [s['symbol'] for s in data.get('nifty_500', [])]
    except Exception:
        return []


def get_nifty500_stocks():
    """Get full Nifty 500 stock list with name and sector."""
    import json
    try:
        with open(STOCKS_FILE) as f:
            data = json.load(f)
        return data.get('nifty_500', [])
    except Exception:
        return []


# =============================================================================
# Tailwind / External Factors Configuration
# =============================================================================

TAILWIND_THEMES_FILE = PROJECT_ROOT / "tailwinds" / "themes.json"
TAILWIND_NEWS_CACHE_EXPIRY_HOURS = 24
TAILWIND_NEWS_RATE_LIMIT_DELAY = 3.0
TAILWIND_NEWS_TIMEOUT = 15
TAILWIND_NEWS_MAX_RETRIES = 2

COMPOSITE_WEIGHTS = {
    'internal': 0.50,
    'external': 0.30,
    'valuation': 0.20,
}

# Sector keyword mapping for news detection
TAILWIND_SECTOR_KEYWORDS = {
    'IT': ['it sector', 'software', 'tech ', 'digital', 'saas', 'ai ', 'cloud', 'data center', 'cybersecurity'],
    'Banking': ['bank', 'banking', 'npa', 'credit growth', 'deposit', 'lending', 'rbi rate'],
    'Financial Services': ['financial services', 'nbfc', 'fintech', 'mutual fund', 'wealth management', 'microfinance'],
    'Pharma': ['pharma', 'drug', 'api ', 'biotech', 'generic', 'pharmaceutical', 'usfda'],
    'Healthcare': ['healthcare', 'hospital', 'medical', 'diagnostics', 'health insurance'],
    'Auto': ['auto', 'automobile', 'ev ', 'electric vehicle', 'car ', 'two-wheeler', 'suv', 'oem'],
    'FMCG': ['fmcg', 'consumer goods', 'food', 'beverage', 'personal care', 'packaged'],
    'Consumer': ['consumer', 'retail', 'e-commerce', 'premium', 'lifestyle', 'apparel', 'jewellery'],
    'Infra': ['infra', 'infrastructure', 'construction', 'road', 'highway', 'railway', 'metro', 'airport'],
    'Capital Goods': ['capital goods', 'engineering', 'manufacturing', 'pli', 'defence', 'defense', 'electrical'],
    'Cement': ['cement', 'concrete', 'building material', 'clinker'],
    'Metals': ['metal', 'steel', 'aluminium', 'copper', 'mining', 'iron ore', 'zinc'],
    'Oil & Gas': ['oil', 'gas', 'crude', 'petroleum', 'refinery', 'pipeline', 'lng', 'natural gas'],
    'Power': ['power', 'electricity', 'solar', 'wind', 'renewable', 'energy transition', 'grid', 'thermal'],
    'Insurance': ['insurance', 'life insurance', 'general insurance', 'health insurance', 'irdai'],
    'Real Estate': ['real estate', 'realty', 'housing', 'property', 'affordable housing', 'rera'],
    'Telecom': ['telecom', 'jio', 'airtel', 'vodafone', '5g', 'spectrum', 'tower'],
    'Chemicals': ['chemical', 'specialty chemical', 'agrochemical', 'pesticide', 'fertilizer', 'dye'],
    'Textiles': ['textile', 'garment', 'cotton', 'yarn', 'fabric', 'apparel manufacturing'],
    'Media': ['media', 'entertainment', 'broadcasting', 'ott', 'streaming', 'advertising'],
    'Diversified': ['conglomerate', 'diversified'],
}

POLICY_KEYWORDS = [
    'pli', 'production linked incentive', 'subsidy', 'gst',
    'tax', 'income tax', 'customs duty', 'excise', 'cess',
    'sebi', 'rbi', 'irdai', 'trai', 'rera',
    'fiscal', 'budget', 'allocation', 'scheme', 'mission',
    'regulation', 'deregulation', 'reform', 'policy',
    'fdi', 'foreign direct investment', 'ease of doing business',
    'make in india', 'atmanirbhar', 'self-reliant',
    'nip', 'national infrastructure pipeline',
    'green hydrogen', 'national hydrogen mission',
    'import duty', 'export incentive', 'tariff',
]

BULLISH_KEYWORDS = [
    'surge', 'rally', 'boom', 'growth', 'record high', 'bullish',
    'outperform', 'upgrade', 'expansion', 'strong demand', 'beat estimate',
    'profit jump', 'revenue growth', 'market share gain', 'order win',
    'capacity expansion', 'new plant', 'investment', 'positive',
    'opportunity', 'upside', 'breakout', 'all-time high',
]

BEARISH_KEYWORDS = [
    'crash', 'slump', 'decline', 'fall', 'bearish', 'downgrade',
    'underperform', 'weak demand', 'margin pressure', 'miss estimate',
    'profit decline', 'revenue fall', 'loss', 'negative', 'risk',
    'headwind', 'slowdown', 'contraction', 'layoff', 'debt concern',
    'default', 'fraud', 'investigation', 'penalty',
]

# =============================================================================
# VCP Scanner Configuration (Minervini)
# =============================================================================
VCP_CONFIG = {
    'min_contractions': 2,
    'max_base_days': 65,
    'first_pullback_min_pct': 10,
    'first_pullback_max_pct': 40,
    'contraction_ratio': 0.65,       # each pullback < 65% of previous
    'volume_decline_min': 0.25,      # volume must drop 25%+ across base
    'pivot_proximity_pct': 5.0,      # within 5% of pivot to score "ready"
    'swing_window': 5,               # bars on each side for pivot detection
}

# =============================================================================
# TTM Squeeze Configuration (John Carter)
# =============================================================================
TTM_SQUEEZE_CONFIG = {
    'bb_length': 20,
    'bb_mult': 2.0,
    'kc_length': 20,
    'kc_mult': 1.5,
    'min_squeeze_bars': 6,
    'momentum_lookback': 20,
}

# =============================================================================
# Factor Model Configuration (Multi-Factor Investing)
# =============================================================================
FACTOR_MODEL_CONFIG = {
    'weights': {
        'momentum': 0.25,
        'value': 0.20,
        'quality': 0.25,
        'growth': 0.20,
        'low_vol': 0.10,
    },
}

# =============================================================================
# Portfolio Risk Configuration
# =============================================================================
PORTFOLIO_RISK_CONFIG = {
    'var_confidence': 0.95,
    'var_method': 'historical',
    'max_portfolio_var_pct': 5.0,
    'correlation_threshold_reduce': 0.7,
    'correlation_reduce_factor': 0.5,
}

# =============================================================================
# Telegram Alerts Configuration
# =============================================================================
TELEGRAM_CONFIG = {
    'enabled': False,
    'send_on': ['STRONG_BUY', 'BUY'],
    # Set via env vars: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
}
