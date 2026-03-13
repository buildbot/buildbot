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

import os
import shutil
import stat
import sys
import tempfile
from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from types import TracebackType


class PrivateTemporaryDirectory:
    """Works similarly to python 3.2+ TemporaryDirectory except the
    also sets the permissions of the created directory and

    Note, that Windows ignores the permissions.
    """

    def __init__(
        self,
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
        mode: int = 0o700,
    ) -> None:
        self.name = tempfile.mkdtemp(suffix, prefix, dir)
        self.mode = mode
        self._cleanup_needed = True

    def __enter__(self) -> str:
        return self.name

    def __exit__(
        self,
        exc: type[BaseException] | None,
        value: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        if self._cleanup_needed:

            def remove_readonly(func: Any, path: Any, _: Any) -> None:
                """Workaround Permission Error on Windows if any files in path are read-only.

                See https://docs.python.org/3/library/shutil.html#rmtree-example
                """
                os.chmod(path, stat.S_IWRITE)
                func(path)

            if sys.version_info >= (3, 12):
                shutil.rmtree(self.name, onexc=remove_readonly)
            else:
                shutil.rmtree(self.name, onerror=remove_readonly)
            self._cleanup_needed = False
