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

from twisted.python.compat import nativeString
from twisted.python.compat import networkString

# patch for http://twistedmatrix.com/trac/ticket/9127
# unfortunately the impacted code is deeply inside render method, so we need to patch the whole
# render method


def render(self, request):
    """
    Send www-authenticate headers to the client
    """
    def generateWWWAuthenticate(scheme, challenge):
        _l = []
        for k, v in challenge.items():
            _l.append(networkString("%s=%s" %
                                    (nativeString(k), quoteString(nativeString(v)))))
        return b" ".join([scheme, b", ".join(_l)])

    def quoteString(s):
        return '"%s"' % (s.replace('\\', '\\\\').replace('"', '\\"'),)

    request.setResponseCode(401)
    for fact in self._credentialFactories:
        challenge = fact.getChallenge(request)
        request.responseHeaders.addRawHeader(
            b'www-authenticate',
            generateWWWAuthenticate(fact.scheme, challenge))
    if request.method == b'HEAD':
        return b''
    return b'Unauthorized'


def patch():
    from twisted.web._auth.wrapper import UnauthorizedResource
    UnauthorizedResource.render = render
