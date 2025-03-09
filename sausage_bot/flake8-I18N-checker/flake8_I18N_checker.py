import ast
import glob
from collections.abc import Iterator
from typing import NamedTuple
from pathlib import Path
import yaml
import os

ROOT_DIR = Path(__file__).resolve().parent.parent
LOCALE_DIR = ROOT_DIR / 'locale'


def check_yaml_number_lists(i18n_in, yaml_in):
    i18n_in_split = i18n_in.split('.')
    yaml_in_split = yaml_in.split('.')

    # Normally there should only be one extra element if its a list,
    # so anything more than +1 will fail
    if len(yaml_in_split) - len(i18n_in_split) != 1:
        return False
    elif yaml_in_split[-1] in [
            'zero', 'one', 'two', 'few', 'many', 'other'
    ]:
        return True
    else:
        return False


def flatten_yaml(locale_lang, d, parent_key='', sep='.'):
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if locale_lang in new_key:
            new_key = new_key.replace(f'{locale_lang}.', '')
        if isinstance(v, dict):
            items.update(flatten_yaml(locale_lang, v, new_key, sep=sep))
        else:
            items[new_key] = v
    return items


class Flake8ASTErrorInfo(NamedTuple):
    line_number: int
    offset: int
    msg: str
    cls: type  # unused currently, but required


def get_locale_files(name: str) -> list[str]:
    filelist = glob.glob(f'{LOCALE_DIR}/{name}.*.yml', recursive=True)
    # Get module name
    return filelist


class DescribeShouldBeI18N:
    msg = "LC101 Describe decorator argument value \"{}\" is not I18N"

    @classmethod
    def check(cls, node: ast.Name, errors: list[Flake8ASTErrorInfo]) -> None:
        for child in ast.walk(node):
            if not isinstance(child, ast.Name):
                continue
            if not hasattr(child, 'id'):
                continue
            if child.id != 'describe':
                continue
            for kw in child.parent.keywords:
                if not hasattr(kw, 'value'):
                    continue
                if not isinstance(kw.value, ast.Call):
                    _child = kw.value
                    err = Flake8ASTErrorInfo(
                        _child.lineno, _child.col_offset,
                        cls.msg.format(
                            kw.arg
                        ), cls
                    )
                    errors.append(err)
                if not hasattr(kw.value, 'func') or\
                        not hasattr(kw.value.func, 'value') or\
                        not hasattr(kw.value.func.value, 'id'):
                    continue
                else:
                    if kw.value.func.value.id != 'I18N':
                        _child = kw.value.func.value
                        err = Flake8ASTErrorInfo(
                            _child.lineno, _child.col_offset,
                            cls.msg.format(
                                kw.arg
                            ), cls
                        )
                        errors.append(err)


class I18NStringIsNotFound:
    msg110 = "LC110 Could not find I18N string \"{}\" for translation in "\
        "\"{}\" file"
    msg111 = "LC111 I18N should only have one argument, found {}"
    msg112 = "LC112 Locale file \"{}\" not found"

    @classmethod
    def check(cls, node: ast.Name, errors: list[Flake8ASTErrorInfo]) -> None:
        for child in ast.walk(node):
            if not isinstance(child, ast.Name):
                continue
            if not hasattr(child, 'id'):
                continue
            if child.id == 'I18N':
                if not hasattr(child.parent, 'attr'):
                    continue
                if child.parent.attr != 't':
                    continue
                if len(child.parent.parent.args) > 1:
                    err = Flake8ASTErrorInfo(
                        child.lineno, child.col_offset,
                        cls.msg111.format(
                            len(child.parent.parent.args)
                        ), cls
                    )
                    errors.append(err)
                    continue
                if not hasattr(child.parent.parent, 'args'):
                    continue
                for arg in child.parent.parent.args:
                    if not hasattr(arg, 'value'):
                        continue
                    i18n_string = arg.value.split('.')
                    locale_files = get_locale_files(i18n_string[0])
                    if len(locale_files) == 0:
                        err = Flake8ASTErrorInfo(
                            arg.lineno, arg.col_offset,
                            cls.msg112.format(
                                i18n_string[0]
                            ), cls
                        )
                        errors.append(err)
                    for _file in locale_files:
                        with open(_file, 'r', encoding='utf-8') as file_in:
                            yaml_in = yaml.safe_load(file_in)
                        filename = str(_file).split(os.sep)[-1]
                        locale_lang = filename.split('.')[1]
                        yaml_in = flatten_yaml(locale_lang, yaml_in)
                        i18n_compare = '.'.join(i18n_string[1:])
                        if i18n_compare not in yaml_in:
                            for _yaml in yaml_in:
                                num_list_check = check_yaml_number_lists(
                                    i18n_compare, _yaml
                                )
                                if num_list_check:
                                    break
                            if num_list_check is not True:
                                err = Flake8ASTErrorInfo(
                                    child.lineno, child.col_offset,
                                    cls.msg110.format(
                                        arg.value,
                                        locale_lang
                                    ), cls
                                )
                                errors.append(err)
                                continue


class GroupsShouldHaveLocale_str:
    msg = "LC120 Discord Groups should use \"locale_str\" before I18N in description"

    @classmethod
    def check(cls, node: ast.Name, errors: list[Flake8ASTErrorInfo]) -> None:
        for child in ast.walk(node):
            if not isinstance(child, ast.Name):
                continue
            if not hasattr(child, 'id'):
                continue
            if child.id == 'I18N':
                if not hasattr(child, 'parent'):
                    continue
                if not hasattr(child.parent, 'parent'):
                    continue
                if not hasattr(child.parent.parent, 'parent'):
                    continue
                if not hasattr(child.parent.parent.parent, 'parent'):
                    continue
                if not isinstance(child.parent.parent.parent, ast.keyword):
                    continue
                if hasattr(child.parent.parent.parent.parent, 'arg') and\
                        child.parent.parent.parent.parent.arg != 'description':
                    continue
                if hasattr(child.parent.parent.parent, 'arg') and\
                        child.parent.parent.parent.arg != 'description':
                    continue
                if not hasattr(child.parent.parent.parent, 'func'):
                    err = Flake8ASTErrorInfo(
                        child.lineno, child.col_offset,
                        cls.msg, cls
                    )
                    errors.append(err)
                    continue
                if not hasattr(child.parent.parent.parent.func, 'id'):
                    err = Flake8ASTErrorInfo(
                        child.lineno, child.col_offset,
                        cls.msg, cls
                    )
                    errors.append(err)
                    continue
                if child.parent.parent.parent.func.id != 'locale_str':
                    err = Flake8ASTErrorInfo(
                        child.lineno, child.col_offset,
                        cls.msg, cls
                    )
                    errors.append(err)


class DiscordCommandsShouldHaveLocale_str:
    msg = "LC130 Discord Commands should use \"locale_str\" before I18N in description"

    @classmethod
    def check(cls, node, errors: list[Flake8ASTErrorInfo]) -> None:
        for child in ast.walk(node):
            if hasattr(child, 'decorator_list'):
                for dec in child.decorator_list:
                    if not isinstance(dec, ast.Call):
                        continue
                    if not hasattr(dec, 'func'):
                        continue
                    if not hasattr(dec.func, 'attr'):
                        continue
                    if dec.func.attr != 'command':
                        continue
                    if not hasattr(dec, 'keywords'):
                        continue
                    for kw in dec.keywords:
                        if kw.arg == 'description':
                            if not isinstance(kw.value, ast.Call):
                                err = Flake8ASTErrorInfo(
                                    kw.lineno, kw.col_offset,
                                    cls.msg, cls
                                )
                                errors.append(err)
                                continue
                            if not isinstance(kw.value.func, ast.Name):
                                err = Flake8ASTErrorInfo(
                                    kw.lineno, kw.col_offset,
                                    cls.msg, cls
                                )
                                errors.append(err)
                                continue
                            if hasattr(kw.value.func, 'id') and\
                                    kw.value.func.id != 'locale_str':
                                err = Flake8ASTErrorInfo(
                                    kw.lineno, kw.col_offset,
                                    cls.msg, cls
                                )
                                errors.append(err)
                                continue


class I18NVisitor(ast.NodeVisitor):

    def __init__(self):
        self.errors: list[Flake8ASTErrorInfo] = []

    def visit_FunctionDef(self, node):
        DiscordCommandsShouldHaveLocale_str.check(node, self.errors)
        self.generic_visit(node)  # continue visiting child nodes

    def visit_Name(self, node):
        GroupsShouldHaveLocale_str.check(node, self.errors)
        DescribeShouldBeI18N.check(node, self.errors)
        I18NStringIsNotFound.check(node, self.errors)
        self.generic_visit(node)  # continue visiting child nodes


class I18N_Checker:
    name = 'flake8_I18N_checker'
    version = '0.0.1'

    def __init__(self, tree: ast.AST):
        self._tree = tree

    def run(self) -> Iterator[Flake8ASTErrorInfo]:
        visitor = I18NVisitor()
        visitor.visit(self._tree)
        yield from visitor.errors
