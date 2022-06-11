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


import json

from twisted.internet import defer

from buildbot import config
from buildbot.process import buildstep
from buildbot.process import logobserver
from buildbot.process import results


class GitDiffInfo(buildstep.ShellMixin, buildstep.BuildStep):
    name = 'GitDiffInfo'
    description = 'running GitDiffInfo'
    descriptionDone = 'GitDiffInfo'

    def __init__(self, compareToRef='master', dataName='diffinfo-master', **kwargs):
        try:
            from unidiff import PatchSet
            [PatchSet]  # silence pylint
        except ImportError:
            config.error('unidiff package must be installed in order to use GitDiffInfo')

        kwargs = self.setupShellMixin(kwargs, prohibitArgs=['command'])
        super().__init__(**kwargs)
        self._compare_to_ref = compareToRef
        self._data_name = dataName
        self._observer = logobserver.BufferLogObserver()

    def _convert_hunk(self, hunk):
        # TODO: build an intermediate class that would handle serialization. We want to output
        # as few data as possible, even if the json is not human-readable
        return {
            'ss': hunk.source_start,
            'sl': hunk.source_length,
            'ts': hunk.target_start,
            'tl': hunk.target_length,
        }

    def _convert_file(self, file):
        return {
            'source_file': file.source_file,
            'target_file': file.target_file,
            'is_binary': file.is_binary_file,
            'is_rename': file.is_rename,
            'hunks': [self._convert_hunk(hunk) for hunk in file]
        }

    def _convert_patchset(self, patchset):
        return [self._convert_file(file) for file in patchset]

    @defer.inlineCallbacks
    def run(self):
        command = ['git', 'merge-base', 'HEAD', self._compare_to_ref]
        cmd = yield self.makeRemoteShellCommand(command=command, stdioLogName='stdio-merge-base',
                                                collectStdout=True)

        yield self.runCommand(cmd)
        log = yield self.getLog("stdio-merge-base")
        yield log.finish()

        if cmd.results() != results.SUCCESS:
            return cmd.results()

        commit = cmd.stdout.strip()
        self.setProperty('diffinfo-merge-base-commit', commit, 'GitDiffInfo')

        self.addLogObserver('stdio-diff', self._observer)

        command = ['git', 'diff', '--no-prefix', '-U0', commit, 'HEAD']
        cmd = yield self.makeRemoteShellCommand(command=command, stdioLogName='stdio-diff')

        yield self.runCommand(cmd)

        if cmd.results() != results.SUCCESS:
            return cmd.results()

        from unidiff import PatchSet
        patchset = PatchSet(self._observer.getStdout(), metadata_only=True)

        data = json.dumps(self._convert_patchset(patchset)).encode('utf-8')
        yield self.setBuildData(self._data_name, data, 'GitDiffInfo')

        return cmd.results()
