#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'''
Auto-document all relevant files in the module

Open the terminal, get into `pipenv shell` and run `python -m sausage_bot
.docs.autodoc`. This will create `documentation.md` in the docs folder,
containing all the functions in a markdown format which makes it easier
to make, update and post all your changes to github.

It is not perfect, but for now it serves it's purpose.
'''
import ast
import os
import sys
import glob
from pprint import pprint
from ..docs.modules import doc_vars
from .modules.doc_args import doc_args
from ..funcs import file_io
from ..log import log
from time import sleep


def logp(input):
    if doc_args.print:
        pprint(input)
    if doc_args.slow:
        sleep(3)


def dump(item):
    'Prettydump the content of item and exit'
    try:
        print(item.name)
    except:
        pass
    try:
        pprint(vars(item))
    except(TypeError):
        pprint(item)
    print('\n-----------\n')
    tree = ast.parse(item)
    pprint(astunparse.dump(tree))
    sys.exit()


def get_decorators(func):
    decs_list = func.decorator_list
    if len(decs_list) > 0:
        for dec in decs_list:
            if isinstance(dec, ast.Attribute):
                return f'{dec.value.id}.{dec.attr}'
            elif isinstance(dec, ast.Name):
                return dec.id
            else:
                return None


def get_funcs(parsed_file, level=1):
    '''
    Get the functions of a file, it's arguments and docstring, and
    return them
    '''
    func_out = ''
    unwanted_funcs = ['setup', '__init__', 'on_ready']
    docstring = None
    for func in parsed_file.body:
        if isinstance(
            func, (
                ast.AsyncFunctionDef,
                ast.ClassDef,
                ast.FunctionDef
            )
        ):
            type = None
            # Get a string for the type
            if isinstance(func, ast.AsyncFunctionDef):
                type = 'async Function'
            elif isinstance(func, ast.ClassDef):
                type = 'Class'
            elif isinstance(func, ast.FunctionDef):
                type = 'Function'
            name = func.name
            log.log_more(f'Got function: `{name}` ({type})')
            if name in unwanted_funcs:
                continue
            log.log_more(f'Got level `{level}`')
            func_out += f'#{"#"*level} {name}'
            # Get arguments for command
            args = get_args(func)
            if args is not None:
                func_out += f'({args})\n'
            else:
                func_out += '\n'
            # Add type descriptor
            func_out += f'Type: {type}\n'
            # Get decorators
            decs = get_decorators(func)
            if decs is not None:
                func_out += f'Decorators: @{decs}\n'
            # Find aliases for command
            aliases = get_cmd_aliases(func)
            if aliases is not None:
                func_out += f'Aliases: {aliases}\n'
            # Get permission levels
            permissions = get_cmd_permissions(func)
            if permissions is not None:
                func_out += f'Permissions: {permissions}\n'
            # Get docstring for command
            docstring = ast.get_docstring(func)
            if docstring is not None:
                if func_out != '':
                    func_out += '\n'
                func_out += f'{docstring}\n'
            func_out += '\n'
            func_out += f'{get_funcs(func, level+1)}'
    return func_out


def get_cmd_aliases(func):
    aliases = None
    if len(func.decorator_list) > 0:
        for dec in func.decorator_list:
            if 'func' in dict(vars(dec)):
                if dec.func.attr == 'command':
                    for kw in dec.keywords:
                        if kw.arg == 'aliases':
                            aliases = ''
                            for const in kw.value.elts:
                                aliases += const.value
                                if const != kw.value.elts[-1]:
                                    aliases += ', '
    return aliases


def get_cmd_permissions(func):
    permissions = None
    if len(func.decorator_list) > 0:
        for dec in func.decorator_list:
            if 'func' in vars(dec):
                if dec.func.attr == 'check_any':                
                    if len(dec.args) > 0:
                        permissions = ''
                        for arg in dec.args:
                            if arg.func.attr == 'is_owner':
                                if permissions != '':
                                    permissions += ', '
                                permissions += arg.func.attr
                            elif arg.func.attr == 'has_permissions':
                                for kw in arg.keywords:
                                    if permissions != '':
                                        permissions += ', '
                                    permissions += f'{kw.arg}={kw.value.value}'
    return permissions


def get_args(func):
    'Get available (and wanted) arguments from a function/class'
    def get_args_and_defs(_args, _defs):
        'Get and sort any arguments and their corresponding defaults'
        out = ''
        args_len = len(_args)
        defs_len = len(_defs)
        index_diff = args_len - defs_len
        defs_start = 0 - index_diff
        for arg in _args:
            log.log_more(f'Got arg: {arg.arg}')
            out += arg.arg
            if defs_start >= 0:
                # Get defaults
                if isinstance(_defs[defs_start], (ast.Constant, ast.Name)) is True:
                    if 'id' in vars(_defs[defs_start]):
                        out += f'={_defs[defs_start].id}'
                    elif 'value' in vars(_defs[defs_start]):
                        out += f'={_defs[defs_start].value}'
            else:
                if arg.annotation is not None:
                    if 'attr' in vars(arg.annotation):
                        out += f': {arg.annotation.value.id}.'\
                            f'{arg.annotation.attr}'
                    elif 'slice' in vars(arg.annotation):
                        out += f'{arg.annotation.value.value.id}'\
                            f'.{arg.annotation.value.attr}'\
                            f'[{arg.annotation.slice.value.id}]'
            if arg != _args[-1]:
                out += ', '
            defs_start += 1
        if out != '':
            return out
        else:
            return None

    args_out = ''
    if 'args' in dict(vars(func)):
        # Add arguments and their defaults
        argdefs = get_args_and_defs(
            func.args.args, func.args.defaults
        )
        if argdefs != None:
            args_out += f'{argdefs}'
        # Add keyword args and their defaults
        kwargdefs = get_args_and_defs(
            func.args.kwonlyargs, func.args.kw_defaults
        )
        if kwargdefs != None:
            args_out += f', *, {kwargdefs}'
        if args_out != '':
            return args_out
    elif 'bases' in dict(vars(func)):
        for base in func.bases:
            try:
                args_out += f'{base.attr}.{base.value.id}'
            except:
                args_out += base.id
        return args_out
    else:
        return None


def get_info_from_file(filename):
    info_out = ''
    with open(filename) as fd:
        file_contents = fd.read()
    log.log(f'Got filename `{filename}`')
    info_out += f'# {filename}\n'
    # Get the parsed_file's functions
    parsed_file = ast.parse(file_contents)
    # Get docstring from file if exist
    docstring = ast.get_docstring(parsed_file)
    if docstring is not None:
        info_out += f'{docstring}\n\n'
    else:
        info_out += '\n'
    # Get funcs
    _funcs = get_funcs(parsed_file)
    if _funcs is not None:
        info_out += f'{_funcs}'
    info_out += '---\n\n'
    return info_out


if __name__ == "__main__":
    md_out = ''
    unwanted_elements = ['/docs/', '/test/', '__init__']
    # Don't read all files if a single file is specified
    # Confirm that the file exist
    filelist = None
    filename = None
    # Check if the script is given a single filename
    if isinstance(doc_args.file, str):
        filename = doc_vars.ROOT_DIR / doc_args.file
        log.log_more(f'filename: {filename}')
    if file_io.file_size(str(filename)) is not False:
        filelist = [filename]
        # Get module name
        single_filename = str(filename).split(os.sep)[-1]
        module_name = f'# {single_filename}\n\n'
    elif doc_args.file == None:
        log.log_more('Getting all files')
        filelist = glob.glob('**/*.py', recursive=True)
        # Get module name
        module_name = f'# {filelist[0].split(os.sep)[0]}\n\n'
    for filename in filelist:
        single_filename = str(filename).split(os.sep)[-1]
        if not doc_args.file:
            rel_filename = filename.replace(str(doc_vars.ROOT_DIR), '')
            # We do not want to process some type of files or folders
            if any(unwanted in str(filename) for unwanted in unwanted_elements):
                log.log_more(f'Skipped file: `{rel_filename}`')
                continue
        md_out += get_info_from_file(filename)
    file_io.write_file(doc_vars.docs_file, md_out)
