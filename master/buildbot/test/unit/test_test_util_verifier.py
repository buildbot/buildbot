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

from twisted.trial import unittest
from buildbot.test.util import verifier

class VerifyDict(unittest.TestCase):

    attrs=dict(
        testid='integer',
        somestring='string',
        string_or_none='string:none',
    )

    def test_matches(self):
        verifier.verifyDict(self,
            { 'testid' : 13,
              'somestring' : u'hi',
              'string_or_none' : u'there' }, 'thing', self.attrs)

    def test_matches_none(self):
        verifier.verifyDict(self,
            { 'testid' : 13,
              'somestring' : u'hi',
              'string_or_none' : None }, 'thing', self.attrs)

    def test_nonmatching_extra_key(self):
        self.assertRaises(AssertionError, lambda :
            verifier.verifyDict(self,
                { 'testid' : 13,
                'somestring' : u'hi',
                'string_or_none' : None,
                'extra' : u'key'}, 'thing', self.attrs))

    def test_nonmatching_missing_key(self):
        self.assertRaises(AssertionError, lambda :
            verifier.verifyDict(self,
                { 'testid' : 13,
                'string_or_none' : u'world' }, 'thing', self.attrs))

    def test_nonmatching_wrong_type(self):
        self.assertRaises(AssertionError, lambda :
            verifier.verifyDict(self,
                { 'testid' : u'unexpected_string',
                'somestring' : u'hi',
                'string_or_none' : None }, 'thing', self.attrs))

    def do_test_type(self, type, matching, nonmatching):
        for v in matching:
            verifier.verifyDict(self, dict(x=v),
                type+'-test', dict(x=type))
        for v in nonmatching:
            self.assertRaises(AssertionError, lambda :
                verifier.verifyDict(self, dict(x=v),
                    type+'-test', dict(x=type)))

    def test_integer(self):
        self.do_test_type('integer', matching=[10],
                nonmatching=['10', (1,), None])

    def test_string(self):
        self.do_test_type('string', matching=[u'a'],
                nonmatching=[10, None, 'non-unicode', [1]])

    def test_stringlist(self):
        self.do_test_type('stringlist', matching=[[], [u'a', u'b']],
                nonmatching=[10, [1], (u'a', u'b'), None, ['non-unicode']])

    def test_sourcedProperties(self):
        self.do_test_type('sourcedProperties',
            matching=[ {}, {u'prop' : ([['v'],'alue'], u'src')} ],
            nonmatching=[
                'prop', 10, [ 'prop' ], None,
                {u'prop' : [['v'],'alue']},
                {u'prop' : (u'src', [['v'],'alue'])},
                {u'prop' : ([['v'],'alue'], 'src-not-unicode')},
                {u'prop' : (['nonjson', lambda x : None], u'src')},
                {'prop-not-unicode' : ([['v'],'alue'], u'src')},
            ])

class VerifyMessage(unittest.TestCase):

    def test_success(self):
        verifier.verifyMessage(self, ( 'foo', '10', 'explode' ),
            dict(fooid=10), 'foo', ('fooid',), set(['explode']),
            dict(fooid='integer'))

    def test_attrs_failure(self):
        # note that most attrs failures are tested sufficiently above
        self.assertRaises(AssertionError, lambda :
            verifier.verifyMessage(self, ( 'foo', 'explode' ), dict(),
                'foo', (), set(['explode']), dict(fooid='integer')))

    def test_short_routingKey(self):
        self.assertRaises(AssertionError, lambda :
            verifier.verifyMessage(self, ( 'foo', ), dict(),
                'foo', (), set(['explode']), dict()))

    def test_unkown_event(self):
        self.assertRaises(AssertionError, lambda :
            verifier.verifyMessage(self, ( 'foo', 'fizzles' ), dict(),
                'foo', (), set(['explode']), dict()))

    def test_wrong_type(self):
        self.assertRaises(AssertionError, lambda :
            verifier.verifyMessage(self, ( 'bar', 'explode' ), dict(),
                'foo', (), set(['explode']), dict()))

    def test_keyFields_no_such_field(self):
        self.assertRaises(AssertionError, lambda :
            verifier.verifyMessage(self, ( 'foo', '10', 'explode' ), dict(),
                'foo', ('fooid',), set(['explode']), dict()))

    def test_keyFields_mismatch(self):
        self.assertRaises(AssertionError, lambda :
            verifier.verifyMessage(self, ( 'foo', '11', 'explode' ),
                dict(fooid=10), 'foo', ('fooid',), set(['explode']),
                dict(fooid='integer')))

