#!/usr/bin/env python
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

import cyclone.escape
import cyclone.httpclient
from twisted.internet import defer, reactor


@defer.inlineCallbacks
def test():
    print("get http://google.com followRecirect=0")
    response = yield cyclone.httpclient.fetch("http://google.com/")
    print("headers:", response.headers)
    print("code and phrase:", response.code, response.phrase)
    print("length and body:", response.length, response.body)

    print("\nget http://google.com followRecirect=1")
    response = yield cyclone.httpclient.fetch("http://google.com/",
                                              followRedirect=1, maxRedirects=2)
    print("headers:", response.headers)
    print("code and phrase:", response.code, response.phrase)
    print("length and body:", response.length, response.body)

    #print("\npost")
    #json = cyclone.escape.json_encode({"user":"foo", "pass":"bar"})
    #response = yield cyclone.httpclient.fetch("http://localhost:8888/",
    #                        followRedirect=1, maxRedirects=2, postdata=json,
    #                        headers={"Content-Type":["application/json"]})
    #print("headers:", response.headers)
    #print("code and phrase:", response.code, response.phrase)
    #print("length and body:", response.length, response.body)


if __name__ == "__main__":
    test().addCallback(lambda ign: reactor.stop())
    reactor.run()
