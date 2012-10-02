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
from buildbot.util import namespace
import pickle
from buildbot.util import json

class Namespace(unittest.TestCase):

    def test_basic(self):
        n = namespace.Namespace({'a':{'b':{'c':1}}})

        self.assertEqual(n.a.b.c, 1)
        self.assertEqual(n['a']['b']['c'], 1)
        self.assertEqual(n['a'].b['c'], 1)
        self.assertEqual(n['a']['b'].c, 1)
        self.assertEqual(n['a'].b.c, 1)
        self.assertEqual(list(n.keys()),['a'])
        self.assertEqual(list(n.a.b.values()),[1])
        self.assertEqual(list(n.a.b.items()),[('c',1)])
        n.a.b.c = 2
        self.assertEqual(n.has_key('a'),True)
        self.assertEqual(n.has_key('b'),False)

        self.assertEqual(n['a']['b']['c'], 2)
        n.a.b = {'d':3}
        self.assertEqual(n.a.b.d, 3)
        n.a.b = namespace.Namespace({'e':4})
        self.assertEqual(n.a.b.e, 4)
        self.assertRaises(KeyError, lambda : n.a.b.d == 3)
        self.assertEqual(namespace.Namespace(1),1)
        self.assertEqual(namespace.Namespace([1]),[1])
        self.assertEqual(namespace.Namespace("1"),"1")
        self.assertEqual(namespace.Namespace(["1"]),["1"])

        self.assertRaises(KeyError, lambda : n["__getitem__"])
        n.a['b'] = {'f':5}
        self.assertEqual(n.a.b.f, 5)

    def test_nonzero(self):
        n = namespace.Namespace({'a':{'b':{'c':1}}})
        self.failUnless(n)
        n = namespace.Namespace({})
        self.failIf(n)

    def test_list(self):
        n = namespace.Namespace([{'a':{'b':{'c':1}}},{'a':{'b':{'c':2}}}])
        self.assertEqual(n[0].a.b.c, 1)
        self.assertEqual(n[1].a.b.c, 2)
        for i in n:
            self.assertEqual(i.a.b.c, i.a.b.c)

    def test_jsondump(self):
        s = '[{"a": {"b": {"c": 1}}}, {"a": {"b": {"c": 2}}}]'
        n = namespace.Namespace(json.loads(s))
        self.assertEqual(json.dumps(n),s)

    def test_prettyprint(self):
        n = namespace.Namespace({'a':[{'b':{'c':1}}]})
        expected = """\
{
    "a": [
        {
            "b": {
                "c": 1
            }
        }
    ]
}"""
        self.assertEqual(repr(n), expected)
        expected = """\
a -> list
a[i] -> dict
a[i].b -> dict
a[i].b.c -> int
"""
        self.assertEqual(namespace.documentNamespace(n), expected)

    def test_pickle(self):
        n = namespace.Namespace([{'a':{'b':{'c':1}}},{'a':{'b':{'c':2}}}])
        s = pickle.dumps(n)
        n = pickle.loads(s)
        self.assertEqual(n[0].a.b.c, 1)
        self.assertEqual(n[1].a.b.c, 2)
        for i in n:
            self.assertEqual(i.a.b.c, i.a.b.c)

    def test_pedantic(self):
        self.assertRaises(TypeError, lambda:namespace.Namespace({'a': set([1,2,3])}))
        self.patch(namespace,"pedantic", False)
        # should not crash if pendentic disabled
        n = namespace.Namespace({'a': set([1,2,3])})
        self.assertRaises(TypeError,lambda:repr(n))

