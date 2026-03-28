"""Fundamental screening strategies."""

from .value import ValueScreen
from .growth import GrowthScreen
from .quality import QualityScreen
from .garp import GARPScreen
from .dividend import DividendScreen

SCREENS = {
    'value': ValueScreen,
    'growth': GrowthScreen,
    'quality': QualityScreen,
    'garp': GARPScreen,
    'dividend': DividendScreen,
}


def get_screen(name: str):
    """Get a screen class by name."""
    cls = SCREENS.get(name.lower())
    if cls is None:
        raise ValueError(
            f"Unknown screen: {name}. Available: {', '.join(SCREENS.keys())}"
        )
    return cls()
