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


from twisted.trial import unittest

from buildbot.config.errors import capture_config_errors
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.util import ssl


class Tests(unittest.TestCase, ConfigErrorsMixin):
    @ssl.skipUnless
    def test_ClientContextFactory(self):
        from twisted.internet.ssl import ClientContextFactory

        self.assertEqual(ssl.ClientContextFactory, ClientContextFactory)

    @ssl.skipUnless
    def test_ConfigError(self):
        old_error = ssl.ssl_import_error
        old_has_ssl = ssl.has_ssl
        try:
            ssl.ssl_import_error = "lib xxx do not exist"
            ssl.has_ssl = False
            with capture_config_errors() as errors:
                ssl.ensureHasSSL("myplugin")
            self.assertConfigError(
                errors,
                "TLS dependencies required for myplugin are not installed : "
                "lib xxx do not exist\n pip install 'buildbot[tls]'",
            )
        finally:
            ssl.ssl_import_error = old_error
            ssl.has_ssl = old_has_ssl
