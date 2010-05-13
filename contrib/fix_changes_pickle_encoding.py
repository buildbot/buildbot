#!/usr/bin/python
"""%prog [options] [changes.pck] old_encoding

Re-encodes changes in a pickle file to UTF-8 from the given encoding
"""

def recode_changes(changes, old_encoding):
    """Returns a new list of changes, with the change attributes re-encoded
    as UTF-8 bytestrings"""
    retval = []
    nconvert = 0
    for c in changes:
        for attr in ("who", "comments", "revlink", "category", "branch", "revision"):
            a = getattr(c, attr)
            if isinstance(a, str):
                try:
                    setattr(c, attr, a.decode(old_encoding))
                    nconvert += 1
                except UnicodeDecodeError:
                    raise UnicodeError("Error decoding %s of change #%s as %s:\n%s" % (attr, c.number, old_encoding, a))
        retval.append(c)
    print "converted %d strings" % nconvert
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

    print "opening %s" % (changes_file,)
    try:
        fp = open(changes_file)
    except IOError, e:
        parser.error("Couldn't open %s: %s" % (changes_file, str(e)))

    changes = load(fp)
    fp.close()

    print "decoding bytestrings in %s using %s" % (changes_file, old_encoding)
    changes.changes = recode_changes(changes.changes, old_encoding)

    changes_backup = changes_file + ".old"
    i = 0
    while os.path.exists(changes_backup):
        i += 1
        changes_backup = changes_file + ".old.%i" % i

    print "backing up %s to %s" % (changes_file, changes_backup)
    os.rename(changes_file, changes_backup)
    dump(changes, open(changes_file, "w"))
