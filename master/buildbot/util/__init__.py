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
import itertools
import json
import locale
import re
import sys
import textwrap
import time
from builtins import bytes
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

import dateutil.tz

from twisted.python import reflect
from twisted.python.deprecate import deprecatedModuleAttribute
from twisted.python.versions import Version
from zope.interface import implementer

from buildbot.interfaces import IConfigured
from buildbot.util.giturlparse import giturlparse
from buildbot.util.misc import deferredLocked

from ._notifier import Notifier


def naturalSort(array):
    array = array[:]

    def try_int(s):
        try:
            return int(s)
        except ValueError:
            return s

    def key_func(item):
        return [try_int(s) for s in re.split(r'(\d+)', item)]
    # prepend integer keys to each element, sort them, then strip the keys
    keyed_array = sorted([(key_func(i), i) for i in array])
    array = [i[1] for i in keyed_array]
    return array


def flattened_iterator(l, types=(list, tuple)):
    """
    Generator for a list/tuple that potentially contains nested/lists/tuples of arbitrary nesting
    that returns every individual non-list/tuple element.  In other words, [(5, 6, [8, 3]), 2, [2, 1, (3, 4)]]
    will yield 5, 6, 8, 3, 2, 2, 1, 3, 4

    This is safe to call on something not a list/tuple - the original input is yielded.
    """
    if not isinstance(l, types):
        yield l
        return

    for element in l:
        for sub_element in flattened_iterator(element, types):
            yield sub_element


def flatten(l, types=(list, )):
    """
    Given a list/tuple that potentially contains nested lists/tuples of arbitrary nesting,
    flatten into a single dimension.  In other words, turn [(5, 6, [8, 3]), 2, [2, 1, (3, 4)]]
    into [5, 6, 8, 3, 2, 2, 1, 3, 4]

    This is safe to call on something not a list/tuple - the original input is returned as a list
    """
    # For backwards compatibility, this returned a list, not an iterable.
    # Changing to return an iterable could break things.
    if not isinstance(l, types):
        return l
    return list(flattened_iterator(l, types))


def now(_reactor=None):
    if _reactor and hasattr(_reactor, "seconds"):
        return _reactor.seconds()
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


def fuzzyInterval(seconds):
    """
    Convert time interval specified in seconds into fuzzy, human-readable form
    """
    if seconds <= 1:
        return "a moment"
    if seconds < 20:
        return "{:d} seconds".format(seconds)
    if seconds < 55:
        return "{:d} seconds".format(round(seconds / 10.) * 10)
    minutes = round(seconds / 60.)
    if minutes == 1:
        return "a minute"
    if minutes < 20:
        return "{:d} minutes".format(minutes)
    if minutes < 55:
        return "{:d} minutes".format(round(minutes / 10.) * 10)
    hours = round(minutes / 60.)
    if hours == 1:
        return "an hour"
    if hours < 24:
        return "{:d} hours".format(hours)
    days = (hours + 6) // 24
    if days == 1:
        return "a day"
    if days < 30:
        return "{:d} days".format(days)
    months = int((days + 10) / 30.5)
    if months == 1:
        return "a month"
    if months < 12:
        return "{} months".format(months)
    years = round(days / 365.25)
    if years == 1:
        return "a year"
    return "{} years".format(years)


@implementer(IConfigured)
class ComparableMixin:
    compare_attrs = ()

    class _None:
        pass

    def __hash__(self):
        compare_attrs = []
        reflect.accumulateClassList(
            self.__class__, 'compare_attrs', compare_attrs)

        alist = [self.__class__] + \
                [getattr(self, name, self._None) for name in compare_attrs]
        return hash(tuple(map(str, alist)))

    def _cmp_common(self, them):
        if type(self) != type(them):
            return (False, None, None)

        if self.__class__ != them.__class__:
            return (False, None, None)

        compare_attrs = []
        reflect.accumulateClassList(
            self.__class__, 'compare_attrs', compare_attrs)

        self_list = [getattr(self, name, self._None)
                     for name in compare_attrs]
        them_list = [getattr(them, name, self._None)
                     for name in compare_attrs]
        return (True, self_list, them_list)

    def __eq__(self, them):
        (isComparable, self_list, them_list) = self._cmp_common(them)
        if not isComparable:
            return False
        return self_list == them_list

    def __ne__(self, them):
        (isComparable, self_list, them_list) = self._cmp_common(them)
        if not isComparable:
            return True
        return self_list != them_list

    def __lt__(self, them):
        (isComparable, self_list, them_list) = self._cmp_common(them)
        if not isComparable:
            return False
        return self_list < them_list

    def __le__(self, them):
        (isComparable, self_list, them_list) = self._cmp_common(them)
        if not isComparable:
            return False
        return self_list <= them_list

    def __gt__(self, them):
        (isComparable, self_list, them_list) = self._cmp_common(them)
        if not isComparable:
            return False
        return self_list > them_list

    def __ge__(self, them):
        (isComparable, self_list, them_list) = self._cmp_common(them)
        if not isComparable:
            return False
        return self_list >= them_list

    def getConfigDict(self):
        compare_attrs = []
        reflect.accumulateClassList(
            self.__class__, 'compare_attrs', compare_attrs)
        return {k: getattr(self, k)
                for k in compare_attrs
                if hasattr(self, k) and k not in ("passwd", "password")}


def diffSets(old, new):
    if not isinstance(old, set):
        old = set(old)
    if not isinstance(new, set):
        new = set(new)
    return old - new, new - old


# Remove potentially harmful characters from builder name if it is to be
# used as the build dir.
badchars_map = bytes.maketrans(b"\t !#$%&'()*+,./:;<=>?@[\\]^{|}~",
                               b"______________________________")


def safeTranslate(s):
    if isinstance(s, str):
        s = s.encode('utf8')
    return s.translate(badchars_map)


def none_or_str(x):
    if x is not None and not isinstance(x, str):
        return str(x)
    return x


def unicode2bytes(x, encoding='utf-8', errors='strict'):
    if isinstance(x, str):
        x = x.encode(encoding, errors)
    return x


def bytes2unicode(x, encoding='utf-8', errors='strict'):
    if isinstance(x, (str, type(None))):
        return x
    return str(x, encoding, errors)


_hush_pyflakes = [json]

deprecatedModuleAttribute(
    Version("buildbot", 0, 9, 4),
    message="Use json from the standard library instead.",
    moduleName="buildbot.util",
    name="json",
)


def toJson(obj):
    if isinstance(obj, datetime.datetime):
        return datetime2epoch(obj)


# changes and schedulers consider None to be a legitimate name for a branch,
# which makes default function keyword arguments hard to handle.  This value
# is always false.


class NotABranch:

    def __bool__(self):
        return False


NotABranch = NotABranch()

# time-handling methods

# this used to be a custom class; now it's just an instance of dateutil's class
UTC = dateutil.tz.tzutc()


def epoch2datetime(epoch):
    """Convert a UNIX epoch time to a datetime object, in the UTC timezone"""
    if epoch is not None:
        return datetime.datetime.fromtimestamp(epoch, tz=UTC)
    return None


def datetime2epoch(dt):
    """Convert a non-naive datetime object to a UNIX epoch timestamp"""
    if dt is not None:
        return calendar.timegm(dt.utctimetuple())
    return None


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
        hours = int(delta.seconds / 3600)
        if hours > 0:
            result.append('%d hours' % (hours,))
        minutes = int((delta.seconds - hours * 3600) / 60)
        if minutes:
            result.append('%d minutes' % (minutes,))
        seconds = delta.seconds % 60
        if seconds > 0:
            result.append('%d seconds' % (seconds,))

    if result:
        return ', '.join(result)
    return 'super fast'


def makeList(input):
    if isinstance(input, str):
        return [input]
    elif input is None:
        return []
    return list(input)


def in_reactor(f):
    """decorate a function by running it with maybeDeferred in a reactor"""
    def wrap(*args, **kwargs):
        from twisted.internet import reactor, defer
        result = []

        def _async():
            d = defer.maybeDeferred(f, *args, **kwargs)

            @d.addErrback
            def eb(f):
                f.printTraceback(file=sys.stderr)

            @d.addBoth
            def do_stop(r):
                result.append(r)
                reactor.stop()
        reactor.callWhenRunning(_async)
        reactor.run()
        return result[0]
    wrap.__doc__ = f.__doc__
    wrap.__name__ = f.__name__
    wrap._orig = f  # for tests
    return wrap


def string2boolean(str):
    return {
        b'on': True,
        b'true': True,
        b'yes': True,
        b'1': True,
        b'off': False,
        b'false': False,
        b'no': False,
        b'0': False,
    }[str.lower()]


def asyncSleep(delay, reactor=None):
    from twisted.internet import defer
    from twisted.internet import reactor as internet_reactor
    if reactor is None:
        reactor = internet_reactor

    d = defer.Deferred()
    reactor.callLater(delay, d.callback, None)
    return d


def check_functional_environment(config):
    try:
        locale.getdefaultlocale()
    except (KeyError, ValueError) as e:
        config.error("\n".join([
            "Your environment has incorrect locale settings. This means python cannot handle strings safely.",
            " Please check 'LANG', 'LC_CTYPE', 'LC_ALL' and 'LANGUAGE'"
            " are either unset or set to a valid locale.", str(e)
        ]))


_netloc_url_re = re.compile(r':[^@]*@')


def stripUrlPassword(url):
    parts = list(urlsplit(url))
    parts[1] = _netloc_url_re.sub(':xxxx@', parts[1])
    return urlunsplit(parts)


def join_list(maybeList):
    if isinstance(maybeList, (list, tuple)):
        return ' '.join(bytes2unicode(s) for s in maybeList)
    return bytes2unicode(maybeList)


def command_to_string(command):
    words = command
    if isinstance(words, (bytes, str)):
        words = words.split()

    try:
        len(words)
    except (AttributeError, TypeError):
        # WithProperties and Property don't have __len__
        # For old-style classes instances AttributeError raised,
        # for new-style classes instances - TypeError.
        return None

    # flatten any nested lists
    words = flatten(words, (list, tuple))

    # strip instances and other detritus (which can happen if a
    # description is requested before rendering)
    stringWords = []
    for w in words:
        if isinstance(w, (bytes, str)):
            # If command was bytes, be gentle in
            # trying to covert it.
            w = bytes2unicode(w, errors="replace")
            stringWords.append(w)
    words = stringWords

    if not words:
        return None
    if len(words) < 3:
        rv = "'%s'" % (' '.join(words))
    else:
        rv = "'%s ...'" % (' '.join(words[:2]))

    return rv


def rewrap(text, width=None):
    """
    Rewrap text for output to the console.

    Removes common indentation and rewraps paragraphs according to the console
    width.

    Line feeds between paragraphs preserved.
    Formatting of paragraphs that starts with additional indentation
    preserved.
    """

    if width is None:
        width = 80

    # Remove common indentation.
    text = textwrap.dedent(text)

    def needs_wrapping(line):
        # Line always non-empty.
        return not line[0].isspace()

    # Split text by lines and group lines that comprise paragraphs.
    wrapped_text = ""
    for do_wrap, lines in itertools.groupby(text.splitlines(True),
                                            key=needs_wrapping):
        paragraph = ''.join(lines)

        if do_wrap:
            paragraph = textwrap.fill(paragraph, width)

        wrapped_text += paragraph

    return wrapped_text


def dictionary_merge(a, b):
    """merges dictionary b into a
       Like dict.update, but recursive
    """
    for key, value in b.items():
        if key in a and isinstance(a[key], dict) and isinstance(value, dict):
            dictionary_merge(a[key], b[key])
            continue
        a[key] = b[key]
    return a


__all__ = [
    'naturalSort', 'now', 'formatInterval', 'ComparableMixin',
    'safeTranslate', 'none_or_str',
    'NotABranch', 'deferredLocked', 'UTC',
    'diffSets', 'makeList', 'in_reactor', 'string2boolean',
    'check_functional_environment', 'human_readable_delta',
    'rewrap',
    'Notifier',
    "giturlparse",
]
