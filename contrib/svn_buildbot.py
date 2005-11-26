#!/usr/bin/env python2.3

# this requires python >=2.3 for the 'sets' module.

# The sets.py from python-2.3 appears to work fine under python2.2 . To
# install this script on a host with only python2.2, copy
# /usr/lib/python2.3/sets.py from a newer python into somewhere on your
# PYTHONPATH, then edit the #! line above to invoke python2.2

# python2.1 is right out

# If you run this program as part of your SVN post-commit hooks, it will
# deliver Change notices to a buildmaster that is running a PBChangeSource
# instance.

# edit your svn-repository/hooks/post-commit file, and add lines that look
# like this:

'''
# set up PYTHONPATH to contain Twisted/buildbot perhaps, if not already
# installed site-wide
. ~/.environment

/path/to/svn_buildbot.py --repository "$REPOS" --revision "$REV" --bbserver localhost --bbport 9989
'''

import commands, sys, os
import re
import sets

# We have hackish "-d" handling here rather than in the Options
# subclass below because a common error will be to not have twisted in
# PYTHONPATH; we want to be able to print that error to the log if
# debug mode is on, so we set it up before the imports.

DEBUG = None

if '-d' in sys.argv:
    i = sys.argv.index('-d')
    DEBUG = sys.argv[i+1]
    del sys.argv[i]
    del sys.argv[i]

if DEBUG:
    f = open(DEBUG, 'a')
    sys.stderr = f
    sys.stdout = f

from twisted.internet import reactor
from twisted.python import usage
from twisted.spread import pb
from twisted.cred import credentials

class Options(usage.Options):
    optParameters = [
        ['repository', 'r', None,
         "The repository that was changed."],
        ['revision', 'v', None,
         "The revision that we want to examine (default: latest)"],
        ['bbserver', 's', 'localhost',
         "The hostname of the server that buildbot is running on"],
        ['bbport', 'p', 8007,
         "The port that buildbot is listening on"],
        ['include', 'f', None,
         '''\
Search the list of changed files for this regular expression, and if there is
at least one match notify buildbot; otherwise buildbot will not do a build.
You may provide more than one -f argument to try multiple
patterns.  If no filter is given, buildbot will always be notified.'''],
        ['filter', 'f', None, "Same as --include.  (Deprecated)"],
        ['exclude', 'F', None,
         '''\
The inverse of --filter.  Changed files matching this expression will never  
be considered for a build.  
You may provide more than one -F argument to try multiple
patterns.  Excludes override includes, that is, patterns that match both an
include and an exclude will be excluded.'''],
        ]

    def __init__(self):
        usage.Options.__init__(self)
        self._includes = []
        self._excludes = []
        self['includes'] = None
        self['excludes'] = None

    def opt_include(self, arg):
        self._includes.append('.*%s.*' % (arg,))
    opt_filter = opt_include

    def opt_exclude(self, arg):
        self._excludes.append('.*%s.*' % (arg,))

    def postOptions(self):
        if self['repository'] is None:
            raise usage.error("You must pass --repository")
        if self._includes:
            self['includes'] = '(%s)' % ('|'.join(self._includes),)
        if self._excludes:
            self['excludes'] = '(%s)' % ('|'.join(self._excludes),)


def main(opts):
    repo = opts['repository']
    print "Repo:", repo
    rev_arg = ''
    if opts['revision']:
        rev_arg = '-r %s' % (opts['revision'],)
    changed = commands.getoutput('svnlook changed %s "%s"' % (rev_arg, repo)
                                 ).split('\n')
    changed = [x[1:].strip() for x in changed]
    message = commands.getoutput('svnlook log %s "%s"' % (rev_arg, repo))
    who = commands.getoutput('svnlook author %s "%s"' % (rev_arg, repo))
    revision = opts.get('revision')
    if revision is not None:
        revision = int(revision)

    # see if we even need to notify buildbot by looking at filters first
    changestring = '\n'.join(changed)
    fltpat = opts['includes']
    if fltpat:
        included = sets.Set(re.findall(fltpat, changestring))
    else:
        included = sets.Set(changed)

    expat = opts['excludes']
    if expat:
        excluded = sets.Set(re.findall(expat, changestring))
    else:
        excluded = sets.Set([])
    if len(included.difference(excluded)) == 0:
        print changestring
        print """\
Buildbot was not interested, no changes matched any of these filters:\n %s
or all the changes matched these exclusions:\n %s\
""" % (fltpat, expat)
        sys.exit(0)

    pbcf = pb.PBClientFactory()
    reactor.connectTCP(opts['bbserver'], int(opts['bbport']),
                       pbcf)

    def gotPersp(persp):
        print "who", repr(who)
        print "what", repr(changed)
        print "why", repr(message)
        print "new revision", repr(revision)
        return persp.callRemote('addChange', {'who': who,
                                              'files': changed,
                                              'comments': message,
                                              'revision': revision})

    def quit(*why):
        print "quitting! because", why
        reactor.stop()


    pbcf.login(credentials.UsernamePassword('change', 'changepw')
               ).addCallback(gotPersp
               ).addCallback(quit, "SUCCESS"
               ).addErrback(quit, "FAILURE")

    # timeout of 60 seconds
    reactor.callLater(60, quit, "TIMEOUT")

    reactor.run()

if __name__ == '__main__':
    opts = Options()
    try:
        opts.parseOptions()
    except usage.error, ue:
        print opts
        print "%s: %s" % (sys.argv[0], ue)
        sys.exit()
    main(opts)
