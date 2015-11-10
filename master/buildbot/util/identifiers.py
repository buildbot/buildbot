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

import re

from buildbot import util

ident_re = re.compile('^[a-zA-Z_-][a-zA-Z0-9_-]*$')
initial_re = re.compile('^[^a-zA-Z_-]')
subsequent_re = re.compile('[^a-zA-Z0-9_-]')
trailing_digits_re = re.compile('_([0-9]+)$')


def isIdentifier(maxLength, object):
    if not isinstance(object, unicode):
        return False
    elif not ident_re.match(object):
        return False
    elif not 0 < len(object) <= maxLength:
        return False
    return True


def forceIdentifier(maxLength, str):
    if not isinstance(str, basestring):
        raise TypeError("%r cannot be coerced to an identifier" % (str,))

    # usually ascii2unicode can handle it
    str = util.ascii2unicode(str)
    if isIdentifier(maxLength, str):
        return str

    # trim to length and substitute out invalid characters
    str = str[:maxLength]
    str = initial_re.sub('_', str)
    str = subsequent_re.subn('_', str)[0]
    return str


def incrementIdentifier(maxLength, ident):
    num = 1
    mo = trailing_digits_re.search(ident)
    if mo:
        ident = ident[:mo.start(1) - 1]
        num = int(mo.group(1))
    num = '_%d' % (num + 1)
    if len(num) > maxLength:
        raise ValueError("cannot generate a larger identifier")
    ident = ident[:maxLength - len(num)] + num
    return ident
