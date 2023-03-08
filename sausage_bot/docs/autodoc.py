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
import astpretty
import os
import sys
import glob
from pprint import pprint
from .modules import doc_envs
from .modules.doc_args import doc_args
from ..util import envs, file_io, datetime_handling
from ..util.args import args
from ..util.log import log
from time import sleep
import re


def dump(item):
    'Prettydump the content of item and exit'
    _dump = astpretty.pformat(item, indent=4, show_offsets=True)
    if doc_args.file_out:
        file_io.write_file(doc_envs.DOCS_DIR / doc_args.file_out, _dump)
    else:
        filename = 'dump-{}_{}.md'.format(
            datetime_handling.get_dt(
                format='revdate', sep='-'
            ),
            datetime_handling.get_dt(
                format='timefull', sep='-'
            )
        )
        file_io.write_file(doc_envs.DOCS_DIR / filename, _dump)
    sys.exit()


def dump_output(
    output, timed=True, name: str = None, hard_exit=False
) -> str:
    '''
    Write output to file and exit

    timed       Add date and time to the filename (on by default)
    name        Use a different name than 'dump' (None by default)
    hard_exit   Do a `sys.exit()` at the end of the dump (off by default)
    '''
    if doc_args.file_out:
        if isinstance(output, dict):
            file_io.write_json(
                doc_envs.DOCS_DIR / doc_args.file_out, output
            )
        else:
            file_io.write_file(
                doc_envs.DOCS_DIR / doc_args.file_out, output
            )
    else:
        filename = ''
        if name is not None:
            filename += name
        else:
            filename += 'dump'
        if timed:
            filename += '-{}_{}'.format(
                datetime_handling.get_dt(
                    format='revdate', sep='-'
                ),
                datetime_handling.get_dt(
                    format='timefull', sep='-'
                )
            )
        if isinstance(output, dict):
            filename += '.json'
            file_io.write_json(
                doc_envs.DOCS_DIR / filename, output
            )
        else:
            filename += '.md'
            file_io.write_file(
                doc_envs.DOCS_DIR / filename, output
            )
    if hard_exit:
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
    def set_len_desc(item_in):
        '''
        If the `item_in` is a list or a dict, drill down to a string,
        check it's length, and return the max length.
        '''
        max_len = 0
        try:
            log.debug(f'`item_in` is {type(item_in)}')
            for item_group in item_in:
                for _arg in item_in[item_group]:
                    if len(_arg) > max_len:
                        max_len = len(_arg)
            return max_len
        except(TypeError):
            return 0


    func_out = ''
    docstring = None
    for func in parsed_file.body:
        if isinstance(
            func, (
                ast.AsyncFunctionDef,
                ast.ClassDef,
                ast.FunctionDef
            )
        ):
            log.debug(f'Getting function `{func.name}`')
            func_type = None
###
#            if func.name == 'pretty_quote':
#                dump(func)
###
            # Get a string for the func_type
            if isinstance(func, ast.AsyncFunctionDef):
                func_type = 'async Function'
            elif isinstance(func, ast.ClassDef):
                func_type = 'Class'
            elif isinstance(func, ast.FunctionDef):
                func_type = 'Function'
            name = func.name
            log.debug(f'Got function: `{name}` ({func_type})')
            docstring = ast.get_docstring(func)
            # Skip this function if it is unwanted
            if name in doc_envs.skip_function:
                log.debug(f'Skipping `{name}` because of `doc_envs.skip_function`')
                continue
                # Look for a keyword in docstring that indicates that this
                # function should not be parsed for output
            elif docstring is not None and doc_envs.skip_keyword in docstring.lower():
                log.debug(f'Skipping `{name}` because of `doc_envs.skip_keyword`')
                continue
            log.debug(f'Got level `{level}`')
            func_out += f'#{"#"*level} {name}'
            # Get arguments for command
            _args = {}
            _args_func = get_args(func, _args)
            log.debug(f'Got `_args_func`: {_args_func}')
            if len(_args_func) > 0:
                if len(_args_func['argdefs']) != 0 and\
                        len(_args_func['kwargdefs']) != 0:
                    func_out += ' ('
                    log.debug(f'`_args_func`: {_args_func}')
                    for arg_group in _args_func:
                        for arg_name in _args_func[arg_group]:
                            if arg_name in doc_envs.skip_variable:
                                continue
                            else:
                                func_out += f'{arg_name}, '
                        func_out = re.sub(', $', '', func_out)
                    func_out += ')\n'
            if func_out != '':
                func_out += '\n\n'
            func_out += f'Type: {func_type}\n'
            decs = get_decorators(func)
            log.debug(f'`decs` is {decs}')
            if decs is not None:
                if func_out != '':
                    func_out += '\n'
                func_out += f'Decorators: @{decs}\n'
            # Find aliases for command
            aliases = get_cmd_aliases(func)
            log.debug(f'`aliases` is {aliases}')
            if aliases is not None:
                if func_out != '':
                    func_out += '\n'
                func_out += f'Aliases: {aliases}\n'
            # Get permission levels
            permissions = get_cmd_permissions(func)
            log.debug(f'`permissions` is {permissions}')
            if permissions is not None:
                if func_out != '':
                    func_out += '\n'
                func_out += f'Permissions: {permissions}\n'
            # Get docstring for command
            docstring = ast.get_docstring(func)
            log.debug(f'`docstring` is {docstring}')
            if docstring is not None:
                if func_out != '':
                    func_out += '\n'
                func_out += f'{docstring}\n'
            # Get function variable specifications
            if _args_func is not None:
                arg_spec_len = 0
                for _arg_func in _args_func:
                    for _arg_spec in _args_func[_arg_func]:
                        if len(_args_func[_arg_func][_arg_spec]) > arg_spec_len:
                            arg_spec_len = len(_args_func[_arg_func][_arg_spec])
                if arg_spec_len > 0:
                    if func_out != '':
                        func_out += '\n'
                var_max_len = set_len_desc(_args_func)
                log.debug(f'`var_max_len` is {var_max_len}')
                for arg_group in _args_func:
                    for arg in _args_func[arg_group]:
                        if _args_func[arg_group][arg] != {}:
                            _arg_out = ''
                            _arg = _args_func[arg_group][arg]
                            _arg_out += f'{arg:{var_max_len}}\t'
                            if 'type_hint' in _arg:
                                _type_hint = _arg['type_hint']
                                _arg_out += f'({_type_hint}) '
                            if 'description' in _arg:
                                _desc = _arg['description']
                                _arg_out += f'{_desc}'
                            _arg_out += '\n'
                            func_out += _arg_out
                func_out += '\n'
            func_out += f'{get_funcs(func, level+1)}'
            if 'returns' in vars(func):
                if func.returns is not None and 'id' in vars(func.returns):
                    func_out += f'Returns: {func.returns.id}\n'
            func_out += '\n'
    return func_out


def get_cmd_aliases(func):
    aliases = None
    if len(func.decorator_list) > 0:
        for dec in func.decorator_list:
            if 'func' in dict(vars(dec)) and dec.func.attr == 'command':
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


def get_args(func_in, args_in):
    'Get available (and wanted) arguments from a function/class'
    def get_args_and_defs(_args, _defs):
        'Get and sort any arguments and their corresponding defaults'
        out = {}
        def_index = len(_defs) - len(_args)
        for arg in _args:
            if arg.arg in doc_envs.skip_variable:
                def_index += 1
                continue
            log.debug(f'Got arg: {arg.arg}')
            out[arg.arg] = {}
            if 'annotation' in vars(arg) and arg.annotation is not None:
                log.debug('Checking out `annotation`')
                out[arg.arg]['type_hint'] = ''
                try:
                    _ann_s = arg.annotation.slice
                    if 'id' in vars(_ann_s.value):
                        log.debug(f'Got `_ann_s.value.id`: {_ann_s.value.id}')
                        out[arg.arg]['type_hint'] += f'{_ann_s.value.id}'
                except:
                    try:
                        log.debug(f'Got `arg.annotation.id`: {arg.annotation.id}')
                        out[arg.arg]['type_hint'] = f'{arg.annotation.id}'
                    except:
                        if 'attr' in vars(arg.annotation):
                            log.debug(f'Got `arg.annotation.attr`: {arg.annotation.attr}')
                        else:
                            print(f'arg.annotation.value.attr: {arg.annotation.value.attr}')
                            print(f'arg.annotation.slice.id: {arg.annotation.slice.id}')
                            #out[arg.arg]['type_hint'] = f'{arg.annotation.slice.id}'
                        try:
                            log.debug(f'Got `arg.annotation.value.id`: {arg.annotation.value.id}')
                            out[arg.arg]['type_hint'] = f'{arg.annotation.value.id}.{arg.annotation.attr}'
                        except:
                            log.debug('NO MORE TO DO')
            if def_index >= 0:
                if isinstance(
                        _defs[def_index], (
                            ast.Constant, ast.Name, ast.Call
                        )) is True:
                    if 'keywords' in vars(_defs[def_index]):
                        log.debug('Found `keywords`')
                        try:
                            log.debug('vars(_defs[def_index]):')
                            pprint(vars(_defs[def_index]))
                        except:
                            log.debug(f'_defs[def_index]:')
                            pprint(_defs[def_index])
                        for _kw in _defs[def_index].keywords:
                            pprint(f'_kw.arg: {_kw.arg}')
                            pprint(f'_kw.value.value: {_kw.value.value}')
                            out[arg.arg][_kw.arg] = _kw.value.value
                        pprint(out)
                else:
                    pass
            def_index += 1
        log.debug(f'Got this for `out`: {out}')
        return out

    if 'args' in dict(vars(func_in)):
        # Add arguments and their defaults
        argdefs = get_args_and_defs(
            func_in.args.args, func_in.args.defaults
        )
        log.debug(f'Got `argdefs`: {argdefs}', extra_info=func_in.name)
        if argdefs != None:
            args_in['argdefs'] = argdefs
        # Add keyword args and their defaults
        kwargdefs = get_args_and_defs(
            func_in.args.kwonlyargs, func_in.args.kw_defaults
        )
        log.debug(f'Got `kwargdefs`: {kwargdefs}', extra_info=func_in.name)
        if kwargdefs != None:
            args_in['kwargdefs'] = kwargdefs
        if len(args_in) > 0:
            return args_in
    elif 'bases' in dict(vars(func_in)):
        pprint(f'BASES: {func_in.bases}')
        for base in func_in.bases:
            # TODO Check if "bases" is something we want
            log.debug('Only printing from `base`?', extra_color='red')
            try:
                pprint(f'{base.attr}.{base.value.id}')
            except:
                pprint(base.id)
        return args_in
    else:
        return None


def get_info_from_file(filename):
    info_out = ''
    with open(filename) as fd:
        file_contents = fd.read()
    short_filename = str(filename).split(os.sep)[-1]
    log.log(f'Got file `{short_filename}`')
    info_out += f'# `{short_filename}`\n'
    # Get the parsed_file's functions
    parsed_file = ast.parse(file_contents)
    # Get docstring from file if exist
    docstring = ast.get_docstring(parsed_file)
    if docstring is not None:
        info_out += f'\n{docstring}\n'
    # Get funcs
    _funcs = get_funcs(parsed_file)
    if _funcs != '':
        info_out += f'\n{_funcs}'
    info_out += '---\n\n'
    return info_out


if __name__ == "__main__":
    md_out = ''
    # Don't read all files if a single file is specified
    # Confirm that the file exist
    filelist = None
    filename = None
    # Check if the script is given a single filename
    if doc_args.file and file_io.file_size(
        str(doc_envs.ROOT_DIR / doc_args.file)
    ) is not False:
        filename = doc_envs.ROOT_DIR / doc_args.file
        log.debug(f'filename: {filename}')
        filelist = [filename]
        # Get module name
        single_filename = str(filename).split(os.sep)[-1]
        module_name = f'# {single_filename}\n'
    elif doc_args.file == None:
        log.debug('Getting all files')
        filelist = glob.glob('**/*.py', recursive=True)
        # Get module name
        module_name = f'# {filelist[0].split(os.sep)[0]}\n'
    if not filelist:
        if doc_args.file:
            print(f'Could not read input `{doc_args.file}`. Does the file exist?')
        else:
            print(f'Could not find any python files in `{doc_envs.ROOT_DIR}`.')
        sys.exit()
    for filename in filelist:
        single_filename = str(filename).split(os.sep)[-1]
        if not doc_args.file:
            rel_filename = filename.replace(str(envs.ROOT_DIR), '')
            # We do not want to process some type of files or folders
            if any(unwanted in str(filename) for unwanted in doc_envs.skip_folder_or_file):
                log.debug(f'Skipped file: `{rel_filename}`')
                continue
        md_out += get_info_from_file(filename)
    if not doc_args.file_out:
        log.debug(f'Writing output to `{doc_envs.docs_file}`')
        file_io.write_file(doc_envs.docs_file, md_out)
    else:
        out_file = doc_envs.DOCS_DIR / doc_args.file_out
        log.debug(f'Writing output to `{out_file}`')
        file_io.write_file(out_file, md_out)
