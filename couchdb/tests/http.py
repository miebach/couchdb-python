# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 Christopher Lenz
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.

import doctest
import socket
import time
import unittest
from six import BytesIO
import six

from couchdb import http
from couchdb.tests import testutil


class SessionTestCase(testutil.TempDatabaseMixin, unittest.TestCase):

    def test_timeout(self):
        dbname, db = self.temp_db()
        timeout = 1
        session = http.Session(timeout=timeout)
        start = time.time()
        status, headers, body = session.request('GET', db.resource.url + '/_changes?feed=longpoll&since=1000&timeout=%s' % (timeout*2*1000,))
        self.assertRaises(socket.timeout, body.read)
        self.assertTrue(time.time() - start < timeout * 1.3)


class ResponseBodyTestCase(unittest.TestCase):
    def test_close(self):
        class TestStream(BytesIO):
            def __init__(self, buf):
                self._buf = buf
                BytesIO.__init__(self, buf)

            def isclosed(self):
                return len(self._buf) == self.tell()

        class Counter(object):
            def __init__(self):
                self.value = 0

            def __call__(self):
                self.value += 1

        counter = Counter()

        response = http.ResponseBody(TestStream(b'foobar'), counter)

        response.read(10) # read more than stream has. close() is called
        response.read() # steam ended. another close() call

        self.assertEqual(counter.value, 1)

    def test_double_iteration_over_same_response_body(self):
        class TestHttpResp(object):
            msg = {'transfer-encoding': 'chunked'}
            def __init__(self, fp, _len):
                self.fp = fp
                self._len = _len

            def isclosed(self):
                return self._len == self.fp.tell()

        data = b'foobarbaz'
        data = b'\n'.join([hex(len(data))[2:].encode('utf-8'), data])
        response = http.ResponseBody(TestHttpResp(BytesIO(data), len(data)),
                                     lambda *a, **k: None)
        self.assertEqual(list(response.iterchunks()), [b'foobarbaz'])
        self.assertEqual(list(response.iterchunks()), [])


class CacheTestCase(testutil.TempDatabaseMixin, unittest.TestCase):

    def test_remove_miss(self):
        """Check that a cache remove miss is handled gracefully."""
        url = 'http://localhost:5984/foo'
        cache = http.Cache()
        cache.put(url, (None, None, None))
        cache.remove(url)
        cache.remove(url)


def suite():
    suite = unittest.TestSuite()
    if six.PY2:
        suite.addTest(doctest.DocTestSuite(http))
    suite.addTest(unittest.makeSuite(SessionTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ResponseBodyTestCase, 'test'))
    suite.addTest(unittest.makeSuite(CacheTestCase, 'test'))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
