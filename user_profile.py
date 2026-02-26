"""
User profile management for Bookaboo.

Stores and loads the diner's personal details used when making reservations.
Profile is persisted at ~/.config/restaurant-reservations/user_profile.json
with 0600 permissions.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".config" / "restaurant-reservations"
PROFILE_FILE = CONFIG_DIR / "user_profile.json"

_DEFAULT_PROFILE_PATH = Path(__file__).parent / "config" / "user_profile.json"


@dataclass
class UserProfile:
    first_name: str = "Devin"
    last_name: str = "Pillemer"
    email: str = "devin.pillemer@gmail.com"
    phone: str = "+972-50-724-2120"
    # Booking preferences
    party_size: int = 2
    preferred_time: str = "20:00"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserProfile":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_profile() -> UserProfile:
    """
    Load the user profile from disk.

    Falls back to the bundled default config, and then to hard-coded
    defaults if neither exists.
    """
    for path in (PROFILE_FILE, _DEFAULT_PROFILE_PATH):
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                return UserProfile.from_dict(data)
            except (json.JSONDecodeError, OSError, TypeError):
                continue
    return UserProfile()


def save_profile(profile: UserProfile) -> None:
    """Persist *profile* to disk with 0600 permissions."""
    _ensure_config_dir()
    with PROFILE_FILE.open("w", encoding="utf-8") as fh:
        json.dump(profile.to_dict(), fh, ensure_ascii=False, indent=2)
    PROFILE_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
