#!/usr/bin/env python3
"""
Fallback runner — use this if the `rss` command isn't available.
Usage:  python3 run.py <command> [args]
Example: python3 run.py fetch
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rss_reader.main import app
app()
