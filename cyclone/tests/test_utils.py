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
from cyclone.escape import xhtml_escape, xhtml_unescape
from cyclone.escape import json_encode, json_decode
from cyclone.escape import squeeze, url_escape, url_unescape
from cyclone.escape import utf8, to_unicode, to_basestring
from cyclone.escape import recursive_unicode, linkify, _convert_entity
from cyclone.util import _emit, ObjectDict, import_object
from unittest.mock import Mock
import datetime


class EscapeTest(unittest.TestCase):
    def test_xhtml_escape(self):
        xml = "<"
        result = xhtml_escape(xml)
        self.assertEqual(result, "&lt;")

    def test_xhtml_unescape(self):
        escaped = "&lt;"
        result = xhtml_unescape(escaped)
        self.assertEqual(result, "<")

    def test_json_encode(self):
        data = {"a": "b"}
        result = json_encode(data)
        self.assertEqual(result, '{"a": "b"}')

    def test_json_decode(self):
        data = '{"a": "b"}'
        result = json_decode(data)
        self.assertEqual(result, {"a": "b"})

    def test_squeeze(self):
        self.assertEqual(squeeze("a  test"), "a test")

    def test_url_escape(self):
        self.assertEqual(url_escape("a value"), "a+value")

    def test_url_unescape(self):
        self.assertEqual(url_unescape("a+value", encoding=None), "a value")
        self.assertEqual(url_unescape("a+value"), "a value")

    def test_utf8(self):
        self.assertEqual(utf8("rawr"), b"rawr")
        self.assertEqual(utf8(u"rawr"), b"rawr")

    def test_to_unicode(self):
        self.assertEqual(to_unicode("rawr"), u"rawr")
        self.assertEqual(to_unicode(u"rawr"), u"rawr")

    def test_to_basestring(self):
        """
        Not sure this is 100% testable in python 2.
        """
        self.assertEqual(to_basestring("rawr"), "rawr")
        self.assertEqual(to_basestring(u"rawr"), "rawr")

    def test_recursive_unicode(self):
        self.assertEqual(recursive_unicode("rawr"), u"rawr")
        self.assertEqual(
            recursive_unicode({"rawr": "rawr"}), {"rawr": u"rawr"})
        self.assertEqual(
            recursive_unicode(["rawr", "rawr"]), [u"rawr", u"rawr"])

    def test_linkify(self):
        """
        Rough tests just to ensure we don't have exceptions.
        """
        urls = [
            "http://testing.com/a/long/url/right/here",
        ]
        for u in urls:
            link = linkify(u, shorten=True)
            self.assertTrue(
                link.startswith("<a "), link
            )
        linkify("spdy://testing.com/a/long/url/right/here", shorten=True)
        linkify(
            "spdy://testing.com/a/long/url/right/here",
            shorten=True,
            extra_params="x=y"
        )
        linkify(
            "http://testing.com/alongurlrighthere"
            "alongurlrighthere"
            "alongurlrighthere"
            "alongurlrighthere"
            "/a/long/url/right/here",
            shorten=True, require_protocol=True, extra_params=lambda x: "x=y")

    def test_convert_entity(self):
        """
        A bit hacky for now. Gets things covered though.
        """
        m = Mock()
        _convert_entity(m)
        m.group.return_value = "#"
        _convert_entity(m)


class UtilsTest(unittest.TestCase):
    def test_emit(self):
        m = Mock()
        t = datetime.time()
        _emit(m, {
            "message": "some message",
            "time": t
        })
        m.formatTime.assert_called_with(t)

    def test_emit_empty(self):
        m = Mock()
        t = datetime.time()
        failure = Mock()
        failure.getTraceback.return_value = ""
        _emit(m, {
            "message": "",
            "time": t,
            "isError": "",
            "failure": failure
        })
        self.assertEqual(m.formatTime.call_count, 0)

    def test_object_dict(self):
        od = ObjectDict()
        self.assertRaises(AttributeError, getattr, od, "something")
        od["foo"] = "bar"
        self.assertEqual(od['foo'], "bar")
        self.assertEqual(od.foo, "bar")
        od.rah = "meow"
        self.assertEqual(od['rah'], "meow")

    def test_import_object(self):
        import os.path
        other_os = import_object("os.path")
        self.assertIs(os.path, other_os)

    def test_import_object_fail(self):
        self.assertRaises(ImportError, import_object, "meowkittens.something")

    def test_import_object_fail_no_method(self):
        self.assertRaises(ImportError, import_object, "os.something")
