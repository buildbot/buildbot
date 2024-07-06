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

from __future__ import annotations

import datetime
import shutil
import subprocess
from os import PathLike
from pathlib import Path


class TestGitRepository:
    def __init__(self, repository_path: PathLike, git_bin: PathLike | None = None):
        if git_bin is None:
            git_bin = shutil.which('git')
            if git_bin is None:
                raise FileNotFoundError('Failed to find git')

        self.git_bin = git_bin

        self.repository_path = Path(repository_path)
        self.repository_path.mkdir(parents=True, exist_ok=True)

        self.exec_git(['init', '--quiet', '--initial-branch=main'])

    def exec_git(self, args: list[str], env: dict[str] | None = None):
        subprocess.check_call(
            [str(self.git_bin), *args],
            cwd=self.repository_path,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def commit(
        self,
        message: str,
        files: list[PathLike] | None = None,
        env: dict[str] | None = None,
    ) -> str:
        args = ['commit', '--quiet', f'--message={message}']
        if files is not None:
            args.extend(str(f) for f in files)

        self.exec_git(args, env=env)

        return subprocess.check_output(
            [str(self.git_bin), 'rev-parse', 'HEAD'],
            cwd=self.repository_path,
            text=True,
        ).strip()

    @staticmethod
    def git_author_env(author_name: str, author_mail: str):
        return {
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": author_mail,
            "GIT_COMMITTER_NAME": author_name,
            "GIT_COMMITTER_EMAIL": author_mail,
        }

    @staticmethod
    def git_date_env(date: datetime.datetime):
        def _format_date(_d: datetime.datetime) -> str:
            # just in case, make sure we use UTC
            return _d.astimezone(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S +0000")

        return {
            "GIT_AUTHOR_DATE": _format_date(date),
            "GIT_COMMITTER_DATE": _format_date(date),
        }
