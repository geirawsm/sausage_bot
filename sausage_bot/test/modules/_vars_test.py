#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from pathlib import Path

# Folders
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
TEST_DIR = ROOT_DIR / 'test'
PAGES_DIR = TEST_DIR / 'in' / 'pages'
NIFS_DIR = PAGES_DIR / 'nifs'

# Files
kamp_ferdig_fil = 'file://{}'.format(
    (NIFS_DIR / 'kamp_ferdig.html')
)
