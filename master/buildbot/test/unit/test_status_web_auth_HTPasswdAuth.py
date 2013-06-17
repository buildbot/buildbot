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
Test Passwords
desbuildmaster:yifux5rkzvI5w
desbuildslave:W8SPURMnCs7Tc
desbuildbot:IzclhyfHAq6Oc
"""

from twisted.trial import unittest
from buildbot.status.web.auth import HTPasswdAuth
from buildbot.test.util import compat
from buildbot.test.unit.test_status_web_authz_Authz import StubRequest

class TestHTPasswdAuth(unittest.TestCase):

    htpasswd = HTPasswdAuth(__file__)

    @compat.skipUnlessPlatformIs('posix') # crypt module
    def test_authenticate_des(self):
        for key in ('buildmaster','buildslave','buildbot'):                
            if self.htpasswd.authenticate(StubRequest('des'+key, key)) is None:
                self.fail("authenticate failed for '%s'" % ('des'+key))

    def test_authenticate_unknown(self):
        if self.htpasswd.authenticate(StubRequest('foo', 'bar')) == "foo":
            self.fail("authenticate succeed for 'foo:bar'")

    @compat.skipUnlessPlatformIs('posix') # crypt module
    def test_authenticate_wopassword(self):
        for algo in ('des','md5','sha'):
            user = algo + "buildmaster"
            if self.htpasswd.authenticate(StubRequest(user, '')) == user:
                self.fail("authenticate succeed for %s w/o password" % (user))

    @compat.skipUnlessPlatformIs('posix') # crypt module
    def test_authenticate_wrongpassword(self):
        for algo in ('des','md5','sha'):
            user = algo + "buildmaster"
            if self.htpasswd.authenticate(StubRequest(user, algo)) == user:
                self.fail(
                    "authenticate succeed for %s w/ wrong password" % (user))

