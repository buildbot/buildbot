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
from buildbot.test.util import resourcetype

class ResourceTypeVerifier(unittest.TestCase):

    verifier = None
    def setUp(self):
        # just set this up once..
        if not self.verifier:
            verifier = resourcetype.ResourceTypeVerifier(
                    'testtype',
                    attrs=dict(testid='integer', somestring='string',
                        string_or_none='string:none'))
            self.__class__.verifier = verifier

    def test_matches(self):
        self.verifier(self,
            { 'testid' : 13,
              'somestring' : u'hi',
              'string_or_none' : u'there' })

    def test_matches_none(self):
        self.verifier(self,
            { 'testid' : 13,
              'somestring' : u'hi',
              'string_or_none' : None })

    def test_nonmatching_extra_key(self):
        self.assertRaises(AssertionError, lambda :
            self.verifier(self,
                { 'testid' : 13,
                'somestring' : u'hi',
                'string_or_none' : None,
                'extra' : u'key'}))

    def test_nonmatching_missing_key(self):
        self.assertRaises(AssertionError, lambda :
            self.verifier(self,
                { 'testid' : 13,
                'string_or_none' : u'world' }))

    def test_nonmatching_wrong_type(self):
        self.assertRaises(AssertionError, lambda :
            self.verifier(self,
                { 'testid' : u'unexpected_string',
                'somestring' : u'hi',
                'string_or_none' : None }))

    def do_test_type(self, type, matching, nonmatching):
        verif = resourcetype.ResourceTypeVerifier(type + '-test',
                attrs=dict(x=type))
        for v in matching:
            verif(self, dict(x=v))
        for v in nonmatching:
            self.assertRaises(AssertionError, verif, self, dict(x=v))

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
