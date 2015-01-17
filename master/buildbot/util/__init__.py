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


import calendar
import datetime
import locale
import re
import string
import time
import types

from twisted.python import reflect

from buildbot.util.misc import SerializedInvocation
from buildbot.util.misc import deferredLocked


def naturalSort(l):
    l = l[:]

    def try_int(s):
        try:
            return int(s)
        except ValueError:
            return s

    def key_func(item):
        return [try_int(s) for s in re.split(r'(\d+)', item)]
    # prepend integer keys to each element, sort them, then strip the keys
    keyed_l = sorted([(key_func(i), i) for i in l])
    l = [i[1] for i in keyed_l]
    return l


def flatten(l, types=list):
    if l and isinstance(l, types):
        rv = []
        for e in l:
            if isinstance(e, types):
                rv.extend(flatten(e))
            else:
                rv.append(e)
        return rv
    else:
        return l


def now(_reactor=None):
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

    compare_attrs = []

    class _None:
        pass

    def __hash__(self):
        compare_attrs = []
        reflect.accumulateClassList(self.__class__, 'compare_attrs', compare_attrs)

        alist = [self.__class__] + \
                [getattr(self, name, self._None) for name in compare_attrs]
        return hash(tuple(map(str, alist)))

    def __cmp__(self, them):
        result = cmp(type(self), type(them))
        if result:
            return result

        result = cmp(self.__class__, them.__class__)
        if result:
            return result

        compare_attrs = []
        reflect.accumulateClassList(self.__class__, 'compare_attrs', compare_attrs)

        self_list = [getattr(self, name, self._None)
                     for name in compare_attrs]
        them_list = [getattr(them, name, self._None)
                     for name in compare_attrs]
        return cmp(self_list, them_list)


def diffSets(old, new):
    if not isinstance(old, set):
        old = set(old)
    if not isinstance(new, set):
        new = set(new)
    return old - new, new - old

# Remove potentially harmful characters from builder name if it is to be
# used as the build dir.
badchars_map = string.maketrans("\t !#$%&'()*+,./:;<=>?@[\\]^{|}~",
                                "______________________________")


def safeTranslate(str):
    if isinstance(str, unicode):
        str = str.encode('utf8')
    return str.translate(badchars_map)


def none_or_str(x):
    if x is not None and not isinstance(x, str):
        return str(x)
    return x


def ascii2unicode(x):
    if isinstance(x, (unicode, types.NoneType)):
        return x
    return unicode(x, 'ascii')

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
    import json  # python 2.6 or 2.7
try:
    _tmp = json.loads
except AttributeError:
    import warnings
    import sys
    warnings.warn("Use simplejson, not the old json module.")
    sys.modules.pop('json')  # get rid of the bad json module
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
    if epoch is not None:
        return datetime.datetime.fromtimestamp(epoch, tz=UTC)


def datetime2epoch(dt):
    """Convert a non-naive datetime object to a UNIX epoch timestamp"""
    if dt is not None:
        return calendar.timegm(dt.utctimetuple())


# TODO: maybe "merge" with formatInterval?
def human_readable_delta(start, end):
    """
    Return a string of human readable time delta.
    """
    start_date = datetime.datetime.fromtimestamp(start)
    end_date = datetime.datetime.fromtimestamp(end)
    delta = end_date - start_date

    result = []
    if delta.days > 0:
        result.append('%d days' % (delta.days,))
    if delta.seconds > 0:
        hours = delta.seconds / 3600
        if hours > 0:
            result.append('%d hours' % (hours,))
        minutes = (delta.seconds - hours * 3600) / 60
        if minutes:
            result.append('%d minutes' % (minutes,))
        seconds = delta.seconds % 60
        if seconds > 0:
            result.append('%d seconds' % (seconds,))

    if result:
        return ', '.join(result)
    else:
        return 'super fast'


def makeList(input):
    if isinstance(input, basestring):
        return [input]
    elif input is None:
        return []
    else:
        return list(input)


def in_reactor(f):
    """decorate a function by running it with maybeDeferred in a reactor"""
    def wrap(*args, **kwargs):
        from twisted.internet import reactor, defer
        result = []

        def async():
            d = defer.maybeDeferred(f, *args, **kwargs)

            def eb(f):
                f.printTraceback()
            d.addErrback(eb)

            def do_stop(r):
                result.append(r)
                reactor.stop()
            d.addBoth(do_stop)
        reactor.callWhenRunning(async)
        reactor.run()
        return result[0]
    wrap.__doc__ = f.__doc__
    wrap.__name__ = f.__name__
    wrap._orig = f  # for tests
    return wrap


def asyncSleep(delay):
    from twisted.internet import reactor, defer
    d = defer.Deferred()
    reactor.callLater(delay, d.callback, None)
    return d


def check_functional_environment(config):
    try:
        locale.getdefaultlocale()
    except KeyError:
        config.error("\n".join([
            "Your environment has incorrect locale settings. This means python cannot handle strings safely.",
            "Please check 'LANG', 'LC_CTYPE', 'LC_ALL' and 'LANGUAGE' are either unset or set to a valid locale.",
        ]))


__all__ = [
    'naturalSort', 'now', 'formatInterval', 'ComparableMixin', 'json',
    'safeTranslate', 'none_or_str',
    'NotABranch', 'deferredLocked', 'SerializedInvocation', 'UTC',
    'diffSets', 'makeList', 'in_reactor', 'check_functional_environment',
    'human_readable_delta']
