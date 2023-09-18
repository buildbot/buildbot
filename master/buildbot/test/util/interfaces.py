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
from collections import OrderedDict

import zope.interface.interface
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
        def filter(signature):
            if len(signature.parameters) == 0:
                return signature

            parameters = OrderedDict(signature.parameters)
            for name in parameters:
                if name == 'self':
                    parameters.pop('self')
                break

            delete_names = []
            for name in parameters:
                if name.startswith('_'):
                    delete_names.append(name)
            for name in delete_names:
                parameters.pop(name)

            signature = signature.replace(parameters=parameters.values())
            return signature

        def remove_decorators(func):
            try:
                return func.__wrapped__
            except AttributeError:
                return func

        def filter_argspec(func):
            return filter(
                inspect.signature(remove_decorators(func)))

        def assert_same_argspec(expected, actual):
            if expected != actual:
                msg = f"Expected: {expected}; got: {actual}"
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
