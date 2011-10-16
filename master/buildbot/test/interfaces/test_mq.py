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
from twisted.python import log
from twisted.trial import unittest
from buildbot.test.fake import fakemaster, fakemq
from buildbot.test.util import interfaces
from buildbot.mq import simple

class Tests(interfaces.InterfaceTests):

    def setUp(self):
        raise NotImplementedError

    def test_empty_produce(self):
        self.mq.produce('a.b.c', dict(x=1))
        # ..nothing happens

    def test_signature_produce(self):
        @self.assertArgSpecMatches(self.mq.produce)
        def produce(self, routing_key, data):
            pass

    def test_signature_startConsuming(self):
        @self.assertArgSpecMatches(self.mq.startConsuming)
        # note that kwargs is really persistent_name=, but Python2's syntax
        # doesn't allow keyword args and *args to be mixed very well
        def startConsuming(self, callback, *topics, **kwargs):
            pass

    def test_signature_stopConsuming(self):
        cons = self.mq.startConsuming(lambda : None, 'topic')
        @self.assertArgSpecMatches(cons.stopConsuming)
        def stopConsuming(self):
            pass


class RealTests(Tests):

    # tests that only "real" implementations will pass

    def do_test_match(self, routing_key, should_match, *topics):
        log.msg("do_test_match(%r, %r, %r)" % (routing_key, should_match, topics))
        cb = mock.Mock()
        self.mq.startConsuming(cb, *topics)
        self.mq.produce(routing_key, 'x')
        self.assertEqual(should_match, cb.call_count == 1)
        if should_match:
            cb.assert_called_once_with(routing_key, 'x')

    def test_simple_topic_match(self):
        self.do_test_match('abc', True, 'abc')

    def test_simple_topic_no_match(self):
        self.do_test_match('abc', False, 'def')

    def test_multiple_topic_match(self):
        self.do_test_match('b', True, 'a', 'b', 'c')

    def test_dotted_topic_match(self):
        self.do_test_match('a.b.c', True, 'a.b.c')

    def test_dotted_topic_match_topic_prefix(self):
        self.do_test_match('a.b.c', False, 'a.b')

    def test_dotted_topic_match_topic_suffix(self):
        self.do_test_match('a.b.c', False, 'b.c')

    def test_dotted_topic_match_rk_prefix(self):
        self.do_test_match('a.b', False, 'a.b.c')

    def test_dotted_topic_match_rk_suffix(self):
        self.do_test_match('b.c', False, 'a.b.c')

    def test_star_match(self):
        self.do_test_match('a.b.c', True, 'a.*.c')

    def test_star_match_empty(self):
        self.do_test_match('a..c', False, 'a.*.c')

    def test_star_match_missing(self):
        self.do_test_match('a.c', False, 'a.*.c')

    def test_star_no_match(self):
        self.do_test_match('a.x.b', False, 'a.*.c')

    def test_star_no_match_two_words(self):
        self.do_test_match('a.x.y.c', False, 'a.*.c')

    def test_star_match_start(self):
        self.do_test_match('x.c', True, '*.c')

    def test_star_no_match_start(self):
        self.do_test_match('w.x.c', False, '*.c')

    def test_star_match_end(self):
        self.do_test_match('c.x', True, 'c.*')

    def test_star_no_match_end(self):
        self.do_test_match('c.x.y', False, 'c.*')

    def test_star_match_alone(self):
        self.do_test_match('x', True, '*')

    def test_star_no_match_alone(self):
        self.do_test_match('x.y', False, '*')

    def test_regexp_special_char_plus(self):
        self.do_test_match('xxxx', False, 'x+')

    def test_regexp_special_char_star(self):
        self.do_test_match('xxxx', False, 'x*')

    def test_regexp_special_char_question(self):
        self.do_test_match('xy.b', False, 'xyz?.b')

    def test_regexp_special_char_backslash(self):
        self.do_test_match('a\\xb', False, 'a\\.b')

    def test_regexp_special_char_brackets(self):
        self.do_test_match('a.b.c', False, 'a.[abcd].c')

    def test_regexp_special_char_braces(self):
        self.do_test_match('xxx.c', False, 'x{3}.c')

    def test_regexp_special_char_bar(self):
        self.do_test_match('xy', False, 'xy|ab')

    def test_regexp_special_char_parens(self):
        self.do_test_match('a.b.c', False, 'a.(b).c')

    def test_octothope_middle_zero(self):
        self.do_test_match('a.c', True, 'a.#.c')

    def test_octothope_middle_one(self):
        self.do_test_match('a.b.c', True, 'a.#.c')

    def test_octothope_middle_two(self):
        self.do_test_match('a.b.b.c', True, 'a.#.c')

    def test_octothope_middle_unanchored(self):
        self.do_test_match('d.a.b.b.c.d', False, 'a.#.c')

    def test_octothope_end_zero(self):
        self.do_test_match('a.b', True, 'a.b.#')

    def test_octothope_end_one(self):
        self.do_test_match('a.b.c', True, 'a.b.#')

    def test_octothope_end_two(self):
        self.do_test_match('a.b.c.d', True, 'a.b.#')

    def test_octothope_end_unanchored(self):
        self.do_test_match('d.a.b.c.d', False, 'a.b.#')

    def test_octothope_only_zero(self):
        self.do_test_match('', False, '#')

    def test_octothope_only_one(self):
        self.do_test_match('a', True, '#')

    def test_octothope_only_two(self):
        self.do_test_match('a.b', True, '#')

    def test_double_octothope(self):
        self.do_test_match('a.b.b.b.b.c.d', False, 'a.#.#.c')

    def test_star_octothope(self):
        self.do_test_match('a.b.b.b.b.c', True, 'a.*.#.c')

    def test_star_octothope_zero_matches(self):
        self.do_test_match('a.c', False, 'a.*.#.c')

    def test_star_octothope_separated(self):
        self.do_test_match('a.b.b.b.b.b.c', True, 'a.*.b.#.c')

    def test_octothope_star_separated(self):
        self.do_test_match('a.b.b.b.b.b.c', True, 'a.#.b.*.c')

    def test_stopConsuming(self):
        cb = mock.Mock()
        qref = self.mq.startConsuming(cb, 'abc')
        self.mq.produce('abc', dict(x=1))
        qref.stopConsuming()
        self.mq.produce('abc', dict(x=1))
        cb.assert_called_once_with('abc', dict(x=1))

    def test_stopConsuming_twice(self):
        cb = mock.Mock()
        qref = self.mq.startConsuming(cb, 'abc')
        qref.stopConsuming()
        qref.stopConsuming()
        # ..nothing bad happens

    def test_non_persistent(self):
        cb = mock.Mock()
        qref = self.mq.startConsuming(cb, 'abc')

        cb2 = mock.Mock()
        qref2 = self.mq.startConsuming(cb2, 'abc')

        qref.stopConsuming()
        self.mq.produce('abc', '{}')

        qref = self.mq.startConsuming(cb, 'abc')
        qref.stopConsuming()
        qref2.stopConsuming()

        self.assertTrue(cb2.called)
        self.assertFalse(cb.called)

    def test_persistent(self):
        cb = mock.Mock()

        qref = self.mq.startConsuming(cb, 'abc', persistent_name='ABC')
        qref.stopConsuming()

        self.mq.produce('abc', '{}')

        qref = self.mq.startConsuming(cb, 'abc', persistent_name='ABC')
        qref.stopConsuming()

        self.assertTrue(cb.called)


class TestFakeMQ(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.mq = fakemq.FakeMQConnector(self.master)

class TestSimpleMQ(unittest.TestCase, RealTests):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.mq = simple.SimpleMQ(self.master)
