#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest
from unittest import mock
from sausage_bot.util import file_io, envs


def test_write_file_input():
    with mock.patch('sausage_bot.util.file_io.open'):
        # Perfect example
        assert file_io.write_file(
            'sausage_bot/test/out/testfile', 'test') is True
        # Correct path, turn ints to str
        assert file_io.write_file(
            'sausage_bot/test/out/testfile', 1234) is True


def test_file_size():
    actual_file = envs.ROOT_DIR / '__main__.py'
    non_file = envs.ROOT_DIR / 'main.py'
    assert type(file_io.file_size(actual_file)) is int
    assert file_io.file_size(non_file) is False


def test_check_similarity():
    similar1 = ('tested1', 'tested1')
    dissimilar1 = ('tested1', 'tested2')
    similar_list = ['tested2', 'tested3', 'tested1']
    dissimilar_list = ['tested2', 'tested3']
    assert file_io.check_similarity(similar1[0], similar1[1]) == 'tested1'
    assert file_io.check_similarity(dissimilar1[0], dissimilar1[1]) is False
    assert file_io.check_similarity(similar1[0], similar_list) == 'tested1'
    assert file_io.check_similarity(similar1[0], dissimilar_list) is False
