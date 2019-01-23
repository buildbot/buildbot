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


from twisted.python import log

from buildbot.steps.source.git import Git


class GitLab(Git):
    """
    Source step that knows how to handle merge requests from
    the GitLab change source
    """

    def startVC(self, branch, revision, patch):
        # If this is a merge request:
        if self.build.hasProperty("target_branch"):
            target_repourl = self.build.getProperty("target_git_ssh_url", None)
            if self.repourl != target_repourl:
                log.msg("GitLab.startVC: note: GitLab step for merge requests"
                        " should probably have repourl='%s' instead of '%s'?" %
                        (target_repourl, self.repourl))
            # This step is (probably) configured to fetch the target
            # branch of a merge (because it is impractical for users to
            # configure one builder for each of the infinite number of
            # possible source branches for merge requests).
            # Point instead to the source being proposed for merge.
            branch = self.build.getProperty("source_branch", None)
            # FIXME: layering violation, should not be modifying self here?
            self.repourl = self.build.getProperty("source_git_ssh_url", None)
            # The revision is unlikely to exist in the repo already,
            # so tell Git to not check.
            revision = None

        super(GitLab, self).startVC(branch, revision, patch)
