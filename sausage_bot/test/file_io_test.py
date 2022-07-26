#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing_extensions import assert_type
import pytest
from unittest import mock
from ..funcs import file_io


def test_write_file_input():
    with mock.patch('sausage_bot.funcs.file_io.open') as _file:
        # Perfect example
        assert file_io.write_file('sausage_bot/test/out/testfile', 'test') is True
        # No path, so no file to write to
        assert file_io.write_file(1234, 'test') is None
        # Correct path, turn ints to str
        assert file_io.write_file('sausage_bot/test/out/testfile', 1234) is True


def test_import_file_as_list(mocker):
    mocker_ensure_file = mocker.patch('os.path.exists')
    mocker_ensure_file.return_value.ok = True
    mocker_file_size = mocker.patch('os.stat')
    mocker_file_size.return_value.ok = 500
    # Valid list
    with mock.patch(
        'sausage_bot.funcs.file_io.open',
        new=mock.mock_open(read_data="['one', 'two']")) as _file:
        assert file_io.import_file_as_list(_file) == ['one', 'two']
    # Invalid list
    with mock.patch(
        'sausage_bot.funcs.file_io.open',
        new=mock.mock_open(read_data="['one', 'two")) as _file:
        pytest.raises(SyntaxError)


def test_add_to_list(mocker):
    mocker_ensure_file = mocker.patch('os.path.exists')
    mocker_ensure_file.return_value.ok = True
    mocker_file_size = mocker.patch('os.stat')
    mocker_file_size.return_value.ok = 500
    # Normal text should be added to the list
    with mock.patch(
        'sausage_bot.funcs.file_io.open',
        new=mock.mock_open(read_data="['one', 'two']")
    ) as _file:
        assert file_io.add_to_list(_file, 'three')\
            == ['one', 'two', 'three']


def test_read_json(mocker):
    mocker_ensure_file = mocker.patch('os.path.exists')
    mocker_ensure_file.return_value.ok = True
    mocker_file_size = mocker.patch('os.stat')
    mocker_file_size.return_value.ok = 500
    # Valid dict
    with mock.patch('sausage_bot.funcs.file_io.open', new=mock.mock_open(read_data='{"one": "", "two": []}')) as _file:
        assert file_io.read_json(_file) == {'one': '', 'two': []}
    # Invalid dict
    with mock.patch('sausage_bot.funcs.file_io.open', new=mock.mock_open(read_data='{"one": "", "two": [')) as _file:
        assert file_io.read_json(_file) is None


