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


from zope.interface import implements
from twisted.persisted import styles
from twisted.internet import defer
from buildbot.changes.changes import Change
from buildbot import util, interfaces

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
       then apply a patch to the source, with C{patch -pPATCHLEVEL <DIFF}.
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

    @ivar changes: tuple of changes that went into this source stamp, sorted by
    number

    @ivar project: project name

    @ivar repository: repository URL
    """

    persistenceVersion = 2
    persistenceForgets = ( 'wasUpgraded', )

    # all six of these are publically visible attributes
    branch = None
    revision = None
    patch = None
    changes = ()
    project = ''
    repository = ''
    ssid = None

    compare_attrs = ('branch', 'revision', 'patch', 'changes', 'project', 'repository')

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

        sourcestamp.patch = None
        if ssdict['patch_body']:
            # note that this class does not store the patch_subdir
            sourcestamp.patch = (ssdict['patch_level'], ssdict['patch_body'])

        if ssdict['changeids']:
            # sort the changeids in order, oldest to newest
            sorted_changeids = sorted(ssdict['changeids'])
            def gci(id):
                d = master.db.changes.getChange(id)
                d.addCallback(lambda chdict :
                    Change.fromChdict(master, chdict))
                return d
            d = defer.gatherResults([ gci(id)
                                for id in sorted_changeids ])
        else:
            d = defer.succeed([])
        def got_changes(changes):
            sourcestamp.changes = tuple(changes)
            return sourcestamp
        d.addCallback(got_changes)
        return d

    def __init__(self, branch=None, revision=None, patch=None,
                 changes=None, project='', repository='', _fromSsdict=False,
                 _ignoreChanges=False):
        # skip all this madness if we're being built from the database
        if _fromSsdict:
            return

        if patch is not None:
            assert len(patch) == 2
            assert int(patch[0]) != -1
        self.branch = branch
        self.patch = patch
        self.project = project or ''
        self.repository = repository or ''
        if changes and not _ignoreChanges:
            self.changes = tuple(changes)
            # set branch and revision to most recent change
	    if changes[-1] is not None:
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
        self._getSourceStampId_lock = defer.DeferredLock();

    def canBeMergedWith(self, other):
        # this algorithm implements the "compatible" mergeRequests defined in
        # detail in cfg-buidlers.texinfo; change that documentation if the
        # algorithm changes!
        if other.repository != self.repository:
            return False
        if other.branch != self.branch:
            return False # the builds are completely unrelated
        if other.project != self.project:
            return False

        if self.changes and other.changes:
            return True
        elif self.changes and not other.changes:
            return False # we're using changes, they aren't
        elif not self.changes and other.changes:
            return False # they're using changes, we aren't

        if self.patch or other.patch:
            return False # you can't merge patched builds with anything
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
        newsource = SourceStamp(branch=self.branch,
                                revision=self.revision,
                                patch=self.patch,
                                project=self.project,
                                repository=self.repository,
                                changes=changes)
        return newsource

    def getAbsoluteSourceStamp(self, got_revision):
        return SourceStamp(branch=self.branch, revision=got_revision,
                           patch=self.patch, repository=self.repository,
                           project=self.project, changes=self.changes,
                           _ignoreChanges=True)

    def getText(self):
        # note: this won't work for VC systems with huge 'revision' strings
        text = []
        if self.project:
            text.append("for %s" % self.project)
        if self.repository:
            text.append("in %s" % self.repository)
        if self.revision is None:
            return text + [ "latest" ]
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
        result['branch'] = self.branch
        result['changes'] = [c.asDict() for c in getattr(self, 'changes', [])]
        result['project'] = self.project
        result['repository'] = self.repository
        return result

    def upgradeToVersion1(self):
        # version 0 was untyped; in version 1 and later, types matter.
        if self.branch is not None and not isinstance(self.branch, str):
            self.branch = str(self.branch)
        if self.revision is not None and not isinstance(self.revision, str):
            self.revision = str(self.revision)
        if self.patch is not None:
            self.patch = ( int(self.patch[0]), str(self.patch[1]) )
        self.wasUpgraded = True

    def upgradeToVersion2(self):
        # version 1 did not have project or repository; just set them to a default ''
        self.project = ''
        self.repository = ''
        self.wasUpgraded = True

    @util.deferredLocked('_getSourceStampId_lock')
    def getSourceStampId(self, master):
        "temporary; do not use widely!"
        if self.ssid:
            return defer.succeed(self.ssid)
        # add it to the DB
        patch_body = None
        patch_level = None
        if self.patch:
            patch_level, patch_body = self.patch
        d = master.db.sourcestamps.addSourceStamp(
                branch=self.branch, revision=self.revision,
                repository=self.repository, project=self.project,
                patch_body=patch_body, patch_level=patch_level,
                patch_subdir=None, changeids=[c.number for c in self.changes])
        def set_ssid(ssid):
            self.ssid = ssid
            return ssid
        d.addCallback(set_ssid)
        return d
