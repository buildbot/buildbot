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

ident_re = re.compile('^[a-zA-Z\u00a0-\U0010ffff_-][a-zA-Z0-9\u00a0-\U0010ffff_-]*$', flags=re.UNICODE)
initial_re = re.compile('^[^a-zA-Z_-]')
subsequent_re = re.compile('[^a-zA-Z0-9_-]')
trailing_digits_re = re.compile('_([0-9]+)$')


def isIdentifier(maxLength, obj):
    if not isinstance(obj, str):
        return False
    elif not ident_re.match(obj):
        return False
    elif not obj or len(obj) > maxLength:
        return False
    return True


def forceIdentifier(maxLength, s):
    if not isinstance(s, str):
        raise TypeError("%r cannot be coerced to an identifier" % (str,))

    # usually bytes2unicode can handle it
    s = util.bytes2unicode(s)
    if isIdentifier(maxLength, s):
        return s

    # trim to length and substitute out invalid characters
    s = s[:maxLength]
    s = initial_re.sub('_', s)
    s = subsequent_re.subn('_', s)[0]
    return s


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
