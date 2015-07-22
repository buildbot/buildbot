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
#
#
# Documentation
# =============
#
# Mercurial "changegroup" hook that notifies Buildbot when a number of
# changsets is brought into the repository from elsewhere.
#
# Copy this file to ".hg/hgbuildbot.py" in the repository that should notify
# Buildbot.
#
# Add it to the "[hooks]" section of ".hg/hgrc".  Also add a "[hgbuildbot]"
# section with additional parameters, for example:
#
#     [hooks]
#     changegroup.buildbot = python:.hg/hgbuiltbot.py:hook
#
#     [hgbuildbot]
#     venv = /home/buildbot/.virtualenvs/builtbot/lib/python2.7/site-packages
#     master = localhost:9987
#     passwd = aA8(-adf8j3-_3uX
#
#
# Available parmeters
# -------------------
#
# venv
#   The hook needs the Python package "buildbot".  You can optionally point to
#   virtualenv if it is not installed globally:
#
#   Optional; default: None
#
#   Example:
#
#       venv = /path/to/venv/lib/pythonX.Y/site-packages
#
# master
#   Host and port of the Buildmaster(s) to notify.
#   Can be a single entry or a comma-separated list.
#
#   Mandatory.
#
#   Examples:
#
#       master = localhost:9989
#       master = bm1.example.org:9989,bm2.example.org:9989
#
# user
#   User for connecting to the Buildmaster.
#
#   Optional; default: change
#
# passwd
#   Password for connecting to the Buildmaster.
#
#   Optional; default: changepw
#
# branchtype
#   The branchmodel you use: "inrepo" for named branches (managed by
#   "hg branch") or "dirname" for directory based branches (the last component
#   of the repository's directory will then be used as branch name).
#
#   Optional; default: inrepo
#
# branch
#   Explicitly specify a branchname instead of using the repo's basename when
#   using "branchtype = dirname".
#
#   Optional.
#
# baseurl
#   Prefix for the repository URL sent to the Buildmaster.  See below for
#   details.
#
#   Optional.  The hook will also check the [web] section for this parameter.
#
# strip
#   Strip as many slashes from the repo dir before appending it to baseurl.
#   See below for details.
#
#   Optional; default: 0; The hook will also check the [notify] section for
#   this parameter.
#
# category
#   Category to assign to all change sets.
#
#   Optional.
#
# project
#   Project that the repo belongs to.
#
#   Optional.
#
# codebase
#   Codebase name for the repo.
#
#   Optional.
#
#
# Repository URLs
# ---------------
#
# The hook sends a repository URL to the Buildmasters.  It can be used by
# schedulers (e.g., for filtering) and is also used in the webview to create
# a link to the corresponding changeset.
#
# By default, the absolute repository path (e.g., "/home/hg/repos/myrepo") will
# be used.  The webview will in this case simply append the path to its own
# hostname in order to create a link to that change (e.g.,
# "http://localhost:8020/home/hg/repos/myrepo").
#
# You can alternatively strip some of the repo path's components and prepend
# a custom base URL instead.  For example, if you want to create an URL like
# "https://code.company.com/myrepo", you must specify the following parameters:
#
#     baseurl = https://code.company.com/
#     strip = 4
#
# This would strip everything until (and including) the 4th "/" in the repo's
# path leaving only "myrepo" left.  This would then be append to the base URL.

import os
import os.path
import sys

from mercurial.encoding import fromlocal
from mercurial.node import hex
from mercurial.node import nullid


def hook(ui, repo, hooktype, node=None, source=None, **kwargs):
    if hooktype != 'changegroup':
        ui.status('hgbuildbot: hooktype %s not supported.\n' % hooktype)
        return

    # Read config parameters
    masters = ui.configlist('hgbuildbot', 'master')
    if not masters:
        ui.write('* You must add a [hgbuildbot] section to .hg/hgrc in '
                 'order to use the Buildbot hook\n')
        return

    # - virtualenv
    venv = ui.config('hgbuildbot', 'venv', None)
    if venv is not None:
        if not os.path.isdir(venv):
            ui.write('* Virtualenv "%s" does not exist.\n' % venv)
        sys.path.insert(0, venv)

    # - auth
    username = ui.config('hgbuildbot', 'user', 'change')
    password = ui.config('hgbuildbot', 'passwd', 'changepw')

    # - branch
    branchtype = ui.config('hgbuildbot', 'branchtype', 'inrepo')
    branch = ui.config('hgbuildbot', 'branch', None)

    # - repo URL
    baseurl = ui.config('hgbuildbot', 'baseurl',
                        ui.config('web', 'baseurl', ''))
    stripcount = int(ui.config('hgbuildbot', 'strip',
                               ui.config('notify', 'strip', 0)))

    # - category, project and codebase
    category = ui.config('hgbuildbot', 'category', None)
    project = ui.config('hgbuildbot', 'project', '')
    codebase = ui.config('hgbuildbot', 'codebase', '')

    # Only import this after the (optional) venv has been added to sys.path:
    from buildbot.clients import sendchange
    from twisted.internet import defer, reactor

    # Process changesets
    if branch is None and branchtype == 'dirname':
        branch = os.path.basename(repo.root)
    # If branchtype == 'inrepo', update "branch" for each commit later.

    repository = strip(repo.root, stripcount)
    repository = baseurl + repository

    start = repo[node].rev()
    end = len(repo)

    for master in masters:
        s = sendchange.Sender(master, auth=(username, password))
        d = defer.Deferred()
        reactor.callLater(0, d.callback, None)

        for rev in range(start, end):
            # send changeset
            node = repo.changelog.node(rev)
            log = repo.changelog.read(node)
            manifest, user, (time, timezone), files, desc, extra = log
            parents = [p for p in repo.changelog.parents(node) if p != nullid]

            if branchtype == 'inrepo':
                branch = extra['branch']
            if branch:
                branch = fromlocal(branch)

            is_merge = len(parents) > 1
            # merges don't always contain files, but at least one file is
            # required by buildbot
            if is_merge and not files:
                files = ["merge"]
            properties = {'is_merge': is_merge}

            change = {
                # 'master': master,
                'branch': branch,
                'revision': hex(node),
                'comments': fromlocal(desc),
                'files': files,
                'username': fromlocal(user),
                'category': category,
                'time': time,
                'properties': properties,
                'repository': repository,
                'project': project,
                'codebase': codebase,
            }
            d.addCallback(send_cs, s, change)

    def _printSuccess(res):
        ui.status(s.getSuccessString(res) + '\n')

    def _printFailure(why):
        ui.warn(s.getFailureString(why) + '\n')

    d.addCallbacks(_printSuccess, _printFailure)
    d.addBoth(lambda _: reactor.stop())
    reactor.run()


def strip(path, count):
    """Strip the count first slash of the path"""
    # First normalize it
    path = '/'.join(path.split(os.sep))
    # and strip the *count* first slash
    return path.split('/', count)[-1]


def send_cs(res, s, c):
    """Send a changeset *c* using the sender *s*."""
    return s.send(c['branch'], c['revision'], c['comments'], c['files'],
                  who=c['username'],
                  category=c['category'],
                  when=c['time'],
                  properties=c['properties'],
                  repository=c['repository'],
                  vc='hg',
                  project=c['project'],
                  # revlink='',
                  codebase=c['codebase'])
