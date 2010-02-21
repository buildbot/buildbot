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

class DictOfSets:
    """
    This is a dictionary with a default value of an empty set, but it is
    careful not to store empty sets, so it can be used for long-term storge
    without fear of excessive memory use.

    Note that __setitem__ is not supported:
    >>> my_dictofsets[13] = set(1, 3) # WILL NOT WORK
    use the add method instead
    """
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

