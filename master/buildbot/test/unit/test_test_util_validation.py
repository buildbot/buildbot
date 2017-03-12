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

import datetime
import locale

from twisted.python import log
from twisted.trial import unittest

from buildbot.test.util import validation
from buildbot.util import UTC


class VerifyDict(unittest.TestCase):

    def doValidationTest(self, validator, good, bad):
        for g in good:
            log.msg('expect %r to be good' % (g,))
            msgs = list(validator.validate('g', g))
            self.assertEqual(msgs, [], 'messages for %r' % (g,))
        for b in bad:
            log.msg('expect %r to be bad' % (b,))
            msgs = list(validator.validate('b', b))
            self.assertNotEqual(msgs, [], 'no messages for %r' % (b,))
            log.msg('..got messages:')
            for msg in msgs:
                log.msg("  " + msg)

    def test_IntValidator(self):
        self.doValidationTest(validation.IntValidator(),
                              good=[
                                  1, 10 ** 100
        ], bad=[
                                  1.0, "one", "1", None
        ])

    def test_BooleanValidator(self):
        self.doValidationTest(validation.BooleanValidator(),
                              good=[
                                  True, False
        ], bad=[
                                  "yes", "no", 1, 0, None
        ])

    def test_StringValidator(self):
        self.doValidationTest(validation.StringValidator(),
                              good=[
                                  u"unicode only"
        ], bad=[
                                  None, b"bytestring"
        ])

    def test_BinaryValidator(self):
        self.doValidationTest(validation.BinaryValidator(),
                              good=[
                                  b"bytestring"
        ], bad=[
                                  None, u"no unicode"
        ])

    def test_DateTimeValidator(self):
        self.doValidationTest(validation.DateTimeValidator(),
                              good=[
                                  datetime.datetime(
                                      1980, 6, 15, 12, 31, 15, tzinfo=UTC),
        ], bad=[
                                  None, 198847493,
                                  # no timezone
                                  datetime.datetime(1980, 6, 15, 12, 31, 15),
        ])

    def test_IdentifierValidator(self):
        os_encoding = locale.getpreferredencoding()
        try:
            u'\N{SNOWMAN}'.encode(os_encoding)
        except UnicodeEncodeError:
            # Default encoding of Windows console is 'cp1252'
            # which cannot encode the snowman.
            raise(unittest.SkipTest("Cannot encode weird unicode "
                "on this platform with {}".format(os_encoding)))

        self.doValidationTest(validation.IdentifierValidator(50),
                              good=[
                                  u"linux", u"Linux", u"abc123", u"a" * 50,
        ], bad=[
                                  None, u'', b'linux', u'a/b', u'\N{SNOWMAN}', u"a.b.c.d",
                                  u"a-b_c.d9", 'spaces not allowed', u"a" * 51,
                                  u"123 no initial digits",
        ])

    def test_NoneOk(self):
        self.doValidationTest(
            validation.NoneOk(validation.BooleanValidator()),
            good=[
                True, False, None
            ], bad=[
                1, "yes"
            ])

    def test_DictValidator(self):
        self.doValidationTest(validation.DictValidator(
            a=validation.BooleanValidator(),
            b=validation.StringValidator(),
            optionalNames=['b']),
            good=[
                {'a': True},
                {'a': True, 'b': u'xyz'},
        ],
            bad=[
                None, 1, "hi",
                {},
                {'a': 1},
                {'a': 1, 'b': u'xyz'},
                {'a': True, 'b': 999},
                {'a': True, 'b': u'xyz', 'c': 'extra'},
        ])

    def test_DictValidator_names(self):
        v = validation.DictValidator(
            a=validation.BooleanValidator())
        self.assertEqual(list(v.validate('v', {'a': 1})), [
            "v['a'] (1) is not a boolean"
        ])

    def test_ListValidator(self):
        self.doValidationTest(
            validation.ListValidator(validation.BooleanValidator()),
            good=[
                [],
                [True],
                [False, True],
            ], bad=[
                None,
                ['a'],
                [True, 'a'],
                1, "hi"
            ])

    def test_ListValidator_names(self):
        v = validation.ListValidator(validation.BooleanValidator())
        self.assertEqual(list(v.validate('v', ['a'])), [
            "v[0] ('a') is not a boolean"
        ])

    def test_SourcedPropertiesValidator(self):
        self.doValidationTest(validation.SourcedPropertiesValidator(),
                              good=[
                                  {u'pname': ('{"a":"b"}', u'test')},
        ], bad=[
                                  None, 1, b"hi",
                                  {u'pname': {b'a': b'b'}},  # no source
                                  # name not unicode
                                  {'pname': ({b'a': b'b'}, u'test')},
                                  # source not unicode
                                  {u'pname': ({b'a': b'b'}, 'test')},
                                  # self is not json-able
                                  {u'pname': (self, u'test')},
        ])

    def test_MessageValidator(self):
        self.doValidationTest(validation.MessageValidator(
            events=[b'started', b'stopped'],
            messageValidator=validation.DictValidator(
                a=validation.BooleanValidator(),
                xid=validation.IntValidator(),
                yid=validation.IntValidator())),
            good=[
                (('thing', '1', '2', 'started'),
                 {'xid': 1, 'yid': 2, 'a': True}),
        ], bad=[
                # routingKey is not a tuple
                ('thing', {}),
                # routingKey has wrong event
                (('thing', '1', '2', 'exploded'),
                 {'xid': 1, 'yid': 2, 'a': True}),
                # routingKey element has wrong type
                (('thing', 1, 2, 'started'),
                 {'xid': 1, 'yid': 2, 'a': True}),
                # routingKey element isn't in message
                (('thing', '1', '2', 'started'),
                 {'xid': 1, 'a': True}),
                # message doesn't validate
                (('thing', '1', '2', 'started'),
                 {'xid': 1, 'yid': 2, 'a': 'x'}),
        ])

    def test_Selector(self):
        sel = validation.Selector()
        sel.add(lambda x: x == 'int', validation.IntValidator())
        sel.add(lambda x: x == 'str', validation.StringValidator())
        self.doValidationTest(sel,
                              good=[
                                  ('int', 1),
                                  ('str', u'hi'),
                              ], bad=[
                                  ('int', u'hi'),
                                  ('str', 1),
                                  ('float', 1.0),
                              ])
