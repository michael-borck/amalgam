"""Shared pytest fixtures for the Amalgam analysis tests."""

import sys
from pathlib import Path

# Make `analysis`, `registry`, and `builders` importable without installation.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))