import os

def nl(s):
    """Convert the given string to the native newline format, assuming it is
    already in normal UNIX newline format (\n).  Use this to create the
    appropriate expectation in a failUnlessEqual"""
    if not isinstance(s, basestring):
        return s
    return s.replace('\n', os.linesep)
