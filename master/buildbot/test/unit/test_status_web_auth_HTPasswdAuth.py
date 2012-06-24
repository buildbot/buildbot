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
md5buildmaster:$apr1$pSepI8Wp$eJZcfhnpENrRlUn28wak50
md5buildslave:$apr1$dtX6FDei$vFB5BlnR9bjQisy7v3ZaC0
md5buildbot:$apr1$UcfsHmrF$i9fYa4OsPI3AK8UBbN3ju1
shabuildmaster:{SHA}vpAKSO3uPt6z8KL6cqf5W5Sredk=
shabuildslave:{SHA}sNA10GbdONwGJ+a8VGRNtEyWd9I=
shabuildbot:{SHA}TwEDa5Q31ZhI4GLmIbE1VrrAkpk=
"""


from twisted.trial import unittest

from buildbot.status.web.auth import HTPasswdAuth

class TestHTPasswdAuth(unittest.TestCase):

    htpasswd = HTPasswdAuth(__file__)

    def test_authenticate(self):
    	algos = ('des',)
        try:
            from ctypes import CDLL
            apr = CDLL("libaprutil-1.so.0")
            if apr:
                algos = ('des','md5','sha')
        except:
            pass
   
        for algo in algos:
            for key in ('buildmaster','buildslave','buildbot'):
                if self.htpasswd.authenticate(algo+key, key) == False:
			raise unittest.FailTest("authenticate faild for '%s'"
			                        % (algo+key))

    def test_authenticate_unknown(self):
        if self.htpasswd.authenticate('foo', 'bar') == True:
            raise unittest.FailTest("authenticate succeed for 'foo:bar'")

    def test_authenticate_wopassword(self):
        for algo in ('des','md5','sha'):
            if self.htpasswd.authenticate(algo+'buildmaster', '') == True:
                raise unittest.FailTest("authenticate succeed for %s w/o password"
                                        % (algo+'buildmaster'))

    def test_authenticate_wrongpassword(self):
        for algo in ('des','md5','sha'):
            if self.htpasswd.authenticate(algo+'buildmaster', algo) == True:
                raise unittest.FailTest("authenticate succeed for %s w/ wrong password"
                                        % (algo+'buildmaster'))




