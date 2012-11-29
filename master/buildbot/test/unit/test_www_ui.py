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

from buildbot.www import ui
from buildbot.test.util import www
from twisted.trial import unittest

class Test(www.WwwTestMixin, unittest.TestCase):
    def test_render(self):
        master = self.make_master(url='h:/a/b/')
        rsrc = ui.UIResource(master, extra_routes=[], index_html='base_url:"h:/a/b/"')

        d = self.render_resource(rsrc, [''])
        @d.addCallback
        def check(rv):
            self.assertIn('base_url:"h:/a/b/"', rv)
        return d

class TestGhostPy(www.WwwTestMixin,www.WwwGhostTestMixin, unittest.TestCase):
    def test_doh_dojo_tests_colors(self):
        """simple test to make sure our doh tester work. tests an already working dojo unit test"""
        return self.doDohPageLoadRunnerTests()

    def test_doh_dojo_tests_buildbotsuite(self):
        return self.doDohPageLoadRunnerTests("all")
