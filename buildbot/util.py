# -*- test-case-name: buildbot.test.test_util -*-

from twisted.internet.defer import Deferred
from twisted.spread import pb
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
    r = failure.trap(pb.DeadReferenceError, pb.PBConnectionLost)
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
        return hash(tuple(alist))

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
