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

import calendar
import time


def fixed_mktime_tz(data):
    if data[9] is None:
        # No zone info, so localtime is better assumption than GMT
        return time.mktime(data[:8] + (-1,))
    t = calendar.timegm(data)
    return t - data[9]


def patch():
    # Fix for http://bugs.python.org/issue14653 for Python 2.7.3 and below.
    # Required to fix http://trac.buildbot.net/ticket/2522 issue

    import email.utils
    email.utils.mktime_tz = fixed_mktime_tz
