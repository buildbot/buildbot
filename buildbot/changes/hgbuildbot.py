# hgbuildbot.py - mercurial hooks for buildbot
#
# Copyright 2007 Frederic Leroy <fredo@starox.org>
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.

# hook extension to send change notifications to buildbot when a changeset is
# brought into the repository from elsewhere.
#
# default mode is to use mercurial branch
#
# to use, configure hgbuildbot in .hg/hgrc like this:
#
#   [hooks]
#   changegroup = python:buildbot.changes.hgbuildbot.hook
#
#   [hgbuildbot]
#   # config items go in here
#
# config items:
#
# REQUIRED:
#   master = host:port                   # host to send buildbot changes
#
# OPTIONAL:
#   branchtype = inrepo|dirname          # dirname: branch = name of directory
#                                        #          containing the repository
#                                        #
#                                        # inrepo:  branch = mercurial branch
#
#   branch = branchname                  # if set, branch is always branchname
#
#   fork = True|False                    # if mercurial should fork before 
#                                        # notifying the master
#
#   strip = 3                            # number of path to strip for local 
#                                        # repo path to form 'repository'
#
#   category = None                      # category property
#   project = ''                         # project this repository belong to

import os

from mercurial.i18n import gettext as _ #@UnresolvedImport
from mercurial.node import bin, hex, nullid #@UnresolvedImport
from mercurial.context import workingctx #@UnresolvedImport

# mercurial's on-demand-importing hacks interfere with the:
#from zope.interface import Interface
# that Twisted needs to do, so disable it.
try:
    from mercurial import demandimport
    demandimport.disable()
except ImportError:
    pass

def hook(ui, repo, hooktype, node=None, source=None, **kwargs):
    # read config parameters
    master = ui.config('hgbuildbot', 'master')
    if master:
        branchtype = ui.config('hgbuildbot', 'branchtype')
        branch = ui.config('hgbuildbot', 'branch')
        fork = ui.configbool('hgbuildbot', 'fork', False)
        # notify also has this setting
        stripcount = int(ui.config('notify','strip') or ui.config('hgbuildbot','strip',3))
        category = ui.config('hgbuildbot', 'category', None)
        project = ui.config('hgbuildbot', 'project', '')
    else:
        ui.write("* You must add a [hgbuildbot] section to .hg/hgrc in "
                 "order to use buildbot hook\n")
        return

    if hooktype != "changegroup":
        ui.status("hgbuildbot: hooktype %s not supported.\n" % hooktype)
        return

    if fork:
        child_pid = os.fork()
        if child_pid == 0:
            #child
            pass
        else:
            #parent
            ui.status("Notifying buildbot...\n")
            return

    # only import inside the fork if forked
    from buildbot.clients import sendchange
    from twisted.internet import defer, reactor

    if branch is None:
        if branchtype is not None:
            if branchtype == 'dirname':
                branch = os.path.basename(repo.root)
            if branchtype == 'inrepo':
                branch = workingctx(repo).branch()

    s = sendchange.Sender(master, None)
    d = defer.Deferred()
    reactor.callLater(0, d.callback, None)
    # process changesets
    def _send(res, c):
        if not fork:
            ui.status("rev %s sent\n" % c['revision'])
        return s.send(c['branch'], c['revision'], c['comments'],
                      c['files'], c['username'], category=category,
                      repository=repository, project=project)

    try:    # first try Mercurial 1.1+ api
        start = repo[node].rev()
        end = len(repo)
    except TypeError:   # else fall back to old api
        start = repo.changelog.rev(bin(node))
        end = repo.changelog.count()

    repository = strip(repo.root, stripcount)

    for rev in xrange(start, end):
        # send changeset
        node = repo.changelog.node(rev)
        manifest, user, (time, timezone), files, desc, extra = repo.changelog.read(node)
        parents = filter(lambda p: not p == nullid, repo.changelog.parents(node))
        if branchtype == 'inrepo':
            branch = extra['branch']
        # merges don't always contain files, but at least one file is required by buildbot
        if len(parents) > 1 and not files:
            files = ["merge"]
        change = {
            'master': master,
            'username': user,
            'revision': hex(node),
            'comments': desc,
            'files': files,
            'branch': branch
        }
        d.addCallback(_send, change)

    d.addCallbacks(s.printSuccess, s.printFailure)
    d.addBoth(s.stop)
    s.run()

    if fork:
        os._exit(os.EX_OK)
    else:
        return

# taken from the mercurial notify extension
def strip(path, count):
    '''Strip the count first slash of the path'''

    # First normalize it
    path = '/'.join(path.split(os.sep))
    # and strip it part after part
    while count > 0:
        c = path.find('/')
        if c == -1:
            break
        path = path[c + 1:]
        count -= 1
    return path
