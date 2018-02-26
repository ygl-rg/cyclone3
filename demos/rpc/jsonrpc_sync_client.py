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

import json
import urllib


def request(url, func, *args):
    req = json.dumps({"method": func, "params": args, "id": 1})
    result = urllib.urlopen(url, req).read()
    try:
        response = json.loads(result)
    except:
        return "error: %s" % result
    else:
        return response.get("result", response.get("error"))

url = "http://localhost:8888/jsonrpc"
print "echo:", request(url, "echo", "foo bar")
print "sort:", request(url, "sort", ["foo", "bar"])
print "count:", request(url, "count", ["foo", "bar"])
print "geoip_lookup:", request(url, "geoip_lookup", "google.com")
