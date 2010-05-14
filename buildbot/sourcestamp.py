# -*- test-case-name: buildbot.test.test_sourcestamp -*-

from zope.interface import implements
from twisted.persisted import styles
from buildbot import util, interfaces

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
    """

    persistenceVersion = 2

    # all six of these are publically visible attributes
    branch = None
    revision = None
    patch = None
    changes = ()
    project = ''
    repository = ''
    ssid = None # filled in by db.get_sourcestampid()

    compare_attrs = ('branch', 'revision', 'patch', 'changes', 'project', 'repository')

    implements(interfaces.ISourceStamp)

    def __init__(self, branch=None, revision=None, patch=None,
                 changes=None, project='', repository=''):
        if revision is not None:
            if isinstance(revision, int):
                revision = str(revision)
        if patch is not None:
            patch_level = patch[0]
            patch_level = int(patch_level)
            patch_diff = patch[1]
            if len(patch) > 2:
                patch_subdir = patch[2]
        self.branch = branch
        self.revision = revision
        self.patch = patch
        self.project = project
        self.repository = repository
        if changes:
            self.changes = tuple(changes)
            # set branch and revision to most recent change
            self.branch = changes[-1].branch
            self.revision = str(changes[-1].revision)
            if not self.project:
                self.project = changes[-1].project
            if not self.repository:
                self.repository = changes[-1].repository

    def canBeMergedWith(self, other):
        if other.repository != self.repository:
            return False
        if other.branch != self.branch:
            return False # the builds are completely unrelated
        if other.project != self.project:
            return False

        if self.changes and other.changes:
            # TODO: consider not merging these. It's a tradeoff between
            # minimizing the number of builds and obtaining finer-grained
            # results.
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
        BuildRequests. This is called by a Build when it starts, to figure
        out what its sourceStamp should be."""

        # either we're all building the same thing (changes==None), or we're
        # all building changes (which can be merged)
        changes = []
        changes.extend(self.changes)
        for req in others:
            assert self.canBeMergedWith(req) # should have been checked already
            changes.extend(req.changes)
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
                           project=self.project)

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
        result['hasPatch']= self.patch is not None
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

    def upgradeToVersion2(self):
        # version 1 did not have project or repository; just set them to a default ''
        self.project = ''
        self.repository = ''

# vim: set ts=4 sts=4 sw=4 et:
