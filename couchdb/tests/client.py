# -*- coding: utf-8 -*-
#
# Copyright (C) 2007-2009 Christopher Lenz
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.

import doctest
import os
from StringIO import StringIO
import unittest

from couchdb import client, http
http.CACHE_SIZE = 2, 3


class ServerTestCase(unittest.TestCase):

    def setUp(self):
        uri = os.environ.get('COUCHDB_URI', client.DEFAULT_BASE_URL)
        self.server = client.Server(uri, full_commit=False)

    def tearDown(self):
        try:
            self.server.delete('python-tests')
        except http.ResourceNotFound:
            pass
        try:
            self.server.delete('python-tests-a')
        except http.ResourceNotFound:
            pass

    def test_server_vars(self):
        version = self.server.version()
        config = self.server.config()
        stats = self.server.stats()
        tasks = self.server.tasks()

    def test_get_db_missing(self):
        self.assertRaises(http.ResourceNotFound,
                          lambda: self.server['python-tests'])

    def test_create_db_conflict(self):
        self.server.create('python-tests')
        self.assertRaises(http.PreconditionFailed, self.server.create,
                          'python-tests')

    def test_delete_db(self):
        self.server.create('python-tests')
        assert 'python-tests' in self.server
        self.server.delete('python-tests')
        assert 'python-tests' not in self.server

    def test_delete_db_missing(self):
        self.assertRaises(http.ResourceNotFound, self.server.delete,
                          'python-tests')

    def test_replicate(self):
        a = self.server.create('python-tests')
        id = a.create({'test': 'a'})
        b = self.server.create('python-tests-a')
        result = self.server.replicate('python-tests', 'python-tests-a')
        self.assertEquals(result['ok'], True)
        self.assertEquals(b[id]['test'], 'a')

        doc = b[id]
        doc['test'] = 'b'
        b.update([doc])
        self.server.replicate(client.DEFAULT_BASE_URL + 'python-tests-a',
                              'python-tests')
        self.assertEquals(b[id]['test'], 'b')

    def test_replicate_continuous(self):
        a = self.server.create('python-tests')
        b = self.server.create('python-tests-a')
        result = self.server.replicate('python-tests', 'python-tests-a', continuous=True)
        self.assertEquals(result['ok'], True)
        version = tuple(int(i) for i in self.server.version().split('.')[:2])
        if version >= (0, 10):
            self.assertTrue('_local_id' in result)

class DatabaseTestCase(unittest.TestCase):

    def setUp(self):
        uri = os.environ.get('COUCHDB_URI', client.DEFAULT_BASE_URL)
        self.server = client.Server(uri, full_commit=False)
        try:
            self.server.delete('python-tests')
        except http.ResourceNotFound:
            pass
        self.db = self.server.create('python-tests')

    def tearDown(self):
        try:
            self.server.delete('python-tests')
        except http.ResourceNotFound:
            pass

    def test_create_large_doc(self):
        self.db['foo'] = {'data': '0123456789' * 110 * 1024} # 10 MB
        self.assertEqual('foo', self.db['foo']['_id'])

    def test_doc_id_quoting(self):
        self.db['foo/bar'] = {'foo': 'bar'}
        self.assertEqual('bar', self.db['foo/bar']['foo'])
        del self.db['foo/bar']
        self.assertEqual(None, self.db.get('foo/bar'))

    def test_unicode(self):
        self.db[u'føø'] = {u'bår': u'Iñtërnâtiônàlizætiøn', 'baz': 'ASCII'}
        self.assertEqual(u'Iñtërnâtiônàlizætiøn', self.db[u'føø'][u'bår'])
        self.assertEqual(u'ASCII', self.db[u'føø'][u'baz'])

    def test_disallow_nan(self):
        try:
            self.db['foo'] = {u'number': float('nan')}
            self.fail('Expected ValueError')
        except ValueError, e:
            pass

    def test_doc_revs(self):
        doc = {'bar': 42}
        self.db['foo'] = doc
        old_rev = doc['_rev']
        doc['bar'] = 43
        self.db['foo'] = doc
        new_rev = doc['_rev']

        new_doc = self.db.get('foo')
        self.assertEqual(new_rev, new_doc['_rev'])
        new_doc = self.db.get('foo', rev=new_rev)
        self.assertEqual(new_rev, new_doc['_rev'])
        old_doc = self.db.get('foo', rev=old_rev)
        self.assertEqual(old_rev, old_doc['_rev'])

        revs = [i for i in self.db.revisions('foo')]
        self.assertEqual(revs[0]['_rev'], new_rev)
        self.assertEqual(revs[1]['_rev'], old_rev)
        gen = self.db.revisions('crap')
        self.assertRaises(StopIteration, lambda: gen.next())

        self.assertTrue(self.db.compact())
        while self.db.info()['compact_running']:
            pass

        # 0.10 responds with 404, 0.9 responds with 500, same content
        doc = 'fail'
        try:
            doc = self.db.get('foo', rev=old_rev)
        except http.ServerError:
            doc = None
        assert doc is None

    def test_attachment_crud(self):
        doc = {'bar': 42}
        self.db['foo'] = doc
        old_rev = doc['_rev']

        self.db.put_attachment(doc, 'Foo bar', 'foo.txt', 'text/plain')
        self.assertNotEquals(old_rev, doc['_rev'])

        doc = self.db['foo']
        attachment = doc['_attachments']['foo.txt']
        self.assertEqual(len('Foo bar'), attachment['length'])
        self.assertEqual('text/plain', attachment['content_type'])

        self.assertEqual('Foo bar',
                         self.db.get_attachment(doc, 'foo.txt').read())
        self.assertEqual('Foo bar',
                         self.db.get_attachment('foo', 'foo.txt').read())

        old_rev = doc['_rev']
        self.db.delete_attachment(doc, 'foo.txt')
        self.assertNotEquals(old_rev, doc['_rev'])
        self.assertEqual(None, self.db['foo'].get('_attachments'))

    def test_attachment_crud_with_files(self):
        doc = {'bar': 42}
        self.db['foo'] = doc
        old_rev = doc['_rev']
        fileobj = StringIO('Foo bar baz')

        self.db.put_attachment(doc, fileobj, 'foo.txt')
        self.assertNotEquals(old_rev, doc['_rev'])

        doc = self.db['foo']
        attachment = doc['_attachments']['foo.txt']
        self.assertEqual(len('Foo bar baz'), attachment['length'])
        self.assertEqual('text/plain', attachment['content_type'])

        self.assertEqual('Foo bar baz',
                         self.db.get_attachment(doc, 'foo.txt').read())
        self.assertEqual('Foo bar baz',
                         self.db.get_attachment('foo', 'foo.txt').read())

        old_rev = doc['_rev']
        self.db.delete_attachment(doc, 'foo.txt')
        self.assertNotEquals(old_rev, doc['_rev'])
        self.assertEqual(None, self.db['foo'].get('_attachments'))

    def test_empty_attachment(self):
        doc = {}
        self.db['foo'] = doc
        old_rev = doc['_rev']

        self.db.put_attachment(doc, '', 'empty.txt')
        self.assertNotEquals(old_rev, doc['_rev'])

        doc = self.db['foo']
        attachment = doc['_attachments']['empty.txt']
        self.assertEqual(0, attachment['length'])

    def test_include_docs(self):
        doc = {'foo': 42, 'bar': 40}
        self.db['foo'] = doc

        rows = list(self.db.query(
            'function(doc) { emit(doc._id, null); }',
            include_docs=True
        ))
        self.assertEqual(1, len(rows))
        self.assertEqual(doc, rows[0].doc)

    def test_query_multi_get(self):
        for i in range(1, 6):
            self.db.create({'i': i})
        res = list(self.db.query('function(doc) { emit(doc.i, null); }',
                                 keys=range(1, 6, 2)))
        self.assertEqual(3, len(res))
        for idx, i in enumerate(range(1, 6, 2)):
            self.assertEqual(i, res[idx].key)

    def test_view_multi_get(self):
        for i in range(1, 6):
            self.db.create({'i': i})
        self.db['_design/test'] = {
            'language': 'javascript',
            'views': {
                'multi_key': {'map': 'function(doc) { emit(doc.i, null); }'}
            }
        }

        res = list(self.db.view('test/multi_key', keys=range(1, 6, 2)))
        self.assertEqual(3, len(res))
        for idx, i in enumerate(range(1, 6, 2)):
            self.assertEqual(i, res[idx].key)

    def test_view_compaction(self):
        for i in range(1, 6):
            self.db.create({'i': i})
        self.db['_design/test'] = {
            'language': 'javascript',
            'views': {
                'multi_key': {'map': 'function(doc) { emit(doc.i, null); }'}
            }
        }

        res = self.db.view('test/multi_key')
        self.assertTrue(self.db.compact('test'))

    def test_view_function_objects(self):
        if 'python' not in self.server.config()['query_servers']:
            return

        for i in range(1, 4):
            self.db.create({'i': i, 'j':2*i})

        def map_fun(doc):
            yield doc['i'], doc['j']
        res = list(self.db.query(map_fun, language='python'))
        self.assertEqual(3, len(res))
        for idx, i in enumerate(range(1,4)):
            self.assertEqual(i, res[idx].key)
            self.assertEqual(2*i, res[idx].value)

        def reduce_fun(keys, values):
            return sum(values)
        res = list(self.db.query(map_fun, reduce_fun, 'python'))
        self.assertEqual(1, len(res))
        self.assertEqual(12, res[0].value)

    def test_bulk_update_conflict(self):
        docs = [
            dict(type='Person', name='John Doe'),
            dict(type='Person', name='Mary Jane'),
            dict(type='City', name='Gotham City')
        ]
        self.db.update(docs)

        # update the first doc to provoke a conflict in the next bulk update
        doc = docs[0].copy()
        self.db[doc['_id']] = doc

        results = self.db.update(docs)
        self.assertEqual(False, results[0][0])
        assert isinstance(results[0][2], http.ResourceConflict)

    def test_bulk_update_all_or_nothing(self):
        docs = [
            dict(type='Person', name='John Doe'),
            dict(type='Person', name='Mary Jane'),
            dict(type='City', name='Gotham City')
        ]
        self.db.update(docs)

        # update the first doc to provoke a conflict in the next bulk update
        doc = docs[0].copy()
        doc['name'] = 'Jane Doe'
        self.db[doc['_id']] = doc

        results = self.db.update(docs, all_or_nothing=True)
        self.assertEqual(True, results[0][0])

        doc = self.db.get(doc['_id'], conflicts=True)
        assert '_conflicts' in doc

    def test_copy_doc(self):
        self.db['foo'] = {'status': 'testing'}
        result = self.db.copy('foo', 'bar')
        self.assertEqual(result, self.db['bar'].rev)

    def test_copy_doc_conflict(self):
        self.db['bar'] = {'status': 'idle'}
        self.db['foo'] = {'status': 'testing'}
        self.assertRaises(http.ResourceConflict, self.db.copy, 'foo', 'bar')

    def test_copy_doc_overwrite(self):
        self.db['bar'] = {'status': 'idle'}
        self.db['foo'] = {'status': 'testing'}
        result = self.db.copy('foo', self.db['bar'])
        doc = self.db['bar']
        self.assertEqual(result, doc.rev)
        self.assertEqual('testing', doc['status'])

    def test_copy_doc_srcobj(self):
        self.db['foo'] = {'status': 'testing'}
        self.db.copy(self.db['foo'], 'bar')
        self.assertEqual('testing', self.db['bar']['status'])

    def test_changes(self):
        self.db['foo'] = {'bar': True}
        self.assertEqual(self.db.changes(since=0)['last_seq'], 1)
        first = self.db.changes(feed='continuous').next()
        self.assertEqual(first['seq'], 1)
        self.assertEqual(first['id'], 'foo')


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ServerTestCase, 'test'))
    suite.addTest(unittest.makeSuite(DatabaseTestCase, 'test'))
    suite.addTest(doctest.DocTestSuite(client))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
