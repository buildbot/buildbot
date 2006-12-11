
if 0:
    print "hey python-mode, stop thinking I want 8-char indentation"

"""
utilities to be compatible with both Twisted-1.3 and 2.0

"""

import os

from twisted.copyright import version

from twisted.internet import utils
if not hasattr(utils, "getProcessOutputAndValue"):
    from twisted.internet import reactor, protocol
    _callProtocolWithDeferred = utils._callProtocolWithDeferred
    try:
        import cStringIO
        StringIO = cStringIO
    except ImportError:
        import StringIO

    class _EverythingGetter(protocol.ProcessProtocol):

        def __init__(self, deferred):
            self.deferred = deferred
            self.outBuf = StringIO.StringIO()
            self.errBuf = StringIO.StringIO()
            self.outReceived = self.outBuf.write
            self.errReceived = self.errBuf.write

        def processEnded(self, reason):
            out = self.outBuf.getvalue()
            err = self.errBuf.getvalue()
            e = reason.value
            code = e.exitCode
            if e.signal:
                self.deferred.errback((out, err, e.signal))
            else:
                self.deferred.callback((out, err, code))

    def getProcessOutputAndValue(executable, args=(), env={}, path='.', 
                                 reactor=reactor):
        """Spawn a process and returns a Deferred that will be called back
        with its output (from stdout and stderr) and it's exit code as (out,
        err, code) If a signal is raised, the Deferred will errback with the
        stdout and stderr up to that point, along with the signal, as (out,
        err, signalNum)
        """
        return _callProtocolWithDeferred(_EverythingGetter,
                                         executable, args, env, path,
                                         reactor)
    utils.getProcessOutputAndValue = getProcessOutputAndValue


# copied from Twisted circa 2.2.0
def _which(name, flags=os.X_OK):
    """Search PATH for executable files with the given name.

    @type name: C{str}
    @param name: The name for which to search.

    @type flags: C{int}
    @param flags: Arguments to L{os.access}.

    @rtype: C{list}
    @return: A list of the full paths to files found, in the
    order in which they were found.
    """
    result = []
    exts = filter(None, os.environ.get('PATHEXT', '').split(os.pathsep))
    for p in os.environ['PATH'].split(os.pathsep):
        p = os.path.join(p, name)
        if os.access(p, flags):
            result.append(p)
        for e in exts:
            pext = p + e
            if os.access(pext, flags):
                result.append(pext)
    return result

which = _which
try:
    from twisted.python.procutils import which
except ImportError:
    pass
