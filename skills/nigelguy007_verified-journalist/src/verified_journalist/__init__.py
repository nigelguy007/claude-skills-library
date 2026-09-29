"""Verified Journalist: research, write, and fact-check articles with hard source checks."""

from .config import Settings
from .models import Article
from .pipeline import InsufficientSourcesError, Journalist

__all__ = ["Article", "InsufficientSourcesError", "Journalist", "Settings"]
__version__ = "0.1.0"
