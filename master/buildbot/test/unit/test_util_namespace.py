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
from time import time
from mock import Mock
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

    def do_benchmark(self, D, m, f1,f2):
        self.patch(namespace,"pedantic", False)
        numtime = 100
        start = time()
        for i in xrange(numtime*100):
            d = dict(D)
            f1(d)
        t1 =  (time()-start)/100
        start = time()
        for i in xrange(numtime*100):
            f1(d)
        t1bis =  (time()-start)/100
        start = time()
        for i in xrange(numtime):
            d = namespace.Namespace(D)
            f1(d)
        t2 =  time()-start
        start = time()
        for i in xrange(numtime):
            f1(d)
        t2bis =  time()-start
        start = time()
        for i in xrange(numtime):
            d = namespace.Namespace(D)
            f2(d)
        t3 =  time()-start
        start = time()
        for i in xrange(numtime):
            f2(d)
        t3bis =  time()-start
        start = time()
        for i in xrange(numtime):
            f2(m)
        t4bis =  time()-start
        def fmt(i):
            return "%d kread/s"%(int(i)/1000)
        print
        print "create + access"
        print "pure dict          :",fmt(numtime/t1)
        print "Namespace as dict  :",fmt(numtime/t2), "(x",int(t2/t1),")"
        print "Namespace as object:",fmt(numtime/t3), "(x",int(t3/t1),")"
        print "access only"
        print "pure dict          :",fmt(numtime/t1bis)
        print "Namespace as dict  :",fmt(numtime/t2bis), "(x",int(t2bis/t1bis),")"
        print "Namespace as object:",fmt(numtime/t3bis), "(x",int(t3bis/t1bis),")"
        print "Mock as object:",fmt(numtime/t4bis), "(x",int(t4bis/t1bis),")"
    def test_benchmark1(self):
        m = Mock()
        m.a.b.c = 2
        self.do_benchmark({'a':{'b':{'c':1}}},m,
                          lambda d:d['a']['b']['c']==2,
                          lambda d:d.a.b.c==2)
    def test_benchmark2(self):
        m = Mock()
        m1 = Mock()
        m1.b.c=1
        m2 = Mock()
        m2.b.d=2
        m.a = [m1,m2]
        self.do_benchmark({'a':[{'b':{'c':1}},{'b':{'d':2}}]},m,
                          lambda d:d['a'][0]['b']['c']==2,
                          lambda d:d.a[0].b.c==2)
    def test_benchmark3(self):
        d = {}
        m = Mock()
        c = d
        f1 = f2 = "lambda d:d"
        f3= "m"
        for i in xrange(25):
            k = chr(ord('a')+i)
            c[k] = {'z':1}
            c = c[k]
            f1+="['"+k+"']"
            f2+="."+k
            f3+="."+k
        f1 = eval(f1)
        f2 = eval(f2)
        f3+="=2"
        exec f3
        self.do_benchmark(d,m,
                          f1,
                          f2)
