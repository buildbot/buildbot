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

def now():
    #return int(time.time())
    return time.time()

def earlier(old, new):
    # minimum of two things, but "None" counts as +infinity
    if old:
        if new < old:
            return new
        return old
    return new

def later(old, new):
    # maximum of two things, but "None" counts as -infinity
    if old:
        if new > old:
            return new
        return old
    return new

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

class CancelableDeferred(Deferred):
    """I am a version of Deferred that can be canceled by calling my
    .cancel() method. After being canceled, no callbacks or errbacks will be
    executed.
    """
    def __init__(self):
        Deferred.__init__(self)
        self.canceled = 0
    def cancel(self):
        self.canceled = 1
    def _runCallbacks(self):
        if self.canceled:
            self.callbacks = []
            return
        Deferred._runCallbacks(self)

def ignoreStaleRefs(failure):
    """d.addErrback(util.ignoreStaleRefs)"""
    failure.trap(pb.DeadReferenceError, pb.PBConnectionLost)
    return None

class _None:
    pass

class ComparableMixin:
    """Specify a list of attributes that are 'important'. These will be used
    for all comparison operations."""

    compare_attrs = []

    def __hash__(self):
        alist = [self.__class__] + \
                [getattr(self, name, _None) for name in self.compare_attrs]
        return hash(tuple(map(str,alist)))

    def __cmp__(self, them):
        result = cmp(type(self), type(them))
        if result:
            return result

        result = cmp(self.__class__, them.__class__)
        if result:
            return result

        assert self.compare_attrs == them.compare_attrs
        self_list= [getattr(self, name, _None) for name in self.compare_attrs]
        them_list= [getattr(them, name, _None) for name in self.compare_attrs]
        return cmp(self_list, them_list)

def to_text(s):
    if isinstance(s, (str, unicode)):
        return s
    else:
        return str(s)

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
    synchronized = ["get", "add"]

    def __init__(self, max_size=50):
        self._max_size = max_size
        self._cache = {} # basic LRU cache
        self._cached_ids = [] # = [LRU .. MRU]

    def get(self, id):
        thing = self._cache.get(id, None)
        if thing:
            self._cached_ids.remove(id)
            self._cached_ids.append(id)
        return thing

    def add(self, id, thing):
        if id in self._cache:
            return
        while len(self._cached_ids) >= self._max_size:
            del self._cache[self._cached_ids.pop(0)]
        self._cache[id] = thing
        self._cached_ids.append(id)

threadable.synchronize(LRUCache)


# collections.defaultdict only appeared in py2.5, but buildbot supports 2.4
class defaultdict(dict):
    def __init__(self, default_factory=None, *args, **kwargs):
        self._default_factory = default_factory
        dict.__init__(self, *args, **kwargs)
    def __getitem__(self, key):
        if key not in self and self._default_factory:
            self[key] = self._default_factory()
        return dict.__getitem__(self, key)

class DictOfSets:
    # a bit like defaultdict(set), but don't keep empty sets around, so it
    # doesn't grow forever. "key in d" can be used to rule out empty sets.
    # Also don't create a set just to probe for members.
    def __init__(self):
        self.d = dict()
    def add(self, key, value):
        if key not in self.d:
            self.d[key] = set()
        self.d[key].add(value)
    def remove(self, key, value):
        if key in self.d:
            self.d[key].discard(value)
            if not self.d[key]:
                del self.d[key]
    def __contains__(self, key):
        return key in self.d
    def __getitem__(self, key):
        return self.d[key]
    def pop(self, key):
        if key in self.d:
            return self.d.pop(key)
        return set()
