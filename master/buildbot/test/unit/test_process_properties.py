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

from buildbot.process.properties import PropertyMap, Properties, WithProperties, Property
from buildbot.interfaces import IRenderable

class FakeProperties(object):
    def __init__(self, **kwargs):
        self.dict = kwargs
    def __getitem__(self, k):
        return self.dict[k]
    def has_key(self, k):
        return self.dict.has_key(k)

class FakeBuild(object):
    def __init__(self, properties):
        self.properties = properties
    def getProperties(self):
        return self.properties
    def getProperty(self, key, default=None):
        return self.properties.getProperty(key, default)
    def render(self, value):
        return IRenderable(value).getRenderingFor(self)

class TestPropertyMap(unittest.TestCase):
    def setUp(self):
        self.fp = FakeProperties(
            prop_str='a-string',
            prop_none=None,
            prop_list=['a', 'b'],
            prop_zero=0,
            prop_one=1,
            prop_false=False,
            prop_true=True,
            prop_empty='',
        )
        self.pm = PropertyMap(self.fp)

    def testSimpleStr(self):
        self.assertEqual(self.pm['prop_str'], 'a-string')

    def testSimpleNone(self):
        # None is special-cased to become an empty string
        self.assertEqual(self.pm['prop_none'], '')

    def testSimpleList(self):
        self.assertEqual(self.pm['prop_list'], ['a', 'b'])

    def testSimpleZero(self):
        self.assertEqual(self.pm['prop_zero'], 0)

    def testSimpleOne(self):
        self.assertEqual(self.pm['prop_one'], 1)

    def testSimpleFalse(self):
        self.assertEqual(self.pm['prop_false'], False)

    def testSimpleTrue(self):
        self.assertEqual(self.pm['prop_true'], True)

    def testSimpleEmpty(self):
        self.assertEqual(self.pm['prop_empty'], '')

    def testSimpleUnset(self):
        self.assertRaises(KeyError, lambda : self.pm['prop_nosuch'])


    def testColonMinusSet(self):
        self.assertEqual(self.pm['prop_str:-missing'], 'a-string')

    def testColonMinusNone(self):
        # None is special-cased here, too
        self.assertEqual(self.pm['prop_none:-missing'], '')

    def testColonMinusZero(self):
        self.assertEqual(self.pm['prop_zero:-missing'], 0)

    def testColonMinusOne(self):
        self.assertEqual(self.pm['prop_one:-missing'], 1)

    def testColonMinusFalse(self):
        self.assertEqual(self.pm['prop_false:-missing'], False)

    def testColonMinusTrue(self):
        self.assertEqual(self.pm['prop_true:-missing'], True)

    def testColonMinusEmpty(self):
        self.assertEqual(self.pm['prop_empty:-missing'], '')

    def testColonMinusUnset(self):
        self.assertEqual(self.pm['prop_nosuch:-missing'], 'missing')


    def testColonTildeSet(self):
        self.assertEqual(self.pm['prop_str:~missing'], 'a-string')

    def testColonTildeNone(self):
        # None is special-cased *differently* for ~:
        self.assertEqual(self.pm['prop_none:~missing'], 'missing')

    def testColonTildeZero(self):
        self.assertEqual(self.pm['prop_zero:~missing'], 'missing')

    def testColonTildeOne(self):
        self.assertEqual(self.pm['prop_one:~missing'], 1)

    def testColonTildeFalse(self):
        self.assertEqual(self.pm['prop_false:~missing'], 'missing')

    def testColonTildeTrue(self):
        self.assertEqual(self.pm['prop_true:~missing'], True)

    def testColonTildeEmpty(self):
        self.assertEqual(self.pm['prop_empty:~missing'], 'missing')

    def testColonTildeUnset(self):
        self.assertEqual(self.pm['prop_nosuch:~missing'], 'missing')


    def testColonPlusSet(self):
        self.assertEqual(self.pm['prop_str:+present'], 'present')

    def testColonPlusNone(self):
        self.assertEqual(self.pm['prop_none:+present'], 'present')

    def testColonPlusZero(self):
        self.assertEqual(self.pm['prop_zero:+present'], 'present')

    def testColonPlusOne(self):
        self.assertEqual(self.pm['prop_one:+present'], 'present')

    def testColonPlusFalse(self):
        self.assertEqual(self.pm['prop_false:+present'], 'present')

    def testColonPlusTrue(self):
        self.assertEqual(self.pm['prop_true:+present'], 'present')

    def testColonPlusEmpty(self):
        self.assertEqual(self.pm['prop_empty:+present'], 'present')

    def testColonPlusUnset(self):
        self.assertEqual(self.pm['prop_nosuch:+present'], '')

    def testNoTempValues(self):
        self.assertEqual(self.pm.temp_vals, {})

    def testClearTempValues(self):
        self.pm.add_temporary_value('prop_temp', 'present')
        self.pm.clear_temporary_values()
        self.assertEqual(self.pm.temp_vals, {})

    def testTempValue(self):
        self.pm.add_temporary_value('prop_temp', 'present')
        self.assertEqual(self.pm['prop_temp'], 'present')
        self.pm.clear_temporary_values()

    def testTempValueOverrides(self):
        self.pm.add_temporary_value('prop_one', 2)
        self.assertEqual(self.pm['prop_one'], 2)
        self.pm.clear_temporary_values()

    def testTempValueColonMinusSet(self):
        self.pm.add_temporary_value('prop_one', 2)
        self.assertEqual(self.pm['prop_one:-missing'], 2)
        self.pm.clear_temporary_values()

    def testTempValueColonMinusUnset(self):
        self.pm.add_temporary_value('prop_nosuch', 'temp')
        self.assertEqual(self.pm['prop_nosuch:-missing'], 'temp')
        self.pm.clear_temporary_values()

    def testTempValueColonTildeTrueSet(self):
        self.pm.add_temporary_value('prop_false', 'temp')
        self.assertEqual(self.pm['prop_false:~nontrue'], 'temp')
        self.pm.clear_temporary_values()

    def testTempValueColonTildeTrueUnset(self):
        self.pm.add_temporary_value('prop_nosuch', 'temp')
        self.assertEqual(self.pm['prop_nosuch:~nontrue'], 'temp')
        self.pm.clear_temporary_values()

    def testTempValueColonTildeFalseFalse(self):
        self.pm.add_temporary_value('prop_false', False)
        self.assertEqual(self.pm['prop_false:~nontrue'], 'nontrue')
        self.pm.clear_temporary_values()

    def testTempValueColonTildeTrueFalse(self):
        self.pm.add_temporary_value('prop_true', False)
        self.assertEqual(self.pm['prop_true:~nontrue'], True)
        self.pm.clear_temporary_values()

    def testTempValueColonTildeNoneFalse(self):
        self.pm.add_temporary_value('prop_nosuch', False)
        self.assertEqual(self.pm['prop_nosuch:~nontrue'], 'nontrue')
        self.pm.clear_temporary_values()


    def testTempValueColonTildeFalseZero(self):
        self.pm.add_temporary_value('prop_false', 0)
        self.assertEqual(self.pm['prop_false:~nontrue'], 'nontrue')
        self.pm.clear_temporary_values()

    def testTempValueColonTildeTrueZero(self):
        self.pm.add_temporary_value('prop_true', 0)
        self.assertEqual(self.pm['prop_true:~nontrue'], True)
        self.pm.clear_temporary_values()

    def testTempValueColonTildeNoneZero(self):
        self.pm.add_temporary_value('prop_nosuch', 0)
        self.assertEqual(self.pm['prop_nosuch:~nontrue'], 'nontrue')
        self.pm.clear_temporary_values()

    def testTempValueColonTildeFalseBlank(self):
        self.pm.add_temporary_value('prop_false', '')
        self.assertEqual(self.pm['prop_false:~nontrue'], 'nontrue')
        self.pm.clear_temporary_values()

    def testTempValueColonTildeTrueBlank(self):
        self.pm.add_temporary_value('prop_true', '')
        self.assertEqual(self.pm['prop_true:~nontrue'], True)
        self.pm.clear_temporary_values()

    def testTempValueColonTildeNoneBlank(self):
        self.pm.add_temporary_value('prop_nosuch', '')
        self.assertEqual(self.pm['prop_nosuch:~nontrue'], 'nontrue')
        self.pm.clear_temporary_values()

    def testTempValuePlusSetSet(self):
        self.pm.add_temporary_value('prop_one', 2)
        self.assertEqual(self.pm['prop_one:+set'], 'set')
        self.pm.clear_temporary_values()

    def testTempValuePlusUnsetSet(self):
        self.pm.add_temporary_value('prop_nosuch', 1)
        self.assertEqual(self.pm['prop_nosuch:+set'], 'set')

class TestWithProperties(unittest.TestCase):
    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(self.props)

    def testBasic(self):
        # test basic substitution with WithProperties
        self.props.setProperty("revision", "47", "test")
        command = WithProperties("build-%s.tar.gz", "revision")
        self.failUnlessEqual(self.build.render(command),
                             "build-47.tar.gz")

    def testDict(self):
        # test dict-style substitution with WithProperties
        self.props.setProperty("other", "foo", "test")
        command = WithProperties("build-%(other)s.tar.gz")
        self.failUnlessEqual(self.build.render(command),
                             "build-foo.tar.gz")

    def testDictColonMinus(self):
        # test dict-style substitution with WithProperties
        self.props.setProperty("prop1", "foo", "test")
        command = WithProperties("build-%(prop1:-empty)s-%(prop2:-empty)s.tar.gz")
        self.failUnlessEqual(self.build.render(command),
                             "build-foo-empty.tar.gz")

    def testDictColonPlus(self):
        # test dict-style substitution with WithProperties
        self.props.setProperty("prop1", "foo", "test")
        command = WithProperties("build-%(prop1:+exists)s-%(prop2:+exists)s.tar.gz")
        self.failUnlessEqual(self.build.render(command),
                             "build-exists-.tar.gz")

    def testEmpty(self):
        # None should render as ''
        self.props.setProperty("empty", None, "test")
        command = WithProperties("build-%(empty)s.tar.gz")
        self.failUnlessEqual(self.build.render(command),
                             "build-.tar.gz")

    def testRecursiveList(self):
        self.props.setProperty("x", 10, "test")
        self.props.setProperty("y", 20, "test")
        command = [ WithProperties("%(x)s %(y)s"), "and",
                    WithProperties("%(y)s %(x)s") ]
        self.failUnlessEqual(self.build.render(command),
                             ["10 20", "and", "20 10"])

    def testRecursiveTuple(self):
        self.props.setProperty("x", 10, "test")
        self.props.setProperty("y", 20, "test")
        command = ( WithProperties("%(x)s %(y)s"), "and",
                    WithProperties("%(y)s %(x)s") )
        self.failUnlessEqual(self.build.render(command),
                             ("10 20", "and", "20 10"))

    def testRecursiveDict(self):
        self.props.setProperty("x", 10, "test")
        self.props.setProperty("y", 20, "test")
        command = { WithProperties("%(x)s %(y)s") : 
                    WithProperties("%(y)s %(x)s") }
        self.failUnlessEqual(self.build.render(command),
                             {"10 20" : "20 10"})

    def testLambdaSubst(self):
        command = WithProperties('%(foo)s', foo=lambda _: 'bar')
        self.failUnlessEqual(self.build.render(command), 'bar')

    def testLambdaOverride(self):
        self.props.setProperty('x', 10, 'test')
        command = WithProperties('%(x)s', x=lambda _: 20)
        self.failUnlessEqual(self.build.render(command), '20')

    def testLambdaCallable(self):
        self.assertRaises(ValueError, lambda: WithProperties('%(foo)s', foo='bar'))

    def testLambdaUseExisting(self):
        self.props.setProperty('x', 10, 'test')
        self.props.setProperty('y', 20, 'test')
        command = WithProperties('%(z)s', z=lambda build: build.getProperty('x') + build.getProperty('y'))
        self.failUnlessEqual(self.build.render(command), '30')

class TestProperties(unittest.TestCase):
    def setUp(self):
        self.props = Properties()

    def testDictBehavior(self):
        self.props.setProperty("do-tests", 1, "scheduler")
        self.props.setProperty("do-install", 2, "scheduler")

        self.assert_(self.props.has_key('do-tests'))
        self.failUnlessEqual(self.props['do-tests'], 1)
        self.failUnlessEqual(self.props['do-install'], 2)
        self.assertRaises(KeyError, lambda : self.props['do-nothing'])
        self.failUnlessEqual(self.props.getProperty('do-install'), 2)

    def testAsList(self):
        self.props.setProperty("happiness", 7, "builder")
        self.props.setProperty("flames", True, "tester")

        self.assertEqual(sorted(self.props.asList()),
                [ ('flames', True, 'tester'), ('happiness', 7, 'builder') ])

    def testAsDict(self):
        self.props.setProperty("msi_filename", "product.msi", 'packager')
        self.props.setProperty("dmg_filename", "product.dmg", 'packager')

        self.assertEqual(self.props.asDict(),
                dict(msi_filename=('product.msi', 'packager'), dmg_filename=('product.dmg', 'packager')))

    def testUpdate(self):
        self.props.setProperty("x", 24, "old")
        newprops = { 'a' : 1, 'b' : 2 }
        self.props.update(newprops, "new")

        self.failUnlessEqual(self.props.getProperty('x'), 24)
        self.failUnlessEqual(self.props.getPropertySource('x'), 'old')
        self.failUnlessEqual(self.props.getProperty('a'), 1)
        self.failUnlessEqual(self.props.getPropertySource('a'), 'new')

    def testUpdateFromProperties(self):
        self.props.setProperty("a", 94, "old")
        self.props.setProperty("x", 24, "old")
        newprops = Properties()
        newprops.setProperty('a', 1, "new")
        newprops.setProperty('b', 2, "new")
        self.props.updateFromProperties(newprops)

        self.failUnlessEqual(self.props.getProperty('x'), 24)
        self.failUnlessEqual(self.props.getPropertySource('x'), 'old')
        self.failUnlessEqual(self.props.getProperty('a'), 1)
        self.failUnlessEqual(self.props.getPropertySource('a'), 'new')

    def testUpdateFromPropertiesNoRuntime(self):
        self.props.setProperty("a", 94, "old")
        self.props.setProperty("b", 84, "old")
        self.props.setProperty("x", 24, "old")
        newprops = Properties()
        newprops.setProperty('a', 1, "new", runtime=True)
        newprops.setProperty('b', 2, "new", runtime=False)
        newprops.setProperty('c', 3, "new", runtime=True)
        newprops.setProperty('d', 3, "new", runtime=False)
        self.props.updateFromPropertiesNoRuntime(newprops)

        self.failUnlessEqual(self.props.getProperty('a'), 94)
        self.failUnlessEqual(self.props.getPropertySource('a'), 'old')
        self.failUnlessEqual(self.props.getProperty('b'), 2)
        self.failUnlessEqual(self.props.getPropertySource('b'), 'new')
        self.failUnlessEqual(self.props.getProperty('c'), None) # not updated
        self.failUnlessEqual(self.props.getProperty('d'), 3)
        self.failUnlessEqual(self.props.getPropertySource('d'), 'new')
        self.failUnlessEqual(self.props.getProperty('x'), 24)
        self.failUnlessEqual(self.props.getPropertySource('x'), 'old')

    # render() is pretty well tested by TestWithProperties, above

class TestProperty(unittest.TestCase):
    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(self.props)

    def testIntProperty(self):
        self.props.setProperty("do-tests", 1, "scheduler")
        value = Property("do-tests")

        self.failUnlessEqual(self.build.render(value),
                1)

    def testStringProperty(self):
        self.props.setProperty("do-tests", "string", "scheduler")
        value = Property("do-tests")

        self.failUnlessEqual(self.build.render(value),
                "string")

    def testMissingProperty(self):
        value = Property("do-tests")

        self.failUnlessEqual(self.build.render(value),
                None)

    def testDefaultValue(self):
        value = Property("do-tests", default="Hello!")

        self.failUnlessEqual(self.build.render(value),
                "Hello!")

    def testIgnoreDefaultValue(self):
        self.props.setProperty("do-tests", "string", "scheduler")
        value = Property("do-tests", default="Hello!")

        self.failUnlessEqual(self.build.render(value),
                "string")

    def testIgnoreFalseValue(self):
        self.props.setProperty("do-tests-string", "", "scheduler")
        self.props.setProperty("do-tests-int", 0, "scheduler")
        self.props.setProperty("do-tests-list", [], "scheduler")
        self.props.setProperty("do-tests-None", None, "scheduler")

        value = [ Property("do-tests-string", default="Hello!"),
                  Property("do-tests-int", default="Hello!"),
                  Property("do-tests-list", default="Hello!"),
                  Property("do-tests-None", default="Hello!") ]

        self.failUnlessEqual(self.build.render(value),
                ["Hello!"] * 4)

    def testDefaultWhenFalse(self):
        self.props.setProperty("do-tests-string", "", "scheduler")
        self.props.setProperty("do-tests-int", 0, "scheduler")
        self.props.setProperty("do-tests-list", [], "scheduler")
        self.props.setProperty("do-tests-None", None, "scheduler")

        value = [ Property("do-tests-string", default="Hello!", defaultWhenFalse=False),
                  Property("do-tests-int", default="Hello!", defaultWhenFalse=False),
                  Property("do-tests-list", default="Hello!", defaultWhenFalse=False),
                  Property("do-tests-None", default="Hello!", defaultWhenFalse=False) ]

        self.failUnlessEqual(self.build.render(value),
                ["", 0, [], None])
