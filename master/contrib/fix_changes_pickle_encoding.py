#!/usr/bin/python
"""%prog [options] [changes.pck] old_encoding

Re-encodes changes in a pickle file to UTF-8 from the given encoding
"""

if __name__ == '__main__':
    import os
    from buildbot.util.pickle import load, dump
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

    changemgr = load(fp)
    fp.close()

    print "decoding bytestrings in %s using %s" % (changes_file, old_encoding)
    changemgr.recode_changes(old_encoding)

    changes_backup = changes_file + ".old"
    i = 0
    while os.path.exists(changes_backup):
        i += 1
        changes_backup = changes_file + ".old.%i" % i
    print "backing up %s to %s" % (changes_file, changes_backup)
    os.rename(changes_file, changes_backup)

    dump(changemgr, open(changes_file, "w"))
