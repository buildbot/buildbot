from twisted.internet import defer

class FakeRemote:
    """
    Wrap a local object to make it look like it's remote
    """
    def __init__(self, original, method_prefix="remote_"):
        self.original = original
        self.method_prefix = method_prefix

    def callRemote(self, meth, *args, **kwargs):
        fn = getattr(self.original, self.method_prefix + meth)
        return defer.maybeDeferred(fn, *args, **kwargs)

    def notifyOnDisconnect(self, what): pass
    def dontNotifyOnDisconnect(self, what): pass
