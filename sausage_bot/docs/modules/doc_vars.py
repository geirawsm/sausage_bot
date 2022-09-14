#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from pathlib import Path
from ...funcs import _vars

# Folders
DOCS_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = _vars.ROOT_DIR

# Files
docs_file = DOCS_DIR / 'documentation.md'
