# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Portions Copyright Buildbot Team Members
# Portions Copyright 2007 Frederic Leroy <fredo@starox.org>

# hook extension to send change notifications to buildbot when a changeset is
# brought into the repository from elsewhere.
#
# See the Buildbot manual for configuration instructions.

## WARNING
# This code does not work with recent versions of Twisted and Mercurial.  It
# was never a good idea to try to run Twisted code within Mercurial, and now it
# doesn't work.  Use this code with caution.
##

import os

from mercurial.node import bin
from mercurial.node import hex
from mercurial.node import nullid  # @UnresolvedImport

# mercurial's on-demand-importing hacks interfere with the:
#from zope.interface import Interface
# that Twisted needs to do, so disable it.
try:
    from mercurial import demandimport
    demandimport.disable()
except ImportError:
    pass

# In Mercurial post-1.7, some strings might be stored as a
# encoding.localstr class. encoding.fromlocal will translate
# those back to UTF-8 strings.
try:
    from mercurial.encoding import fromlocal
    _hush_pyflakes = [fromlocal]
    del _hush_pyflakes
except ImportError:
    def fromlocal(s):
        return s


def hook(ui, repo, hooktype, node=None, source=None, **kwargs):
    # read config parameters
    baseurl = ui.config('hgbuildbot', 'baseurl',
                        ui.config('web', 'baseurl', ''))
    masters = ui.configlist('hgbuildbot', 'master')
    if masters:
        branchtype = ui.config('hgbuildbot', 'branchtype', 'inrepo')
        branch = ui.config('hgbuildbot', 'branch')
        fork = ui.configbool('hgbuildbot', 'fork', False)
        # notify also has this setting
        stripcount = int(ui.config('notify', 'strip') or ui.config('hgbuildbot', 'strip', 3))
        category = ui.config('hgbuildbot', 'category', None)
        project = ui.config('hgbuildbot', 'project', '')
        auth = ui.config('hgbuildbot', 'auth', None)
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
            # child
            pass
        else:
            # parent
            ui.status("Notifying buildbot...\n")
            return

    # only import inside the fork if forked
    from buildbot.clients import sendchange
    from twisted.internet import defer, reactor

    if branch is None:
        if branchtype == 'dirname':
            branch = os.path.basename(repo.root)

    if not auth:
        auth = 'change:changepw'
    auth = auth.split(':', 1)

    # process changesets
    def _send(res, s, c):
        if not fork:
            ui.status("rev %s sent\n" % c['revision'])
        return s.send(c['branch'], c['revision'], c['comments'],
                      c['files'], c['username'], category=category,
                      repository=repository, project=project, vc='hg',
                      properties=c['properties'])

    try:    # first try Mercurial 1.1+ api
        start = repo[node].rev()
        end = len(repo)
    except TypeError:   # else fall back to old api
        start = repo.changelog.rev(bin(node))
        end = repo.changelog.count()

    repository = strip(repo.root, stripcount)
    repository = baseurl + repository

    for master in masters:
        s = sendchange.Sender(master, auth=auth)
        d = defer.Deferred()
        reactor.callLater(0, d.callback, None)

        for rev in xrange(start, end):
            # send changeset
            node = repo.changelog.node(rev)
            manifest, user, (time, timezone), files, desc, extra = repo.changelog.read(node)
            parents = filter(lambda p: not p == nullid, repo.changelog.parents(node))
            if branchtype == 'inrepo':
                branch = extra['branch']
            is_merge = len(parents) > 1
            # merges don't always contain files, but at least one file is required by buildbot
            if is_merge and not files:
                files = ["merge"]
            properties = {'is_merge': is_merge}
            if branch:
                branch = fromlocal(branch)
            change = {
                'master': master,
                'username': fromlocal(user),
                'revision': hex(node),
                'comments': fromlocal(desc),
                'files': files,
                'branch': branch,
                'properties': properties
            }
            d.addCallback(_send, s, change)

    def _printSuccess(res):
        ui.status(s.getSuccessString(res) + '\n')

    def _printFailure(why):
        ui.warn(s.getFailureString(why) + '\n')

    d.addCallbacks(_printSuccess, _printFailure)
    d.addBoth(lambda _: reactor.stop())
    reactor.run()

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
