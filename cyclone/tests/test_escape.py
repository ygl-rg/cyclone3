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
from unittest.mock import Mock

from cyclone import escape


class TestEscape(unittest.TestCase):

    def test_xhtml(self):
        self.assertEqual(
            escape.xhtml_escape("abc42"),
            "abc42"
        )
        self.assertEqual(
            escape.xhtml_escape("<>"),
            "&lt;&gt;"
        )
        self.assertEqual(
            escape.xhtml_escape("\"'"),
            "&quot;&#39;"
        )