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

import inspect

class InterfaceTests(object):

    # assertions

    def assertArgSpecMatches(self, actual):
        def wrap(template):
            actual_argspec = inspect.getargspec(actual)
            template_argspec = inspect.getargspec(template)
            if actual_argspec != template_argspec:
                msg = "Expected: %s; got: %s" % (
                    inspect.formatargspec(*template_argspec),
                    inspect.formatargspec(*actual_argspec))
                self.fail(msg)
            return template  # just in case it's useful
        return wrap
