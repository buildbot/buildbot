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

from twisted.internet import defer
from twisted.trial.unittest import SynchronousTestCase

from buildbot.test.util.patch_delay import patchForDelay


class TestException(Exception):
    pass


def fun_to_patch(*args, **kwargs):
    return defer.succeed((args, kwargs))


def fun_to_patch_exception():
    raise TestException()


non_callable = 1


class Tests(SynchronousTestCase):

    def test_raises_not_found(self):
        with self.assertRaises(Exception):
            with patchForDelay(__name__ + '.notfound'):
                pass

    def test_raises_not_callable(self):
        with self.assertRaises(Exception):
            with patchForDelay(__name__ + '.non_callable'):
                pass

    def test_patches_within_context(self):
        d = fun_to_patch()
        self.assertTrue(d.called)

        with patchForDelay(__name__ + '.fun_to_patch') as delay:
            d = fun_to_patch()
            self.assertEqual(len(delay), 1)
            self.assertFalse(d.called)
            delay.fire()
            self.assertEqual(len(delay), 0)
            self.assertTrue(d.called)

        d = fun_to_patch()
        self.assertTrue(d.called)

    def test_auto_fires_unfired_delay(self):
        with patchForDelay(__name__ + '.fun_to_patch') as delay:
            d = fun_to_patch()
            self.assertEqual(len(delay), 1)
            self.assertFalse(d.called)
        self.assertTrue(d.called)

    def test_auto_fires_unfired_delay_exception(self):
        try:
            with patchForDelay(__name__ + '.fun_to_patch') as delay:
                d = fun_to_patch()
                self.assertEqual(len(delay), 1)
                self.assertFalse(d.called)
                raise TestException()
        except TestException:
            pass
        self.assertTrue(d.called)

    def test_passes_arguments(self):
        with patchForDelay(__name__ + '.fun_to_patch') as delay:
            d = fun_to_patch('arg', kw='kwarg')
            self.assertEqual(len(delay), 1)
            delay.fire()
            args = self.successResultOf(d)

        self.assertEqual(args, (('arg',), {'kw': 'kwarg'}))

    def test_passes_exception(self):
        with patchForDelay(__name__ + '.fun_to_patch_exception') as delay:
            d = fun_to_patch_exception()
            self.assertEqual(len(delay), 1)
            delay.fire()
            f = self.failureResultOf(d)
            f.check(TestException)
