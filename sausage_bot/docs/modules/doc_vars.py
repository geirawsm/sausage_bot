#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from pathlib import Path
from ...util import mod_vars

# Folders
DOCS_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = mod_vars.ROOT_DIR

# Files
docs_file = DOCS_DIR / 'documentation.md'
