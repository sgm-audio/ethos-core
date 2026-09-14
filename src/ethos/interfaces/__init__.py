"""
ETHOS Interfaces Subsystem
FastAPI REST service and command-line interfaces.
"""

from ethos.interfaces.api import app
from ethos.interfaces.cli import main

__all__ = ["app", "main"]
