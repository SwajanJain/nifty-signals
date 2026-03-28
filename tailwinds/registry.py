"""Theme registry - loads and queries macro themes from JSON."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from config import TAILWIND_THEMES_FILE
from .models import Theme, ThemeCategory


class ThemeRegistry:
    """Loads and queries the macro theme registry."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or TAILWIND_THEMES_FILE
        self._themes: List[Theme] = []
        self._load()

    def _load(self):
        """Load themes from JSON file."""
        try:
            with open(self.path) as f:
                data = json.load(f)

            self._themes = []
            for entry in data.get("themes", []):
                theme = Theme(
                    id=entry["id"],
                    name=entry["name"],
                    category=entry["category"],
                    description=entry.get("description", ""),
                    direction=entry["direction"],
                    strength=entry["strength"],
                    affected_sectors=entry.get("affected_sectors", {}),
                    affected_stocks=entry.get("affected_stocks", []),
                    evidence=entry.get("evidence", []),
                    started=entry.get("started", ""),
                    expected_duration=entry.get("expected_duration", ""),
                    last_reviewed=entry.get("last_reviewed", ""),
                    active=entry.get("active", True),
                )
                self._themes.append(theme)

        except FileNotFoundError:
            self._themes = []
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error loading themes: {e}")
            self._themes = []

    def reload(self):
        """Reload themes from disk."""
        self._load()

    def get_all_themes(self) -> List[Theme]:
        return list(self._themes)

    def get_active_themes(self) -> List[Theme]:
        return [t for t in self._themes if t.active]

    def get_themes_for_sector(self, sector: str) -> List[Theme]:
        """Get all active themes that affect a given sector."""
        return [
            t
            for t in self._themes
            if t.active and sector in t.affected_sectors
        ]

    def get_themes_for_stock(self, symbol: str) -> List[Theme]:
        """Get all active themes that specifically mention a stock."""
        return [
            t
            for t in self._themes
            if t.active and symbol in t.affected_stocks
        ]

    def get_themes_by_category(self, category: str) -> List[Theme]:
        return [
            t for t in self._themes if t.active and t.category == category
        ]

    def get_tailwind_themes(self) -> List[Theme]:
        return [
            t for t in self._themes if t.active and t.direction == "TAILWIND"
        ]

    def get_headwind_themes(self) -> List[Theme]:
        return [
            t for t in self._themes if t.active and t.direction == "HEADWIND"
        ]

    def get_all_sectors(self) -> List[str]:
        """Get all unique sectors mentioned across themes."""
        sectors = set()
        for t in self._themes:
            if t.active:
                sectors.update(t.affected_sectors.keys())
        return sorted(sectors)

    def get_sector_theme_summary(self) -> Dict[str, Dict]:
        """Get a summary of tailwind/headwind count and net strength per sector."""
        summary = {}
        for sector in self.get_all_sectors():
            themes = self.get_themes_for_sector(sector)
            tailwinds = [t for t in themes if t.direction == "TAILWIND"]
            headwinds = [t for t in themes if t.direction == "HEADWIND"]

            tw_strength = sum(
                t.strength * t.affected_sectors.get(sector, 0)
                for t in tailwinds
            )
            hw_strength = sum(
                t.strength * t.affected_sectors.get(sector, 0)
                for t in headwinds
            )

            summary[sector] = {
                "tailwind_count": len(tailwinds),
                "headwind_count": len(headwinds),
                "net_strength": tw_strength - hw_strength,
                "top_theme": max(themes, key=lambda t: t.strength).name if themes else "",
            }
        return summary
