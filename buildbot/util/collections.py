try:
    from collections import defaultdict
except ImportError:
    # collections.defaultdict only appeared in py2.5, but buildbot supports 2.4
    class defaultdict(dict):
        def __init__(self, default_factory=None, *args, **kwargs):
            self._default_factory = default_factory
            dict.__init__(self, *args, **kwargs)
        def __getitem__(self, key):
            if key not in self and self._default_factory:
                self[key] = self._default_factory()
            return dict.__getitem__(self, key)

class KeyedSets:
    """
    This is a collection of named sets.  In principal, it contains an empty set
    for every name, and you can add things to sets, discard things from sets,
    and so on.

    >>> ks = KeyedSets()
    >>> ks['tim']                   # get a named set
    set([])
    >>> ks.add('tim', 'friendly')   # add an element to a set
    >>> ks.add('tim', 'dexterous')
    >>> ks['tim']
    set(['friendly', 'dexterous'])
    >>> 'tim' in ks                 # membership testing
    True
    >>> 'ron' in ks
    False
    >>> ks.discard('tim', 'friendly')# discard set element
    >>> ks.pop('tim')               # return set and reset to empty
    set(['dexterous'])
    >>> ks['tim']
    set([])

    This class is careful to conserve memory space - empty sets do not occupy
    any space.
    """
    def __init__(self):
        self.d = dict()
    def add(self, key, value):
        if key not in self.d:
            self.d[key] = set()
        self.d[key].add(value)
    def discard(self, key, value):
        if key in self.d:
            self.d[key].discard(value)
            if not self.d[key]:
                del self.d[key]
    def __contains__(self, key):
        return key in self.d
    def __getitem__(self, key):
        return self.d.get(key, set())
    def pop(self, key):
        if key in self.d:
            return self.d.pop(key)
        return set()

