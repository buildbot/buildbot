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

import json
import re
import buildbot
from buildbot.www import ui
from buildbot.test.util import www
from twisted.trial import unittest

class Test(www.WwwTestMixin, unittest.TestCase):
    class Application:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    def test_render(self):
        master = self.make_master(url='h:/a/b/')
        rsrc = ui.UIResource(master, {
            'base' : self.Application(description='B',
                version='1.0',
                static_dir='/static',
                packages=['pkg1', 'pkg2'],
                routes=[{'name':'rt1'}]),
        })

        d = self.render_resource(rsrc, [''])
        @d.addCallback
        def check(rv):
            # extract the dojoConfig JSON and compare
            mo = re.search("<script>var dojoConfig = (.*?);</script>", rv, re.S)
            if not mo:
                self.fail("could not find dojoConfig")
            dojoConfig = json.loads(mo.group(1))
            self.assertEqual(dojoConfig, {
                'async': 1,
                'baseUrl': 'h:/a/b',
                'bb': {
                    'appInfo': [
                        {'description': 'B', 'name': 'base', 'version': '1.0'}
                    ],
                    'buildbotVersion': buildbot.version,
                    'routes': [{'name': 'rt1'}],
                    'wsUrl': 'h:/a/b/ws',
                },
                'packages': [
                    {'location': 'app/base/pkg1', 'name': 'pkg1'},
                    {'location': 'app/base/pkg2', 'name': 'pkg2'},
                ],
                'tlmSiblingOfDojo': 0,
            })
        return d

class TestGhostPy(www.WwwTestMixin,www.WwwGhostTestMixin, unittest.TestCase):
    def test_doh_dojo_tests_colors(self):
        """simple test to make sure our doh tester work. tests an already working dojo unit test"""
        return self.doDohPageLoadRunnerTests()

    def test_doh_dojo_tests_buildbotsuite(self):
        return self.doDohPageLoadRunnerTests("all")
