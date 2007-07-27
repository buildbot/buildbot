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

import os

from mercurial.i18n import gettext as _
from mercurial.node import bin, hex

# mercurial's on-demand-importing hacks interfere with the:
#from zope.interface import Interface
# that Twisted needs to do, so disable it.
try:
    from mercurial import demandimport
    demandimport.disable()
except ImportError:
    pass

from buildbot.clients import sendchange
from twisted.internet import defer, reactor


def hook(ui, repo, hooktype, node=None, source=None, **kwargs):
    # read config parameters
    master = ui.config('hgbuildbot', 'master')
    if master:
        branchtype = ui.config('hgbuildbot', 'branchtype')
        branch = ui.config('hgbuildbot', 'branch')
    else:
        ui.write("* You must add a [hgbuildbot] section to .hg/hgrc in "
                 "order to use buildbot hook\n")
        return

    if branch is None:
        if branchtype is not None:
            if branchtype == 'dirname':
                branch = os.path.basename(os.getcwd())
            if branchtype == 'inrepo':
                branch=repo.workingctx().branch()

    if hooktype == 'changegroup':
        s = sendchange.Sender(master, None)
        d = defer.Deferred()
        reactor.callLater(0, d.callback, None)
        # process changesets
        def _send(res, c):
            ui.status("rev %s sent\n" % c['revision'])
            return s.send(c['branch'], c['revision'], c['comments'],
                          c['files'], c['username'])

        node=bin(node)
        start = repo.changelog.rev(node)
        end = repo.changelog.count()
        for rev in xrange(start, end):
            # send changeset
            n = repo.changelog.node(rev)
            changeset=repo.changelog.extract(repo.changelog.revision(n))
            change = {
                'master': master,
                # note: this is more likely to be a full email address, which
                # would make the left-hand "Changes" column kind of wide. The
                # buildmaster should probably be improved to display an
                # abbreviation of the username.
                'username': changeset[1],
                'revision': hex(n),
                'comments': changeset[4],
                'files': changeset[3],
                'branch': branch
            }
            d.addCallback(_send, change)

        d.addCallbacks(s.printSuccess, s.printFailure)
        d.addBoth(s.stop)
        s.run()
    else:
        ui.status(_('hgbuildbot: hook %s not supported\n') % hooktype)
    return

