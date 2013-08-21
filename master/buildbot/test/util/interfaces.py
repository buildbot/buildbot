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

    def assertArgSpecMatches(self, *actualMethods):
        """Usage::

            @self.assertArgSpecMatches(obj.methodUnderTest)
            def methodTemplate(self, arg1, arg2):
                pass

        or, more useful when you will be faking out C{methodUnderTest}:

            self.assertArgSpecMatches(obj.methodUnderTest, self.fakeMethod)
        """
        def filter(spec):
            # the tricky thing here is to align args and defaults, since the
            # defaults correspond to the *last* n elements of args.  To make
            # things easier, we go in reverse, and keep a separate counter for
            # the defaults
            args = spec[0]
            defaults = list(spec[3] if spec[3] is not None else [])
            di = -1
            for ai in xrange(len(args)-1, -1, -1):
                arg = args[ai]
                if arg.startswith('_') or (arg == 'self' and ai == 0):
                    del args[ai]
                    if -di <= len(defaults):
                        del defaults[di]
                        di += 1
                di -= 1

            return (args, spec[1], spec[2], defaults or None)

        def remove_decorators(func):
            try:
                return func.func_original
            except AttributeError:
                return func

        def wrap(template):
            for actual in actualMethods:
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

    def assertInterfacesImplemented(self, cls):
        "Given a class, assert that the zope.interface.Interfaces are implemented to specification."
        import zope.interface.interface
        for interface in zope.interface.implementedBy(cls):
            for attr, template_argspec in interface.namesAndDescriptions():
                actual_argspec = getattr(cls, attr)
                actual_argspec = zope.interface.interface.fromMethod(actual_argspec)

                if actual_argspec.getSignatureInfo() != template_argspec.getSignatureInfo():
                    msg = "Expected: %s; got: %s" % (
                        template_argspec.getSignatureString(),
                        actual_argspec.getSignatureString())
                    self.fail(msg)
