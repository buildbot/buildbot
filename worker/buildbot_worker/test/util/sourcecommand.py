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

from typing import TYPE_CHECKING

from twisted.trial.unittest import TestCase

from buildbot_worker.test.util import command

if TYPE_CHECKING:
    from typing import Any
    from typing import TypeVar

    _T = TypeVar('_T')


# TODO: Remove unused?
class SourceCommandTestMixin(command.CommandTestMixin):
    """
    Support for testing Source Commands; an extension of CommandTestMixin
    """

    def make_command(
        self,
        cmdclass: type[command.CommandType],
        args: dict[str, Any],
        makedirs: bool = False,
        initial_sourcedata: str = '',
    ) -> command.CommandType:
        """
        Same as the parent class method, but this also adds some source-specific
        patches:

        * writeSourcedata - writes to self.sourcedata (self is the TestCase)
        * readSourcedata - reads from self.sourcedata
        * doClobber - invokes RunProcess(0, ['clobber', DIRECTORY])
        * doCopy - invokes RunProcess(0, ['copy', cmd.srcdir, cmd.workdir])
        """

        cmd = super().make_command(cmdclass, args, makedirs)

        # note that these patches are to an *instance*, not a class, so there
        # is no need to use self.patch() to reverse them

        self.sourcedata = initial_sourcedata

        def readSourcedata() -> str:
            if self.sourcedata is None:
                raise OSError("File not found")
            return self.sourcedata

        cmd.readSourcedata = readSourcedata  # type: ignore[attr-defined]

        def writeSourcedata(res: _T) -> _T:
            self.sourcedata = cmd.sourcedata  # type: ignore[attr-defined]
            return res

        cmd.writeSourcedata = writeSourcedata  # type: ignore[attr-defined]

        return cmd

    def check_sourcedata(self, _: _T, expected_sourcedata: None) -> _T:
        """
        Assert that the sourcedata (from the patched functions - see
        make_command) is correct.  Use this as a deferred callback.
        """
        assert isinstance(self, TestCase)
        self.assertEqual(self.sourcedata, expected_sourcedata)
        return _
