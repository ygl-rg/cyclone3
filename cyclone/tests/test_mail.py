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
from cyclone.mail import ContextFactory, ClientContextFactory, Message
from cyclone.mail import sendmail
from unittest.mock import Mock, patch


class ContextFactoryTest(unittest.TestCase):
    def test_no_sslv3(self):
        """We must disable ssl v3."""
        ClientContextFactory.getContext = Mock()
        cf = ContextFactory()
        ctx = cf.getContext()
        ctx.set_options.assert_called_with(33554432)


class MessageTest(unittest.TestCase):
    def setUp(self):
        self.message = Message(
            "foo@example.com",
            ["bar@example.com"],
            "hi thar",
            "This is a message."
        )

    def test_init(self):
        self.assertTrue(self.message.message)
        str(self.message)

    def test_init_single_addr(self):
        message = Message(
            "foo@example.com",
            "bar@example.com",
            "hi thar",
            "This is a message."
        )
        self.assertTrue(isinstance(message.to_addrs, list))

    def test_attach(self):
        open("foo.txt", "w").write("sometext")
        self.message.attach("foo.txt")
        self.assertTrue(self.message.msg)

    def test_render(self):
        self.message.add_header("X-MailTag", "foobar")
        sio = self.message.render()
        self.assertTrue("foo@example.com" in sio.getvalue())

    @patch("cyclone.mail.reactor.connectTCP")
    def test_sendmail(self, conn):
        sendmail(
            {"host": "localhost", "tls": True},
            self.message
        )
        self.assertTrue(conn.call_count)
