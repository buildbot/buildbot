# -*- test-case-name: buildbot.test.test_util -*-

from twisted.internet.defer import Deferred
from twisted.spread import pb
from twisted.python import threadable
import time, re, string

def naturalSort(l):
    """Returns a sorted copy of l, so that numbers in strings are sorted in the
    proper order.

    e.g. ['foo10', 'foo1', 'foo2'] will be sorted as ['foo1', 'foo2', 'foo10']
    instead of the default ['foo1', 'foo10', 'foo2']"""
    l = l[:]
    def try_int(s):
        try:
            return int(s)
        except:
            return s
    def key_func(item):
        return [try_int(s) for s in re.split('(\d+)', item)]
    # prepend integer keys to each element, sort them, then strip the keys
    keyed_l = [ (key_func(i), i) for i in l ]
    keyed_l.sort()
    l = [ i[1] for i in keyed_l ]
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
    """Specify a list of attributes that are 'important'. These will be used
    for all comparison operations."""

    compare_attrs = []

    class _None: pass

    def __hash__(self):
        alist = [self.__class__] + \
                [getattr(self, name, self._None) for name in self.compare_attrs]
        return hash(tuple(map(str,alist)))

    def __cmp__(self, them):
        result = cmp(type(self), type(them))
        if result:
            return result

        result = cmp(self.__class__.__name__, them.__class__.__name__)
        if result:
            return result

        assert self.compare_attrs == them.compare_attrs
        self_list= [getattr(self, name, self._None) for name in self.compare_attrs]
        them_list= [getattr(them, name, self._None) for name in self.compare_attrs]
        return cmp(self_list, them_list)

# Remove potentially harmful characters from builder name if it is to be
# used as the build dir.
badchars_map = string.maketrans("\t !#$%&'()*+,./:;<=>?@[\\]^{|}~",
                                "______________________________")
def safeTranslate(str):
    if isinstance(str, unicode):
        str = str.encode('utf8')
    return str.translate(badchars_map)

def remove_userpassword(url):
    if '@' not in url:
        return url
    if '://' not in url:
        return url

    # urlparse would've been nice, but doesn't support ssh... sigh    
    protocol_url = url.split('://')
    protocol = protocol_url[0]
    repo_url = protocol_url[1].split('@')[-1]

    return protocol + '://' + repo_url

class LRUCache:
    """
    A simple least-recently-used cache, with a fixed maximum size.  Note that
    an item's memory will not necessarily be free if other code maintains a reference
    to it, but this class will "lose track" of it all the same.  Without caution, this
    can lead to duplicate items in memory simultaneously.
    """

    synchronized = ["get", "add"]

    def __init__(self, max_size=50):
        self._max_size = max_size
        self._cache = {} # basic LRU cache
        self._cached_ids = [] # = [LRU .. MRU]

    def get(self, id):
        thing = self._cache.get(id, None)
        if thing is not None:
            self._cached_ids.remove(id)
            self._cached_ids.append(id)
        return thing
    __getitem__ = get

    def add(self, id, thing):
        if id in self._cache:
            self._cached_ids.remove(id)
            self._cached_ids.append(id)
            return
        while len(self._cached_ids) >= self._max_size:
            del self._cache[self._cached_ids.pop(0)]
        self._cache[id] = thing
        self._cached_ids.append(id)
    __setitem__ = add

threadable.synchronize(LRUCache)


def none_or_str(x):
    """Cast X to a str if it is not None"""
    if x is not None and not isinstance(x, str):
        return str(x)
    return x

# place a working json module at 'buildbot.util.json'.  Code is from
# Paul Wise <pabs@debian.org>:
#   http://lists.debian.org/debian-python/2010/02/msg00016.html
try:
    import json # python 2.6
except ImportError:
    import simplejson as json # python 2.4 to 2.5
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
