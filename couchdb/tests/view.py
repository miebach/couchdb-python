# -*- coding: utf-8 -*-
#
# Copyright (C) 2007-2008 Christopher Lenz
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.

import doctest
from six import BytesIO
import six
import unittest

from couchdb import view


class ViewServerTestCase(unittest.TestCase):

    def test_reset(self):
        input = BytesIO(b'["reset"]\n')
        output = BytesIO()
        view.run(input=input, output=output)
        self.assertEqual(output.getvalue().decode('utf-8'), 'true\n')

    def test_add_fun(self):
        input = BytesIO(b'["add_fun", "def fun(doc): yield None, doc"]\n')
        output = BytesIO()
        view.run(input=input, output=output)
        self.assertEqual(output.getvalue().decode('utf-8'), 'true\n')

    def test_map_doc(self):
        input = BytesIO(b'["add_fun", "def fun(doc): yield None, doc"]\n'
                         b'["map_doc", {"foo": "bar"}]\n')
        output = BytesIO()
        view.run(input=input, output=output)
        self.assertEqual(output.getvalue().decode('utf-8'),
                         'true\n'
                         '[[[null, {"foo": "bar"}]]]\n')

    def test_i18n(self):
        input = BytesIO(b'["add_fun", "def fun(doc): yield doc[\\"test\\"], doc"]\n'
                         b'["map_doc", {"test": "b\xc3\xa5r"}]\n')
        output = BytesIO()
        view.run(input=input, output=output)
        self.assertEqual(output.getvalue(),
                         b'true\n'
                         b'[[["b\xc3\xa5r", {"test": "b\xc3\xa5r"}]]]\n')

    def test_map_doc_with_logging(self):
        fun = 'def fun(doc): log(\'running\'); yield None, doc'
        input = BytesIO(('["add_fun", "%s"]\n'
                         '["map_doc", {"foo": "bar"}]\n' % fun).encode())
        output = BytesIO()
        view.run(input=input, output=output)
        self.assertEqual(output.getvalue().decode('utf-8'),
                         'true\n'
                         '{"log": "running"}\n'
                         '[[[null, {"foo": "bar"}]]]\n')

    def test_map_doc_with_logging_json(self):
        fun = 'def fun(doc): log([1, 2, 3]); yield None, doc'
        input = BytesIO(('["add_fun", "%s"]\n'
                         '["map_doc", {"foo": "bar"}]\n' % fun).encode())
        output = BytesIO()
        view.run(input=input, output=output)
        self.assertEqual(output.getvalue().decode('utf-8'),
                         'true\n'
                         '{"log": "[1, 2, 3]"}\n'
                         '[[[null, {"foo": "bar"}]]]\n')

    def test_reduce(self):
        input = BytesIO(b'["reduce", '
                        b'["def fun(keys, values): return sum(values)"], '
                        b'[[null, 1], [null, 2], [null, 3]]]\n')
        output = BytesIO()
        view.run(input=input, output=output)
        self.assertEqual(output.getvalue().decode('utf-8'), '[true, [6]]\n')

    def test_reduce_with_logging(self):
        input = BytesIO(b'["reduce", '
                          b'["def fun(keys, values): log(\'Summing %r\' % (values,)); return sum(values)"], '
                          b'[[null, 1], [null, 2], [null, 3]]]\n')
        output = BytesIO()
        view.run(input=input, output=output)
        self.assertEqual(output.getvalue().decode('utf-8'),
                         '{"log": "Summing (1, 2, 3)"}\n'
                         '[true, [6]]\n')

    def test_rereduce(self):
        input = BytesIO(b'["rereduce", '
                          b'["def fun(keys, values, rereduce): return sum(values)"], '
                          b'[1, 2, 3]]\n')
        output = BytesIO()
        view.run(input=input, output=output)
        self.assertEqual(output.getvalue().decode('utf-8'), '[true, [6]]\n')

    def test_reduce_empty(self):
        input = BytesIO(b'["reduce", '
                          b'["def fun(keys, values): return sum(values)"], '
                          b'[]]\n')
        output = BytesIO()
        view.run(input=input, output=output)
        self.assertEqual(output.getvalue().decode('utf-8'),
                         '[true, [0]]\n')


def suite():
    suite = unittest.TestSuite()
    if six.PY2:
        suite.addTest(doctest.DocTestSuite(view))
    suite.addTest(unittest.makeSuite(ViewServerTestCase, 'test'))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
