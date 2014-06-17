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

from __future__ import with_statement

import cPickle
import cStringIO
import os

from buildbot import interfaces
from buildbot import util
from twisted.persisted import styles
from twisted.python import log
from twisted.python import reflect
from twisted.python import runtime
from zope.interface import implements

# This module contains classes that are referenced in pickles, and thus needed
# during upgrade operations, but are no longer used in a running Buildbot
# master.
substituteClasses = {}


class SourceStamp(styles.Versioned):  # pragma: no cover
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

    def __init__(self, branch=None, revision=None, patch=None,
                 patch_info=None, changes=None, project='', repository='',
                 codebase='', _ignoreChanges=False):

        if patch is not None:
            assert 2 <= len(patch) <= 3
            assert int(patch[0]) != -1
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
substituteClasses['buildbot.sourcestamp', 'SourceStamp'] = SourceStamp


class ChangeMaster:  # pragma: no cover

    def __init__(self):
        self.changes = []
        # self.basedir must be filled in by the parent
        self.nextNumber = 1

    def saveYourself(self):
        filename = os.path.join(self.basedir, "changes.pck")
        tmpfilename = filename + ".tmp"
        try:
            with open(tmpfilename, "wb") as f:
                dump(self, f)
            if runtime.platformType == 'win32':
                # windows cannot rename a file on top of an existing one
                if os.path.exists(filename):
                    os.unlink(filename)
            os.rename(tmpfilename, filename)
        except Exception:
            log.msg("unable to save changes")
            log.err()

    # This method is used by contrib/fix_changes_pickle_encoding.py to recode all
    # bytestrings in an old changes.pck into unicode strings
    def recode_changes(self, old_encoding, quiet=False):
        """Processes the list of changes, with the change attributes re-encoded
        unicode objects"""
        nconvert = 0
        for c in self.changes:
            # give revision special handling, in case it is an integer
            if isinstance(c.revision, int):
                c.revision = unicode(c.revision)

            for attr in ("who", "comments", "revlink", "category", "branch", "revision"):
                a = getattr(c, attr)
                if isinstance(a, str):
                    try:
                        setattr(c, attr, a.decode(old_encoding))
                        nconvert += 1
                    except UnicodeDecodeError:
                        raise UnicodeError("Error decoding %s of change #%s as %s:\n%r" %
                                           (attr, c.number, old_encoding, a))

            # filenames are a special case, but in general they'll have the same encoding
            # as everything else on a system.  If not, well, hack this script to do your
            # import!
            newfiles = []
            for filename in util.flatten(c.files):
                if isinstance(filename, str):
                    try:
                        filename = filename.decode(old_encoding)
                        nconvert += 1
                    except UnicodeDecodeError:
                        raise UnicodeError("Error decoding filename '%s' of change #%s as %s:\n%r" %
                                           (filename.decode('ascii', 'replace'),
                                            c.number, old_encoding, a))
                newfiles.append(filename)
            c.files = newfiles
        if not quiet:
            print "converted %d strings" % nconvert
substituteClasses['buildbot.changes.changes', 'ChangeMaster'] = ChangeMaster

# replacements for stdlib pickle methods


def _makeUnpickler(file):
    up = cPickle.Unpickler(file)
    # see http://docs.python.org/2/library/pickle.html#subclassing-unpicklers

    def find_global(modname, clsname):
        try:
            return substituteClasses[(modname, clsname)]
        except KeyError:
            mod = reflect.namedModule(modname)
            return getattr(mod, clsname)
    up.find_global = find_global
    return up


def load(file):
    return _makeUnpickler(file).load()


def loads(str):
    file = cStringIO.StringIO(str)
    return _makeUnpickler(file).load()

dump = cPickle.dump
dumps = cPickle.dumps
