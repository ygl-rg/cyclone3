# coding: utf-8
#
# Copyright 2010 Alexandre Fiori
# based on the original Tornado by Facebook
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

"""An inline SQLite helper class.

All queries run inline, temporarily blocking the execution. Please make sure
you understand the limitations of using SQLite like this.

Example::

    import cyclone.web
    import cyclone.sqlite

    class SQLiteMixin(object):
        sqlite = cyclone.sqlite.InlineSQLite("mydb.sqlite")

    class MyRequestHandler(cyclone.web.RequestHandler):
        def get(self):
            rs = self.sqlite.runQuery("SELECT 1")
            ...

There is no ``Deferred`` responses, and no need to ``yield`` anything.
"""

import sqlite3


class InlineSQLite:
    """An inline SQLite instance"""
    def __init__(self, dbname=":memory:", autoCommit=True):
        """Create new SQLite instance."""
        self.autoCommit = autoCommit
        self.conn = sqlite3.connect(dbname)
        self.curs = self.conn.cursor()

    def runQuery(self, query, *args, **kwargs):
        """Use this function to execute queries that return a result set,
        like ``SELECT``.

        Example (with variable substitution)::

            sqlite.runQuery("SELECT * FROM asd WHERE x=? and y=?", [x, y])
        """
        self.curs.execute(query, *args, **kwargs)
        return [row for row in self.curs]

    def runOperation(self, command, *args, **kwargs):
        """Use this function to execute queries that do NOT return a result
        set, like ``INSERT``, ``UPDATE`` and ``DELETE``.

        Example::

            sqlite.runOperation("CREATE TABLE asd (x int, y text)")
            sqlite.runOperation("INSERT INTO asd VALUES (?, ?)", [x, y])
        """
        self.curs.execute(command, *args, **kwargs)
        if self.autoCommit is True:
            self.conn.commit()

    def runOperationMany(self, command, *args, **kwargs):
        """Same as `runOperation`, but for multiple rows.

        Example::

            sqlite.runOperationMany("INSERT INTO asd VALUES (?, ?)", [
                                        [x1, y1], [x2, y2], [x3, y3]
                                    ])
        """
        self.curs.executemany(command, *args, **kwargs)
        if self.autoCommit is True:
            self.conn.commit()

    def commit(self):
        """Commits pending transactions"""
        self.conn.commit()

    def rollback(self):
        """Gives up pending transactions"""
        self.conn.rollback()

    def close(self):
        """Destroys the instance"""
        self.conn.close()
