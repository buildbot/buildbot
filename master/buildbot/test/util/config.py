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


from buildbot import config


class _AssertRaisesConfigErrorContext:
    def __init__(self, substr_or_re, case):
        self.substr_or_re = substr_or_re
        self.case = case

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is None:
            self.case.fail("ConfigErrors not raised")

        if not issubclass(exc_type, config.ConfigErrors):
            self.case.fail(f"ConfigErrors not raised, instead got {exc_type.__name__}")

        self.case.assertConfigError(exc_value, self.substr_or_re)
        return True


class ConfigErrorsMixin:

    def assertConfigError(self, errors, substr_or_re):
        if len(errors.errors) > 1:
            self.fail(f"too many errors: {errors.errors}")
        elif not errors.errors:
            self.fail("expected error did not occur")
        else:
            curr_error = errors.errors[0]
            if isinstance(substr_or_re, str):
                if substr_or_re not in curr_error:
                    self.fail(f"non-matching error: {curr_error}, expected: {substr_or_re}")
            else:
                if not substr_or_re.search(curr_error):
                    self.fail(f"non-matching error: {curr_error}")

    def assertRaisesConfigError(self, substr_or_re, fn=None):
        context = _AssertRaisesConfigErrorContext(substr_or_re, self)
        if fn is None:
            return context
        with context:
            fn()
        return None

    def assertNoConfigErrors(self, errors):
        self.assertEqual(errors.errors, [])
