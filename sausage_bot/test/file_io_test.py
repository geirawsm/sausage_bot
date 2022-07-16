#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest
from unittest.mock import Mock
from ..funcs import file_io

mock = Mock()

@pytest.mark.parametrize("input, output",[
    (('sausage_bot/test/out/testfile', 'test'), True),
    ((1234, 'test'), None),
    (('sausage_bot/test/out/testfile', 1234), True),
    (('sausage_bot/test/out/testing/testfile', 1234), True)
    ])
def test_write_file_input(input, output):
    assert file_io.write_file(input[0], input[1]) is output


#class test_import_file_as_list():
#    mock_list = "['test1', 'test2]"
