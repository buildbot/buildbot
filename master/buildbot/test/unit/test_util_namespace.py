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
import pickle

class Namespace(unittest.TestCase):
    def assertCrashes(self, func, msg=None):
        crashed = False
        try:
            func()
        except:
            crashed = True
        if not msg:
            msg = repr(func) + "should raise exception"
        self.failUnless(crashed, msg)

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
        self.assertCrashes(lambda : n.a.b.d == 3)
        self.assertEqual(namespace.Namespace(1),1)
        self.assertEqual(namespace.Namespace([1]),[1])
        self.assertEqual(namespace.Namespace("1"),"1")
        self.assertEqual(namespace.Namespace(["1"]),["1"])

        self.assertCrashes(lambda : namespace._Namespace(["1"]))
        self.assertCrashes(lambda : n["__getitem__"])
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

    def test_cannot_inherit(self):
        class myNamespace(namespace._Namespace):
            pass
        self.assertCrashes(lambda : myNamespace({'a':{'b':{'c':1}}}))

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
        self.assertCrashes(lambda:namespace.Namespace({'a': set([1,2,3])}))
        namespace.pedantic = False
        # should not crash if pendentic disabled
        n = namespace.Namespace({'a': set([1,2,3])})
        self.assertCrashes(lambda:repr(n))

    def do_benchmark(self, D, f1,f2):
        start = time()
        for i in xrange(10000):
            d = dict(D)
            f1(d)
        t1 =  time()-start
        start = time()
        for i in xrange(10000):
            f1(d)
        t1bis =  time()-start
        start = time()
        for i in xrange(10000):
            d = namespace.Namespace(D)
            f1(d)
        t2 =  time()-start
        start = time()
        for i in xrange(10000):
            f1(d)
        t2bis =  time()-start
        start = time()
        for i in xrange(10000):
            d = namespace.Namespace(D)
            f2(d)
        t3 =  time()-start
        start = time()
        for i in xrange(10000):
            f2(d)
        t3bis =  time()-start
        print 
        print "create + access"
        print "pure dict          :",t1
        print "Namespace as dict  :",t2, "(",int(t2*100/t1),"%)"
        print "Namespace as object:",t3, "(",int(t3*100/t1),"%)"
        print "access only"
        print "pure dict          :",t1bis
        print "Namespace as dict  :",t2bis, "(",int(t2bis*100/t1bis),"%)"
        print "Namespace as object:",t3bis, "(",int(t3bis*100/t1bis),"%)"
    def test_benchmark1(self):
        self.do_benchmark({'a':{'b':{'c':1}}},
                          lambda d:d['a']['b']['c']==2,
                          lambda d:d.a.b.c==2)
    def test_benchmark2(self):
        self.do_benchmark({'a':[{'b':{'c':1}},{'b':{'d':2}}]},
                          lambda d:d['a'][0]['b']['c']==2,
                          lambda d:d.a[0].b.c==2)
    def test_benchmark3(self):
        d = {}
        c = d
        f1 = f2 = "lambda d:d"
        for i in xrange(25):
            k = chr(ord('a')+i)
            c[k] = {'z':1}
            c = c[k]
            f1+="['"+k+"']"
            f2+="."+k
        f1 = eval(f1)
        f2 = eval(f2)
        self.do_benchmark(d,
                          f1,
                          f2)
