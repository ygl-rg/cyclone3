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

from twisted.internet import defer
from twisted.trial import unittest
from twisted.internet import reactor

from unittest.mock import Mock

from cyclone import template


class TestTemplates(unittest.TestCase):
    def test_simple_var(self):
        t = template.Template(r"My name is: {{ name }}")
        self.assertEqual(t.generate(name="Alice"), b"My name is: Alice")
        self.assertEqual(t.generate(name="Bob"), b"My name is: Bob")

    def test_blocks(self):
        loader = template.DictLoader({
            "base.html": r"value: {% block value %}original{% end %}",
            "ext1.html": r'{% extends "base.html" %}{% block value %}new1{% end %}',
            "ext2.html": r'{% extends "base.html" %}{% block value %}{% super %}, new2{% end %}',
            "ext3.html": r'{% extends "ext2.html" %}{% block value %}{% super %}, new3{% end %}',
            "ext2_1.html": r'{% extends "base.html" %}{% block value %}{% super %}, a={{a}}{% end %}',
            "ext3_1.html": r'{% extends "ext2_1.html" %}{% block value %}{% super %}, a={{a}}{% end %}',
            "ext3_2.html": r'{% extends "ext2_1.html" %}{% block value %}{% super %}, a={{a}}:b={{b}}{% end %}',
            "ext3_3.html": r'{% extends "ext2_1.html" %}{% block value %}{% super %}, b={{b}}{% end %}',
        })
        self.assertEqual(loader.load("base.html").generate(), b"value: original")
        self.assertEqual(loader.load("ext1.html").generate(), b"value: new1")
        self.assertEqual(loader.load("ext2.html").generate(), b"value: original, new2")
        self.assertEqual(loader.load("ext3.html").generate(), b"value: original, new2, new3")

        self.assertEqual(loader.load("ext2_1.html").generate(a=-5), b"value: original, a=-5")
        self.assertEqual(loader.load("ext2_1.html").generate(a=42), b"value: original, a=42")

        self.assertEqual(loader.load("ext3_1.html").generate(a=-5), b"value: original, a=-5, a=-5")
        self.assertEqual(loader.load("ext3_1.html").generate(a=42), b"value: original, a=42, a=42")

        self.assertEqual(loader.load("ext3_2.html").generate(a=42, b=11), b"value: original, a=42, a=42:b=11")
        self.assertEqual(loader.load("ext3_3.html").generate(a=42, b=7), b"value: original, a=42, b=7")

        loader = template.DictLoader({
            "base.html": r"{% block v1 %}1{% end %} {% block v2 %}2{% end %}",
            "ext1.html": r'{% extends "base.html" %}{% block v1 %}Hello{% end %}{% block v2 %}World{% end %}',
            "ext2.html": r'{% extends "base.html" %}{% block v1 %}{% super %}+10{% end %}{% block v2 %}= 9 + {% super %}{% end %}',
        })
        self.assertEqual(loader.load("ext1.html").generate(), b"Hello World")
        self.assertEqual(loader.load("ext2.html").generate(), b"1+10 = 9 + 2")

    def test_if(self):
        t = template.Template(
            r"{% if isinstance(a, str)%}String{% elif a < 0 %}Negative{% elif a==1 %}One{% else %}Unknown{% end %}")
        self.assertEqual(t.generate(a=1), b"One")
        self.assertEqual(t.generate(a=-1), b"Negative")
        self.assertEqual(t.generate(a=-1.67), b"Negative")
        self.assertEqual(t.generate(a=-100), b"Negative")
        self.assertEqual(t.generate(a=42), b"Unknown")
        self.assertEqual(t.generate(a=42.5), b"Unknown")
        self.assertEqual(t.generate(a="meow"), b"String")

    def test_comment(self):
        self.assertEqual(
            template.Template(r"{% comment blah! %}42").generate(),
            b"42"
        )

    def test_set(self):
        self.assertEqual(
            template.Template(r"{% set x=42 %}{{ val + x }}").generate(val=-42),
            b"0"
        )
        self.assertEqual(
            template.Template(r"{% set x=val2 %}{{ val + x }}").generate(val=1, val2=10),
            b"11"
        )

    def test_loops(self):
        self.assertEqual(
            template.Template(r"{% for x in [1,2,3,4] %}{{ x }}:{% end %}").generate(),
            b"1:2:3:4:"
        )
        self.assertEqual(
            template.Template(r"{% set x=0 %}{% while x < 10 %}{{x}};{% set x += 2 %}{% end %}").generate(),
            b"0;2;4;6;8;"
        )

    def test_autoescape(self):
        t = template.Template(r"<{{x}}>")
        self.assertEqual(
            t.generate(x="<"),
            b"<&lt;>"
        )
        self.assertEqual(
            t.generate(x=">"),
            b"<&gt;>"
        )
        t2 = template.Template(r"{% autoescape None %}<{{x}}>")
        self.assertEqual(
            t2.generate(x="<"),
            b"<<>"
        )
        self.assertEqual(
            t2.generate(x=">"),
            b"<>>"
        )

    @defer.inlineCallbacks
    def test_deferreds(self):
        def _mkDeferred(rv, delay=None):
            d = defer.Deferred()
            if delay is None:
                d.callback(rv)
            else:
                reactor.callLater(delay, d.callback, rv)
            return d

        # Test that template immidiatly resolves deferreds if possible
        t = template.Template(r"-) {{x}} <-> {{y(63)}} :!")
        self.assertEqual(
            t.generate(x=_mkDeferred(42), y=_mkDeferred),
            b"-) 42 <-> 63 :!"
        )

        # Test delayed execution
        d = t.generate(
            x=_mkDeferred("hello", 0.1),
            y=lambda val: _mkDeferred(val - 60, 0.5)
        )
        self.assertTrue(isinstance(d, defer.Deferred), d)
        txt = yield d
        self.assertEqual(
            txt,
            b"-) hello <-> 3 :!"
        )
