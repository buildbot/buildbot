import sys

def nl(s):
    """Convert the given string to the native newline format, assuming it is
    already in normal UNIX newline format (\n).  Use this to create the
    appropriate expectation in a failUnlessEqual"""
    if not isinstance(s, basestring):
        return s
    if sys.platform.startswith('win'):
        return s.replace('\n', '\r\n')
    else:
        return s
