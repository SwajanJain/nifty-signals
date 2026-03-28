"""Abstract base class for screening strategies."""

from abc import ABC, abstractmethod
from typing import Dict, List

from fundamentals.models import FundamentalProfile, ScreenResult


class BaseScreen(ABC):
    """Abstract base class for screening strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Strategy description."""

    @abstractmethod
    def screen(self, profile: FundamentalProfile) -> ScreenResult:
        """Screen a single stock. Returns ScreenResult."""

    def screen_batch(
        self, profiles: Dict[str, FundamentalProfile]
    ) -> List[ScreenResult]:
        """Screen multiple stocks, return passing ones sorted by score."""
        results = []
        for symbol, profile in profiles.items():
            result = self.screen(profile)
            if result.passes:
                results.append(result)
        return sorted(results, key=lambda r: r.score, reverse=True)
