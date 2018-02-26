#!/usr/bin/env python
# coding: utf-8
#
$license

import re
import sys

if __name__ == "__main__":
    try:
        filename = sys.argv[1]
        assert filename != "-"
        fd = open(filename)
    except:
        fd = sys.stdin

    line_re = re.compile(r'="([^"]+)"')
    for line in fd:
        line = line_re.sub(r"=\\1", line)
        sys.stdout.write(line)
    fd.close()
