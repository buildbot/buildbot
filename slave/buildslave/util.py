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

import time
import types


def remove_userpassword(url):
    if '@' not in url:
        return url
    if '://' not in url:
        return url

    # urlparse would've been nice, but doesn't support ssh... sigh
    (protocol, repo_url) = url.split('://')
    repo_url = repo_url.split('@')[-1]

    return protocol + '://' + repo_url


def now(_reactor=None):
    if _reactor and hasattr(_reactor, "seconds"):
        return _reactor.seconds()
    else:
        return time.time()


class Obfuscated:

    """An obfuscated string in a command"""

    def __init__(self, real, fake):
        self.real = real
        self.fake = fake

    def __str__(self):
        return self.fake

    def __repr__(self):
        return repr(self.fake)

    def __eq__(self, other):
        return other.__class__ is self.__class__ and \
            other.real == self.real and \
            other.fake == self.fake

    @staticmethod
    def to_text(s):
        if isinstance(s, (str, unicode)):
            return s
        else:
            return str(s)

    @staticmethod
    def get_real(command):
        rv = command
        if isinstance(command, types.ListType):
            rv = []
            for elt in command:
                if isinstance(elt, Obfuscated):
                    rv.append(elt.real)
                else:
                    rv.append(Obfuscated.to_text(elt))
        return rv

    @staticmethod
    def get_fake(command):
        rv = command
        if isinstance(command, types.ListType):
            rv = []
            for elt in command:
                if isinstance(elt, Obfuscated):
                    rv.append(elt.fake)
                else:
                    rv.append(Obfuscated.to_text(elt))
        return rv
