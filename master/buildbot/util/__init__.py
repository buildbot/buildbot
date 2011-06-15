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


import time, re, string
import datetime
import calendar
from buildbot.util.misc import deferredLocked, SerializedInvocation

def naturalSort(l):
    """Returns a sorted copy of l, so that numbers in strings are sorted in the
    proper order.

    e.g. ['foo10', 'foo1', 'foo2'] will be sorted as ['foo1', 'foo2', 'foo10']
    instead of the default ['foo1', 'foo10', 'foo2']"""
    l = l[:]
    def try_int(s):
        try:
            return int(s)
        except ValueError:
            return s
    def key_func(item):
        return [try_int(s) for s in re.split('(\d+)', item)]
    # prepend integer keys to each element, sort them, then strip the keys
    keyed_l = [ (key_func(i), i) for i in l ]
    keyed_l.sort()
    l = [ i[1] for i in keyed_l ]
    return l

def flatten(l):
    """Flatten nested lists into a single-level list"""
    if l and type(l[0]) == list:
        rv = []
        for e in l:
            if type(e) == list:
                rv.extend(e)
            else:
                rv.append(e)
        return rv
    else:
        return l

def now(_reactor=None):
    """Get the time, using reactor.seconds or time.time"""
    if _reactor and hasattr(_reactor, "seconds"):
        return _reactor.seconds()
    else:
        return time.time()

def formatInterval(eta):
    eta_parts = []
    if eta > 3600:
        eta_parts.append("%d hrs" % (eta / 3600))
        eta %= 3600
    if eta > 60:
        eta_parts.append("%d mins" % (eta / 60))
        eta %= 60
    eta_parts.append("%d secs" % eta)
    return ", ".join(eta_parts)

class ComparableMixin:
    """Specify a list of attributes that are 'important'. These will be used
    for all comparison operations."""

    compare_attrs = []

    class _None:
        pass

    def __hash__(self):
        alist = [self.__class__] + \
                [getattr(self, name, self._None) for name in self.compare_attrs]
        return hash(tuple(map(str, alist)))

    def __cmp__(self, them):
        result = cmp(type(self), type(them))
        if result:
            return result

        result = cmp(self.__class__.__name__, them.__class__.__name__)
        if result:
            return result

        result = cmp(self.compare_attrs, them.compare_attrs)
        if result:
            return result

        self_list = [getattr(self, name, self._None)
                     for name in self.compare_attrs]
        them_list = [getattr(them, name, self._None)
                     for name in self.compare_attrs]
        return cmp(self_list, them_list)

# Remove potentially harmful characters from builder name if it is to be
# used as the build dir.
badchars_map = string.maketrans("\t !#$%&'()*+,./:;<=>?@[\\]^{|}~",
                                "______________________________")
def safeTranslate(str):
    if isinstance(str, unicode):
        str = str.encode('utf8')
    return str.translate(badchars_map)

def none_or_str(x):
    """Cast X to a str if it is not None"""
    if x is not None and not isinstance(x, str):
        return str(x)
    return x

# place a working json module at 'buildbot.util.json'.  Code is adapted from
# Paul Wise <pabs@debian.org>:
#   http://lists.debian.org/debian-python/2010/02/msg00016.html
# json doesn't exist as a standard module until python2.6
# However python2.6's json module is much slower than simplejson, so we prefer
# to use simplejson if available.
try:
    import simplejson as json
    assert json
except ImportError:
    import json # python 2.6 or 2.7
try:
    _tmp = json.loads
except AttributeError:
    import warnings
    import sys
    warnings.warn("Use simplejson, not the old json module.")
    sys.modules.pop('json') # get rid of the bad json module
    import simplejson as json

# changes and schedulers consider None to be a legitimate name for a branch,
# which makes default function keyword arguments hard to handle.  This value
# is always false.
class NotABranch:
    def __nonzero__(self):
        return False
NotABranch = NotABranch()

# time-handling methods

class UTC(datetime.tzinfo):
    """Simple definition of UTC timezone"""
    def utcoffset(self, dt):
        return datetime.timedelta(0)

    def dst(self, dt):
        return datetime.timedelta(0)

    def tzname(self):
        return "UTC"
UTC = UTC()

def epoch2datetime(epoch):
    """Convert a UNIX epoch time to a datetime object, in the UTC timezone"""
    return datetime.datetime.fromtimestamp(epoch, tz=UTC)

def datetime2epoch(dt):
    """Convert a non-naive datetime object to a UNIX epoch timestamp"""
    return calendar.timegm(dt.utctimetuple())

__all__ = [
    'naturalSort', 'now', 'formatInterval', 'ComparableMixin', 'json',
    'safeTranslate', 'remove_userpassword', 'LRUCache', 'none_or_str',
    'NotABranch', 'deferredLocked', 'SerializedInvocation', 'UTC' ]
