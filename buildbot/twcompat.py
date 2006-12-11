
if 0:
    print "hey python-mode, stop thinking I want 8-char indentation"

"""
utilities to be compatible with both Twisted-1.3 and 2.0

"""

import os

from twisted.copyright import version

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
