#!/usr/bin/python

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

import os
import re
import subprocess
import sys

import sets
from future.utils import text_type
from twisted.cred import credentials
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import usage
from twisted.spread import pb

'''
# set up PYTHONPATH to contain Twisted/buildbot perhaps, if not already
# installed site-wide
. ~/.environment

/path/to/svn_buildbot.py --repository "$REPOS" --revision "$REV" \
--bbserver localhost --bbport 9989 --username myuser --auth passwd
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
        ['repository', 'r', None, "The repository that was changed."],
        ['worker-repo', 'c', None, "In case the repository differs for the workers."],
        ['revision', 'v', None, "The revision that we want to examine (default: latest)"],
        ['bbserver', 's', 'localhost', "The hostname of the server that buildbot is running on"],
        ['bbport', 'p', 8007, "The port that buildbot is listening on"],
        ['username', 'u', 'change', "Username used in PB connection auth"],
        ['auth', 'a', 'changepw', "Password used in PB connection auth"],
        [
            'include',
            'f',
            None,
            '''\
Search the list of changed files for this regular expression, and if there is
at least one match notify buildbot; otherwise buildbot will not do a build.
You may provide more than one -f argument to try multiple
patterns.  If no filter is given, buildbot will always be notified.''',
        ],
        ['filter', 'f', None, "Same as --include.  (Deprecated)"],
        [
            'exclude',
            'F',
            None,
            '''\
The inverse of --filter.  Changed files matching this expression will never
be considered for a build.
You may provide more than one -F argument to try multiple
patterns.  Excludes override includes, that is, patterns that match both an
include and an exclude will be excluded.''',
        ],
        ['encoding', 'e', "utf8", "The encoding of the strings from subversion (default: utf8)"],
        ['project', 'P', None, "The project for the source."],
    ]
    optFlags = [
        ['dryrun', 'n', "Do not actually send changes"],
    ]

    def __init__(self):
        usage.Options.__init__(self)
        self._includes = []
        self._excludes = []
        self['includes'] = None
        self['excludes'] = None

    def opt_include(self, arg):
        self._includes.append(f'.*{arg}.*')

    opt_filter = opt_include

    def opt_exclude(self, arg):
        self._excludes.append(f'.*{arg}.*')

    def postOptions(self):
        if self['repository'] is None:
            raise usage.error("You must pass --repository")
        if self._includes:
            self['includes'] = '({})'.format('|'.join(self._includes))
        if self._excludes:
            self['excludes'] = '({})'.format('|'.join(self._excludes))


def split_file_dummy(changed_file):
    """Split the repository-relative filename into a tuple of (branchname,
    branch_relative_filename). If you have no branches, this should just
    return (None, changed_file).
    """
    return (None, changed_file)


# this version handles repository layouts that look like:
#  trunk/files..                  -> trunk
#  branches/branch1/files..       -> branches/branch1
#  branches/branch2/files..       -> branches/branch2
#


def split_file_branches(changed_file):
    pieces = changed_file.split(os.sep)
    if pieces[0] == 'branches':
        return (os.path.join(*pieces[:2]), os.path.join(*pieces[2:]))
    if pieces[0] == 'trunk':
        return (pieces[0], os.path.join(*pieces[1:]))
    # there are other sibilings of 'trunk' and 'branches'. Pretend they are
    # all just funny-named branches, and let the Schedulers ignore them.
    # return (pieces[0], os.path.join(*pieces[1:]))

    raise RuntimeError(f"cannot determine branch for '{changed_file}'")


split_file = split_file_dummy


class ChangeSender:
    def getChanges(self, opts):
        """Generate and stash a list of Change dictionaries, ready to be sent
        to the buildmaster's PBChangeSource."""

        # first we extract information about the files that were changed
        repo = opts['repository']
        worker_repo = opts['worker-repo'] or repo
        print("Repo:", repo)
        rev_arg = ''
        if opts['revision']:
            rev_arg = '-r {}'.format(opts['revision'])
        changed = subprocess.check_output(f'svnlook changed {rev_arg} "{repo}"', shell=True)
        changed = changed.decode(sys.stdout.encoding)
        changed = changed.split('\n')
        # the first 4 columns can contain status information
        changed = [x[4:] for x in changed]

        message = subprocess.check_output(f'svnlook log {rev_arg} "{repo}"', shell=True)
        message = message.decode(sys.stdout.encoding)
        who = subprocess.check_output(f'svnlook author {rev_arg} "{repo}"', shell=True)
        who = who.decode(sys.stdout.encoding)
        revision = opts.get('revision')
        if revision is not None:
            revision = str(int(revision))

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
            print(changestring)
            print(
                f"""\
    Buildbot was not interested, no changes matched any of these filters:\n {fltpat}
    or all the changes matched these exclusions:\n {expat}\
    """
            )
            sys.exit(0)

        # now see which branches are involved
        files_per_branch = {}
        for f in changed:
            branch, filename = split_file(f)
            if branch in files_per_branch.keys():
                files_per_branch[branch].append(filename)
            else:
                files_per_branch[branch] = [filename]

        # now create the Change dictionaries
        changes = []
        encoding = opts['encoding']
        for branch, branch_files in files_per_branch.items():
            d = {
                'who': text_type(who, encoding=encoding),
                'repository': text_type(worker_repo, encoding=encoding),
                'comments': text_type(message, encoding=encoding),
                'revision': revision,
                'project': text_type(opts['project'] or "", encoding=encoding),
                'src': 'svn',
            }
            if branch:
                d['branch'] = text_type(branch, encoding=encoding)
            else:
                d['branch'] = branch

            files = []
            for file in branch_files:
                files.append(text_type(file, encoding=encoding))
            d['files'] = files

            changes.append(d)

        return changes

    def sendChanges(self, opts, changes):
        pbcf = pb.PBClientFactory()
        reactor.connectTCP(opts['bbserver'], int(opts['bbport']), pbcf)
        creds = credentials.UsernamePassword(opts['username'], opts['auth'])
        d = pbcf.login(creds)
        d.addCallback(self.sendAllChanges, changes)
        return d

    def sendAllChanges(self, remote, changes):
        dl = [remote.callRemote('addChange', change) for change in changes]
        return defer.gatherResults(dl, consumeErrors=True)

    def run(self):
        opts = Options()
        try:
            opts.parseOptions()
        except usage.error as ue:
            print(opts)
            print(f"{sys.argv[0]}: {ue}")
            sys.exit()

        changes = self.getChanges(opts)
        if opts['dryrun']:
            for i, c in enumerate(changes):
                print(f"CHANGE #{(i + 1)}")
                keys = sorted(c.keys())
                for k in keys:
                    print(f"[{k:>10}]: {c[k]}")
            print("*NOT* sending any changes")
            return

        d = self.sendChanges(opts, changes)

        def quit(*why):
            print("quitting! because", why)
            reactor.stop()

        d.addCallback(quit, "SUCCESS")

        @d.addErrback
        def failed(f):
            print("FAILURE")
            print(f)
            reactor.stop()

        reactor.callLater(60, quit, "TIMEOUT")
        reactor.run()


if __name__ == '__main__':
    s = ChangeSender()
    s.run()
