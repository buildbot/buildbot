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
import pkg_resources

import zope.interface.interface
from twisted.trial import unittest
from zope.interface.interface import Attribute


class InterfaceTests:

    # assertions

    def assertArgSpecMatches(self, actualMethod, *fakeMethods):
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
            for ai in range(len(args) - 1, -1, -1):
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
                return func.__wrapped__
            except AttributeError:
                return func

        def filter_argspec(func):
            return filter(
                inspect.getfullargspec(remove_decorators(func)))

        def assert_same_argspec(expected, actual):
            if expected != actual:
                msg = (f"Expected: {inspect.formatargspec(*expected)}; got: "
                       f"{inspect.formatargspec(*actual)}")
                self.fail(msg)

        actual_argspec = filter_argspec(actualMethod)

        for fakeMethod in fakeMethods:
            fake_argspec = filter_argspec(fakeMethod)
            assert_same_argspec(actual_argspec, fake_argspec)

        def assert_same_argspec_decorator(decorated):
            expected_argspec = filter_argspec(decorated)
            assert_same_argspec(expected_argspec, actual_argspec)
            # The decorated function works as usual.
            return decorated
        return assert_same_argspec_decorator

    def assertInterfacesImplemented(self, cls):
        "Given a class, assert that the zope.interface.Interfaces are implemented to specification."

        # see if this version of zope.interface is too old to run these tests
        zi_vers = pkg_resources.working_set.find(
            pkg_resources.Requirement.parse('zope.interface')).version
        if pkg_resources.parse_version(zi_vers) < pkg_resources.parse_version('4.1.1'):
            raise unittest.SkipTest(
                "zope.interfaces is too old to run this test")

        for interface in zope.interface.implementedBy(cls):
            for attr, template_argspec in interface.namesAndDescriptions():
                if not hasattr(cls, attr):
                    msg = (f"Expected: {repr(cls)}; to implement: {attr} as specified in "
                           f"{repr(interface)}")
                    self.fail(msg)
                actual_argspec = getattr(cls, attr)
                if isinstance(template_argspec, Attribute):
                    continue
                # else check method signatures
                while hasattr(actual_argspec, '__wrapped__'):
                    actual_argspec = actual_argspec.__wrapped__
                actual_argspec = zope.interface.interface.fromMethod(
                    actual_argspec)

                if actual_argspec.getSignatureInfo() != template_argspec.getSignatureInfo():
                    msg = (f"{attr}: expected: {template_argspec.getSignatureString()}; got: "
                           f"{actual_argspec.getSignatureString()}")
                    self.fail(msg)
