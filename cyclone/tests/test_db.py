#
# Copyright 2014 David Novakovic
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from twisted.trial import unittest
from cyclone.sqlite import InlineSQLite
from unittest.mock import Mock


class InlineSQLiteTest(unittest.TestCase):
    def setUp(self):
        self.isq = InlineSQLite()
        self.isq.runOperation(
            "create table nothing (val1 string, val2 string)")
        self.isq.runOperation('insert into nothing values ("a", "b")')

    def test_init(self):
        self.assertTrue(hasattr(self.isq, "autoCommit"))
        self.assertTrue(hasattr(self.isq, "conn"))
        self.assertTrue(hasattr(self.isq, "curs"))

    def test_runQuery(self):
        self.isq.curs = Mock()
        self.isq.curs.__iter__ = Mock(return_value=iter([1, 2, 3]))
        res = self.isq.runQuery("a query")
        self.assertEqual(res, [1, 2, 3])

    def test_runOperation(self):
        self.isq.runOperation('insert into nothing values ("c", "d")')
        res = self.isq.runQuery("select count(*) from nothing")
        self.assertEqual(res[0][0], 2)

    def test_runOperationMany(self):
        self.isq.runOperationMany(
            'insert into nothing values (?, ?)',
            [["a", "b"], ["c", "d"]]
        )
        res = self.isq.runQuery("select count(*) from nothing")
        self.assertEqual(res[0][0], 3)

    def test_commit(self):
        self.isq.conn = Mock()
        self.isq.commit()
        self.isq.conn.commit.assert_called_with()

    def test_rollback(self):
        self.isq.conn = Mock()
        self.isq.rollback()
        self.isq.conn.rollback.assert_called_with()

    def test_close(self):
        self.isq.conn = Mock()
        self.isq.close()
        self.isq.conn.close.assert_called_with()
