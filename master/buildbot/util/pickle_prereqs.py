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

import sys
import types
from zope.interface import implements
from twisted.persisted import styles
from buildbot import interfaces

# This module contains classes that are referenced in pickles, and thus needed
# during upgrade operations, but are no longer used in a running Buildbot
# master.

class SourceStamp(styles.Versioned):
    persistenceVersion = 3
    persistenceForgets = ( 'wasUpgraded', )

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
                 codebase = '', _ignoreChanges=False):

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
            self.patch = ( int(self.patch[0]), str(self.patch[1]) )
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
        #version 2 did not have codebase; set to ''
        self.codebase = ''
        self.wasUpgraded = True

def patch():
    # add SourceStamp to buildbot.sourcestamp
    if 'buildbot.sourcestamp' not in sys.modules:
        mod = types.ModuleType('buildbot.sourcestamp')
        sys.modules['buildbot.sourcestamp'] = mod
        mod.SourceStamp = SourceStamp

def unpatch():
    if 'buildbot.sourcestamp' in sys.modules:
        del sys.modules['buildbot.sourcestamp']
