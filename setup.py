#!/usr/bin/env python
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

import sys
import platform
from distutils import log
from distutils.version import LooseVersion
from distutils.version import StrictVersion

requires = ["twisted", "pyopenssl"]
extra = dict(extras_require={'ssl': requires})

py_version = platform.python_version()

# PyPy and setuptools don't get along too well, yet.
if platform.python_implementation().lower().startswith("pypy"):
    import distutils.core
    setup = distutils.core.setup

else:
    import setuptools
    setup = setuptools.setup

    try:
        from setuptools.command import egg_info
        egg_info.write_toplevel_names
    except (ImportError, AttributeError):
        pass
    else:
        """
        'twisted' should not occur in the top_level.txt file as this
        triggers a bug in pip that removes all of twisted when a package
        with a twisted plugin is removed.
        """
        def _top_level_package(name):
            return name.split('.', 1)[0]

        def _hacked_write_toplevel_names(cmd, basename, filename):
            pkgs = dict.fromkeys(
                [_top_level_package(k)
                    for k in cmd.distribution.iter_distribution_names()
                    if _top_level_package(k) != "twisted"
                ]
            )
            cmd.write_file("top-level names", filename, '\n'.join(pkgs) + '\n')

        egg_info.write_toplevel_names = _hacked_write_toplevel_names


setup(
    name="cyclone",
    version="2020.10.1",
    author="fiorix",
    author_email="fiorix@gmail.com",
    url="http://cyclone.io/",
    license="http://www.apache.org/licenses/LICENSE-2.0",
    description="Non-blocking web server. "
                "A facebook's Tornado on top of Twisted.",
    keywords="python non-blocking web server twisted facebook tornado",
    packages=["cyclone", "cyclone.tests", "cyclone.testing"],
    package_data={"twisted": [],
                  "cyclone": []},
    scripts=[],
    **extra
)

