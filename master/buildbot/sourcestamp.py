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
# Copyright Buildbot Team Members


from buildbot import interfaces
from buildbot import util
from buildbot.changes.changes import Change
from twisted.internet import defer
from twisted.persisted import styles
from zope.interface import implements
# TODO: kill this class, or at least make it less significant


class SourceStamp(util.ComparableMixin, styles.Versioned):

    """This is a tuple of (branch, revision, patchspec, changes, project, repository).

    C{branch} is always valid, although it may be None to let the Source
    step use its default branch. There are three possibilities for the
    remaining elements:
     - (revision=REV, patchspec=None, changes=None): build REV. If REV is
       None, build the HEAD revision from the given branch. Note that REV
       must always be a string: SVN, Perforce, and other systems which use
       integers should provide a string here, but the Source checkout step
       will integerize it when making comparisons.
     - (revision=REV, patchspec=(LEVEL, DIFF), changes=None): checkout REV,
       then apply a patch to the source, with C{patch -pLEVEL <DIFF}.
       If REV is None, checkout HEAD and patch it.
     - (revision=None, patchspec=None, changes=[CHANGES]): let the Source
       step check out the latest revision indicated by the given Changes.
       CHANGES is a tuple of L{buildbot.changes.changes.Change} instances,
       and all must be on the same branch.

    @ivar ssid: sourcestamp ID, or None if this sourcestamp has not yet been
    added to the database

    @ivar branch: branch name or None

    @ivar revision: revision string or None

    @ivar patch: tuple (patch level, patch body) or None

    @ivar patch_info: tuple (patch author, patch comment) or None

    @ivar changes: tuple of changes that went into this source stamp, sorted by
    number

    @ivar project: project name

    @ivar repository: repository URL
    """

    persistenceVersion = 3
    persistenceForgets = ('wasUpgraded', )

    # all seven of these are publicly visible attributes
    branch = None
    revision = None
    patch = None
    patch_info = None
    changes = ()
    project = ''
    repository = ''
    codebase = ''
    sourcestampsetid = None
    ssid = None

    compare_attrs = ('branch', 'revision', 'patch', 'patch_info', 'changes', 'project', 'repository', 'codebase')

    implements(interfaces.ISourceStamp)

    @classmethod
    def fromSsdict(cls, master, ssdict):
        """
        Class method to create a L{SourceStamp} from a dictionary as returned
        by L{SourceStampConnectorComponent.getSourceStamp}.

        @param master: build master instance
        @param ssdict: source stamp dictionary

        @returns: L{SourceStamp} via Deferred
        """
        # try to fetch from the cache, falling back to _make_ss if not
        # found
        cache = master.caches.get_cache("SourceStamps", cls._make_ss)
        return cache.get(ssdict['ssid'], ssdict=ssdict, master=master)

    @classmethod
    def _make_ss(cls, ssid, ssdict, master):
        sourcestamp = cls(_fromSsdict=True)
        sourcestamp.ssid = ssid
        sourcestamp.branch = ssdict['branch']
        sourcestamp.revision = ssdict['revision']
        sourcestamp.project = ssdict['project']
        sourcestamp.repository = ssdict['repository']
        sourcestamp.codebase = ssdict['codebase']
        sourcestamp.sourcestampsetid = ssdict['sourcestampsetid']

        sourcestamp.patch = None
        if ssdict['patch_body']:
            sourcestamp.patch = (ssdict['patch_level'], ssdict['patch_body'],
                                 ssdict.get('patch_subdir'))
            sourcestamp.patch_info = (ssdict['patch_author'],
                                      ssdict['patch_comment'])

        if ssdict['changeids']:
            # sort the changeids in order, oldest to newest
            sorted_changeids = sorted(ssdict['changeids'])

            @defer.inlineCallbacks
            def gci(id):
                chdict = yield master.db.changes.getChange(id)
                if chdict:
                    change = yield Change.fromChdict(master, chdict)
                    defer.returnValue(change)
                else:
                    # change isn't in the DB, so ignore it
                    return
            d = defer.gatherResults([gci(id)
                                     for id in sorted_changeids])
        else:
            d = defer.succeed([])

        def got_changes(changes):
            sourcestamp.changes = tuple(filter(None, changes))
            return sourcestamp
        d.addCallback(got_changes)
        return d

    def __init__(self, branch=None, revision=None, patch=None, sourcestampsetid=None,
                 patch_info=None, changes=None, project='', repository='',
                 codebase='', _fromSsdict=False, _ignoreChanges=False):
        self._addSourceStampToDatabase_lock = defer.DeferredLock()

        # skip all this madness if we're being built from the database
        if _fromSsdict:
            return

        if patch is not None:
            assert 2 <= len(patch) <= 3
            assert int(patch[0]) != -1
        self.sourcestampsetid = sourcestampsetid
        self.branch = branch
        self.patch = patch
        self.patch_info = patch_info
        self.project = project or ''
        self.repository = repository or ''
        self.codebase = codebase or ''
        if changes:
            self.changes = changes = list(changes)
            changes.sort()
            if not _ignoreChanges:
                # set branch and revision to most recent change
                self.branch = changes[-1].branch
                revision = changes[-1].revision
                if not self.project and hasattr(changes[-1], 'project'):
                    self.project = changes[-1].project
                if not self.repository and hasattr(changes[-1], 'repository'):
                    self.repository = changes[-1].repository

        if revision is not None:
            if isinstance(revision, int):
                revision = str(revision)

        self.revision = revision

    def canBeMergedWith(self, other):
        # this algorithm implements the "compatible" mergeRequests defined in
        # detail in cfg-buidlers.texinfo; change that documentation if the
        # algorithm changes!
        if other.codebase != self.codebase:
            return False
        if other.repository != self.repository:
            return False
        if other.branch != self.branch:
            return False  # the builds are completely unrelated
        if other.project != self.project:
            return False
        if self.patch or other.patch:
            # you can't merge patched builds with anything else
            return self is other

        if self.changes and other.changes:
            return True
        elif self.changes and not other.changes:
            return False  # we're using changes, they aren't
        elif not self.changes and other.changes:
            return False  # they're using changes, we aren't

        if self.revision == other.revision:
            # both builds are using the same specific revision, so they can
            # be merged. It might be the case that revision==None, so they're
            # both building HEAD.
            return True

        return False

    def mergeWith(self, others):
        """Generate a SourceStamp for the merger of me and all the other
        SourceStamps. This is called by a Build when it starts, to figure
        out what its sourceStamp should be."""

        # either we're all building the same thing (changes==None), or we're
        # all building changes (which can be merged)
        changes = []
        changes.extend(self.changes)
        for ss in others:
            changes.extend(ss.changes)
        newsource = SourceStamp(sourcestampsetid=self.sourcestampsetid,
                                branch=self.branch,
                                revision=self.revision,
                                patch=self.patch,
                                patch_info=self.patch_info,
                                project=self.project,
                                repository=self.repository,
                                codebase=self.codebase,
                                changes=changes)
        return newsource

    def clone(self):
        # Create an exact but identityless copy
        return SourceStamp(branch=self.branch, revision=self.revision,
                           patch=self.patch, repository=self.repository,
                           codebase=self.codebase, patch_info=self.patch_info,
                           project=self.project, changes=self.changes,
                           _ignoreChanges=True)

    def getAbsoluteSourceStamp(self, got_revision):
        cloned = self.clone()
        cloned.revision = got_revision
        return cloned

    def getText(self):
        # note: this won't work for VC systems with huge 'revision' strings
        text = []
        if self.project:
            text.append("for %s" % self.project)
        if self.repository:
            text.append("in %s" % self.repository)
            if self.codebase:
                text.append("(%s)" % self.codebase)
        if self.revision is None:
            return text + ["latest"]
        text.append(str(self.revision))
        if self.branch:
            text.append("in '%s'" % self.branch)
        if self.patch:
            text.append("[patch]")
        return text

    def asDict(self):
        result = {}
        # Constant
        result['revision'] = self.revision

        # TODO(maruel): Make the patch content a suburl.
        result['hasPatch'] = self.patch is not None
        if self.patch:
            result['patch_level'] = self.patch[0]
            result['patch_body'] = self.patch[1]
            if len(self.patch) > 2:
                result['patch_subdir'] = self.patch[2]
            if self.patch_info:
                result['patch_author'] = self.patch_info[0]
                result['patch_comment'] = self.patch_info[1]

        result['branch'] = self.branch
        result['changes'] = [c.asDict() for c in getattr(self, 'changes', [])]
        result['project'] = self.project
        result['repository'] = self.repository
        result['codebase'] = self.codebase
        return result

    def __setstate__(self, d):
        styles.Versioned.__setstate__(self, d)
        self._addSourceStampToDatabase_lock = defer.DeferredLock()

    def upgradeToVersion1(self):
        # version 0 was untyped; in version 1 and later, types matter.
        if self.branch is not None and not isinstance(self.branch, str):
            self.branch = str(self.branch)
        if self.revision is not None and not isinstance(self.revision, str):
            self.revision = str(self.revision)
        if self.patch is not None:
            self.patch = (int(self.patch[0]), str(self.patch[1]))
        self.wasUpgraded = True

    def upgradeToVersion2(self):
        # version 1 did not have project or repository; just set them to a default ''
        self.project = ''
        self.repository = ''
        self.wasUpgraded = True

    def upgradeToVersion3(self):
        # The database has been upgraded where all existing sourcestamps got an
        # setid equal to its ssid
        self.sourcestampsetid = self.ssid
        # version 2 did not have codebase; set to ''
        self.codebase = ''
        self.wasUpgraded = True

    def getSourceStampSetId(self, master):
        "temporary; do not use widely!"
        if self.sourcestampsetid:
            return defer.succeed(self.sourcestampsetid)
        else:
            return self.addSourceStampToDatabase(master)

    @util.deferredLocked('_addSourceStampToDatabase_lock')
    def addSourceStampToDatabase(self, master, sourcestampsetid=None):
        # add it to the DB
        patch_body = None
        patch_level = None
        patch_subdir = None
        if self.patch:
            patch_level = self.patch[0]
            patch_body = self.patch[1]
            if len(self.patch) > 2:
                patch_subdir = self.patch[2]

        patch_author = None
        patch_comment = None
        if self.patch_info:
            patch_author, patch_comment = self.patch_info

        def get_setid():
            if sourcestampsetid is not None:
                return defer.succeed(sourcestampsetid)
            else:
                return master.db.sourcestampsets.addSourceStampSet()

        def set_setid(setid):
            self.sourcestampsetid = setid
            return setid

        def add_sourcestamp(setid):
            return master.db.sourcestamps.addSourceStamp(
                sourcestampsetid=setid,
                branch=self.branch, revision=self.revision,
                repository=self.repository, codebase=self.codebase,
                project=self.project,
                patch_body=patch_body, patch_level=patch_level,
                patch_author=patch_author, patch_comment=patch_comment,
                patch_subdir=patch_subdir,
                changeids=[c.number for c in self.changes])

        def set_ssid(ssid):
            self.ssid = ssid
            return ssid

        d = get_setid()
        d.addCallback(set_setid)
        d.addCallback(add_sourcestamp)
        d.addCallback(set_ssid)
        d.addCallback(lambda _: self.sourcestampsetid)
        return d
