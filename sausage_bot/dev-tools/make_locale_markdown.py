"""
Flatten the YAML locale files into one markdown file.

Each module (e.g. `common`) gets a section with all its languages:

    # common
    |Line|Lang.|Text|
    |:--|:--:|:--|
    |create_channel.cancel|en|Cancel|
    |create_channel.cancel|nb|Avbryt|

Usage: python sausage_bot/dev-tools/make_flattened_yaml.py [output_file]
(output_file defaults to
`locale_markdown/locale_[year]-[month]-[day]_[hours]-[minutes].md`
next to this script)
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

from sausage_bot.util import envs


def default_out_file() -> Path:
    "locale_markdown/locale_[year]-[month]-[day]_[hours]-[minutes].md"
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    return Path(__file__).parent / "locale_markdown" / f"locale_{stamp}.md"


def get_locale_files() -> list[str]:
    locale_files = os.listdir(envs.LOCALE_DIR)
    return sorted(f for f in locale_files if re.search(r".*\.(.*)\.yml$", f))


def flatten_yaml(yaml_in, parent_key="", sep="."):
    items = {}
    for _key, _value in yaml_in.items():
        new_key = f"{parent_key}{sep}{_key}" if parent_key else str(_key)
        if isinstance(_value, dict):
            items.update(flatten_yaml(_value, new_key, sep=sep))
        else:
            items[new_key] = _value
    return items


def md_escape(text) -> str:
    "Make a value safe for a single markdown table cell"
    return str(text).replace("|", "\\|").replace("\n", "<br>")


def make_section(module: str, rows: list[tuple[str, str, str]]) -> str:
    lines = [
        f"# {module}",
        "|Line|Lang.|Text|",
        "|:--|:--:|:--|",
    ]
    # Stable sort: keeps the language order (en, nb) within each key
    # The key is only written on the first row of each key
    prev_key = None
    for key, lang, text in sorted(rows, key=lambda row: row[0]):
        key_cell = md_escape(key) if key != prev_key else ""
        lines.append(f"|{key_cell}|{lang}|{md_escape(text)}|")
        prev_key = key
    return "\n".join(lines) + "\n"


def main(out_file: Path):
    # Group rows per module (filename without language and extension)
    modules: dict[str, list[tuple[str, str, str]]] = {}
    for _file in get_locale_files():
        with open(envs.LOCALE_DIR / _file, "r", encoding="utf-8") as file_in:
            yaml_in = yaml.safe_load(file_in) or {}
        module, lang, _ = _file.rsplit(".", 2)
        # Locale files have the language code as the single top-level key
        flat = flatten_yaml(yaml_in.get(lang, yaml_in))
        modules.setdefault(module, []).extend(
            (key, lang, text) for key, text in flat.items()
        )
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(
        "\n".join(make_section(m, rows) for m, rows in modules.items()),
        encoding="utf-8",
    )
    print(f"Wrote {out_file}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else default_out_file())
