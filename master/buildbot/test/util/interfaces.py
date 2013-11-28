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
        def filter(spec):
            # the tricky thing here is to align args and defaults, since the
            # defaults correspond to the *last* n elements of args.  To make
            # things easier, we go in reverse, and keep a separate counter for
            # the defaults
            args = spec[0]
            defaults = list(spec[3] or [])
            di = -1
            for ai in xrange(len(args) - 1, -1, -1):
                arg = args[ai]
                if arg.startswith('_') or (arg == 'self' and ai == 0):
                    del args[ai]
                    if -di <= len(defaults):
                        del defaults[di]
                di -= 1

            return (args, spec[1], spec[2], defaults or None)

        def remove_decorators(func):
            try:
                return func.func_original
            except AttributeError:
                return func

        def wrap(template):
            actual_argspec = filter(
                inspect.getargspec(remove_decorators(actual)))
            template_argspec = filter(
                inspect.getargspec(remove_decorators(template)))
            if actual_argspec != template_argspec:
                msg = "Expected: %s; got: %s" % (
                    inspect.formatargspec(*template_argspec),
                    inspect.formatargspec(*actual_argspec))
                self.fail(msg)
            return template  # just in case it's useful
        return wrap
