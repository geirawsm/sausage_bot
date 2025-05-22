#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'doc_envs: envs for autodoc'
from pathlib import Path
from ...util import envs

# Folders
DOCS_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = envs.ROOT_DIR

# Files
docs_file = DOCS_DIR / 'documentation.md'

# Variables
skip_keyword = '#autodoc skip#'
skip_folder_or_file = ['/docs/', '/test/', '__init__', '/testing/']
skip_function = ['setup', '__init__', 'on_ready']
skip_variable = ['self', 'ctx']