#!/usr/bin/python
"""%prog [options] [changes.pck] old_encoding

Re-encodes changes in a pickle file to UTF-8 from the given encoding
"""

def recode_changes(changes, old_encoding):
    """Returns a new list of changes, with the change attributes re-encoded
    as UTF-8 bytestrings"""
    retval = []
    for c in changes:
        for attr in ("who", "comments", "revlink", "category", "branch", "revision"):
            a = getattr(c, attr)
            if isinstance(a, str):
                try:
                    setattr(c, attr, a.decode(old_encoding).encode("utf8"))
                except UnicodeDecodeError:
                    raise UnicodeError("Error decoding %s: %s as %s" % (attr, a, old_encoding))
        retval.append(c)
    return retval

if __name__ == '__main__':
    import sys, os
    from cPickle import load, dump
    from optparse import OptionParser

    parser = OptionParser(__doc__)

    options, args = parser.parse_args()

    if len(args) == 2:
        changes_file = args[0]
        old_encoding = args[1]
    elif len(args) == 1:
        changes_file = "changes.pck"
        old_encoding = args[0]
    else:
        parser.error("Need at least one argument")

    try:
        fp = open(changes_file)
    except IOError, e:
        parser.error("Couldn't open %s: %s" % (changes_file, str(e)))

    changes = load(fp)
    fp.close()

    changes.changes = recode_changes(changes.changes, old_encoding)

    changes_backup = changes_file + ".old"
    i = 0
    while os.path.exists(changes_backup):
        i += 1
        changes_backup = changes_file + ".old.%i" % i

    os.rename(changes_file, changes_backup)
    dump(changes, open(changes_file, "w"))
