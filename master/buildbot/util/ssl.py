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

"""
This modules acts the same as twisted.internet.ssl except it does not raise ImportError

Modules using this should call ensureHasSSL in order to make sure that the user installed buildbot[tls]
"""

from __future__ import absolute_import
from __future__ import print_function

try:
    from twisted.internet.ssl import *  # noqa pylint: disable=unused-wildcard-import, wildcard-import
    ssl_import_error = None
    has_ssl = True
except ImportError as e:
    ssl_import_error = str(e)
    has_ssl = False


def ensureHasSSL(module):
    from buildbot.config import error
    if not has_ssl:
        error("TLS dependencies required for {} are not installed : {}\n pip install 'buildbot[tls]'".format(
            module, ssl_import_error))


def skipUnless(f):
    import unittest
    return unittest.skipUnless(has_ssl, "TLS dependencies required")(f)
