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

class TopicMatchingMixin(object):

    # a bunch of topic-matching tests that all call do_test_match
    # this is used to test this behavior in a few places

    def do_test_match(self, routingKey, shouldMatch, *topics):
        raise NotImplementedError

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

