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
import os
import tempfile

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.scripts import processwwwindex


class TestUsersClient(unittest.TestCase):

    def setUp(self):
        # un-do the effects of @in_reactor
        self.patch(processwwwindex, 'processwwwindex',
                   processwwwindex.processwwwindex._orig)

    @defer.inlineCallbacks
    def test_no_src_dir(self):
        ret = yield processwwwindex.processwwwindex({})

        self.assertEqual(ret, 1)

    @defer.inlineCallbacks
    def test_no_dst_dir(self):
        ret = yield processwwwindex.processwwwindex({'str-dir': '/some/no/where'})

        self.assertEqual(ret, 1)

    @defer.inlineCallbacks
    def test_invalid_input_dir(self):
        ret = yield processwwwindex.processwwwindex({'src-dir': '/some/no/where',
                                                     'dst-dir': '/some/no/where'})

        self.assertEqual(ret, 2)

    @defer.inlineCallbacks
    def test_output_config(self):
        # Get temporary file ending with ".html" that has visible to other
        # operations name.
        with tempfile.TemporaryDirectory(suffix='output_config') as src_dir:
            dst_dir = os.path.join(src_dir, 'output_dir')

            src_html_path = os.path.join(src_dir, 'index.html')
            dst_html_path = os.path.join(dst_dir, 'index.html')

            with open(src_html_path, 'w') as f:
                f.write('{{ configjson|safe }}')

            ret = yield processwwwindex.processwwwindex({'src-dir': src_dir,
                                                         'dst-dir': dst_dir})

            self.assertEqual(ret, 0)
            with open(dst_html_path) as f:
                config = json.loads(f.read())
                self.assertTrue(isinstance(config, dict))
