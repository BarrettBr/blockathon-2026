"""Top-level API router aggregator."""

from handlers import router

# Re-export core helpers for tests/diagnostics.
from core import *  # noqa: F401,F403
