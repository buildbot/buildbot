# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import os
import shutil
import sys
from subprocess import call
from subprocess import check_call
from textwrap import dedent

from twisted.trial import unittest


class BuildbotWWWPkg(unittest.TestCase):
    pkgName = "buildbot_www_react"
    pkgPaths = ["www", "react-base"]
    epName = "base_react"

    loadTestScript = dedent(r"""
        from importlib.metadata import entry_points
        import re
        apps = {}

        eps = entry_points()
        entry_point = "buildbot.www"
        if hasattr(eps, "select"):
            entry_point_group = eps.select(group=entry_point)
        else:
            entry_point_group = eps.get(entry_point, [])

        for ep in entry_point_group:
            apps[ep.name] = ep.load()

        print(apps["%(epName)s"])
        expected_file = "scripts.js"
        if "%(epName)s" == "base_react":
            expected_file = "index.html"
        assert(expected_file in apps["%(epName)s"].resource.listNames())
        assert(re.match(r'\d+\.\d+\.\d+', apps["%(epName)s"].version) is not None)
        assert(apps["%(epName)s"].description is not None)
        """)

    @property
    def path(self):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", *self.pkgPaths))

    def rmtree(self, d):
        if os.path.isdir(d):
            shutil.rmtree(d)

    def setUp(self):
        call("pip uninstall -y " + self.pkgName, shell=True)
        self.rmtree(os.path.join(self.path, "build"))
        self.rmtree(os.path.join(self.path, "dist"))
        self.rmtree(os.path.join(self.path, "static"))

    def run_build(self, kind):
        check_call([sys.executable, "-m", "build", "--no-isolation", f"--{kind}"], cwd=self.path)

    def check_correct_installation(self):
        # assert we can import buildbot_www
        # and that it has an endpoint with resource containing file "script.js" or "index.html" (in case of buildbot_www_react)
        check_call([sys.executable, '-c', self.loadTestScript % dict(epName=self.epName)])

    def test_wheel(self):
        self.run_build("wheel")
        check_call("pip install build dist/*.whl", shell=True, cwd=self.path)
        self.check_correct_installation()

    def test_develop_via_pip(self):
        check_call("pip install build -e .", shell=True, cwd=self.path)
        self.check_correct_installation()

    def test_sdist(self):
        self.run_build("sdist")
        check_call("pip install build dist/*.tar.gz", shell=True, cwd=self.path)
        self.check_correct_installation()


class BuildbotConsolePkg(BuildbotWWWPkg):
    pkgName = "buildbot-react-console-view"
    pkgPaths = ["www", "react-console_view"]
    epName = "react_console_view"


class BuildbotWaterfallPkg(BuildbotWWWPkg):
    pkgName = "buildbot-react-waterfall-view"
    pkgPaths = ["www", "react-waterfall_view"]
    epName = "react_waterfall_view"
