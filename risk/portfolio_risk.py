"""Portfolio Risk Analytics — VaR, CVaR, Correlation, Stress Testing.

Provides quantitative risk metrics for portfolio-level analysis:
  - Historical VaR: direct percentile of return distribution
  - Parametric VaR: normal distribution assumption
  - CVaR (Expected Shortfall): average loss beyond VaR
  - Portfolio VaR: accounts for diversification via covariance
  - Correlation matrix: identifies concentrated risk
  - Stress tests: replay historical crash scenarios
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

try:
    from config import PORTFOLIO_RISK_CONFIG
except ImportError:
    PORTFOLIO_RISK_CONFIG = {}

_CFG = {
    'var_confidence': 0.95,
    'var_method': 'historical',
    'max_portfolio_var_pct': 5.0,
    'correlation_threshold_reduce': 0.7,
    'correlation_reduce_factor': 0.5,
}
_CFG.update(PORTFOLIO_RISK_CONFIG)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class VaRResult:
    """Value at Risk result for a single asset or portfolio."""
    var_pct: float = 0.0          # VaR as percentage
    var_amount: float = 0.0       # VaR in currency
    cvar_pct: float = 0.0         # CVaR (Expected Shortfall) as percentage
    cvar_amount: float = 0.0
    confidence: float = 0.95
    method: str = 'historical'
    period_days: int = 1          # Holding period


@dataclass
class CorrelationResult:
    """Pairwise correlation analysis."""
    matrix: Optional[pd.DataFrame] = None
    high_pairs: List[Tuple[str, str, float]] = field(default_factory=list)
    avg_correlation: float = 0.0


@dataclass
class StressResult:
    """Result of a stress test scenario."""
    scenario: str = ''
    portfolio_loss_pct: float = 0.0
    portfolio_loss_amount: float = 0.0
    individual_losses: Dict[str, float] = field(default_factory=dict)


@dataclass
class PortfolioRiskReport:
    """Complete portfolio risk report."""
    var: VaRResult = field(default_factory=VaRResult)
    diversified_var: VaRResult = field(default_factory=VaRResult)
    correlation: CorrelationResult = field(default_factory=CorrelationResult)
    stress_tests: List[StressResult] = field(default_factory=list)
    individual_var: Dict[str, VaRResult] = field(default_factory=dict)
    total_value: float = 0.0
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stress Scenarios (historical drawdowns)
# ---------------------------------------------------------------------------

STRESS_SCENARIOS = {
    'covid_2020': {
        'description': 'COVID Crash (Mar 2020)',
        'nifty_drop': -38.0,
        'sector_impact': {
            'Banking': -45, 'Financial Services': -42, 'Auto': -40,
            'Real Estate': -50, 'Metals': -35, 'Oil & Gas': -40,
            'IT': -25, 'Pharma': -15, 'FMCG': -20,
            'Telecom': -25, 'Power': -30, 'Infra': -35,
            'Consumer': -30, 'Cement': -30, 'Insurance': -35,
            'Chemicals': -30, 'Capital Goods': -35, 'Healthcare': -15,
        },
        'default_drop': -35,
    },
    'rate_hike_2022': {
        'description': 'Rate Hike Correction (Jun 2022)',
        'nifty_drop': -17.0,
        'sector_impact': {
            'IT': -30, 'Pharma': -15, 'Banking': -10,
            'Financial Services': -15, 'FMCG': -8,
            'Metals': -25, 'Real Estate': -20, 'Auto': -12,
            'Consumer': -18, 'Chemicals': -22,
        },
        'default_drop': -15,
    },
    'il_fs_2018': {
        'description': 'IL&FS / NBFC Crisis (Sep 2018)',
        'nifty_drop': -15.0,
        'sector_impact': {
            'Financial Services': -40, 'Banking': -25,
            'Real Estate': -35, 'Insurance': -20,
            'Auto': -20, 'FMCG': -5, 'IT': -8,
            'Pharma': -10, 'Infra': -25,
        },
        'default_drop': -12,
    },
}


class PortfolioRiskCalculator:
    """Calculate portfolio-level risk metrics."""

    def __init__(self, confidence: float = None, method: str = None):
        self.confidence = confidence or _CFG['var_confidence']
        self.method = method or _CFG['var_method']

    # ------------------------------------------------------------------
    # Single-asset VaR
    # ------------------------------------------------------------------

    def calculate_var(self, returns: pd.Series, position_value: float = 0,
                      confidence: float = None) -> VaRResult:
        """Calculate VaR and CVaR for a single return series.

        Args:
            returns: Daily return series (fractional, e.g. 0.01 = 1%)
            position_value: Position value for currency VaR
            confidence: Confidence level (default from config)
        """
        conf = confidence or self.confidence
        returns = returns.dropna()

        if len(returns) < 30:
            return VaRResult(confidence=conf, method=self.method)

        if self.method == 'historical':
            var_pct = self._historical_var(returns, conf)
        else:
            var_pct = self._parametric_var(returns, conf)

        cvar_pct = self._calculate_cvar(returns, var_pct)

        return VaRResult(
            var_pct=round(abs(var_pct) * 100, 2),
            var_amount=round(abs(var_pct) * position_value, 2),
            cvar_pct=round(abs(cvar_pct) * 100, 2),
            cvar_amount=round(abs(cvar_pct) * position_value, 2),
            confidence=conf,
            method=self.method,
        )

    def _historical_var(self, returns: pd.Series, confidence: float) -> float:
        """VaR via historical percentile."""
        return np.percentile(returns, (1 - confidence) * 100)

    def _parametric_var(self, returns: pd.Series, confidence: float) -> float:
        """VaR assuming normal distribution."""
        from scipy.stats import norm
        mu = returns.mean()
        sigma = returns.std()
        z = norm.ppf(1 - confidence)
        return mu + z * sigma

    def _calculate_cvar(self, returns: pd.Series, var_threshold: float) -> float:
        """CVaR (Expected Shortfall) = average of losses beyond VaR."""
        tail = returns[returns <= var_threshold]
        return tail.mean() if len(tail) > 0 else var_threshold

    # ------------------------------------------------------------------
    # Portfolio VaR (with diversification)
    # ------------------------------------------------------------------

    def portfolio_var(self, positions: Dict[str, float],
                      returns_data: Dict[str, pd.Series]) -> VaRResult:
        """Portfolio VaR accounting for diversification via covariance.

        Args:
            positions: {symbol: position_value}
            returns_data: {symbol: daily_return_series}
        """
        # Align all return series
        common_syms = [s for s in positions if s in returns_data]
        if len(common_syms) < 2:
            # Single position — no diversification
            if common_syms:
                return self.calculate_var(
                    returns_data[common_syms[0]],
                    positions[common_syms[0]],
                )
            return VaRResult(confidence=self.confidence, method=self.method)

        returns_df = pd.DataFrame({s: returns_data[s] for s in common_syms}).dropna()
        if len(returns_df) < 30:
            return VaRResult(confidence=self.confidence, method=self.method)

        total_value = sum(positions[s] for s in common_syms)
        weights = np.array([positions[s] / total_value for s in common_syms])

        # Covariance matrix
        cov = returns_df.cov().values

        # Portfolio variance: w' * Σ * w
        port_var = np.dot(weights, np.dot(cov, weights))
        port_std = np.sqrt(port_var)
        port_mean = np.dot(weights, returns_df.mean().values)

        from scipy.stats import norm
        z = norm.ppf(1 - self.confidence)
        var_pct = port_mean + z * port_std

        # Portfolio CVaR via simulation of weighted returns
        port_returns = returns_df.values @ weights
        cvar_pct = self._calculate_cvar(pd.Series(port_returns), var_pct)

        return VaRResult(
            var_pct=round(abs(var_pct) * 100, 2),
            var_amount=round(abs(var_pct) * total_value, 2),
            cvar_pct=round(abs(cvar_pct) * 100, 2),
            cvar_amount=round(abs(cvar_pct) * total_value, 2),
            confidence=self.confidence,
            method='portfolio_parametric',
        )

    # ------------------------------------------------------------------
    # Correlation analysis
    # ------------------------------------------------------------------

    def correlation_analysis(self, returns_data: Dict[str, pd.Series],
                             threshold: float = None) -> CorrelationResult:
        """Compute correlation matrix and flag high-correlation pairs."""
        threshold = threshold or _CFG['correlation_threshold_reduce']

        if len(returns_data) < 2:
            return CorrelationResult()

        returns_df = pd.DataFrame(returns_data).dropna()
        if len(returns_df) < 30:
            return CorrelationResult()

        corr = returns_df.corr()

        # Find high-correlation pairs
        high_pairs = []
        symbols = list(corr.columns)
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                c = corr.iloc[i, j]
                if abs(c) >= threshold:
                    high_pairs.append((symbols[i], symbols[j], round(c, 3)))

        high_pairs.sort(key=lambda x: abs(x[2]), reverse=True)

        # Average pairwise correlation
        upper = corr.values[np.triu_indices_from(corr.values, k=1)]
        avg_corr = float(np.mean(upper)) if len(upper) > 0 else 0.0

        return CorrelationResult(
            matrix=corr.round(3),
            high_pairs=high_pairs,
            avg_correlation=round(avg_corr, 3),
        )

    # ------------------------------------------------------------------
    # Correlation-aware position sizing multiplier
    # ------------------------------------------------------------------

    def correlation_size_multiplier(self, new_symbol: str,
                                     existing_symbols: List[str],
                                     returns_data: Dict[str, pd.Series]) -> float:
        """Calculate sizing multiplier based on correlation with existing positions.

        Returns a multiplier between 0.5 and 1.0:
          - Correlation > 0.7 → 0.5x (half size)
          - Correlation > 0.5 → 0.75x (three-quarter size)
          - Otherwise → 1.0x (full size)
        """
        if not existing_symbols or new_symbol not in returns_data:
            return 1.0

        new_returns = returns_data[new_symbol].dropna()
        max_corr = 0.0

        for sym in existing_symbols:
            if sym not in returns_data:
                continue
            other = returns_data[sym].dropna()
            # Align
            aligned = pd.concat([new_returns, other], axis=1).dropna()
            if len(aligned) < 30:
                continue
            c = aligned.corr().iloc[0, 1]
            max_corr = max(max_corr, abs(c))

        if max_corr > _CFG['correlation_threshold_reduce']:
            return _CFG['correlation_reduce_factor']
        elif max_corr > 0.5:
            return 0.75
        return 1.0

    # ------------------------------------------------------------------
    # Stress testing
    # ------------------------------------------------------------------

    def stress_test(self, positions: Dict[str, Dict],
                    scenario_name: str = 'covid_2020') -> StressResult:
        """Apply a historical crash scenario to the portfolio.

        Args:
            positions: {symbol: {'value': float, 'sector': str}}
            scenario_name: Key from STRESS_SCENARIOS
        """
        scenario = STRESS_SCENARIOS.get(scenario_name)
        if not scenario:
            return StressResult(scenario=scenario_name)

        total_value = sum(p['value'] for p in positions.values())
        total_loss = 0.0
        individual = {}

        for sym, pos in positions.items():
            sector = pos.get('sector', 'Unknown')
            drop_pct = scenario['sector_impact'].get(sector, scenario['default_drop'])
            loss = pos['value'] * (drop_pct / 100)
            individual[sym] = round(drop_pct, 1)
            total_loss += loss

        return StressResult(
            scenario=scenario.get('description', scenario_name),
            portfolio_loss_pct=round((total_loss / total_value) * 100, 2) if total_value else 0,
            portfolio_loss_amount=round(total_loss, 2),
            individual_losses=individual,
        )

    # ------------------------------------------------------------------
    # Full report
    # ------------------------------------------------------------------

    def full_report(self, positions: Dict[str, Dict],
                    returns_data: Dict[str, pd.Series]) -> PortfolioRiskReport:
        """Generate complete portfolio risk report.

        Args:
            positions: {symbol: {'value': float, 'sector': str}}
            returns_data: {symbol: daily_return_series}
        """
        pos_values = {s: p['value'] for s, p in positions.items()}
        total_value = sum(pos_values.values())

        # Individual VaR
        individual = {}
        for sym in positions:
            if sym in returns_data:
                individual[sym] = self.calculate_var(
                    returns_data[sym], pos_values[sym]
                )

        # Undiversified VaR (sum of individual)
        undiv_var_amt = sum(v.var_amount for v in individual.values())
        undiv_cvar_amt = sum(v.cvar_amount for v in individual.values())
        undiv = VaRResult(
            var_pct=round(undiv_var_amt / total_value * 100, 2) if total_value else 0,
            var_amount=round(undiv_var_amt, 2),
            cvar_pct=round(undiv_cvar_amt / total_value * 100, 2) if total_value else 0,
            cvar_amount=round(undiv_cvar_amt, 2),
            confidence=self.confidence,
            method='undiversified_sum',
        )

        # Diversified VaR
        div = self.portfolio_var(pos_values, returns_data)

        # Correlation
        corr = self.correlation_analysis(returns_data)

        # Stress tests
        stresses = [
            self.stress_test(positions, name)
            for name in STRESS_SCENARIOS
        ]

        # Warnings
        warnings = []
        if undiv.var_pct > _CFG['max_portfolio_var_pct']:
            warnings.append(
                f"Portfolio VaR ({undiv.var_pct}%) exceeds limit ({_CFG['max_portfolio_var_pct']}%)"
            )
        if corr.avg_correlation > 0.6:
            warnings.append(
                f"High avg correlation ({corr.avg_correlation}) — low diversification"
            )
        for a, b, c in corr.high_pairs:
            warnings.append(f"High correlation: {a} & {b} = {c}")

        return PortfolioRiskReport(
            var=undiv,
            diversified_var=div,
            correlation=corr,
            stress_tests=stresses,
            individual_var=individual,
            total_value=total_value,
            warnings=warnings,
        )
