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

import mock


def patch():
    # mock doesn't ordinarily have this method, but we keep calling it by
    # mistake.  It unhelpfully returns without error, regardless of whether
    # the mock has been called!
    mock.Mock.assert_not_called = lambda self: self.assert_has_calls([])

    # similarly, let's make every other 'assert_' method on a mock
    # automatically fail.
    orig = mock.NonCallableMock.__getattr__

    def new__getattr__(self, name):
        if name.startswith('assert_'):
            raise AttributeError(name)
        return orig(self, name)
    mock.NonCallableMock.__getattr__ = new__getattr__
