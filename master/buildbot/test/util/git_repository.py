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
import os
import shutil
import subprocess
from pathlib import Path


class TestGitRepository:
    def __init__(self, repository_path: os.PathLike, git_bin: os.PathLike | None | str = None):
        if git_bin is None:
            git_bin = shutil.which('git')
            if git_bin is None:
                raise FileNotFoundError('Failed to find git')

        self.git_bin = git_bin

        self.repository_path = Path(repository_path)
        self.repository_path.mkdir(parents=True, exist_ok=True)

        self.curr_date = datetime.datetime(2024, 6, 8, 14, 0, 0, tzinfo=datetime.timezone.utc)
        self.curr_author_name = 'test user'
        self.curr_author_email = 'user@example.com'

        self.exec_git(['init', '--quiet', '--initial-branch=main'])

    def advance_time(self, timedelta):
        self.curr_date += timedelta

    def create_file_text(self, relative_path: str, contents: str):
        path = self.repository_path / relative_path
        path.write_text(contents)
        os.utime(path, (self.curr_date.timestamp(), self.curr_date.timestamp()))

    def amend_file_text(self, relative_path: str, contents: str):
        path = self.repository_path / relative_path
        with path.open('a') as fp:
            fp.write(contents)
        os.utime(path, (self.curr_date.timestamp(), self.curr_date.timestamp()))

    def exec_git(self, args: list[str], env: dict[str, str] | None = None):
        final_env = self.git_author_env(
            author_name=self.curr_author_name, author_mail=self.curr_author_email
        )
        final_env.update(self.git_date_env(self.curr_date))
        if env is not None:
            final_env.update(env)

        subprocess.check_call(
            [str(self.git_bin), *args],
            cwd=self.repository_path,
            env=final_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def commit(
        self,
        message: str,
        files: list[os.PathLike] | None = None,
        env: dict[str, str] | None = None,
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
