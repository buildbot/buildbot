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

from twisted.trial import unittest
from subprocess import check_call, call


class BuildbotPkg(unittest.TestCase):

    @property
    def www(self):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "www"))

    def rmtree(self, d):
        if os.path.isdir(d):
            shutil.rmtree(d)

    def setUp(self):
        call("pip uninstall -y buildbot_www", shell=True)
        self.rmtree(os.path.join(self.www, "build"))
        self.rmtree(os.path.join(self.www, "dist"))
        self.rmtree(os.path.join(self.www, "static"))

    def run_setup(self, cmd):
        check_call("python setup.py " + cmd, shell=True, cwd=self.www)

    def check_correct_installation(self):
        # assert we can import buildbot_www
        # and that it has an endpoint with resource containing file "script.js"
        check_call([
            'python', '-c',
            'import buildbot_www;'  # no comma
            'assert("scripts.js" in buildbot_www.ep.resource.listNames())'])

    def test_install(self):
        self.run_setup("install")
        self.check_correct_installation()

    def test_wheel(self):
        self.run_setup("bdist_wheel")
        check_call("pip install dist/*.whl", shell=True, cwd=self.www)
        self.check_correct_installation()

    def test_develop(self):
        self.run_setup("develop")
        self.check_correct_installation()

    def test_develop_via_pip(self):
        check_call("pip install -e .", shell=True, cwd=self.www)
        self.check_correct_installation()

    def test_sdist(self):
        self.run_setup("sdist")
        check_call("pip install dist/*.tar.gz", shell=True, cwd=self.www)
        self.check_correct_installation()

