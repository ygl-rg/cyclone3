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

"""
Command-line tool for creating cyclone applications out of the box. ::

    usage: cyclone app [options]
    Options:
     -h --help              Show this help.
     -n --new               Dumps a sample server code to stdout.
     -p --project=NAME      Create new cyclone project.
     -g --git               Use in conjunction with -p to make it a git \
repository.
     -m --modname=NAME      Use another name for the module \
[default: project_name]
     -v --version=VERSION   Set project version [default: 0.1]
     -s --set-pkg-version   Set version on package name [default: False]
     -t --target=PATH       Set path where project is created \
[default: current directory]
     -l --license=FILE      Append the following license file \
[default: Apache 2]
     -a --appskel=SKEL      Set the application skeleton [default: default]

    SKEL:
      default              Basic cyclone project
      signup               Basic sign up/in/out, password reset, etc
      foreman              Create a foreman based project \
(suited to run on heroku and other PaaS)

    Examples:
     For a simple hello world:
     $ cyclone app -n > hello.py

     For a project that requires sign up:
     $ cyclone app --project=foobar --appskel=signup
"""

from __future__ import with_statement
import base64
import getopt
import os
import re
import string
import sys
import uuid
import zipfile
from datetime import datetime

DEFAULT_LICENSE = """\
# Copyright %(year)s Foo Bar
# Powered by cyclone
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
"""

SAMPLE_SERVER = """\
#
# Start the server:
#   cyclone run server.py

import cyclone.web


class MainHandler(cyclone.web.RequestHandler):
    def get(self):
        self.write("Hello, world")


class Application(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
        ]

        settings = dict(
            xheaders=False,
            static_path="./static",
            templates_path="./templates",
        )

        cyclone.web.Application.__init__(self, handlers, **settings)\
"""


def new_project(**kwargs):
    zf = kwargs["skel"]
    dst = kwargs["project_path"]

    os.mkdir(dst, 0o755)
    for n in zf.namelist():
        mod = n.replace("modname", kwargs["modname"])
        if n[-1] in (os.path.sep, "\\", "/"):
            os.mkdir(os.path.join(dst, mod), 0o755)
        else:
            ext = n.rsplit(".", 1)[-1]
            fd = open(os.path.join(dst, mod), "w", 0o644)
            if ext in ("conf", "html", "txt", "py", "md", "sh", "d") or \
                    n in ("Procfile"):
                #print "patching: %s" % n
                fd.write(string.Template(zf.read(n)).substitute(kwargs))
            else:
                fd.write(zf.read(n))
            fd.close()

    # make sure we can actually run start.sh
    if os.path.exists(os.path.join(dst, "start.sh")):
        os.chmod(os.path.join(dst, "start.sh"), 0o755)

    if kwargs["use_git"] is True:
        os.chdir(kwargs["project_path"])
        os.system("git init")
        os.system("git add .gitignore")


def usage(version):
    print("""\
usage: cyclone app [options]
Options:
 -h --help              Show this help.
 -n --new               Dumps a sample server code to stdout.
 -p --project=NAME      Create new cyclone project.
 -g --git               Use in conjunction with -p to make it a git repository.
 -m --modname=NAME      Use another name for the module [default: project_name]
 -v --version=VERSION   Set project version [default: %s]
 -s --set-pkg-version   Set version on package name [default: False]
 -t --target=PATH       Set path where project is created \
[default: current directory]
 -l --license=FILE      Append the following license file [default: Apache 2]
 -a --appskel=SKEL      Set the application skeleton [default: default]

SKEL:
  default              Basic cyclone project
  signup               Basic sign up/in/out, password reset, etc
  foreman              Create a foreman based project \
(suited to run on heroku and other PaaS)

Examples:
 For a simple hello world:
 $ cyclone app -n > hello.py

 For a project that requires sign up:
 $ cyclone app --project=foobar --appskel=signup""" % (version))
    sys.exit(0)


def main():
    project = None
    modname = None
    use_git = False
    set_pkg_version = False
    default_version, version = "0.1", None
    default_target, target = os.getcwd(), None
    license_file = None
    skel = "default"

    shortopts = "hgsnp:m:v:t:l:a:"
    longopts = ["help", "new", "git", "set-pkg-version",
                 "project=", "modname=", "version=", "target=", "license=",
                 "appskel="]
    try:
        opts, args = getopt.getopt(sys.argv[1:], shortopts, longopts)
    except getopt.GetoptError:
        usage(default_version)

    for o, a in opts:
        if o in ("-h", "--help"):
            usage(default_version)

        if o in ("-n", "--new"):
            print("%s%s" % (DEFAULT_LICENSE % {"year": datetime.now().year},
                            SAMPLE_SERVER))
            sys.exit(1)

        if o in ("-g", "--git"):
            use_git = True

        if o in ("-s", "--set-pkg-version"):
            set_pkg_version = True

        elif o in ("-p", "--project"):
            project = a

        elif o in ("-m", "--modname"):
            modname = a

        elif o in ("-v", "--version"):
            version = a

        elif o in ("-t", "--target"):
            target = a

        elif o in ("-l", "--license"):
            license_file = a

        elif o in ("-a", "--appskel"):
            if a in ("default", "foreman", "signup"):
                skel = a
            else:
                print("Invalid appskel name: %s" % a)
                sys.exit(1)

    if license_file is None:
        license = DEFAULT_LICENSE % {"year": datetime.now().year}
    else:
        with open(license_file) as f:
            license = f.read()

    if project is None:
        usage(default_version)
    elif not re.match(r"^[0-9a-z][0-9a-z_-]+$", project, re.I):
        print("Invalid project name.")
        sys.exit(1)

    mod_is_proj = False
    if modname is None:
        mod_is_proj = True
        modname = project

    if modname in ("frontend", "tools", "twisted"):
        if mod_is_proj is True:
            print("Please specify a different modname, using "
                  "--modname=name. '%s' is not allowed." % modname)
        else:
            print("Please specify a different modname. "
                  "'%s' is not allowed." % modname)
        sys.exit(1)

    if not re.match(r"^[0-9a-z_]+$", modname, re.I):
        print("Invalid module name.")
        sys.exit(1)

    if version is None:
        version = default_version

    if target is None:
        target = default_target

    if not (os.access(target, os.W_OK) and os.access(target, os.X_OK)):
        print("Cannot create project on target directory "
              "'%s': permission denied" % target)
        sys.exit(1)

    name = "Foo Bar"
    email = "root@localhost"
    if use_git is True:
        with os.popen("git config --list") as fd:
            for line in fd:
                line = line.replace("\r", "").replace("\n", "")
                try:
                    k, v = line.split("=", 1)
                except:
                    continue

                if k == "user.name":
                    name = v
                elif k == "user.email":
                    email = v

    skel = zipfile.ZipFile(open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "appskel_%s.zip" % skel), "rb"))

    if set_pkg_version is True:
        project_name = "%s-%s" % (project, version)
    else:
        project_name = project

    project_path = os.path.join(target, project_name)
    if os.path.exists(project_path):
        print("Directory '%s' already exists. Either remove it, or set a "
              "different project name. "
              "e.g.: python -m cyclone.app -p %sz" % (project_path,
                                                      project_name))
        sys.exit(1)

    new_project(skel=skel,
                name=name,
                email=email,
                project=project,
                project_name=project_name,
                project_path=project_path,
                modname=modname,
                version=version,
                target=target,
                use_git=use_git,
                license=license,
                cookie_secret=base64.b64encode(uuid.uuid4().bytes +
                                               uuid.uuid4().bytes))


if __name__ == "__main__":
    main()
