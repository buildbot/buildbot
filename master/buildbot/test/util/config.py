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

from __future__ import absolute_import
from __future__ import print_function

from buildbot import config


class ConfigErrorsMixin(object):

    def assertConfigError(self, errors, substr_or_re):
        if len(errors.errors) > 1:
            self.fail("too many errors: %s" % (errors.errors,))
        elif len(errors.errors) < 1:
            self.fail("expected error did not occur")
        else:
            curr_error = errors.errors[0]
            if isinstance(substr_or_re, str):
                if substr_or_re not in curr_error:
                    self.fail("non-matching error: %s, "
                              "expected: %s" % (curr_error, substr_or_re))
            else:
                if not substr_or_re.search(curr_error):
                    self.fail("non-matching error: %s" % (curr_error,))

    def assertRaisesConfigError(self, substr_or_re, fn):
        try:
            fn()
        except config.ConfigErrors as e:
            self.assertConfigError(e, substr_or_re)
        else:
            self.fail("ConfigErrors not raised")

    def assertNoConfigErrors(self, errors):
        self.assertEqual(errors.errors, [])
