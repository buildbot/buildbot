# Copyright (C) 2008-2009 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""\
bzr buildbot integration
========================

This file contains both bzr commit/change hooks and a bzr poller.

------------
Requirements
------------

This has been tested with buildbot 0.7.9, bzr 1.10, and Twisted 8.1.0.  It
should work in subsequent releases.

For the hook to work, Twisted must be installed in the same Python that bzr
uses.

-----
Hooks
-----

To install, put this file in a bzr plugins directory (e.g.,
~/.bazaar/plugins). Then, in one of your bazaar conf files (e.g.,
~/.bazaar/locations.conf), set the location you want to connect with buildbot
with these keys:

- buildbot_on: one of 'commit', 'push, or 'change'.  Turns the plugin on to
  report changes via commit, changes via push, or any changes to the trunk.
  'change' is recommended.

- buildbot_server: (required to send to a buildbot master) the URL of the
  buildbot master to which you will connect (as of this writing, the same
  server and port to which slaves connect).

- buildbot_port: (optional, defaults to 9989) the port of the buildbot master
  to which you will connect (as of this writing, the same server and port to
  which slaves connect)

- buildbot_auth: (optional, defaults to change:changepw) the credentials
  expected by the change source configuration in the master. Takes the
  "user:password" form.

- buildbot_pqm: (optional, defaults to not pqm) Normally, the user that
  commits the revision is the user that is responsible for the change.  When
  run in a pqm (Patch Queue Manager, see https://launchpad.net/pqm)
  environment, the user that commits is the Patch Queue Manager, and the user
  that committed the *parent* revision is responsible for the change.  To turn
  on the pqm mode, set this value to any of (case-insensitive) "Yes", "Y",
  "True", or "T".

- buildbot_dry_run: (optional, defaults to not a dry run) Normally, the
  post-commit hook will attempt to communicate with the configured buildbot
  server and port. If this parameter is included and any of (case-insensitive)
  "Yes", "Y", "True", or "T", then the hook will simply print what it would
  have sent, but not attempt to contact the buildbot master.

- buildbot_send_branch_name: (optional, defaults to not sending the branch
  name) If your buildbot's bzr source build step uses a repourl, do
  *not* turn this on. If your buildbot's bzr build step uses a baseURL, then
  you may set this value to any of (case-insensitive) "Yes", "Y", "True", or
  "T" to have the buildbot master append the branch name to the baseURL.

Note: The bzr smart server (as of version 2.2.2) doesn't know how to resolve
bzr:// urls into absolute paths so any paths in locations.conf won't match,
hence no change notifications will be sent to Buildbot. Setting configuration
parameters globally or in-branch might still work.

When buildbot no longer has a hardcoded password, it will be a configuration
option here as well.

------
Poller
------

See the Buildbot manual.

-------------------
Contact Information
-------------------

Maintainer/author: gary.poster@canonical.com
"""

try:
    import buildbot.util
    import buildbot.changes.base
    import buildbot.changes.changes
except ImportError:
    DEFINE_POLLER = False
else:
    DEFINE_POLLER = True
import bzrlib.branch
import bzrlib.errors
import bzrlib.trace
import twisted.cred.credentials
import twisted.internet.base
import twisted.internet.defer
import twisted.internet.reactor
import twisted.internet.selectreactor
import twisted.internet.task
import twisted.internet.threads
import twisted.python.log
import twisted.spread.pb


#############################################################################
# This is the code that the poller and the hooks share.

def generate_change(branch,
                    old_revno=None, old_revid=None,
                    new_revno=None, new_revid=None,
                    blame_merge_author=False):
    """Return a dict of information about a change to the branch.

    Dict has keys of "files", "who", "comments", and "revision", as used by
    the buildbot Change (and the PBChangeSource).

    If only the branch is given, the most recent change is returned.

    If only the new_revno is given, the comparison is expected to be between
    it and the previous revno (new_revno -1) in the branch.

    Passing old_revid and new_revid is only an optimization, included because
    bzr hooks usually provide this information.

    blame_merge_author means that the author of the merged branch is
    identified as the "who", not the person who committed the branch itself.
    This is typically used for PQM.
    """
    change = {} # files, who, comments, revision; NOT branch (= branch.nick)
    if new_revno is None:
        new_revno = branch.revno()
    if new_revid is None:
        new_revid = branch.get_rev_id(new_revno)
    # TODO: This falls over if this is the very first revision
    if old_revno is None:
        old_revno = new_revno -1
    if old_revid is None:
        old_revid = branch.get_rev_id(old_revno)
    repository = branch.repository
    new_rev = repository.get_revision(new_revid)
    if blame_merge_author:
        # this is a pqm commit or something like it
        change['who'] = repository.get_revision(
            new_rev.parent_ids[-1]).get_apparent_authors()[0]
    else:
        change['who'] = new_rev.get_apparent_authors()[0]
    # maybe useful to know:
    # name, email = bzrtools.config.parse_username(change['who'])
    change['comments'] = new_rev.message
    change['revision'] = new_revno
    files = change['files'] = []
    changes = repository.revision_tree(new_revid).changes_from(
        repository.revision_tree(old_revid))
    for (collection, name) in ((changes.added, 'ADDED'),
                               (changes.removed, 'REMOVED'),
                               (changes.modified, 'MODIFIED')):
        for info in collection:
            path = info[0]
            kind = info[2]
            files.append(' '.join([path, kind, name]))
    for info in changes.renamed:
        oldpath, newpath, id, kind, text_modified, meta_modified = info
        elements = [oldpath, kind,'RENAMED', newpath]
        if text_modified or meta_modified:
            elements.append('MODIFIED')
        files.append(' '.join(elements))
    return change

#############################################################################
# poller

# We don't want to make the hooks unnecessarily depend on buildbot being
# installed locally, so we conditionally create the BzrPoller class.
if DEFINE_POLLER:

    FULL = object()
    SHORT = object()


    class BzrPoller(buildbot.changes.base.PollingChangeSource,
                    buildbot.util.ComparableMixin):

        compare_attrs = ['url']

        def __init__(self, url, poll_interval=10*60, blame_merge_author=False,
                     branch_name=None, category=None):
            # poll_interval is in seconds, so default poll_interval is 10
            # minutes.
            # bzr+ssh://bazaar.launchpad.net/~launchpad-pqm/launchpad/devel/
            # works, lp:~launchpad-pqm/launchpad/devel/ doesn't without help.
            if url.startswith('lp:'):
                url = 'bzr+ssh://bazaar.launchpad.net/' + url[3:]
            self.url = url
            self.poll_interval = poll_interval
            self.loop = twisted.internet.task.LoopingCall(self.poll)
            self.blame_merge_author = blame_merge_author
            self.branch_name = branch_name
            self.category = category

        def startService(self):
            twisted.python.log.msg("BzrPoller(%s) starting" % self.url)
            if self.branch_name is FULL:
                ourbranch = self.url
            elif self.branch_name is SHORT:
                # We are in a bit of trouble, as we cannot really know what our
                # branch is until we have polled new changes.
                # Seems we would have to wait until we polled the first time,
                # and only then do the filtering, grabbing the branch name from
                # whatever we polled.
                # For now, leave it as it was previously (compare against
                # self.url); at least now things work when specifying the
                # branch name explicitly.
                ourbranch = self.url
            else:
                ourbranch = self.branch_name
            for change in reversed(self.parent.changes):
                if change.branch == ourbranch:
                    self.last_revision = change.revision
                    break
            else:
                self.last_revision = None
            buildbot.changes.base.PollingChangeSource.startService(self)

        def stopService(self):
            twisted.python.log.msg("BzrPoller(%s) shutting down" % self.url)
            return buildbot.changes.base.PollingChangeSource.stopService(self)

        def describe(self):
            return "BzrPoller watching %s" % self.url

        @twisted.internet.defer.inlineCallbacks
        def poll(self):
            # On a big tree, even individual elements of the bzr commands
            # can take awhile. So we just push the bzr work off to a
            # thread.
            try:
                changes = yield twisted.internet.threads.deferToThread(
                    self.getRawChanges)
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                # we'll try again next poll.  Meanwhile, let's report.
                twisted.python.log.err()
            else:
                for change in changes:
                    yield self.addChange(
                        buildbot.changes.changes.Change(**change))
                    self.last_revision = change['revision']

        def getRawChanges(self):
            branch = bzrlib.branch.Branch.open_containing(self.url)[0]
            if self.branch_name is FULL:
                branch_name = self.url
            elif self.branch_name is SHORT:
                branch_name = branch.nick
            else: # presumably a string or maybe None
                branch_name = self.branch_name
            changes = []
            change = generate_change(
                branch, blame_merge_author=self.blame_merge_author)
            if (self.last_revision is None or
                change['revision'] > self.last_revision):
                change['branch'] = branch_name
                change['category'] = self.category
                changes.append(change)
                if self.last_revision is not None:
                    while self.last_revision + 1 < change['revision']:
                        change = generate_change(
                            branch, new_revno=change['revision']-1,
                            blame_merge_author=self.blame_merge_author)
                        change['branch'] = branch_name
                        changes.append(change)
            changes.reverse()
            return changes

        def addChange(self, change):
            d = twisted.internet.defer.Deferred()
            def _add_change():
                d.callback(
                    self.parent.addChange(change, src='bzr'))
            twisted.internet.reactor.callLater(0, _add_change)
            return d

#############################################################################
# hooks

HOOK_KEY = 'buildbot_on'
SERVER_KEY = 'buildbot_server'
PORT_KEY = 'buildbot_port'
AUTH_KEY = 'buildbot_auth'
DRYRUN_KEY = 'buildbot_dry_run'
PQM_KEY = 'buildbot_pqm'
SEND_BRANCHNAME_KEY = 'buildbot_send_branch_name'

PUSH_VALUE = 'push'
COMMIT_VALUE = 'commit'
CHANGE_VALUE = 'change'

def _is_true(config, key):
    val = config.get_user_option(key)
    return val is not None and val.lower().strip() in (
        'y', 'yes', 't', 'true')

def _installed_hook(branch):
    value = branch.get_config().get_user_option(HOOK_KEY)
    if value is not None:
        value = value.strip().lower()
        if value not in (PUSH_VALUE, COMMIT_VALUE, CHANGE_VALUE):
            raise bzrlib.errors.BzrError(
                '%s, if set, must be one of %s, %s, or %s' % (
                    HOOK_KEY, PUSH_VALUE, COMMIT_VALUE, CHANGE_VALUE))
    return value

##########################
# Work around Twisted bug.
# See http://twistedmatrix.com/trac/ticket/3591
import operator
import socket
from twisted.internet import defer
from twisted.python import failure

# replaces twisted.internet.thread equivalent
def _putResultInDeferred(reactor, deferred, f, args, kwargs):
    """
    Run a function and give results to a Deferred.
    """
    try:
        result = f(*args, **kwargs)
    except:
        f = failure.Failure()
        reactor.callFromThread(deferred.errback, f)
    else:
        reactor.callFromThread(deferred.callback, result)

# would be a proposed addition.  deferToThread could use it
def deferToThreadInReactor(reactor, f, *args, **kwargs):
    """
    Run function in thread and return result as Deferred.
    """
    d = defer.Deferred()
    reactor.callInThread(_putResultInDeferred, reactor, d, f, args, kwargs)
    return d

# uses its own reactor for the threaded calls, unlike Twisted's
class ThreadedResolver(twisted.internet.base.ThreadedResolver):
    def getHostByName(self, name, timeout = (1, 3, 11, 45)):
        if timeout:
            timeoutDelay = reduce(operator.add, timeout)
        else:
            timeoutDelay = 60
        userDeferred = defer.Deferred()
        lookupDeferred = deferToThreadInReactor(
            self.reactor, socket.gethostbyname, name)
        cancelCall = self.reactor.callLater(
            timeoutDelay, self._cleanup, name, lookupDeferred)
        self._runningQueries[lookupDeferred] = (userDeferred, cancelCall)
        lookupDeferred.addBoth(self._checkTimeout, name, lookupDeferred)
        return userDeferred
##########################

def send_change(branch, old_revno, old_revid, new_revno, new_revid, hook):
    config = branch.get_config()
    server = config.get_user_option(SERVER_KEY)
    if not server:
        bzrlib.trace.warning(
            'bzr_buildbot: ERROR.  If %s is set, %s must be set',
            HOOK_KEY, SERVER_KEY)
        return
    change = generate_change(
        branch, old_revno, old_revid, new_revno, new_revid,
        blame_merge_author=_is_true(config, PQM_KEY))
    if _is_true(config, SEND_BRANCHNAME_KEY):
        change['branch'] = branch.nick
    # as of this writing (in Buildbot 0.7.9), 9989 is the default port when
    # you make a buildbot master.
    port = int(config.get_user_option(PORT_KEY) or 9989)
    # if dry run, stop.
    if _is_true(config, DRYRUN_KEY):
        bzrlib.trace.note("bzr_buildbot DRY RUN "
                          "(*not* sending changes to %s:%d on %s)",
                          server, port, hook)
        keys = change.keys()
        keys.sort()
        for k in keys:
            bzrlib.trace.note("[%10s]: %s", k, change[k])
        return
    # We instantiate our own reactor so that this can run within a server.
    reactor = twisted.internet.selectreactor.SelectReactor()
    # See other reference to http://twistedmatrix.com/trac/ticket/3591
    # above.  This line can go away with a release of Twisted that addresses
    # this issue.
    reactor.resolver = ThreadedResolver(reactor)
    pbcf = twisted.spread.pb.PBClientFactory()
    reactor.connectTCP(server, port, pbcf)
    auth = config.get_user_option(AUTH_KEY)
    if auth:
        user, passwd = [s.strip() for s in auth.split(':', 1)]
    else:
        user, passwd = ('change', 'changepw')
    deferred = pbcf.login(
        twisted.cred.credentials.UsernamePassword(user, passwd))

    def sendChanges(remote):
        """Send changes to buildbot."""
        bzrlib.trace.mutter("bzrbuildout sending changes: %s", change)
        change['src'] = 'bzr'
        return remote.callRemote('addChange', change)

    deferred.addCallback(sendChanges)

    def quit(ignore, msg):
        bzrlib.trace.note("bzrbuildout: %s", msg)
        reactor.stop()

    def failed(failure):
        bzrlib.trace.warning("bzrbuildout: FAILURE\n %s", failure)
        reactor.stop()

    deferred.addCallback(quit, "SUCCESS")
    deferred.addErrback(failed)
    reactor.callLater(60, quit, None, "TIMEOUT")
    bzrlib.trace.note(
        "bzr_buildbot: SENDING CHANGES to buildbot master %s:%d on %s",
        server, port, hook)
    reactor.run(installSignalHandlers=False) # run in a thread when in server

def post_commit(local_branch, master_branch, # branch is the master_branch
                old_revno, old_revid, new_revno, new_revid):
    if _installed_hook(master_branch) == COMMIT_VALUE:
        send_change(master_branch,
                     old_revid, old_revid, new_revno, new_revid, COMMIT_VALUE)

def post_push(result):
    if _installed_hook(result.target_branch) == PUSH_VALUE:
        send_change(result.target_branch,
                     result.old_revid, result.old_revid,
                     result.new_revno, result.new_revid, PUSH_VALUE)

def post_change_branch_tip(result):
    if _installed_hook(result.branch) == CHANGE_VALUE:
        send_change(result.branch,
                     result.old_revid, result.old_revid,
                     result.new_revno, result.new_revid, CHANGE_VALUE)

bzrlib.branch.Branch.hooks.install_named_hook(
    'post_commit', post_commit,
    'send change to buildbot master')
bzrlib.branch.Branch.hooks.install_named_hook(
    'post_push', post_push,
    'send change to buildbot master')
bzrlib.branch.Branch.hooks.install_named_hook(
    'post_change_branch_tip', post_change_branch_tip,
    'send change to buildbot master')
