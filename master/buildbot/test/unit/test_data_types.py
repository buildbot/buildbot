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

from buildbot.data import types


class TypeMixin:

    klass = None
    good = []
    bad = []
    stringValues = []
    badStringValues = []
    cmpResults = []

    def setUp(self):
        self.ty = self.makeInstance()

    def makeInstance(self):
        return self.klass()

    def test_valueFromString(self):
        for string, expValue in self.stringValues:
            self.assertEqual(self.ty.valueFromString(string), expValue,
                             "value of string %r" % (string,))
        for string in self.badStringValues:
            with self.assertRaises(Exception):
                self.ty.valueFromString(string,
                              "expected error for %r" % (string,))

    def test_cmp(self):
        for val, string, expResult in self.cmpResults:
            self.assertEqual(self.ty.cmp(val, string), expResult,
                             "compare of %r and %r" % (val, string))

    def test_validate(self):
        for o in self.good:
            errors = list(self.ty.validate(repr(o), o))
            self.assertEqual(errors, [], "%s -> %s" % (repr(o), errors))
        for o in self.bad:
            errors = list(self.ty.validate(repr(o), o))
            self.assertNotEqual(errors, [], "no error for %s" % (repr(o),))


class NoneOk(TypeMixin, unittest.TestCase):

    def makeInstance(self):
        return types.NoneOk(types.Integer())

    good = [None, 1]
    bad = ['abc']
    stringValues = [('0', 0), ('-10', -10)]
    badStringValues = ['one', '', '0x10']
    cmpResults = [(10, '9', 1), (-2, '-1', -1)]


class Integer(TypeMixin, unittest.TestCase):

    klass = types.Integer
    good = [0, -1, 1000, 100 ** 100]
    bad = [None, '', '0']
    stringValues = [('0', 0), ('-10', -10)]
    badStringValues = ['one', '', '0x10']
    cmpResults = [(10, '9', 1), (-2, '-1', -1)]


class String(TypeMixin, unittest.TestCase):

    klass = types.String
    good = ['', 'hello', '\N{SNOWMAN}']
    bad = [None, b'', b'hello', 10]
    stringValues = [
        (b'hello', 'hello'),
        ('\N{SNOWMAN}'.encode('utf-8'), '\N{SNOWMAN}'),
    ]
    badStringValues = ['\xe0\xe0']
    cmpResults = [('bbb', 'aaa', 1)]


class Binary(TypeMixin, unittest.TestCase):

    klass = types.Binary
    good = [b'', b'\x01\x80\xfe', '\N{SNOWMAN}'.encode('utf-8')]
    bad = [None, 10, 'xyz']
    stringValues = [('hello', 'hello')]
    cmpResults = [('\x00\x80', '\x10\x10', -1)]


class Boolean(TypeMixin, unittest.TestCase):

    klass = types.Boolean
    good = [True, False]
    bad = [None, 0, 1]
    stringValues = [
        (b'on', True),
        (b'true', True),
        (b'yes', True),
        (b'1', True),
        (b'off', False),
        (b'false', False),
        (b'no', False),
        (b'0', False),
        (b'ON', True),
        (b'TRUE', True),
        (b'YES', True),
        (b'OFF', False),
        (b'FALSE', False),
        (b'NO', False),
    ]
    cmpResults = [
        (False, b'no', 0),
        (True, b'true', 0),
    ]


class Identifier(TypeMixin, unittest.TestCase):

    def makeInstance(self):
        return types.Identifier(len=5)

    good = ['a', 'abcde', 'a1234']
    bad = ['', 'abcdef', b'abcd', '1234', '\N{SNOWMAN}']
    stringValues = [
        (b'abcd', 'abcd'),
    ]
    badStringValues = [
        b'', r'\N{SNOWMAN}', b'abcdef'
    ]
    cmpResults = [
        ('aaaa', b'bbbb', -1),
    ]


class List(TypeMixin, unittest.TestCase):

    def makeInstance(self):
        return types.List(of=types.Integer())

    good = [[], [1], [1, 2]]
    bad = [1, (1,), ['1']]
    badStringValues = [
        '1', '1,2'
    ]


class SourcedProperties(TypeMixin, unittest.TestCase):

    klass = types.SourcedProperties

    good = [{'p': (b'["a"]', 's')}]
    bad = [
        None, (), [],
        {b'not-unicode': ('["a"]', 'unicode')},
        {'unicode': ('["a"]', b'not-unicode')},
        {'unicode': ('not, json', 'unicode')},
    ]


class Entity(TypeMixin, unittest.TestCase):

    class MyEntity(types.Entity):
        field1 = types.Integer()
        field2 = types.NoneOk(types.String())

    def makeInstance(self):
        return self.MyEntity('myentity')

    good = [
        {'field1': 1, 'field2': 'f2'},
        {'field1': 1, 'field2': None},
    ]
    bad = [
        None, [], (),
        {'field1': 1},
        {'field1': 1, 'field2': 'f2', 'field3': 10},
        {'field1': 'one', 'field2': 'f2'},
    ]
