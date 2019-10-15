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


from buildbot.steps.source.git import Git


class Gerrit(Git):

    def startVC(self, branch, revision, patch):
        gerrit_branch = None

        changed_project = self.build.getProperty('event.change.project')
        if (not self.sourcestamp or (self.sourcestamp.project !=
                                     changed_project)):
            # If we don't have a sourcestamp, or the project is  wrong, this
            # isn't the repo that's changed.  Drop through and check out the
            # head of the given branch
            pass
        elif self.build.hasProperty("event.patchSet.ref"):
            gerrit_branch = self.build.getProperty("event.patchSet.ref")
            self.updateSourceProperty("gerrit_branch", gerrit_branch)
        else:
            try:
                change = self.build.getProperty("gerrit_change", '').split('/')
                if len(change) == 2:
                    gerrit_branch = "refs/changes/%2.2d/%d/%d" \
                        % (int(change[0]) % 100, int(change[0]), int(change[1]))
                    self.updateSourceProperty("gerrit_branch", gerrit_branch)
            except Exception:
                pass

        branch = gerrit_branch or branch
        super(Gerrit, self).startVC(branch, revision, patch)
