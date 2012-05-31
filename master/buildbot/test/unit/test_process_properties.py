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

import mock
from zope.interface import implements
from twisted.internet import defer
from twisted.trial import unittest
from twisted.python import components
from buildbot.process.properties import Properties, WithProperties
from buildbot.process.properties import Interpolate
from buildbot.process.properties import Property, PropertiesMixin
from buildbot.interfaces import IRenderable, IProperties
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.properties import FakeRenderable
from buildbot.test.util import compat

class FakeSource:
    def __init__(self):
        self.branch = None
        self.codebase = ''
        self.project = ''
        self.repository = ''
        self.revision = None

    def asDict(self):
        ds = {}
        ds['branch'] = self.branch
        ds['codebase'] = self.codebase
        ds['project'] = self.project
        ds['repository'] = self.repository
        ds['revision'] = self.revision
        return ds
        
class FakeBuild(PropertiesMixin):
    def __init__(self, properties):
        self.sources = {}
        properties.build = self
        self.properties = properties

    def getSourceStamp(self, codebase):
        if codebase in self.sources:
            return self.sources[codebase]
        return None

class DeferredRenderable:
    implements (IRenderable)
    def __init__(self):
        self.d = defer.Deferred()
    def getRenderingFor(self, build):
        return self.d
    def callback(self, value):
        self.d.callback(value)

        
components.registerAdapter(
        lambda build : IProperties(build.properties),
        FakeBuild, IProperties)

class TestPropertyMap(unittest.TestCase):
    """
    Test the behavior of PropertyMap, using the external interace
    provided by WithProperties.
    """

    def setUp(self):
        self.props = Properties(
            prop_str='a-string',
            prop_none=None,
            prop_list=['a', 'b'],
            prop_zero=0,
            prop_one=1,
            prop_false=False,
            prop_true=True,
            prop_empty='',
        )
        self.build = FakeBuild(self.props)

    def doTestSimpleWithProperties(self, fmtstring, expect, **kwargs):
        d = self.build.render(WithProperties(fmtstring, **kwargs))
        d.addCallback(self.failUnlessEqual, "%s" % expect)
        return d

    def testSimpleStr(self):
        return self.doTestSimpleWithProperties('%(prop_str)s', 'a-string')

    def testSimpleNone(self):
        # None is special-cased to become an empty string
        return self.doTestSimpleWithProperties('%(prop_none)s', '')

    def testSimpleList(self):
        return self.doTestSimpleWithProperties('%(prop_list)s', ['a', 'b'])

    def testSimpleZero(self):
        return self.doTestSimpleWithProperties('%(prop_zero)s', 0)

    def testSimpleOne(self):
        return self.doTestSimpleWithProperties('%(prop_one)s', 1)

    def testSimpleFalse(self):
        return self.doTestSimpleWithProperties('%(prop_false)s', False)

    def testSimpleTrue(self):
        return self.doTestSimpleWithProperties('%(prop_true)s', True)

    def testSimpleEmpty(self):
        return self.doTestSimpleWithProperties('%(prop_empty)s', '')

    def testSimpleUnset(self):
        d = self.build.render(WithProperties('%(prop_nosuch)s'))
        return self.assertFailure(d, KeyError)


    def testColonMinusSet(self):
        return self.doTestSimpleWithProperties('%(prop_str:-missing)s', 'a-string')

    def testColonMinusNone(self):
        # None is special-cased here, too
        return self.doTestSimpleWithProperties('%(prop_none:-missing)s', '')

    def testColonMinusZero(self):
        return self.doTestSimpleWithProperties('%(prop_zero:-missing)s', 0)

    def testColonMinusOne(self):
        return self.doTestSimpleWithProperties('%(prop_one:-missing)s', 1)

    def testColonMinusFalse(self):
        return self.doTestSimpleWithProperties('%(prop_false:-missing)s', False)

    def testColonMinusTrue(self):
        return self.doTestSimpleWithProperties('%(prop_true:-missing)s', True)

    def testColonMinusEmpty(self):
        return self.doTestSimpleWithProperties('%(prop_empty:-missing)s', '')

    def testColonMinusUnset(self):
        return self.doTestSimpleWithProperties('%(prop_nosuch:-missing)s', 'missing')


    def testColonTildeSet(self):
        return self.doTestSimpleWithProperties('%(prop_str:~missing)s', 'a-string')

    def testColonTildeNone(self):
        # None is special-cased *differently* for ~:
        return self.doTestSimpleWithProperties('%(prop_none:~missing)s', 'missing')

    def testColonTildeZero(self):
        return self.doTestSimpleWithProperties('%(prop_zero:~missing)s', 'missing')

    def testColonTildeOne(self):
        return self.doTestSimpleWithProperties('%(prop_one:~missing)s', 1)

    def testColonTildeFalse(self):
        return self.doTestSimpleWithProperties('%(prop_false:~missing)s', 'missing')

    def testColonTildeTrue(self):
        return self.doTestSimpleWithProperties('%(prop_true:~missing)s', True)

    def testColonTildeEmpty(self):
        return self.doTestSimpleWithProperties('%(prop_empty:~missing)s', 'missing')

    def testColonTildeUnset(self):
        return self.doTestSimpleWithProperties('%(prop_nosuch:~missing)s', 'missing')


    def testColonPlusSet(self):
        return self.doTestSimpleWithProperties('%(prop_str:+present)s', 'present')

    def testColonPlusNone(self):
        return self.doTestSimpleWithProperties('%(prop_none:+present)s', 'present')

    def testColonPlusZero(self):
        return self.doTestSimpleWithProperties('%(prop_zero:+present)s', 'present')

    def testColonPlusOne(self):
        return self.doTestSimpleWithProperties('%(prop_one:+present)s', 'present')

    def testColonPlusFalse(self):
        return self.doTestSimpleWithProperties('%(prop_false:+present)s', 'present')

    def testColonPlusTrue(self):
        return self.doTestSimpleWithProperties('%(prop_true:+present)s', 'present')

    def testColonPlusEmpty(self):
        return self.doTestSimpleWithProperties('%(prop_empty:+present)s', 'present')

    def testColonPlusUnset(self):
        return self.doTestSimpleWithProperties('%(prop_nosuch:+present)s', '')


    def testColonTernarySet(self):
        return self.doTestSimpleWithProperties('%(prop_str:?:present:missing)s', 'present')

    def testColonTernaryNone(self):
        return self.doTestSimpleWithProperties('%(prop_none:?:present:missing)s', 'present')

    def testColonTernaryZero(self):
        return self.doTestSimpleWithProperties('%(prop_zero:?|present|missing)s', 'present')

    def testColonTernaryOne(self):
        return self.doTestSimpleWithProperties('%(prop_one:?:present:missing)s', 'present')

    def testColonTernaryFalse(self):
        return self.doTestSimpleWithProperties('%(prop_false:?|present|missing)s', 'present')

    def testColonTernaryTrue(self):
        return self.doTestSimpleWithProperties('%(prop_true:?:present:missing)s', 'present')

    def testColonTernaryEmpty(self):
        return self.doTestSimpleWithProperties('%(prop_empty:?ApresentAmissing)s', 'present')

    def testColonTernaryUnset(self):
        return self.doTestSimpleWithProperties('%(prop_nosuch:?#present#missing)s', 'missing')


    def testColonTernaryHashSet(self):
        return self.doTestSimpleWithProperties('%(prop_str:#?:truish:falsish)s', 'truish')
        
    def testColonTernaryHashNone(self):
        # None is special-cased *differently* for '#?'
        return self.doTestSimpleWithProperties('%(prop_none:#?|truish|falsish)s', 'falsish')

    def testColonTernaryHashZero(self):
        return self.doTestSimpleWithProperties('%(prop_zero:#?:truish:falsish)s', 'falsish')

    def testColonTernaryHashOne(self):
        return self.doTestSimpleWithProperties('%(prop_one:#?:truish:falsish)s', 'truish')

    def testColonTernaryHashFalse(self):
        return self.doTestSimpleWithProperties('%(prop_false:#?:truish:falsish)s', 'falsish')

    def testColonTernaryHashTrue(self):
        return self.doTestSimpleWithProperties('%(prop_true:#?|truish|falsish)s', 'truish')

    def testColonTernaryHashEmpty(self):
        return self.doTestSimpleWithProperties('%(prop_empty:#?:truish:falsish)s', 'falsish')

    def testColonTernaryHashUnset(self):
        return self.doTestSimpleWithProperties('%(prop_nosuch:#?.truish.falsish)s', 'falsish')


    def testClearTempValues(self):
        d = self.doTestSimpleWithProperties('', '',
                prop_temp=lambda b: 'present')
        d.addCallback(lambda _:
                self.doTestSimpleWithProperties('%(prop_temp:+present)s', ''))
        return d

    def testTempValue(self):
        self.doTestSimpleWithProperties('%(prop_temp)s', 'present',
                prop_temp=lambda b: 'present')

    def testTempValueOverrides(self):
        return self.doTestSimpleWithProperties('%(prop_one)s', 2,
                prop_one=lambda b: 2)

    def testTempValueColonMinusSet(self):
        return self.doTestSimpleWithProperties('%(prop_one:-missing)s', 2,
                prop_one=lambda b: 2)

    def testTempValueColonMinusUnset(self):
        return self.doTestSimpleWithProperties('%(prop_nosuch:-missing)s', 'temp',
                prop_nosuch=lambda b: 'temp')

    def testTempValueColonTildeTrueSet(self):
        return self.doTestSimpleWithProperties('%(prop_false:~nontrue)s', 'temp',
                prop_false=lambda b: 'temp')

    def testTempValueColonTildeTrueUnset(self):
        return self.doTestSimpleWithProperties('%(prop_nosuch:~nontrue)s', 'temp',
                prop_nosuch=lambda b: 'temp')

    def testTempValueColonTildeFalseFalse(self):
        return self.doTestSimpleWithProperties('%(prop_false:~nontrue)s', 'nontrue',
                prop_false=lambda b: False)

    def testTempValueColonTildeTrueFalse(self):
        return self.doTestSimpleWithProperties('%(prop_true:~nontrue)s', True,
                prop_true=lambda b: False)

    def testTempValueColonTildeNoneFalse(self):
        return self.doTestSimpleWithProperties('%(prop_nosuch:~nontrue)s', 'nontrue',
                prop_nosuch=lambda b: False)


    def testTempValueColonTildeFalseZero(self):
        return self.doTestSimpleWithProperties('%(prop_false:~nontrue)s', 'nontrue',
                prop_false=lambda b: 0)

    def testTempValueColonTildeTrueZero(self):
        return self.doTestSimpleWithProperties('%(prop_true:~nontrue)s', True,
                prop_true=lambda b: 0)

    def testTempValueColonTildeNoneZero(self):
        return self.doTestSimpleWithProperties('%(prop_nosuch:~nontrue)s', 'nontrue',
                prop_nosuch=lambda b: 0)

    def testTempValueColonTildeFalseBlank(self):
        return self.doTestSimpleWithProperties('%(prop_false:~nontrue)s', 'nontrue',
                prop_false=lambda b: '')

    def testTempValueColonTildeTrueBlank(self):
        return self.doTestSimpleWithProperties('%(prop_true:~nontrue)s', True,
                prop_true=lambda b: '')

    def testTempValueColonTildeNoneBlank(self):
        return self.doTestSimpleWithProperties('%(prop_nosuch:~nontrue)s', 'nontrue',
                prop_nosuch=lambda b: '')

    def testTempValuePlusSetSet(self):
        return self.doTestSimpleWithProperties('%(prop_one:+set)s', 'set',
                prop_one=lambda b: 2)

    def testTempValuePlusUnsetSet(self):
        return self.doTestSimpleWithProperties('%(prop_nosuch:+set)s', 'set',
                prop_nosuch=lambda b: 1)


    def testTempValueColonTernaryTrue(self):
        return self.doTestSimpleWithProperties('%(prop_temp:?:present:missing)s', 'present',
                prop_temp=lambda b: True)

    def testTempValueColonTernaryFalse(self):
        return self.doTestSimpleWithProperties('%(prop_temp:?|present|missing)s', 'present',
                prop_temp=lambda b: False)

    def testTempValueColonTernaryHashTrue(self):
        return self.doTestSimpleWithProperties('%(prop_temp:#?|truish|falsish)s', 'truish',
                prop_temp=lambda b: 1)

    def testTempValueColonTernaryHashFalse(self):
        return self.doTestSimpleWithProperties('%(prop_temp:#?|truish|falsish)s', 'falsish',
                prop_nosuch=lambda b: 0)


class TestInterpolateConfigure(unittest.TestCase, ConfigErrorsMixin):
    """
    Test that Interpolate reports erros in the interpolation string
    at configure time.
    """

    def test_invalid_params(self):
        """
        Test that Interpolate rejects strings with both positional and keyword
        substitutionss.
        """
        self.assertRaises(ValueError, lambda :
                Interpolate("%s %(foo)s", 1, foo=2))
    test_invalid_params.skip = "Don't know how to test this."

    def test_positional_string_keyword_args(self):
        """
        """
        self.assertRaisesConfigError("keyword arguments passed to Interpolate "
                "but uses postional substitutions",
                lambda: Interpolate("%s", kwarg="test"))
    test_positional_string_keyword_args.skip = "Don't know how to test this."

    def test_invalid_selector(self):
        self.assertRaisesConfigError("invalid Interpolate selector 'garbage'",
                lambda: Interpolate("%(garbage:test)s"))

    def test_no_selector(self):
        self.assertRaisesConfigError("invalid Interpolate substitution without selector 'garbage'",
                lambda: Interpolate("%(garbage)s"))

    def test_invalid_default_type(self):
        self.assertRaisesConfigError("invalid Interpolate default type '@'",
                lambda: Interpolate("%(prop:some_prop:@wacky)s"))

    def test_nested_invalid_selector(self):
        self.assertRaisesConfigError("invalid Interpolate selector 'garbage'",
                lambda: Interpolate("%(prop:some_prop:~%(garbage:test)s)s"))

    def test_colon_ternary_missing_delimeter(self):
        self.assertRaisesConfigError("invalid Interpolate ternary expression 'one' with delimiter ':'",
                lambda: Interpolate("echo '%(prop:P:?:one)s'"))

    def test_colon_ternary_paren_delimiter(self):
        self.assertRaisesConfigError("invalid Interpolate ternary expression 'one(:)' with delimiter ':'",
                lambda: Interpolate("echo '%(prop:P:?:one(:))s'"))

    def test_colon_ternary_hash_bad_delimeter(self):
        self.assertRaisesConfigError("invalid Interpolate ternary expression 'one' with delimiter '|'",
                lambda: Interpolate("echo '%(prop:P:#?|one)s'"))

    def test_prop_invalid_character(self):
        self.assertRaisesConfigError("Property name must be alphanumeric for prop Interpolation 'a+a'",
                lambda: Interpolate("echo '%(prop:a+a)s'"))

    def test_kw_invalid_character(self):
        self.assertRaisesConfigError("Keyword must be alphanumeric for kw Interpolation 'a+a'",
                lambda: Interpolate("echo '%(kw:a+a)s'"))

    def test_src_codebase_invalid_character(self):
        self.assertRaisesConfigError("Codebase must be alphanumeric for src Interpolation 'a+a:a'",
                lambda: Interpolate("echo '%(src:a+a:a)s'"))

    def test_src_attr_invalid_character(self):
        self.assertRaisesConfigError("Attribute must be alphanumeric for src Interpolation 'a:a+a'",
                lambda: Interpolate("echo '%(src:a:a+a)s'"))


class TestInterpolatePositional(unittest.TestCase):
    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(self.props)

    def test_string(self):
        command = Interpolate("test %s", "one fish")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                        "test one fish")

    def test_twoString(self):
        command = Interpolate("test %s, %s", "one fish", "two fish")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                        "test one fish, two fish")

    def test_deferred(self):
        renderable = DeferredRenderable()
        command = Interpolate("echo '%s'", renderable)
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                            "echo 'red fish'")
        renderable.callback("red fish")
        return d

    def test_renderable(self):
        self.props.setProperty("buildername", "blue fish", "test")
        command = Interpolate("echo '%s'", Property("buildername"))
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                            "echo 'blue fish'")
        return d



class TestInterpolateProperties(unittest.TestCase):
    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(self.props)
    def test_properties(self):
        self.props.setProperty("buildername", "winbld", "test")
        command = Interpolate("echo buildby-%(prop:buildername)s")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo buildby-winbld")
        return d
        
    def test_property_not_set(self):
        command = Interpolate("echo buildby-%(prop:buildername)s")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo buildby-")
        return d

    def test_property_colon_minus(self):
        command = Interpolate("echo buildby-%(prop:buildername:-blddef)s")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo buildby-blddef")
        return d

    def test_property_colon_tilde_true(self):
        self.props.setProperty("buildername", "winbld", "test")
        command = Interpolate("echo buildby-%(prop:buildername:~blddef)s")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo buildby-winbld")
        return d

    def test_property_colon_tilde_false(self):
        self.props.setProperty("buildername", "", "test")
        command = Interpolate("echo buildby-%(prop:buildername:~blddef)s")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo buildby-blddef")
        return d

    def test_property_colon_plus(self):
        self.props.setProperty("project", "proj1", "test")
        command = Interpolate("echo %(prop:project:+projectdefined)s")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo projectdefined")
        return d

    def test_nested_property(self):
        self.props.setProperty("project", "so long!", "test")
        command = Interpolate("echo '%(prop:missing:~%(prop:project)s)s'")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                            "echo 'so long!'")
        return d

    def test_property_substitute_recursively(self):
        self.props.setProperty("project", "proj1", "test")
        command = Interpolate("echo '%(prop:no_such:-%(prop:project)s)s'")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo 'proj1'")
        return d

    def test_property_colon_ternary_present(self):
        self.props.setProperty("project", "proj1", "test")
        command = Interpolate("echo %(prop:project:?:defined:missing)s")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo defined")
        return d

    def test_property_colon_ternary_missing(self):
        command = Interpolate("echo %(prop:project:?|defined|missing)s")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo missing")
        return d

    def test_property_colon_ternary_hash_true(self):
        self.props.setProperty("project", "winbld", "test")
        command = Interpolate("echo buildby-%(prop:project:#?:T:F)s")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo buildby-T")
        return d

    def test_property_colon_ternary_hash_false(self):
        self.props.setProperty("project", "", "test")
        command = Interpolate("echo buildby-%(prop:project:#?|T|F)s")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo buildby-F")
        return d

    def test_property_colon_ternary_substitute_recursively_true(self):
        self.props.setProperty("P", "present", "test")
        self.props.setProperty("one", "proj1", "test")
        self.props.setProperty("two", "proj2", "test")
        command = Interpolate("echo '%(prop:P:?|%(prop:one)s|%(prop:two)s)s'")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo 'proj1'")
        return d

    def test_property_colon_ternary_substitute_recursively_false(self):
        self.props.setProperty("one", "proj1", "test")
        self.props.setProperty("two", "proj2", "test")
        command = Interpolate("echo '%(prop:P:?|%(prop:one)s|%(prop:two)s)s'")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo 'proj2'")
        return d

    def test_property_colon_ternary_substitute_recursively_delimited_true(self):
        self.props.setProperty("P", "present", "test")
        self.props.setProperty("one", "proj1", "test")
        self.props.setProperty("two", "proj2", "test")
        command = Interpolate("echo '%(prop:P:?|%(prop:one:?|true|false)s|%(prop:two:?|false|true)s)s'")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo 'true'")
        return d

    def test_property_colon_ternary_substitute_recursively_delimited_false(self):
        self.props.setProperty("one", "proj1", "test")
        self.props.setProperty("two", "proj2", "test")
        command = Interpolate("echo '%(prop:P:?|%(prop:one:?|true|false)s|%(prop:two:?|false|true)s)s'")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo 'false'")
        return d


class TestInterpolateSrc(unittest.TestCase):
    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(self.props)
        sa = FakeSource()
        sb = FakeSource()
        sc = FakeSource()
        
        sa.repository = 'cvs://A..'
        sa.codebase = 'cbA'
        sa.project = "Project"
        self.build.sources['cbA'] = sa
        
        sb.repository = 'cvs://B..'
        sb.codebase = 'cbB'
        sb.project = "Project"
        self.build.sources['cbB'] = sb
        
        sc.repository = 'cvs://C..'
        sc.codebase = 'cbC'
        sc.project = None
        self.build.sources['cbC'] = sc

    def test_src(self):
        command = Interpolate("echo %(src:cbB:repository)s")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo cvs://B..")
        return d

    def test_src_src(self):
        command = Interpolate("echo %(src:cbB:repository)s %(src:cbB:project)s")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo cvs://B.. Project")
        return d

    def test_src_attr_empty(self):
        command = Interpolate("echo %(src:cbC:project)s")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo ")
        return d

    def test_src_attr_codebase_notfound(self):
        command = Interpolate("echo %(src:unknown_codebase:project)s")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo ")
        return d

    def test_src_colon_plus_false(self):
        command = Interpolate("echo '%(src:cbD:project:+defaultrepo)s'")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo ''")
        return d

    def test_src_colon_plus_true(self):
        command = Interpolate("echo '%(src:cbB:project:+defaultrepo)s'")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo 'defaultrepo'")
        return d

    def test_src_colon_minus(self):
        command = Interpolate("echo %(src:cbB:nonattr:-defaultrepo)s")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo defaultrepo")
        return d

    def test_src_colon_minus_false(self):
        command = Interpolate("echo '%(src:cbC:project:-noproject)s'")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo ''")
        return d

    def test_src_colon_minus_true(self):
        command = Interpolate("echo '%(src:cbB:project:-noproject)s'")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo 'Project'")
        return d

    def test_src_colon_minus_codebase_notfound(self):
        command = Interpolate("echo '%(src:unknown_codebase:project:-noproject)s'")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo 'noproject'")
        return d

    def test_src_colon_tilde_true(self):
        command = Interpolate("echo '%(src:cbB:project:~noproject)s'")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo 'Project'")
        return d

    def test_src_colon_tilde_false(self):
        command = Interpolate("echo '%(src:cbC:project:~noproject)s'")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo 'noproject'")
        return d

    def test_src_colon_tilde_false_src_as_replacement(self):
        command = Interpolate("echo '%(src:cbC:project:~%(src:cbA:project)s)s'")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo 'Project'")
        return d

    def test_src_colon_tilde_codebase_notfound(self):
        command = Interpolate("echo '%(src:unknown_codebase:project:~noproject)s'")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo 'noproject'")
        return d


class TestInterpolateKwargs(unittest.TestCase):
    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(self.props)
        sa = FakeSource()

        sa.repository = 'cvs://A..'
        sa.codebase = 'cbA'
        sa.project = None
        sa.branch = "default"
        self.build.sources['cbA'] = sa

    def test_kwarg(self):
        command = Interpolate("echo %(kw:repository)s", repository = "cvs://A..")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo cvs://A..")
        return d

    def test_kwarg_kwarg(self):
        command = Interpolate("echo %(kw:repository)s %(kw:branch)s",
                              repository = "cvs://A..", branch = "default")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo cvs://A.. default")
        return d

    def test_kwarg_not_mapped(self):
        command = Interpolate("echo %(kw:repository)s", project = "projectA")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo ")
        return d

    def test_kwarg_colon_minus_not_available(self):
        command = Interpolate("echo %(kw:repository)s", project = "projectA")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo ")
        return d

    def test_kwarg_colon_minus_not_available_default(self):
        command = Interpolate("echo %(kw:repository:-cvs://A..)s", project = "projectA")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo cvs://A..")
        return d

    def test_kwarg_colon_minus_available(self):
        command = Interpolate("echo %(kw:repository:-cvs://A..)s", repository = "cvs://B..")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo cvs://B..")
        return d

    def test_kwarg_colon_tilde_true(self):
        command = Interpolate("echo %(kw:repository:~cvs://B..)s", repository = "cvs://A..")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo cvs://A..")
        return d

    def test_kwarg_colon_tilde_false(self):
        command = Interpolate("echo %(kw:repository:~cvs://B..)s", repository = "")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo cvs://B..")
        return d

    def test_kwarg_colon_tilde_none(self):
        command = Interpolate("echo %(kw:repository:~cvs://B..)s", repository = None)
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo cvs://B..")
        return d

    def test_kwarg_colon_plus_false(self):
        command = Interpolate("echo %(kw:repository:+cvs://B..)s", project = "project")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo ")
        return d

    def test_kwarg_colon_plus_true(self):
        command = Interpolate("echo %(kw:repository:+cvs://B..)s", repository = None)
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo cvs://B..")
        return d

    def test_kwargs_colon_minus_false_src_as_replacement(self):
        command = Interpolate("echo '%(kw:text:-%(src:cbA:branch)s)s'", notext='ddd')
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "echo 'default'")
        return d

    def test_kwargs_renderable(self):
        command = Interpolate("echo '%(kw:test)s'", test = FakeRenderable('testing'))
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                            "echo 'testing'")
        return d

    def test_kwargs_deferred(self):
        renderable = DeferredRenderable()
        command = Interpolate("echo '%(kw:test)s'", test = renderable)
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                            "echo 'testing'")
        renderable.callback('testing')
        return d

    def test_kwarg_deferred(self):
        renderable = DeferredRenderable()
        command = Interpolate("echo '%(kw:project)s'", project=renderable)
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                            "echo 'testing'")
        renderable.callback('testing')
        return d

    def test_nested_kwarg_deferred(self):
        renderable = DeferredRenderable()
        command = Interpolate("echo '%(kw:missing:~%(kw:fishy)s)s'", missing=renderable, fishy="so long!")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                            "echo 'so long!'")
        renderable.callback(False)
        return d

class TestWithProperties(unittest.TestCase):

    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(self.props)

    def testInvalidParams(self):
        self.assertRaises(ValueError, lambda :
                WithProperties("%s %(foo)s", 1, foo=2))

    def testBasic(self):
        # test basic substitution with WithProperties
        self.props.setProperty("revision", "47", "test")
        command = WithProperties("build-%s.tar.gz", "revision")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "build-47.tar.gz")
        return d

    def testDict(self):
        # test dict-style substitution with WithProperties
        self.props.setProperty("other", "foo", "test")
        command = WithProperties("build-%(other)s.tar.gz")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "build-foo.tar.gz")
        return d

    def testDictColonMinus(self):
        # test dict-style substitution with WithProperties
        self.props.setProperty("prop1", "foo", "test")
        command = WithProperties("build-%(prop1:-empty)s-%(prop2:-empty)s.tar.gz")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "build-foo-empty.tar.gz")
        return d

    def testDictColonPlus(self):
        # test dict-style substitution with WithProperties
        self.props.setProperty("prop1", "foo", "test")
        command = WithProperties("build-%(prop1:+exists)s-%(prop2:+exists)s.tar.gz")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "build-exists-.tar.gz")
        return d

    def testDictColonTernary(self):
        # test dict-style substitution with WithProperties
        self.props.setProperty("prop1", "foo", "test")
        command = WithProperties("build-%(prop1:?:exists:missing)s-%(prop2:?:exists:missing)s.tar.gz")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "build-exists-missing.tar.gz")
        return d

    def testEmpty(self):
        # None should render as ''
        self.props.setProperty("empty", None, "test")
        command = WithProperties("build-%(empty)s.tar.gz")
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             "build-.tar.gz")
        return d

    def testRecursiveList(self):
        self.props.setProperty("x", 10, "test")
        self.props.setProperty("y", 20, "test")
        command = [ WithProperties("%(x)s %(y)s"), "and",
                    WithProperties("%(y)s %(x)s") ]
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             ["10 20", "and", "20 10"])
        return d

    def testRecursiveTuple(self):
        self.props.setProperty("x", 10, "test")
        self.props.setProperty("y", 20, "test")
        command = ( WithProperties("%(x)s %(y)s"), "and",
                    WithProperties("%(y)s %(x)s") )
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             ("10 20", "and", "20 10"))
        return d

    def testRecursiveDict(self):
        self.props.setProperty("x", 10, "test")
        self.props.setProperty("y", 20, "test")
        command = { WithProperties("%(x)s %(y)s") : 
                    WithProperties("%(y)s %(x)s") }
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual,
                             {"10 20" : "20 10"})
        return d

    def testLambdaSubst(self):
        command = WithProperties('%(foo)s', foo=lambda _: 'bar')
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual, 'bar')
        return d

    def testLambdaHasattr(self):
        command = WithProperties('%(foo)s',
                foo=lambda b : b.hasProperty('x') and 'x' or 'y')
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual, 'y')
        return d

    def testLambdaOverride(self):
        self.props.setProperty('x', 10, 'test')
        command = WithProperties('%(x)s', x=lambda _: 20)
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual, '20')
        return d

    def testLambdaCallable(self):
        self.assertRaises(ValueError, lambda: WithProperties('%(foo)s', foo='bar'))

    def testLambdaUseExisting(self):
        self.props.setProperty('x', 10, 'test')
        self.props.setProperty('y', 20, 'test')
        command = WithProperties('%(z)s', z=lambda props: props.getProperty('x') + props.getProperty('y'))
        d = self.build.render(command)
        d.addCallback(self.failUnlessEqual, '30')
        return d

class TestProperties(unittest.TestCase):
    def setUp(self):
        self.props = Properties()

    def testDictBehavior(self):
        # note that dictionary-like behavior is deprecated and not exposed to
        # users!
        self.props.setProperty("do-tests", 1, "scheduler")
        self.props.setProperty("do-install", 2, "scheduler")

        self.assert_(self.props.has_key('do-tests'))
        self.failUnlessEqual(self.props['do-tests'], 1)
        self.failUnlessEqual(self.props['do-install'], 2)
        self.assertRaises(KeyError, lambda : self.props['do-nothing'])
        self.failUnlessEqual(self.props.getProperty('do-install'), 2)
        self.assertIn('do-tests', self.props)
        self.assertNotIn('missing-do-tests', self.props)

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

    def testUpdateRuntime(self):
        self.props.setProperty("x", 24, "old")
        newprops = { 'a' : 1, 'b' : 2 }
        self.props.update(newprops, "new", runtime=True)

        self.failUnlessEqual(self.props.getProperty('x'), 24)
        self.failUnlessEqual(self.props.getPropertySource('x'), 'old')
        self.failUnlessEqual(self.props.getProperty('a'), 1)
        self.failUnlessEqual(self.props.getPropertySource('a'), 'new')
        self.assertEqual(self.props.runtime, set(['a', 'b']))

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

    @compat.usesFlushWarnings
    def test_setProperty_notJsonable(self):
        self.props.setProperty("project", FakeRenderable('testing'), "test")
        self.props.setProperty("project", object, "test")
        self.assertEqual(len(self.flushWarnings([self.test_setProperty_notJsonable])), 2)

    # IProperties methods

    def test_getProperty(self):
        self.props.properties['p1'] = (['p', 1], 'test')
        self.assertEqual(self.props.getProperty('p1'), ['p', 1])

    def test_getProperty_default_None(self):
        self.assertEqual(self.props.getProperty('p1'), None)

    def test_getProperty_default(self):
        self.assertEqual(self.props.getProperty('p1', 2), 2)

    def test_hasProperty_false(self):
        self.assertFalse(self.props.hasProperty('x'))

    def test_hasProperty_true(self):
        self.props.properties['x'] = (False, 'test')
        self.assertTrue(self.props.hasProperty('x'))

    def test_has_key_false(self):
        self.assertFalse(self.props.has_key('x'))

    def test_setProperty(self):
        self.props.setProperty('x', 'y', 'test')
        self.assertEqual(self.props.properties['x'], ('y', 'test'))
        self.assertNotIn('x', self.props.runtime)

    def test_setProperty_runtime(self):
        self.props.setProperty('x', 'y', 'test', runtime=True)
        self.assertEqual(self.props.properties['x'], ('y', 'test'))
        self.assertIn('x', self.props.runtime)

    def test_setProperty_no_source(self):
        self.assertRaises(TypeError, lambda :
                self.props.setProperty('x', 'y'))

    def test_getProperties(self):
        self.assertIdentical(self.props.getProperties(), self.props)

    def test_getBuild(self):
        self.assertIdentical(self.props.getBuild(), self.props.build)

    def test_render(self):
        class FakeRenderable(object):
            implements(IRenderable)
            def getRenderingFor(self, props):
                return props.getProperty('x') + 'z'
        self.props.setProperty('x', 'y', 'test')
        d = self.props.render(FakeRenderable())
        d.addCallback(self.assertEqual, 'yz')
        return d


class MyPropertiesThing(PropertiesMixin):
    set_runtime_properties = True

def adaptMyProperties(mp):
    return mp.properties

components.registerAdapter(adaptMyProperties, MyPropertiesThing, IProperties)


class TestPropertiesMixin(unittest.TestCase):

    def setUp(self):
        self.mp = MyPropertiesThing()
        self.mp.properties = mock.Mock()

    def test_getProperty(self):
        self.mp.getProperty('abc')
        self.mp.properties.getProperty.assert_called_with('abc', None)

    def xtest_getProperty_default(self):
        self.mp.getProperty('abc', 'def')
        self.mp.properties.getProperty.assert_called_with('abc', 'def')

    def test_hasProperty(self):
        self.mp.properties.hasProperty.return_value = True
        self.assertTrue(self.mp.hasProperty('abc'))
        self.mp.properties.hasProperty.assert_called_with('abc')

    def test_has_key(self):
        self.mp.properties.hasProperty.return_value = True
        self.assertTrue(self.mp.has_key('abc'))
        self.mp.properties.hasProperty.assert_called_with('abc')

    def test_setProperty(self):
        self.mp.setProperty('abc', 'def', 'src')
        self.mp.properties.setProperty.assert_called_with('abc', 'def', 'src',
                                                          runtime=True)

    def test_setProperty_no_source(self):
        # this compatibility is maintained for old code
        self.mp.setProperty('abc', 'def')
        self.mp.properties.setProperty.assert_called_with('abc', 'def',
                                                    'Unknown', runtime=True)

    def test_render(self):
        self.mp.render([1,2])
        self.mp.properties.render.assert_called_with([1,2])

class TestProperty(unittest.TestCase):

    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(self.props)

    def testIntProperty(self):
        self.props.setProperty("do-tests", 1, "scheduler")
        value = Property("do-tests")

        d = self.build.render(value)
        d.addCallback(self.failUnlessEqual,
                1)
        return d

    def testStringProperty(self):
        self.props.setProperty("do-tests", "string", "scheduler")
        value = Property("do-tests")

        d = self.build.render(value)
        d.addCallback(self.failUnlessEqual,
                "string")
        return d

    def testMissingProperty(self):
        value = Property("do-tests")

        d = self.build.render(value)
        d.addCallback(self.failUnlessEqual,
                None)
        return d

    def testDefaultValue(self):
        value = Property("do-tests", default="Hello!")

        d = self.build.render(value)
        d.addCallback(self.failUnlessEqual,
                "Hello!")
        return d

    def testDefaultValueNested(self):
        self.props.setProperty("xxx", 'yyy', "scheduler")
        value = Property("do-tests",
                default=WithProperties("a-%(xxx)s-b"))

        d = self.build.render(value)
        d.addCallback(self.failUnlessEqual,
                "a-yyy-b")
        return d

    def testIgnoreDefaultValue(self):
        self.props.setProperty("do-tests", "string", "scheduler")
        value = Property("do-tests", default="Hello!")

        d = self.build.render(value)
        d.addCallback(self.failUnlessEqual,
                "string")
        return d

    def testIgnoreFalseValue(self):
        self.props.setProperty("do-tests-string", "", "scheduler")
        self.props.setProperty("do-tests-int", 0, "scheduler")
        self.props.setProperty("do-tests-list", [], "scheduler")
        self.props.setProperty("do-tests-None", None, "scheduler")

        value = [ Property("do-tests-string", default="Hello!"),
                  Property("do-tests-int", default="Hello!"),
                  Property("do-tests-list", default="Hello!"),
                  Property("do-tests-None", default="Hello!") ]

        d = self.build.render(value)
        d.addCallback(self.failUnlessEqual,
                ["Hello!"] * 4)
        return d

    def testDefaultWhenFalse(self):
        self.props.setProperty("do-tests-string", "", "scheduler")
        self.props.setProperty("do-tests-int", 0, "scheduler")
        self.props.setProperty("do-tests-list", [], "scheduler")
        self.props.setProperty("do-tests-None", None, "scheduler")

        value = [ Property("do-tests-string", default="Hello!", defaultWhenFalse=False),
                  Property("do-tests-int", default="Hello!", defaultWhenFalse=False),
                  Property("do-tests-list", default="Hello!", defaultWhenFalse=False),
                  Property("do-tests-None", default="Hello!", defaultWhenFalse=False) ]

        d = self.build.render(value)
        d.addCallback(self.failUnlessEqual,
                ["", 0, [], None])
        return d

    def testDeferredDefault(self):
        default = DeferredRenderable()
        value = Property("no-such-property", default)
        d = self.build.render(value)
        d.addCallback(self.failUnlessEqual,
                "default-value")
        default.callback("default-value")
        return d


class TestRenderalbeAdapters(unittest.TestCase):
    """
    Tests for list, tuple and dict renderers.
    """

    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(self.props)


    def test_list_deferred(self):
        r1 = DeferredRenderable()
        r2 = DeferredRenderable()
        d = self.build.render([r1, r2])
        d.addCallback(self.failUnlessEqual,
                ["lispy", "lists"])
        r2.callback("lists")
        r1.callback("lispy")
        return d


    def test_tuple_deferred(self):
        r1 = DeferredRenderable()
        r2 = DeferredRenderable()
        d = self.build.render((r1, r2))
        d.addCallback(self.failUnlessEqual,
                ("totally", "tupled"))
        r2.callback("tupled")
        r1.callback("totally")
        return d


    def test_dict(self):
        r1 = DeferredRenderable()
        r2 = DeferredRenderable()
        k1 = DeferredRenderable()
        k2 = DeferredRenderable()
        d = self.build.render({k1: r1, k2: r2})
        d.addCallback(self.failUnlessEqual,
                {"lock": "load", "dict": "lookup"})
        k1.callback("lock")
        r1.callback("load")
        k2.callback("dict")
        r2.callback("lookup")
        return d
