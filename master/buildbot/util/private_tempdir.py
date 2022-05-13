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

import os
import shutil
import stat
import tempfile


class PrivateTemporaryDirectory:
    """Works similarly to python 3.2+ TemporaryDirectory except the
    also sets the permissions of the created directory and

    Note, that Windows ignores the permissions.
    """

    def __init__(self, suffix=None, prefix=None, dir=None, mode=0o700):
        self.name = tempfile.mkdtemp(suffix, prefix, dir)
        self.mode = mode
        self._cleanup_needed = True

    def __enter__(self):
        return self.name

    def __exit__(self, exc, value, tb):
        self.cleanup()

    def cleanup(self):
        if self._cleanup_needed:

            def remove_readonly(func, path, _):
                """Workaround Permission Error on Windows if any files in path are read-only.

                See https://docs.python.org/3/library/shutil.html#rmtree-example
                """
                os.chmod(path, stat.S_IWRITE)
                func(path)

            shutil.rmtree(self.name, onerror=remove_readonly)
            self._cleanup_needed = False
