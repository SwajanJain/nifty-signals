#!/usr/bin/env python3
"""
Stage C: Scan Universe

Scans ALL stocks in the universe and calculates:
- Technical indicators
- Model votes (momentum, trend, breakout, mean reversion)
- Conviction scores
- Preliminary trade setups (entry, stop, targets)
- Skip reasons (liquidity, earnings, etc.)

Outputs: candidates.json (ALL stocks with full data)

This is deterministic. Code considers FULL universe.
Claude cannot filter at this stage.
"""

import json
import sys
import numpy as np
import pandas as pd
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.reliable_fetcher import get_reliable_fetcher, KNOWN_FAILURES
from config import get_nifty100_symbols
from core.conviction import ConvictionScorer
from indicators.candlestick import CandlestickPatterns
from indicators.fibonacci import FibonacciAnalysis
from indicators.technical import TechnicalIndicators
from indicators.divergence import DivergenceDetector
from indicators.multi_timeframe import MultiTimeframeAnalyzer
from indicators.price_action import PriceActionAnalyzer
from indicators.sector_strength import get_sector_for_stock
from indicators.trend_strength import TrendStrength
from models.breakout import BreakoutModel
from models.ensemble import ModelEnsemble, SignalDirection
from models.mean_reversion import MeanReversionModel
from models.momentum import MomentumModel
from models.trend_following import TrendFollowingModel

try:
    from indicators.chart_patterns import ChartPatterns
except Exception:
    ChartPatterns = None

def load_config() -> dict:
    """Load trading configuration."""
    config_path = PROJECT_ROOT / "config" / "trading_config.json"
    with open(config_path) as f:
        return json.load(f)


def load_market_context(run_dir: Path) -> dict:
    """Load market context from previous stage."""
    context_path = run_dir / "market_context.json"
    with open(context_path) as f:
        return json.load(f)


def load_data_health(run_dir: Path) -> dict:
    """Load data health from Stage A."""
    data_path = run_dir / "data_health.json"
    with open(data_path) as f:
        return json.load(f)

def load_symbol_meta(run_dir: Path) -> Optional[dict]:
    """Load pinned symbol meta (earnings + fundamentals), if present."""
    path = run_dir / "symbol_meta.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def load_internals(run_dir: Path) -> Optional[dict]:
    """Load pinned market internals (breadth), if present."""
    path = run_dir / "internals.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def load_sector_strength(run_dir: Path) -> Optional[dict]:
    """Load pinned sector strength artifact, if present."""
    path = run_dir / "sector_strength.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _load_snapshot_df(run_dir: Path, symbol: str) -> Optional[pd.DataFrame]:
    """
    Load OHLCV from the run snapshot.

    Returns None if not found/unreadable.
    """
    path = run_dir / "data" / "daily" / f"{symbol}.csv"
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        expected = {"open", "high", "low", "close", "volume"}
        if not expected.issubset(set(df.columns)):
            return None
        return df[["open", "high", "low", "close", "volume"]].sort_index()
    except Exception:
        return None


def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """Calculate RSI."""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    if loss.iloc[-1] == 0:
        return 100.0

    rs = gain.iloc[-1] / loss.iloc[-1]
    return 100 - (100 / (1 + rs))


def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """Calculate MACD, signal, and histogram."""
    exp1 = prices.ewm(span=fast).mean()
    exp2 = prices.ewm(span=slow).mean()
    macd = exp1 - exp2
    macd_signal = macd.ewm(span=signal).mean()
    macd_hist = macd - macd_signal

    return float(macd.iloc[-1]), float(macd_signal.iloc[-1]), float(macd_hist.iloc[-1])


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculate Average True Range."""
    high = df['high']
    low = df['low']
    close = df['close']

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    return float(atr.iloc[-1])


def to_python_types(obj):
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: to_python_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_python_types(v) for v in obj]
    elif isinstance(obj, (float, np.floating)) and (np.isnan(obj) or np.isinf(obj)):
        return None
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        val = float(obj)
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj


def _clamp_int(value: int, low: int, high: int) -> int:
    """Clamp integer to inclusive [low, high]."""
    return int(max(low, min(high, int(value))))


def _resample_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLCV into weekly OHLCV (W-FRI)."""
    if df.empty:
        return df
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    out = out.sort_index()
    weekly = out.resample("W-FRI").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    return weekly.dropna()


def _pct_return(close: pd.Series, periods: int) -> float:
    """Percent return over N periods, deterministic fallback to 0."""
    if close is None or len(close) <= periods:
        return 0.0
    prior = float(close.iloc[-(periods + 1)])
    latest = float(close.iloc[-1])
    if prior <= 0:
        return 0.0
    return ((latest / prior) - 1) * 100


def _regime_to_score(regime: str) -> int:
    """Map discrete regime to an integer score used by ConvictionScorer."""
    mapping = {
        "STRONG_BULL": 5,
        "BULL": 3,
        "NEUTRAL": 0,
        "BEAR": -3,
        "STRONG_BEAR": -5,
        "CRASH": -8,
    }
    return mapping.get(regime or "NEUTRAL", 0)


def _global_risk_score(market_context: dict) -> float:
    """Compute a small numeric risk score from the pinned market context."""
    vix = market_context.get("vix")
    sp500_change = (market_context.get("global") or {}).get("sp500_change")
    breadth = market_context.get("breadth") or {}
    breadth_state = breadth.get("state") if isinstance(breadth, dict) else None

    score = 0.0

    if sp500_change is not None:
        try:
            sp = float(sp500_change)
            if sp > 1:
                score += 1.0
            elif sp > 0:
                score += 0.5
            elif sp < -1:
                score -= 1.0
            elif sp < 0:
                score -= 0.5
        except Exception:
            pass

    if vix is not None:
        try:
            v = float(vix)
            if v < 15:
                score += 1.0
            elif v < 20:
                score += 0.0
            elif v < 25:
                score -= 1.0
            else:
                score -= 2.0
        except Exception:
            pass

    # Breadth overlay (minor)
    if breadth_state == "RISK_ON":
        score += 0.5
    elif breadth_state == "RISK_OFF":
        score -= 1.0

    return float(score)


def _sector_strength_from_rank(rank: int, total_sectors: int) -> str:
    """Convert sector rank into a coarse strength bucket."""
    if total_sectors <= 0 or rank <= 0 or rank > total_sectors:
        return "WEAK"

    top_cutoff = max(3, round(total_sectors * 0.2))
    mid_cutoff = max(5, round(total_sectors * 0.5))
    weak_cutoff = max(8, round(total_sectors * 0.8))

    if rank <= top_cutoff:
        return "STRONG"
    if rank <= mid_cutoff:
        return "MODERATE"
    if rank <= weak_cutoff:
        return "WEAK"
    return "VERY_WEAK"


def _build_ensemble(config: dict) -> ModelEnsemble:
    """Create a weighted multi-model ensemble (Simons-style)."""
    weights = (config.get("model_weights") or {})
    return ModelEnsemble(
        models=[
            MomentumModel(weight=float(weights.get("momentum", 0.25))),
            TrendFollowingModel(weight=float(weights.get("trend", 0.25))),
            BreakoutModel(weight=float(weights.get("breakout", 0.25))),
            MeanReversionModel(weight=float(weights.get("mean_reversion", 0.25))),
        ]
    )


def _analyze_stock_raw(
    symbol: str,
    df: pd.DataFrame,
    config: dict,
    regime: str,
    ensemble: ModelEnsemble,
) -> dict:
    """Compute per-symbol analysis inputs (conviction computed in a second pass)."""
    tech_params = config["technical_params"]

    current_price = float(df["close"].iloc[-1])

    # Key technicals
    ema20_val = float(df["close"].ewm(span=tech_params["ema_fast"]).mean().iloc[-1])
    ema50_val = float(df["close"].ewm(span=tech_params["ema_medium"]).mean().iloc[-1])
    ema200_val = float(df["close"].ewm(span=tech_params["ema_slow"]).mean().iloc[-1])

    rsi = calculate_rsi(df["close"], tech_params["rsi_period"])
    macd, macd_signal, macd_hist = calculate_macd(
        df["close"],
        tech_params["macd_fast"],
        tech_params["macd_slow"],
        tech_params["macd_signal"],
    )
    atr = calculate_atr(df, tech_params["atr_period"])

    high_52w = float(df["high"].tail(252).max() if len(df) >= 252 else df["high"].max())
    low_52w = float(df["low"].tail(252).min() if len(df) >= 252 else df["low"].min())
    distance_from_high = ((high_52w - current_price) / high_52w) * 100 if high_52w > 0 else 0.0

    avg_volume = float(df["volume"].rolling(20).mean().iloc[-1])
    current_volume = float(df["volume"].iloc[-1])
    volume_ratio = (current_volume / avg_volume) if avg_volume > 0 else 1.0

    prev_high = float(df["high"].iloc[-2])

    # ----------------------------
    # Multi-timeframe alignment
    # ----------------------------
    weekly_df = _resample_to_weekly(df)
    mtf = MultiTimeframeAnalyzer(df, weekly_df) if not weekly_df.empty else None
    mtf_alignment = 0
    mtf_summary = {}
    if mtf:
        alignment = mtf.get_alignment()
        mtf_alignment = int(alignment.get("alignment_score", 0))
        mtf_summary = {
            "alignment_score": mtf_alignment,
            "recommendation": alignment.get("recommendation"),
            "confidence": alignment.get("confidence"),
            "summary": alignment.get("summary"),
        }

    # ----------------------------
    # Price action / divergence / ADX
    # ----------------------------
    price_action = PriceActionAnalyzer(df)
    pa = price_action.get_all_signals()

    divergence = DivergenceDetector(df)
    div = divergence.get_all_divergences()

    trend_strength = TrendStrength(df)
    ts = trend_strength.get_all_signals()

    # ----------------------------
    # Expanded chart-based indicator stack
    # ----------------------------
    technical_indicators = TechnicalIndicators(df)
    ti_signals = technical_indicators.get_all_signals()
    ti_latest = technical_indicators.get_latest()

    candlesticks = CandlestickPatterns(df)
    candle_patterns = candlesticks.get_all_patterns()

    fib = FibonacciAnalysis(df)
    fib_signals = fib.get_all_signals()

    if ChartPatterns is not None:
        chart_patterns = ChartPatterns(df).get_all_patterns()
    else:
        chart_patterns = {
            "patterns": [],
            "total_score": 0,
            "description": "Chart patterns unavailable (missing scipy dependency)",
        }

    # ----------------------------
    # Overlap control: bucket + cap, then clamp to ConvictionScorer expected range
    # ConvictionScorer assumes raw_score roughly in [-15, +15].
    # ----------------------------
    raw_components = {
        "price_action": int(pa.get("total_score", 0)),
        "divergence": int(div.get("total_score", 0)),
        "trend_strength": int(ts.get("total_score", 0)),
        "technical": int((ti_signals or {}).get("total_score", 0)),
        "candlestick": int((candle_patterns or {}).get("total_score", 0)),
        "chart_patterns": int((chart_patterns or {}).get("total_score", 0)),
        "fibonacci": int((fib_signals or {}).get("total_score", 0)),
    }
    caps = {
        "price_action": 5,
        "divergence": 5,
        "trend_strength": 4,
        "technical": 6,
        "candlestick": 4,
        "chart_patterns": 4,
        "fibonacci": 3,
    }
    capped_components = {
        k: _clamp_int(v, -caps[k], caps[k]) for k, v in raw_components.items()
    }
    raw_score = int(sum(capped_components.values()))
    technical_score = _clamp_int(raw_score, -15, 15)

    # ----------------------------
    # Model ensemble (independent models)
    # ----------------------------
    ensemble_signal = ensemble.generate_ensemble_signal(symbol, df, regime=regime)
    model_signals = ensemble_signal.model_signals or []

    votes = {
        ms.model_name.lower(): (ms.direction.value > 0)
        for ms in model_signals
    }
    bullish_votes = int(sum(1 for v in votes.values() if v))

    if ensemble_signal.direction == SignalDirection.STRONG_BUY:
        signal = "STRONG_BUY"
    elif ensemble_signal.direction == SignalDirection.BUY:
        signal = "BUY"
    elif ensemble_signal.direction in (SignalDirection.SELL, SignalDirection.STRONG_SELL):
        signal = "SELL"
    else:
        signal = "HOLD"

    # ----------------------------
    # Trade setup (rule-based, deterministic)
    # ----------------------------
    stop_mult = tech_params["stop_atr_multiplier"]
    t1_mult = tech_params["target1_atr_multiplier"]
    t2_mult = tech_params["target2_atr_multiplier"]

    is_breakout_focused = votes.get("breakout", False) and current_price < prev_high
    entry = prev_high if is_breakout_focused else current_price
    entry_type = "breakout" if is_breakout_focused else "market"

    stop_loss = entry - (stop_mult * atr)
    target1 = entry + (t1_mult * atr)
    target2 = entry + (t2_mult * atr)

    risk = entry - stop_loss
    reward = target1 - entry
    rr_ratio = (reward / risk) if risk > 0 else 0.0

    distance_to_entry = abs(entry - current_price) / current_price * 100 if current_price > 0 else 0.0

    # ----------------------------
    # Conviction scorer inputs
    # ----------------------------
    near_support = bool(pa.get("support_distance") is not None and pa.get("support_distance") <= 2)
    bullish_divergence = bool(div.get("total_score", 0) > 0)
    golden_cross = bool(ema50_val > ema200_val and current_price > ema50_val)
    extended_from_ema = bool(current_price > ema20_val * 1.05)
    low_volume = bool(volume_ratio < 0.8)
    breakout_with_volume = bool(pa.get("breakout", {}).get("score") == 2)
    resistance_break = bool(pa.get("breakout", {}).get("score", 0) > 0)
    bullish_candle = bool((candle_patterns or {}).get("total_score", 0) > 0)
    bullish_chart_pattern = bool((chart_patterns or {}).get("total_score", 0) > 0)
    bullish_fibonacci = bool((fib_signals or {}).get("total_score", 0) > 0)
    macd_cross = bool((ti_signals or {}).get("macd", {}).get("score", 0) == 2)
    adx_trending = bool((ts or {}).get("adx", 0) is not None and float(ts.get("adx", 0)) >= 25)

    signal_details = {
        "breakout_with_volume": breakout_with_volume,
        "bullish_divergence": bullish_divergence,
        "at_support": near_support,
        "golden_cross": golden_cross,
        "extended_from_ema": extended_from_ema,
        "low_volume": low_volume,
        "resistance_break": resistance_break,
        "bullish_candle": bullish_candle,
        "chart_pattern": bullish_chart_pattern,
        "fibonacci_level": bullish_fibonacci,
        "macd_cross": macd_cross,
        "adx_trending": adx_trending,
    }

    active_signals: List[str] = []
    for model_key, bullish in votes.items():
        if bullish:
            active_signals.append(f"model_{model_key}")
    if breakout_with_volume:
        active_signals.append("volume_breakout")
    if near_support:
        active_signals.append("support_bounce")
    if resistance_break:
        active_signals.append("resistance_break")
    if bullish_divergence:
        active_signals.append("bullish_divergence")
    if golden_cross:
        active_signals.append("golden_cross")
    if not low_volume and volume_ratio >= 1.5:
        active_signals.append("volume_confirmation")
    if ema20_val > ema50_val and current_price > ema20_val:
        active_signals.append("ema_alignment")
    if rsi <= 30:
        active_signals.append("rsi_oversold")
    if macd_cross:
        active_signals.append("macd_cross")
    if bullish_candle:
        active_signals.append("bullish_candle")
    if bullish_chart_pattern:
        active_signals.append("chart_pattern")
    if bullish_fibonacci:
        active_signals.append("fibonacci_level")
    if adx_trending:
        active_signals.append("adx_trending")

    # Liquidity proxy (ADV in Cr)
    daily_value_cr = (avg_volume * current_price) / 1e7 if avg_volume > 0 else 0.0

    last_date = df.index[-1]
    if hasattr(last_date, "tz") and last_date.tz is not None:
        last_date = last_date.tz_localize(None)

    return {
        "symbol": symbol,
        "price": round(current_price, 2),
        "signal": signal,

        "sector": get_sector_for_stock(symbol) or "Unknown",
        "ret_5d": round(_pct_return(df["close"], 5), 2),
        "ret_20d": round(_pct_return(df["close"], 20), 2),

        "data": {
            "bars": int(len(df)),
            "last_date": last_date.strftime("%Y-%m-%d"),
        },

        "votes": votes,
        "bullish_votes": bullish_votes,
        "ensemble": {
            "direction": ensemble_signal.direction.name,
            "normalized_score": round(float(ensemble_signal.normalized_score), 4),
            "confidence": round(float(ensemble_signal.confidence), 3),
            "agreement_pct": round(float(ensemble_signal.agreement_pct), 3),
            "reasons": ensemble_signal.reasons[:6],
        },

        "mtf": mtf_summary,
        "mtf_alignment": mtf_alignment,

        "technicals": {
            "rsi": round(rsi, 2),
            "macd": round(macd, 4),
            "macd_signal": round(macd_signal, 4),
            "macd_hist": round(macd_hist, 4),
            "ema20": round(ema20_val, 2),
            "ema50": round(ema50_val, 2),
            "ema200": round(ema200_val, 2),
            "atr": round(atr, 2),
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
            "distance_from_high_pct": round(distance_from_high, 2),
            "volume_ratio": round(volume_ratio, 2),
            "adv_value_cr": round(daily_value_cr, 2),
            "bb_upper": round(float(ti_latest.get("bb_upper", 0) or 0), 2),
            "bb_middle": round(float(ti_latest.get("bb_middle", 0) or 0), 2),
            "bb_lower": round(float(ti_latest.get("bb_lower", 0) or 0), 2),
            "bb_width": round(float(ti_latest.get("bb_width", 0) or 0), 4),
            "adx": round(float(ts.get("adx", 0) or 0), 2),
        },

        "indicators": {
            "price_action": pa,
            "divergence": div,
            "trend_strength": ts,
            "technical": ti_signals,
            "candlestick": candle_patterns,
            "chart_patterns": chart_patterns,
            "fibonacci": fib_signals,
        },
        "technical_components": {
            "raw": raw_components,
            "capped": capped_components,
            "raw_score": int(raw_score),
            "technical_score": int(technical_score),
        },

        "setup": {
            "entry": round(entry, 2),
            "entry_type": entry_type,
            "stop_loss": round(stop_loss, 2),
            "target1": round(target1, 2),
            "target2": round(target2, 2),
            "risk": round(risk, 2),
            "reward": round(reward, 2),
            "rr_ratio": round(rr_ratio, 2),
        },

        "_conviction_inputs": {
            "technical_score": int(technical_score),
            "signal_details": signal_details,
            "active_signals": active_signals,
            "distance_to_entry": round(distance_to_entry, 2),
            "days_since_breakout": 0 if entry_type == "breakout" else 1,
            "volume_confirmation": bool(volume_ratio >= 1.5),
        },
    }


def scan_universe(run_dir: Path) -> dict:
    """
    Scan all stocks in the universe.

    Returns:
        Full candidates data for ALL stocks
    """
    config = load_config()
    market_context = load_market_context(run_dir)
    data_health = load_data_health(run_dir)
    symbol_meta = load_symbol_meta(run_dir) or {}
    meta_by_symbol = (symbol_meta.get("symbols") or {}) if isinstance(symbol_meta, dict) else {}
    sector_strength = load_sector_strength(run_dir) or {}
    sector_rows = (sector_strength.get("sectors") or []) if isinstance(sector_strength, dict) else []
    sector_meta = {
        (s.get("sector") or ""): s for s in sector_rows if isinstance(s, dict) and s.get("sector")
    }
    avoid_sectors = set(((sector_strength.get("summary") or {}).get("avoid_sectors") or [])) if isinstance(sector_strength, dict) else set()

    regime = market_context.get("regime") or "NEUTRAL"
    regime_multiplier = float(market_context.get("regime_multiplier", 0.5))
    regime_score = _regime_to_score(regime)
    global_risk = _global_risk_score(market_context)

    ensemble = _build_ensemble(config)
    conviction_scorer = ConvictionScorer()

    # Get all symbols
    symbols = get_nifty100_symbols()
    if not symbols:
        stocks_file = PROJECT_ROOT / "stocks.json"
        if stocks_file.exists():
            with open(stocks_file) as f:
                data = json.load(f)
            symbols = [s['symbol'] for s in data.get('nifty_100', [])]

    print(f"Scanning {len(symbols)} stocks...")
    print(f"Regime: {regime} (multiplier: {regime_multiplier})")

    candidates = []
    scanned = 0
    failed = 0
    sector_members: Dict[str, List[Dict[str, Any]]] = {}
    asof_date = data_health.get("last_trading_day")

    for symbol in symbols:
        # Skip known failures
        if symbol in KNOWN_FAILURES:
            candidates.append({
                "symbol": symbol,
                "signal": "SKIP",
                "conviction": 0,
                "grade": "D",
                "risk_pct": 0,
                "skip_reasons": ["Known yfinance failure"],
                "should_skip": True,
            })
            failed += 1
            continue

        try:
            df = _load_snapshot_df(run_dir, symbol)
            if df is None or len(df) < 50:
                candidates.append({
                    "symbol": symbol,
                    "signal": "SKIP",
                    "conviction": 0,
                    "grade": "D",
                    "risk_pct": 0,
                    "skip_reasons": ["Missing/invalid snapshot data"],
                    "should_skip": True,
                })
                failed += 1
                continue

            analysis = _analyze_stock_raw(symbol, df, config, regime=regime, ensemble=ensemble)
            # Attach pinned meta (earnings/fundamentals) if available
            meta = meta_by_symbol.get(symbol)
            if isinstance(meta, dict):
                analysis["meta"] = {
                    "earnings": meta.get("earnings"),
                    "fundamentals": meta.get("fundamentals"),
                }
            # Attach sector RS snapshot meta if available
            sec_name = analysis.get("sector") or "Unknown"
            sec_row = sector_meta.get(sec_name)
            if isinstance(sec_row, dict):
                analysis["sector_meta"] = {
                    "rank": sec_row.get("rank"),
                    "strength": sec_row.get("strength"),
                    "rs_score": sec_row.get("rs_score"),
                    "monthly_return": sec_row.get("monthly_return"),
                    "weekly_return": sec_row.get("weekly_return"),
                    "top_stocks": sec_row.get("top_stocks"),
                }
            # Aggregate sector stats for ranking (from the same price data)
            sector = analysis.get("sector") or "Unknown"
            sector_score = (0.7 * float(analysis.get("ret_20d", 0))) + (0.3 * float(analysis.get("ret_5d", 0)))
            analysis["sector_score"] = round(sector_score, 2)
            sector_members.setdefault(sector, []).append({"symbol": symbol, "score": sector_score})
            candidates.append(analysis)
            scanned += 1

            # Print progress
            if scanned % 20 == 0:
                print(f"  Scanned {scanned} stocks...")

        except Exception as e:
            candidates.append({
                "symbol": symbol,
                "signal": "SKIP",
                "conviction": 0,
                "grade": "D",
                "risk_pct": 0,
                "skip_reasons": [f"Error: {str(e)}"],
                "should_skip": True,
            })
            failed += 1

    # -------------------------------------------------------------------------
    # Sector ranking (computed from universe returns; avoids extra network calls)
    # -------------------------------------------------------------------------
    sector_avg = {}
    for sector, members in sector_members.items():
        if not members:
            continue
        sector_avg[sector] = float(np.mean([m["score"] for m in members]))

    sorted_sectors = sorted(sector_avg.items(), key=lambda x: x[1], reverse=True)
    sector_rank = {sector: idx + 1 for idx, (sector, _) in enumerate(sorted_sectors)}
    total_sectors = len(sector_rank)

    sector_leaders = {
        sector: set([m["symbol"] for m in sorted(members, key=lambda x: x["score"], reverse=True)[:2]])
        for sector, members in sector_members.items()
        if members
    }

    # -------------------------------------------------------------------------
    # Conviction scoring + skip reasons (2nd pass)
    # -------------------------------------------------------------------------
    min_liquidity_cr = float((config.get("risk_limits") or {}).get("min_liquidity_cr", 10.0))
    min_conviction = int((config.get("conviction") or {}).get("min_for_trade", 40))

    for c in candidates:
        if c.get("should_skip"):
            continue

        sector = c.get("sector") or "Unknown"
        sec_row = sector_meta.get(sector)
        if isinstance(sec_row, dict) and sec_row.get("rank"):
            rank = int(sec_row.get("rank"))
            strength = str(sec_row.get("strength") or "WEAK")
            is_leader = bool(c.get("symbol") in set(sec_row.get("top_stocks") or []))
        else:
            rank = int(sector_rank.get(sector, total_sectors + 1))
            strength = _sector_strength_from_rank(rank, total_sectors) if rank <= total_sectors else "WEAK"
            is_leader = bool(c.get("symbol") in sector_leaders.get(sector, set()))

        inputs = c.pop("_conviction_inputs", {}) or {}

        level, score, factors, reasoning = conviction_scorer.calculate_conviction(
            technical_score=int(inputs.get("technical_score", 0)),
            signal_details=(inputs.get("signal_details") or {}),
            active_signals=(inputs.get("active_signals") or []),
            regime_score=regime_score,
            mtf_alignment=int(c.get("mtf_alignment", 0)),
            global_risk_score=global_risk,
            sector_rank=rank,
            sector_strength=strength,
            is_sector_leader=is_leader,
            relative_strength=0.0,
            distance_to_entry=float(inputs.get("distance_to_entry", 0)),
            days_since_breakout=int(inputs.get("days_since_breakout", 0)),
            volume_confirmation=bool(inputs.get("volume_confirmation", False)),
        )

        conviction = int(round(float(score)))
        grade = level.label
        risk_pct = float(((config.get("conviction") or {}).get("grades", {}).get(grade, {}) or {}).get("risk_pct", 0))

        # Attach scoring context
        c["sector_rank"] = rank
        c["sector_strength"] = strength
        c["is_sector_leader"] = is_leader
        c["conviction"] = conviction
        c["grade"] = grade
        c["risk_pct"] = risk_pct
        c["conviction_factors"] = {
            "technical": round(factors.technical_score, 1),
            "confluence": round(factors.confluence_score, 1),
            "context": round(factors.context_score, 1),
            "sector": round(factors.sector_score, 1),
            "timing": round(factors.timing_score, 1),
            "historical": round(factors.historical_score, 1),
        }
        c["conviction_inputs"] = {
            "technical_score": int(inputs.get("technical_score", 0)),
            "active_signals": inputs.get("active_signals", []),
            "signal_details": inputs.get("signal_details", {}),
            "distance_to_entry_pct": float(inputs.get("distance_to_entry", 0)),
        }

        # Build skip reasons (PM-style hard filters)
        skip_reasons: List[str] = []

        # Data freshness (must match consensus as-of date)
        last_date = (c.get("data") or {}).get("last_date")
        if asof_date:
            if last_date != asof_date:
                skip_reasons.append(f"Stale data: {last_date} != {asof_date}")
        else:
            skip_reasons.append("Unknown as-of date (data_health.last_trading_day missing)")

        # Liquidity
        adv_cr = float((c.get("technicals") or {}).get("adv_value_cr", 0))
        if adv_cr < min_liquidity_cr:
            skip_reasons.append(f"Low liquidity: {adv_cr:.1f} Cr < {min_liquidity_cr:.1f} Cr")

        # Earnings / event risk (pinned meta, fail-conservative)
        earnings = ((c.get("meta") or {}).get("earnings") or {})
        e_status = earnings.get("status")
        e_days = earnings.get("days_to")
        if e_status == "BLOCK":
            skip_reasons.append(f"Earnings risk: BLOCK ({e_days} days)")

        # Fundamentals gate (pinned meta)
        fundamentals = ((c.get("meta") or {}).get("fundamentals") or {})
        f_grade = fundamentals.get("grade")
        f_mult = fundamentals.get("multiplier")
        if f_mult == 0.0 or f_grade == "D":
            skip_reasons.append(f"Fundamentals grade too weak: {f_grade or 'UNKNOWN'}")

        # Long-only gating
        if c.get("signal") not in ("BUY", "STRONG_BUY"):
            skip_reasons.append(f"Not a long signal: {c.get('signal')}")

        # MTF alignment
        if int(c.get("mtf_alignment", 0)) < 0:
            skip_reasons.append("MTF conflict")

        # Sector weakness
        if strength == "VERY_WEAK":
            skip_reasons.append(f"Weak sector: {sector} (Rank {rank})")
        if sector in avoid_sectors:
            skip_reasons.append(f"Avoid sector (rotation): {sector}")

        # Trend filter (200 EMA)
        ema200 = float((c.get("technicals") or {}).get("ema200", 0))
        if ema200 and float(c.get("price", 0)) < ema200:
            skip_reasons.append("Below 200 EMA")

        # Conviction threshold
        if conviction < min_conviction:
            skip_reasons.append(f"Low conviction: {conviction} < {min_conviction}")

        # Risk/reward
        rr = float((c.get("setup") or {}).get("rr_ratio", 0))
        if rr < 1.5:
            skip_reasons.append(f"Poor R:R ratio: {rr:.2f} < 1.5")

        # Extreme overbought
        rsi = float((c.get("technicals") or {}).get("rsi", 0))
        if rsi > 80:
            skip_reasons.append(f"Overbought: RSI {rsi:.1f} > 80")

        c["skip_reasons"] = skip_reasons
        c["should_skip"] = len(skip_reasons) > 0

    # Sort by conviction (highest first)
    candidates.sort(
        key=lambda x: (
            x.get("conviction", 0),
            (x.get("setup") or {}).get("rr_ratio", 0),
        ),
        reverse=True,
    )

    # Add rank
    for rank, candidate in enumerate(candidates, 1):
        candidate['rank'] = rank

    # Summary stats
    tradeable = [c for c in candidates if not c.get('should_skip', True)]
    buy_signals = [c for c in tradeable if c.get('signal') in ['BUY', 'STRONG_BUY']]

    summary = {
        'scan_timestamp': datetime.now().isoformat(),
        'asof_date': asof_date,
        'total_scanned': len(symbols),
        'successful_scans': scanned,
        'failed_scans': failed,
        'tradeable_candidates': len(tradeable),
        'buy_signals': len(buy_signals),
        'regime': regime,
        'regime_multiplier': regime_multiplier
    }

    output = {
        'summary': summary,
        'sector_ranking': [
            {'sector': sector, 'rank': sector_rank[sector], 'score': round(score, 2)}
            for sector, score in sorted_sectors
        ],
        'candidates': candidates
    }

    # Convert numpy types to Python native types
    output = to_python_types(output)

    # Save to run directory
    output_path = run_dir / "candidates.json"
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nScan Summary:")
    print(f"  Total: {len(symbols)}")
    print(f"  Scanned: {scanned}")
    print(f"  Failed: {failed}")
    print(f"  Tradeable: {len(tradeable)}")
    print(f"  Buy Signals: {len(buy_signals)}")

    if buy_signals:
        print(f"\n  Top 5 by Conviction:")
        for c in buy_signals[:5]:
            print(f"    {c['rank']}. {c['symbol']}: {c['conviction']}/100 ({c['signal']}) - {c['grade']}")

    return output


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scan_universe.py <run_dir>")
        print("Example: python scan_universe.py journal/runs/2026-01-17_0830")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"Error: Run directory does not exist: {run_dir}")
        sys.exit(1)

    # Check that market_context.json exists
    if not (run_dir / "market_context.json").exists():
        print("Error: market_context.json not found. Run build_context.py first.")
        sys.exit(1)

    if not (run_dir / "data_health.json").exists():
        print("Error: data_health.json not found. Run prepare_data.py first.")
        sys.exit(1)

    scan_universe(run_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()
