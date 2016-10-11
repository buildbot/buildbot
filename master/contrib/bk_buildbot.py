#!/usr/local/bin/python
#
# BitKeeper hook script.
#
# svn_buildbot.py was used as a base for this file, if you find any bugs or
# errors please email me.
#
# Amar Takhar <amar@ntp.org>

from __future__ import division
from __future__ import print_function

import commands
import sys

from twisted.cred import credentials
from twisted.internet import reactor
from twisted.python import usage
from twisted.spread import pb

'''
/path/to/bk_buildbot.py --repository "$REPOS" --revision "$REV" --branch \
"<branch>" --bbserver localhost --bbport 9989
'''


# We have hackish "-d" handling here rather than in the Options
# subclass below because a common error will be to not have twisted in
# PYTHONPATH; we want to be able to print that error to the log if
# debug mode is on, so we set it up before the imports.

DEBUG = None

if '-d' in sys.argv:
    i = sys.argv.index('-d')
    DEBUG = sys.argv[i + 1]
    del sys.argv[i]
    del sys.argv[i]

if DEBUG:
    f = open(DEBUG, 'a')
    sys.stderr = f
    sys.stdout = f


class Options(usage.Options):
    optParameters = [
        ['repository', 'r', None,
         "The repository that was changed."],
        ['revision', 'v', None,
         "The revision that we want to examine (default: latest)"],
        ['branch', 'b', None,
         "Name of the branch to insert into the branch field. (REQUIRED)"],
        ['category', 'c', None,
         "Schedular category."],
        ['bbserver', 's', 'localhost',
         "The hostname of the server that buildbot is running on"],
        ['bbport', 'p', 8007,
         "The port that buildbot is listening on"]
    ]
    optFlags = [
        ['dryrun', 'n', "Do not actually send changes"],
    ]

    def __init__(self):
        usage.Options.__init__(self)

    def postOptions(self):
        if self['repository'] is None:
            raise usage.error("You must pass --repository")


class ChangeSender:

    def getChanges(self, opts):
        """Generate and stash a list of Change dictionaries, ready to be sent
        to the buildmaster's PBChangeSource."""

        # first we extract information about the files that were changed
        repo = opts['repository']
        print("Repo:", repo)
        rev_arg = ''
        if opts['revision']:
            rev_arg = '-r"%s"' % (opts['revision'], )
        changed = commands.getoutput("bk changes -v %s -d':GFILE:\\n' '%s'" % (
            rev_arg, repo)).split('\n')

        # Remove the first line, it's an info message you can't remove
        # (annoying)
        del changed[0]

        change_info = commands.getoutput("bk changes %s -d':USER:\\n$each(:C:){(:C:)\\n}' '%s'" % (
            rev_arg, repo)).split('\n')

        # Remove the first line, it's an info message you can't remove
        # (annoying)
        del change_info[0]

        who = change_info.pop(0)
        branch = opts['branch']
        message = '\n'.join(change_info)
        revision = opts.get('revision')

        changes = {'who': who,
                   'branch': branch,
                   'files': changed,
                   'comments': message,
                   'revision': revision}

        if opts.get('category'):
            changes['category'] = opts.get('category')

        return changes

    def sendChanges(self, opts, changes):
        pbcf = pb.PBClientFactory()
        reactor.connectTCP(opts['bbserver'], int(opts['bbport']), pbcf)
        d = pbcf.login(credentials.UsernamePassword('change', 'changepw'))
        d.addCallback(self.sendAllChanges, changes)
        return d

    def sendAllChanges(self, remote, changes):
        dl = remote.callRemote('addChange', changes)
        return dl

    def run(self):
        opts = Options()
        try:
            opts.parseOptions()
            if not opts['branch']:
                print("You must supply a branch with -b or --branch.")
                sys.exit(1)

        except usage.error as ue:
            print(opts)
            print("%s: %s" % (sys.argv[0], ue))
            sys.exit()

        changes = self.getChanges(opts)
        if opts['dryrun']:
            for k in changes.keys():
                print("[%10s]: %s" % (k, changes[k]))
            print("*NOT* sending any changes")
            return

        d = self.sendChanges(opts, changes)

        def quit(*why):
            print("quitting! because", why)
            reactor.stop()

        @d.addErrback(failed)
        def failed(f):
            print("FAILURE: %s" % f)
            reactor.stop()

        d.addCallback(quit, "SUCCESS")
        reactor.callLater(60, quit, "TIMEOUT")

        reactor.run()


if __name__ == '__main__':
    s = ChangeSender()
    s.run()
