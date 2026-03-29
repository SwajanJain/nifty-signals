"""Supply Chain Mapper (E4) — Map macro themes to beneficiary stocks.

Uses a "picks and shovels" approach: when a theme like "EV adoption"
is surging, who actually benefits? Not just the obvious EV makers but
battery suppliers, charging infra, copper/lithium miners, and auto
ancillaries.

Each theme maps stocks into four roles:
  - direct        : Companies building the core product/service
  - supply_chain  : Component suppliers and enablers
  - raw_material  : Upstream commodity / input providers
  - infra         : Infrastructure providers that scale with the theme
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fundamentals.models import FundamentalProfile


# ---------------------------------------------------------------------------
# Static theme -> beneficiary mapping (expandable)
# ---------------------------------------------------------------------------

THEME_BENEFICIARIES: Dict[str, Dict[str, Any]] = {
    "ev_adoption": {
        "description": "Electric Vehicle Transition",
        "direct": ["TATAMOTORS", "M&M", "HEROMOTOCO", "BAJAJ-AUTO", "MARUTI"],
        "supply_chain": [
            "EXIDEIND", "AMARAJABAT", "BOSCHLTD", "MOTHERSON",
            "SUNDRMFAST", "BHARATFORG",
        ],
        "raw_material": ["HINDALCO", "TATASTEEL", "VEDL", "NMDC"],
        "infra": ["TATAPOWER", "ADANIGREEN", "NTPC", "POWERGRID"],
    },
    "data_center_ai": {
        "description": "AI & Data Center Build-out",
        "direct": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM"],
        "supply_chain": ["POLYCAB", "HAVELLS", "VOLTAS", "BLUESTARLT"],
        "raw_material": ["HINDALCO", "VEDL"],
        "infra": ["ADANIGREEN", "TATAPOWER", "NTPC"],
    },
    "china_plus_one": {
        "description": "Manufacturing Shift from China",
        "direct": ["DIXON", "AMBER", "KAYNES"],
        "supply_chain": ["POLYMED", "AUROPHARMA", "DRREDDY", "CIPLA"],
        "raw_material": ["TATASTEEL", "HINDALCO", "JSWSTEEL"],
        "infra": [],
    },
    "defense_indigenization": {
        "description": "Make in India Defense",
        "direct": ["HAL", "BEL", "COCHINSHIP", "GRSE"],
        "supply_chain": ["BHEL", "BHARATFORG", "MAZDOCK"],
        "raw_material": ["TATASTEEL", "HINDALCO", "MIDHANI"],
        "infra": [],
    },
    "green_hydrogen": {
        "description": "National Green Hydrogen Mission",
        "direct": ["ADANIGREEN", "RELIANCE", "NTPC", "IOC", "GAIL"],
        "supply_chain": ["THERMAX", "LINDE", "SIEMENS", "ABB"],
        "raw_material": ["VEDL", "HINDALCO"],
        "infra": ["POWERGRID", "TATAPOWER"],
    },
    "infra_buildout": {
        "description": "National Infrastructure Pipeline",
        "direct": ["LT", "ULTRACEMCO", "AMBUJACEM", "SHREECEM", "ACC"],
        "supply_chain": [
            "CUMMINSIND", "THERMAX", "SIEMENS", "ABB", "KEC",
        ],
        "raw_material": ["TATASTEEL", "JSWSTEEL", "NMDC", "COALINDIA"],
        "infra": ["POWERGRID", "NTPC"],
    },
    "digital_payments": {
        "description": "UPI & Digital Finance",
        "direct": ["PAYTM", "BAJFINANCE", "SBICARD"],
        "supply_chain": ["TCS", "INFY", "HCLTECH"],
        "raw_material": [],
        "infra": ["BHARTIARTL", "JIO"],
    },
    "pharma_crams": {
        "description": "Pharma CRAMS/CDMO",
        "direct": ["DIVIS", "LALPATHLAB", "SYNGENE"],
        "supply_chain": ["AUROPHARMA", "DRREDDY", "CIPLA", "SUNPHARMA"],
        "raw_material": ["PIIND", "AARTI"],
        "infra": [],
    },
    "premiumization": {
        "description": "Consumer Premiumization",
        "direct": ["TITAN", "DMART", "TRENT", "PAGEIND"],
        "supply_chain": ["ASIANPAINT", "PIDILITIND", "BERGEPAINT"],
        "raw_material": [],
        "infra": [],
    },
    "real_estate_cycle": {
        "description": "Housing & Real Estate Recovery",
        "direct": [
            "DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "BRIGADE",
        ],
        "supply_chain": [
            "ULTRACEMCO", "AMBUJACEM", "PIDILITIND", "ASIANPAINT",
        ],
        "raw_material": ["TATASTEEL", "JSWSTEEL"],
        "infra": ["POLYCAB", "HAVELLS"],
    },
}

# Ordered priority for role labels (used when a stock appears in multiple roles)
ROLE_PRIORITY = ["direct", "supply_chain", "raw_material", "infra"]

ROLE_LABEL_MAP = {
    "direct": "DIRECT",
    "supply_chain": "SUPPLY_CHAIN",
    "raw_material": "RAW_MATERIAL",
    "infra": "INFRA",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SupplyChainResult:
    """Supply-chain mapping result for a single stock."""

    symbol: str
    theme_exposures: List[Dict[str, str]] = field(default_factory=list)
    # Each dict: {theme, role, description}
    theme_count: int = 0
    strongest_theme: str = ""
    beneficiary_type: str = ""  # "DIRECT", "SUPPLY_CHAIN", "RAW_MATERIAL", "INFRA"
    diversification_score: int = 0  # 0-100


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class SupplyChainMapper:
    """Map macro themes to specific beneficiary stocks."""

    def __init__(
        self,
        beneficiaries: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.beneficiaries = beneficiaries or THEME_BENEFICIARIES

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def map_stock(self, symbol: str) -> SupplyChainResult:
        """Return all theme exposures for a given stock symbol.

        Parameters
        ----------
        symbol : NSE symbol (e.g. "TATAMOTORS").

        Returns
        -------
        SupplyChainResult with every theme + role the stock appears in,
        its strongest theme, primary beneficiary type, and a
        diversification score.
        """
        symbol_upper = symbol.upper()
        exposures: List[Dict[str, str]] = []

        for theme_key, mapping in self.beneficiaries.items():
            description = mapping.get("description", theme_key)
            for role in ROLE_PRIORITY:
                stocks_in_role = mapping.get(role, [])
                if symbol_upper in [s.upper() for s in stocks_in_role]:
                    exposures.append({
                        "theme": theme_key,
                        "role": ROLE_LABEL_MAP[role],
                        "description": description,
                    })
                    break  # one role per theme for this stock

        if not exposures:
            return SupplyChainResult(symbol=symbol_upper)

        # Strongest theme: first "direct" exposure, else first exposure
        strongest = ""
        primary_type = ""
        for exp in exposures:
            if exp["role"] == "DIRECT":
                strongest = exp["theme"]
                primary_type = "DIRECT"
                break
        if not strongest:
            strongest = exposures[0]["theme"]
            primary_type = exposures[0]["role"]

        # Diversification: how many distinct, non-correlated themes?
        # More themes and more role diversity = higher score.
        unique_themes = {e["theme"] for e in exposures}
        unique_roles = {e["role"] for e in exposures}
        theme_diversity = min(len(unique_themes), 6)  # cap at 6
        role_diversity = len(unique_roles)

        # Score: up to 60 for theme count (10 each, max 6) + up to 40 for
        # role diversity (10 each, max 4 roles).
        diversification = min(
            100,
            theme_diversity * 10 + role_diversity * 10,
        )

        return SupplyChainResult(
            symbol=symbol_upper,
            theme_exposures=exposures,
            theme_count=len(unique_themes),
            strongest_theme=strongest,
            beneficiary_type=primary_type,
            diversification_score=diversification,
        )

    def find_beneficiaries(self, theme: str) -> Dict[str, List[str]]:
        """Return {role: [symbols]} for a given theme key.

        Parameters
        ----------
        theme : Key in THEME_BENEFICIARIES (e.g. "ev_adoption").

        Raises
        ------
        ValueError if the theme key is not found.
        """
        theme_lower = theme.lower()
        mapping = self.beneficiaries.get(theme_lower)
        if mapping is None:
            available = ", ".join(sorted(self.beneficiaries.keys()))
            raise ValueError(
                f"Unknown theme: {theme}. Available: {available}"
            )

        result: Dict[str, List[str]] = {}
        for role in ROLE_PRIORITY:
            stocks = mapping.get(role, [])
            if stocks:
                result[role] = list(stocks)
        return result

    def find_theme_plays(
        self,
        theme: str,
        profiles: Dict[str, FundamentalProfile],
    ) -> List[Dict[str, Any]]:
        """Return ranked beneficiaries for a theme with fundamental scores.

        Parameters
        ----------
        theme    : Theme key (e.g. "infra_buildout").
        profiles : {symbol: FundamentalProfile} of available stocks.

        Returns
        -------
        List of dicts sorted by combined score (descending):
            {symbol, role, fundamental_score, description}
        """
        roles = self.find_beneficiaries(theme)
        description = self.beneficiaries[theme.lower()].get(
            "description", theme
        )

        scored: List[Dict[str, Any]] = []

        for role, symbols in roles.items():
            for symbol in symbols:
                profile = profiles.get(symbol) or profiles.get(symbol.upper())
                if profile is None:
                    continue

                # Simple fundamental score from profile fields
                fund_score = self._quick_fundamental_score(profile)

                # Role weight: direct stocks get a boost
                role_weight = {
                    "direct": 1.2,
                    "supply_chain": 1.0,
                    "raw_material": 0.9,
                    "infra": 0.85,
                }.get(role, 1.0)

                combined = int(round(fund_score * role_weight))

                scored.append({
                    "symbol": symbol,
                    "role": ROLE_LABEL_MAP[role],
                    "fundamental_score": fund_score,
                    "combined_score": min(100, combined),
                    "description": description,
                    "key_metrics": {
                        "ROCE": f"{profile.roce or 0:.1f}%",
                        "ROE": f"{profile.roe or 0:.1f}%",
                        "Revenue Growth 3Y": f"{profile.revenue_growth_3y:.0f}%",
                        "PE": f"{profile.pe_ratio or 0:.1f}",
                        "Market Cap": f"{profile.market_cap:.0f} Cr",
                    },
                })

        scored.sort(key=lambda x: x["combined_score"], reverse=True)
        return scored

    def get_all_themes(self) -> List[Dict[str, str]]:
        """Return a list of all available themes with descriptions."""
        return [
            {"theme": key, "description": mapping.get("description", key)}
            for key, mapping in self.beneficiaries.items()
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _quick_fundamental_score(profile: FundamentalProfile) -> int:
        """Compute a quick 0-100 fundamental score from profile fields.

        Simplified scoring for ranking within a theme bucket:
          - Profitability (ROCE, ROE)     : 0-30
          - Growth (revenue, profit)       : 0-30
          - Financial health (D/E, ICR)    : 0-20
          - Valuation (PE reasonableness)  : 0-20
        """
        score = 0

        # Profitability
        roce = profile.roce or 0
        roe = profile.roe or 0
        if roce >= 20:
            score += 20
        elif roce >= 15:
            score += 15
        elif roce >= 10:
            score += 10

        if roe >= 18:
            score += 10
        elif roe >= 12:
            score += 7
        elif roe >= 8:
            score += 4

        # Growth
        if profile.revenue_growth_3y >= 25:
            score += 15
        elif profile.revenue_growth_3y >= 15:
            score += 10
        elif profile.revenue_growth_3y >= 8:
            score += 5

        if profile.profit_growth_3y >= 30:
            score += 15
        elif profile.profit_growth_3y >= 20:
            score += 10
        elif profile.profit_growth_3y >= 10:
            score += 5

        # Financial health
        if profile.is_debt_free or profile.debt_to_equity < 0.3:
            score += 12
        elif profile.debt_to_equity < 0.7:
            score += 8
        elif profile.debt_to_equity < 1.0:
            score += 4

        if profile.interest_coverage >= 5:
            score += 8
        elif profile.interest_coverage >= 3:
            score += 5

        # Valuation (not too expensive)
        pe = profile.pe_ratio or 0
        peg = profile.peg_ratio or 0
        if 0 < pe <= 15:
            score += 15
        elif 0 < pe <= 25:
            score += 12
        elif 0 < pe <= 40:
            score += 7
        elif pe > 60:
            score += 0  # Too expensive
        else:
            score += 5

        if 0 < peg <= 1.0:
            score += 5
        elif 0 < peg <= 1.5:
            score += 3

        return min(100, score)
