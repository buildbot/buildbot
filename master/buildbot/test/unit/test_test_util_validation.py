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

import datetime
import locale

from twisted.python import log
from twisted.trial import unittest

from buildbot.test.util import validation
from buildbot.util import UTC


class VerifyDict(unittest.TestCase):

    def doValidationTest(self, validator, good, bad):
        for g in good:
            log.msg(f'expect {repr(g)} to be good')
            msgs = list(validator.validate('g', g))
            self.assertEqual(msgs, [], f'messages for {repr(g)}')
        for b in bad:
            log.msg(f'expect {repr(b)} to be bad')
            msgs = list(validator.validate('b', b))
            self.assertNotEqual(msgs, [], f'no messages for {repr(b)}')
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
                                  "unicode only"
        ], bad=[
                                  None, b"bytestring"
        ])

    def test_BinaryValidator(self):
        self.doValidationTest(validation.BinaryValidator(),
                              good=[
                                  b"bytestring"
        ], bad=[
                                  None, "no unicode"
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
            '\N{SNOWMAN}'.encode(os_encoding)
        except UnicodeEncodeError as e:
            # Default encoding of Windows console is 'cp1252'
            # which cannot encode the snowman.
            raise unittest.SkipTest("Cannot encode weird unicode "
                f"on this platform with {os_encoding}") from e

        self.doValidationTest(validation.IdentifierValidator(50),
                              good=[
                                  "linux", "Linux", "abc123", "a" * 50, '\N{SNOWMAN}'
        ], bad=[
                                  None, '', b'linux', 'a/b', "a.b.c.d",
                                  "a-b_c.d9", 'spaces not allowed', "a" * 51,
                                  "123 no initial digits",
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
                {'a': True, 'b': 'xyz'},
        ],
            bad=[
                None, 1, "hi",
                {},
                {'a': 1},
                {'a': 1, 'b': 'xyz'},
                {'a': True, 'b': 999},
                {'a': True, 'b': 'xyz', 'c': 'extra'},
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
                                  {'pname': ('{"a":"b"}', 'test')},
        ], bad=[
                                  None, 1, b"hi",
                                  {'pname': {b'a': b'b'}},  # no source
                                  # name not unicode
                                  {'pname': ({b'a': b'b'}, 'test')},
                                  # source not unicode
                                  {'pname': ({b'a': b'b'}, 'test')},
                                  # self is not json-able
                                  {'pname': (self, 'test')},
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
                                  ('str', 'hi'),
                              ], bad=[
                                  ('int', 'hi'),
                                  ('str', 1),
                                  ('float', 1.0),
                              ])
