"""Paste into app/domain/strategy/plugins/catalog.py.

This file is a documentation snippet, not a standalone runtime module.
"""

# Add beside the other plugin imports:
from .macd import MACDStrategy


# Add inside register_all(registry):
registry.register(MACDStrategy)

