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

import urllib
import cyclone.web

from twisted.trial import unittest
from twisted.internet import defer
from cyclone.auth import FacebookGraphMixin
from mock import patch, MagicMock


class TestHandler(cyclone.web.RequestHandler,
                  FacebookGraphMixin):
    pass


class TestFacebookGraphMixin(unittest.TestCase):
    def setUp(self):
        self.fgm = TestHandler(MagicMock(), MagicMock())

    @patch('cyclone.auth.httpclient.fetch')
    def test_facebook_request_post(self, mock):
        _args = {'message': 'test message'}
        self.fgm.facebook_request(
            "/me/feed",
            callback=self.fgm.async_callback(lambda x: x),
            access_token='dummy_token',
            post_args=_args
        )

        self.assertTrue(mock.called)
        args, kwargs = mock.call_args
        self.assertIn('postdata', kwargs)
        self.assertEqual(kwargs['postdata'],
                         urllib.urlencode(_args))
