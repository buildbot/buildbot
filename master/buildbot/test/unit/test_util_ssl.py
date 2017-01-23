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

from __future__ import absolute_import
from __future__ import print_function

import mock

from twisted.trial import unittest

from buildbot import config
from buildbot.util import ssl


class Tests(unittest.TestCase):

    @ssl.skipUnless
    def test_ClientContextFactory(self):
        from twisted.internet.ssl import ClientContextFactory
        self.assertEqual(ssl.ClientContextFactory, ClientContextFactory)

    @ssl.skipUnless
    def test_ConfigError(self):
        ssl.ssl_import_error = "lib xxx do not exist"
        ssl.has_ssl = False
        self.patch(config, "_errors", mock.Mock())
        ssl.ensureHasSSL("myplugin")
        config._errors.addError.assert_called_with(
            "TLS dependencies required for myplugin are not installed : "
            "lib xxx do not exist\n pip install 'buildbot[tls]'")
