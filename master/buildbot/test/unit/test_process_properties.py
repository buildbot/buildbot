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

from copy import deepcopy

import mock

from twisted.internet import defer
from twisted.python import components
from twisted.trial import unittest
from zope.interface import implementer

from buildbot.interfaces import IProperties
from buildbot.interfaces import IRenderable
from buildbot.process.buildrequest import TempChange
from buildbot.process.buildrequest import TempSourceStamp
from buildbot.process.properties import FlattenList
from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.process.properties import PropertiesMixin
from buildbot.process.properties import Property
from buildbot.process.properties import Transform
from buildbot.process.properties import WithProperties
from buildbot.process.properties import _Lazy
from buildbot.process.properties import _Lookup
from buildbot.process.properties import _SourceStampDict
from buildbot.process.properties import renderer
from buildbot.test.fake.fakebuild import FakeBuild
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.properties import ConstantRenderable


class FakeSource:

    def __init__(self):
        self.branch = None
        self.codebase = ''
        self.project = ''
        self.repository = ''
        self.revision = None

    def asDict(self):
        ds = {
            'branch': self.branch,
            'codebase': self.codebase,
            'project': self.project,
            'repository': self.repository,
            'revision': self.revision
        }
        return ds


@implementer(IRenderable)
class DeferredRenderable:

    def __init__(self):
        self.d = defer.Deferred()

    def getRenderingFor(self, build):
        return self.d

    def callback(self, value):
        self.d.callback(value)


class TestPropertyMap(unittest.TestCase):

    """
    Test the behavior of PropertyMap, using the external interface
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
        self.build = FakeBuild(props=self.props)

    @defer.inlineCallbacks
    def doTestSimpleWithProperties(self, fmtstring, expect, **kwargs):
        res = yield self.build.render(WithProperties(fmtstring, **kwargs))
        self.assertEqual(res, "%s" % expect)

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

    @defer.inlineCallbacks
    def testClearTempValues(self):
        yield self.doTestSimpleWithProperties('', '',
                                            prop_temp=lambda b: 'present')
        yield self.doTestSimpleWithProperties('%(prop_temp:+present)s', '')

    def testTempValue(self):
        return self.doTestSimpleWithProperties('%(prop_temp)s', 'present',
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


class TestInterpolateConfigure(unittest.TestCase, ConfigErrorsMixin):

    """
    Test that Interpolate reports errors in the interpolation string
    at configure time.
    """

    def test_invalid_args_and_kwargs(self):
        with self.assertRaisesConfigError("Interpolate takes either positional"):
            Interpolate("%s %(foo)s", 1, foo=2)

    def test_invalid_selector(self):
        with self.assertRaisesConfigError(
                "invalid Interpolate selector 'garbage'"):
            Interpolate("%(garbage:test)s")

    def test_no_selector(self):
        with self.assertRaisesConfigError(
                "invalid Interpolate substitution without selector 'garbage'"):
            Interpolate("%(garbage)s")

    def test_invalid_default_type(self):
        with self.assertRaisesConfigError(
                "invalid Interpolate default type '@'"):
            Interpolate("%(prop:some_prop:@wacky)s")

    def test_nested_invalid_selector(self):
        with self.assertRaisesConfigError(
                "invalid Interpolate selector 'garbage'"):
            Interpolate("%(prop:some_prop:~%(garbage:test)s)s")

    def test_colon_ternary_missing_delimeter(self):
        with self.assertRaisesConfigError(
                "invalid Interpolate ternary expression 'one' with delimiter ':'"):
            Interpolate("echo '%(prop:P:?:one)s'")

    def test_colon_ternary_paren_delimiter(self):
        with self.assertRaisesConfigError(
                "invalid Interpolate ternary expression 'one(:)' with delimiter ':'"):
            Interpolate("echo '%(prop:P:?:one(:))s'")

    def test_colon_ternary_hash_bad_delimeter(self):
        with self.assertRaisesConfigError(
                "invalid Interpolate ternary expression 'one' with delimiter '|'"):
            Interpolate("echo '%(prop:P:#?|one)s'")

    def test_prop_invalid_character(self):
        with self.assertRaisesConfigError(
                "Property name must be alphanumeric for prop Interpolation 'a+a'"):
            Interpolate("echo '%(prop:a+a)s'")

    def test_kw_invalid_character(self):
        with self.assertRaisesConfigError(
                "Keyword must be alphanumeric for kw Interpolation 'a+a'"):
            Interpolate("echo '%(kw:a+a)s'")

    def test_src_codebase_invalid_character(self):
        with self.assertRaisesConfigError(
                "Codebase must be alphanumeric for src Interpolation 'a+a:a'"):
            Interpolate("echo '%(src:a+a:a)s'")

    def test_src_attr_invalid_character(self):
        with self.assertRaisesConfigError(
                "Attribute must be alphanumeric for src Interpolation 'a:a+a'"):
            Interpolate("echo '%(src:a:a+a)s'")

    def test_src_missing_attr(self):
        with self.assertRaisesConfigError(
                "Must specify both codebase and attr"):
            Interpolate("echo '%(src:a)s'")


class TestInterpolatePositional(unittest.TestCase):

    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(props=self.props)

    @defer.inlineCallbacks
    def test_string(self):
        command = Interpolate("test %s", "one fish")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "test one fish")

    @defer.inlineCallbacks
    def test_twoString(self):
        command = Interpolate("test %s, %s", "one fish", "two fish")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "test one fish, two fish")

    def test_deferred(self):
        renderable = DeferredRenderable()
        command = Interpolate("echo '%s'", renderable)
        d = self.build.render(command)
        d.addCallback(self.assertEqual,
                      "echo 'red fish'")
        renderable.callback("red fish")
        return d

    @defer.inlineCallbacks
    def test_renderable(self):
        self.props.setProperty("buildername", "blue fish", "test")
        command = Interpolate("echo '%s'", Property("buildername"))
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'blue fish'")


class TestInterpolateProperties(unittest.TestCase):

    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(props=self.props)

    @defer.inlineCallbacks
    def test_properties(self):
        self.props.setProperty("buildername", "winbld", "test")
        command = Interpolate("echo buildby-%(prop:buildername)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo buildby-winbld")

    @defer.inlineCallbacks
    def test_properties_newline(self):
        self.props.setProperty("buildername", "winbld", "test")
        command = Interpolate("aa\n%(prop:buildername)s\nbb")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "aa\nwinbld\nbb")

    @defer.inlineCallbacks
    def test_property_not_set(self):
        command = Interpolate("echo buildby-%(prop:buildername)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo buildby-")

    @defer.inlineCallbacks
    def test_property_colon_minus(self):
        command = Interpolate("echo buildby-%(prop:buildername:-blddef)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo buildby-blddef")

    @defer.inlineCallbacks
    def test_deepcopy(self):
        # After a deepcopy, Interpolate instances used to lose track
        # that they didn't have a ``hasKey`` value
        # see http://trac.buildbot.net/ticket/3505
        self.props.setProperty("buildername", "linux4", "test")
        command = deepcopy(
            Interpolate("echo buildby-%(prop:buildername:-blddef)s"))
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo buildby-linux4")

    @defer.inlineCallbacks
    def test_property_colon_tilde_true(self):
        self.props.setProperty("buildername", "winbld", "test")
        command = Interpolate("echo buildby-%(prop:buildername:~blddef)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo buildby-winbld")

    @defer.inlineCallbacks
    def test_property_colon_tilde_false(self):
        self.props.setProperty("buildername", "", "test")
        command = Interpolate("echo buildby-%(prop:buildername:~blddef)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo buildby-blddef")

    @defer.inlineCallbacks
    def test_property_colon_plus(self):
        self.props.setProperty("project", "proj1", "test")
        command = Interpolate("echo %(prop:project:+projectdefined)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo projectdefined")

    @defer.inlineCallbacks
    def test_nested_property(self):
        self.props.setProperty("project", "so long!", "test")
        command = Interpolate("echo '%(prop:missing:~%(prop:project)s)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'so long!'")

    @defer.inlineCallbacks
    def test_property_substitute_recursively(self):
        self.props.setProperty("project", "proj1", "test")
        command = Interpolate("echo '%(prop:no_such:-%(prop:project)s)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'proj1'")

    @defer.inlineCallbacks
    def test_property_colon_ternary_present(self):
        self.props.setProperty("project", "proj1", "test")
        command = Interpolate("echo %(prop:project:?:defined:missing)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo defined")

    @defer.inlineCallbacks
    def test_property_colon_ternary_missing(self):
        command = Interpolate("echo %(prop:project:?|defined|missing)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo missing")

    @defer.inlineCallbacks
    def test_property_colon_ternary_hash_true(self):
        self.props.setProperty("project", "winbld", "test")
        command = Interpolate("echo buildby-%(prop:project:#?:T:F)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo buildby-T")

    @defer.inlineCallbacks
    def test_property_colon_ternary_hash_false(self):
        self.props.setProperty("project", "", "test")
        command = Interpolate("echo buildby-%(prop:project:#?|T|F)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo buildby-F")

    @defer.inlineCallbacks
    def test_property_colon_ternary_substitute_recursively_true(self):
        self.props.setProperty("P", "present", "test")
        self.props.setProperty("one", "proj1", "test")
        self.props.setProperty("two", "proj2", "test")
        command = Interpolate("echo '%(prop:P:?|%(prop:one)s|%(prop:two)s)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'proj1'")

    @defer.inlineCallbacks
    def test_property_colon_ternary_substitute_recursively_false(self):
        self.props.setProperty("one", "proj1", "test")
        self.props.setProperty("two", "proj2", "test")
        command = Interpolate("echo '%(prop:P:?|%(prop:one)s|%(prop:two)s)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'proj2'")

    @defer.inlineCallbacks
    def test_property_colon_ternary_substitute_recursively_delimited_true(self):
        self.props.setProperty("P", "present", "test")
        self.props.setProperty("one", "proj1", "test")
        self.props.setProperty("two", "proj2", "test")
        command = Interpolate(
            "echo '%(prop:P:?|%(prop:one:?|true|false)s|%(prop:two:?|false|true)s)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'true'")

    @defer.inlineCallbacks
    def test_property_colon_ternary_substitute_recursively_delimited_false(self):
        self.props.setProperty("one", "proj1", "test")
        self.props.setProperty("two", "proj2", "test")
        command = Interpolate(
            "echo '%(prop:P:?|%(prop:one:?|true|false)s|%(prop:two:?|false|true)s)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'false'")


class TestInterpolateSrc(unittest.TestCase):

    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(props=self.props)
        sa = FakeSource()
        wfb = FakeSource()
        sc = FakeSource()

        sa.repository = 'cvs://A..'
        sa.codebase = 'cbA'
        sa.project = "Project"
        self.build.sources['cbA'] = sa

        wfb.repository = 'cvs://B..'
        wfb.codebase = 'cbB'
        wfb.project = "Project"
        self.build.sources['cbB'] = wfb

        sc.repository = 'cvs://C..'
        sc.codebase = 'cbC'
        sc.project = None
        self.build.sources['cbC'] = sc

    @defer.inlineCallbacks
    def test_src(self):
        command = Interpolate("echo %(src:cbB:repository)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://B..")

    @defer.inlineCallbacks
    def test_src_src(self):
        command = Interpolate(
            "echo %(src:cbB:repository)s %(src:cbB:project)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://B.. Project")

    @defer.inlineCallbacks
    def test_src_attr_empty(self):
        command = Interpolate("echo %(src:cbC:project)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo ")

    @defer.inlineCallbacks
    def test_src_attr_codebase_notfound(self):
        command = Interpolate("echo %(src:unknown_codebase:project)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo ")

    @defer.inlineCallbacks
    def test_src_colon_plus_false(self):
        command = Interpolate("echo '%(src:cbD:project:+defaultrepo)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo ''")

    @defer.inlineCallbacks
    def test_src_colon_plus_true(self):
        command = Interpolate("echo '%(src:cbB:project:+defaultrepo)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'defaultrepo'")

    @defer.inlineCallbacks
    def test_src_colon_minus(self):
        command = Interpolate("echo %(src:cbB:nonattr:-defaultrepo)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo defaultrepo")

    @defer.inlineCallbacks
    def test_src_colon_minus_false(self):
        command = Interpolate("echo '%(src:cbC:project:-noproject)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo ''")

    @defer.inlineCallbacks
    def test_src_colon_minus_true(self):
        command = Interpolate("echo '%(src:cbB:project:-noproject)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'Project'")

    @defer.inlineCallbacks
    def test_src_colon_minus_codebase_notfound(self):
        command = Interpolate(
            "echo '%(src:unknown_codebase:project:-noproject)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'noproject'")

    @defer.inlineCallbacks
    def test_src_colon_tilde_true(self):
        command = Interpolate("echo '%(src:cbB:project:~noproject)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'Project'")

    @defer.inlineCallbacks
    def test_src_colon_tilde_false(self):
        command = Interpolate("echo '%(src:cbC:project:~noproject)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'noproject'")

    @defer.inlineCallbacks
    def test_src_colon_tilde_false_src_as_replacement(self):
        command = Interpolate(
            "echo '%(src:cbC:project:~%(src:cbA:project)s)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'Project'")

    @defer.inlineCallbacks
    def test_src_colon_tilde_codebase_notfound(self):
        command = Interpolate(
            "echo '%(src:unknown_codebase:project:~noproject)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'noproject'")


class TestInterpolateKwargs(unittest.TestCase):

    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(props=self.props)
        sa = FakeSource()

        sa.repository = 'cvs://A..'
        sa.codebase = 'cbA'
        sa.project = None
        sa.branch = "default"
        self.build.sources['cbA'] = sa

    @defer.inlineCallbacks
    def test_kwarg(self):
        command = Interpolate("echo %(kw:repository)s", repository="cvs://A..")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://A..")

    @defer.inlineCallbacks
    def test_kwarg_kwarg(self):
        command = Interpolate("echo %(kw:repository)s %(kw:branch)s",
                              repository="cvs://A..", branch="default")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://A.. default")

    @defer.inlineCallbacks
    def test_kwarg_not_mapped(self):
        command = Interpolate("echo %(kw:repository)s", project="projectA")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo ")

    @defer.inlineCallbacks
    def test_kwarg_colon_minus_not_available(self):
        command = Interpolate("echo %(kw:repository)s", project="projectA")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo ")

    @defer.inlineCallbacks
    def test_kwarg_colon_minus_not_available_default(self):
        command = Interpolate(
            "echo %(kw:repository:-cvs://A..)s", project="projectA")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://A..")

    @defer.inlineCallbacks
    def test_kwarg_colon_minus_available(self):
        command = Interpolate(
            "echo %(kw:repository:-cvs://A..)s", repository="cvs://B..")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://B..")

    @defer.inlineCallbacks
    def test_kwarg_colon_tilde_true(self):
        command = Interpolate(
            "echo %(kw:repository:~cvs://B..)s", repository="cvs://A..")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://A..")

    @defer.inlineCallbacks
    def test_kwarg_colon_tilde_false(self):
        command = Interpolate(
            "echo %(kw:repository:~cvs://B..)s", repository="")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://B..")

    @defer.inlineCallbacks
    def test_kwarg_colon_tilde_none(self):
        command = Interpolate(
            "echo %(kw:repository:~cvs://B..)s", repository=None)
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://B..")

    @defer.inlineCallbacks
    def test_kwarg_colon_plus_false(self):
        command = Interpolate(
            "echo %(kw:repository:+cvs://B..)s", project="project")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo ")

    @defer.inlineCallbacks
    def test_kwarg_colon_plus_true(self):
        command = Interpolate(
            "echo %(kw:repository:+cvs://B..)s", repository=None)
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://B..")

    @defer.inlineCallbacks
    def test_kwargs_colon_minus_false_src_as_replacement(self):
        command = Interpolate(
            "echo '%(kw:text:-%(src:cbA:branch)s)s'", notext='ddd')
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'default'")

    @defer.inlineCallbacks
    def test_kwargs_renderable(self):
        command = Interpolate(
            "echo '%(kw:test)s'", test=ConstantRenderable('testing'))
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'testing'")

    def test_kwargs_deferred(self):
        renderable = DeferredRenderable()
        command = Interpolate("echo '%(kw:test)s'", test=renderable)
        d = self.build.render(command)
        d.addCallback(self.assertEqual,
                      "echo 'testing'")
        renderable.callback('testing')

    def test_kwarg_deferred(self):
        renderable = DeferredRenderable()
        command = Interpolate("echo '%(kw:project)s'", project=renderable)
        d = self.build.render(command)
        d.addCallback(self.assertEqual,
                      "echo 'testing'")
        renderable.callback('testing')

    def test_nested_kwarg_deferred(self):
        renderable = DeferredRenderable()
        command = Interpolate(
            "echo '%(kw:missing:~%(kw:fishy)s)s'", missing=renderable, fishy="so long!")
        d = self.build.render(command)
        d.addCallback(self.assertEqual,
                      "echo 'so long!'")
        renderable.callback(False)
        return d


class TestWithProperties(unittest.TestCase):

    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(props=self.props)

    def testInvalidParams(self):
        with self.assertRaises(ValueError):
            WithProperties("%s %(foo)s", 1, foo=2)

    @defer.inlineCallbacks
    def testBasic(self):
        # test basic substitution with WithProperties
        self.props.setProperty("revision", "47", "test")
        command = WithProperties("build-%s.tar.gz", "revision")
        res = yield self.build.render(command)
        self.assertEqual(res, "build-47.tar.gz")

    @defer.inlineCallbacks
    def testDict(self):
        # test dict-style substitution with WithProperties
        self.props.setProperty("other", "foo", "test")
        command = WithProperties("build-%(other)s.tar.gz")
        res = yield self.build.render(command)
        self.assertEqual(res, "build-foo.tar.gz")

    @defer.inlineCallbacks
    def testDictColonMinus(self):
        # test dict-style substitution with WithProperties
        self.props.setProperty("prop1", "foo", "test")
        command = WithProperties(
            "build-%(prop1:-empty)s-%(prop2:-empty)s.tar.gz")
        res = yield self.build.render(command)
        self.assertEqual(res, "build-foo-empty.tar.gz")

    @defer.inlineCallbacks
    def testDictColonPlus(self):
        # test dict-style substitution with WithProperties
        self.props.setProperty("prop1", "foo", "test")
        command = WithProperties(
            "build-%(prop1:+exists)s-%(prop2:+exists)s.tar.gz")
        res = yield self.build.render(command)
        self.assertEqual(res, "build-exists-.tar.gz")

    @defer.inlineCallbacks
    def testEmpty(self):
        # None should render as ''
        self.props.setProperty("empty", None, "test")
        command = WithProperties("build-%(empty)s.tar.gz")
        res = yield self.build.render(command)
        self.assertEqual(res, "build-.tar.gz")

    @defer.inlineCallbacks
    def testRecursiveList(self):
        self.props.setProperty("x", 10, "test")
        self.props.setProperty("y", 20, "test")
        command = [WithProperties("%(x)s %(y)s"), "and",
                   WithProperties("%(y)s %(x)s")]
        res = yield self.build.render(command)
        self.assertEqual(res, ["10 20", "and", "20 10"])

    @defer.inlineCallbacks
    def testRecursiveTuple(self):
        self.props.setProperty("x", 10, "test")
        self.props.setProperty("y", 20, "test")
        command = (WithProperties("%(x)s %(y)s"), "and",
                   WithProperties("%(y)s %(x)s"))
        res = yield self.build.render(command)
        self.assertEqual(res, ("10 20", "and", "20 10"))

    @defer.inlineCallbacks
    def testRecursiveDict(self):
        self.props.setProperty("x", 10, "test")
        self.props.setProperty("y", 20, "test")
        command = {WithProperties("%(x)s %(y)s"):
                   WithProperties("%(y)s %(x)s")}
        res = yield self.build.render(command)
        self.assertEqual(res, {"10 20": "20 10"})

    @defer.inlineCallbacks
    def testLambdaSubst(self):
        command = WithProperties('%(foo)s', foo=lambda _: 'bar')
        res = yield self.build.render(command)
        self.assertEqual(res, 'bar')

    @defer.inlineCallbacks
    def testLambdaHasattr(self):
        command = WithProperties('%(foo)s',
                                 foo=lambda b: b.hasProperty('x') and 'x' or 'y')
        res = yield self.build.render(command)
        self.assertEqual(res, 'y')

    @defer.inlineCallbacks
    def testLambdaOverride(self):
        self.props.setProperty('x', 10, 'test')
        command = WithProperties('%(x)s', x=lambda _: 20)
        res = yield self.build.render(command)
        self.assertEqual(res, '20')

    def testLambdaCallable(self):
        with self.assertRaises(ValueError):
            WithProperties('%(foo)s', foo='bar')

    @defer.inlineCallbacks
    def testLambdaUseExisting(self):
        self.props.setProperty('x', 10, 'test')
        self.props.setProperty('y', 20, 'test')
        command = WithProperties(
            '%(z)s', z=lambda props: props.getProperty('x') + props.getProperty('y'))
        res = yield self.build.render(command)
        self.assertEqual(res, '30')

    @defer.inlineCallbacks
    def testColon(self):
        self.props.setProperty('some:property', 10, 'test')
        command = WithProperties('%(some:property:-with-default)s')
        res = yield self.build.render(command)
        self.assertEqual(res, '10')

    @defer.inlineCallbacks
    def testColon_default(self):
        command = WithProperties('%(some:property:-with-default)s')
        res = yield self.build.render(command)
        self.assertEqual(res, 'with-default')

    @defer.inlineCallbacks
    def testColon_colon(self):
        command = WithProperties('%(some:property:-with:default)s')
        res = yield self.build.render(command)
        self.assertEqual(res, 'with:default')


class TestProperties(unittest.TestCase):

    def setUp(self):
        self.props = Properties()

    def testDictBehavior(self):
        # note that dictionary-like behavior is deprecated and not exposed to
        # users!
        self.props.setProperty("do-tests", 1, "scheduler")
        self.props.setProperty("do-install", 2, "scheduler")

        self.assertTrue('do-tests' in self.props)
        self.assertEqual(self.props['do-tests'], 1)
        self.assertEqual(self.props['do-install'], 2)
        with self.assertRaises(KeyError):
            self.props['do-nothing']
        self.assertEqual(self.props.getProperty('do-install'), 2)
        self.assertIn('do-tests', self.props)
        self.assertNotIn('missing-do-tests', self.props)

    def testAsList(self):
        self.props.setProperty("happiness", 7, "builder")
        self.props.setProperty("flames", True, "tester")

        self.assertEqual(sorted(self.props.asList()),
                         [('flames', True, 'tester'), ('happiness', 7, 'builder')])

    def testAsDict(self):
        self.props.setProperty("msi_filename", "product.msi", 'packager')
        self.props.setProperty("dmg_filename", "product.dmg", 'packager')

        self.assertEqual(self.props.asDict(),
                         dict(msi_filename=('product.msi', 'packager'), dmg_filename=('product.dmg', 'packager')))

    def testUpdate(self):
        self.props.setProperty("x", 24, "old")
        newprops = {'a': 1, 'b': 2}
        self.props.update(newprops, "new")

        self.assertEqual(self.props.getProperty('x'), 24)
        self.assertEqual(self.props.getPropertySource('x'), 'old')
        self.assertEqual(self.props.getProperty('a'), 1)
        self.assertEqual(self.props.getPropertySource('a'), 'new')

    def testUpdateRuntime(self):
        self.props.setProperty("x", 24, "old")
        newprops = {'a': 1, 'b': 2}
        self.props.update(newprops, "new", runtime=True)

        self.assertEqual(self.props.getProperty('x'), 24)
        self.assertEqual(self.props.getPropertySource('x'), 'old')
        self.assertEqual(self.props.getProperty('a'), 1)
        self.assertEqual(self.props.getPropertySource('a'), 'new')
        self.assertEqual(self.props.runtime, set(['a', 'b']))

    def testUpdateFromProperties(self):
        self.props.setProperty("a", 94, "old")
        self.props.setProperty("x", 24, "old")
        newprops = Properties()
        newprops.setProperty('a', 1, "new")
        newprops.setProperty('b', 2, "new")
        self.props.updateFromProperties(newprops)

        self.assertEqual(self.props.getProperty('x'), 24)
        self.assertEqual(self.props.getPropertySource('x'), 'old')
        self.assertEqual(self.props.getProperty('a'), 1)
        self.assertEqual(self.props.getPropertySource('a'), 'new')

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

        self.assertEqual(self.props.getProperty('a'), 94)
        self.assertEqual(self.props.getPropertySource('a'), 'old')
        self.assertEqual(self.props.getProperty('b'), 2)
        self.assertEqual(self.props.getPropertySource('b'), 'new')
        self.assertEqual(self.props.getProperty('c'), None)  # not updated
        self.assertEqual(self.props.getProperty('d'), 3)
        self.assertEqual(self.props.getPropertySource('d'), 'new')
        self.assertEqual(self.props.getProperty('x'), 24)
        self.assertEqual(self.props.getPropertySource('x'), 'old')

    def test_setProperty_notJsonable(self):
        with self.assertRaises(TypeError):
            self.props.setProperty("project", object, "test")

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
        self.assertFalse('x' in self.props)

    def test_setProperty(self):
        self.props.setProperty('x', 'y', 'test')
        self.assertEqual(self.props.properties['x'], ('y', 'test'))
        self.assertNotIn('x', self.props.runtime)

    def test_setProperty_runtime(self):
        self.props.setProperty('x', 'y', 'test', runtime=True)
        self.assertEqual(self.props.properties['x'], ('y', 'test'))
        self.assertIn('x', self.props.runtime)

    def test_setProperty_no_source(self):
        # pylint: disable=no-value-for-parameter
        with self.assertRaises(TypeError):
            self.props.setProperty('x', 'y')

    def test_getProperties(self):
        self.assertIdentical(self.props.getProperties(), self.props)

    def test_getBuild(self):
        self.assertIdentical(self.props.getBuild(), self.props.build)

    def test_unset_sourcestamps(self):
        with self.assertRaises(AttributeError):
            self.props.sourcestamps()

    def test_unset_changes(self):
        with self.assertRaises(AttributeError):
            self.props.changes()
        with self.assertRaises(AttributeError):
            self.props.files()

    def test_build_attributes(self):
        build = FakeBuild(self.props)
        change = TempChange({'author': 'me', 'files': ['main.c']})
        ss = TempSourceStamp({'branch': 'master'})
        ss.changes = [change]
        build.sources[''] = ss
        self.assertEqual(self.props.sourcestamps[0]['branch'], 'master')
        self.assertEqual(self.props.changes[0]['author'], 'me')
        self.assertEqual(self.props.files[0], 'main.c')

    def test_own_attributes(self):
        self.props.sourcestamps = [{'branch': 'master'}]
        self.props.changes = [{'author': 'me', 'files': ['main.c']}]
        self.assertEqual(self.props.sourcestamps[0]['branch'], 'master')
        self.assertEqual(self.props.changes[0]['author'], 'me')
        self.assertEqual(self.props.files[0], 'main.c')

    @defer.inlineCallbacks
    def test_render(self):
        @implementer(IRenderable)
        class Renderable:

            def getRenderingFor(self, props):
                return props.getProperty('x') + 'z'
        self.props.setProperty('x', 'y', 'test')
        res = yield self.props.render(Renderable())
        self.assertEqual(res, 'yz')


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
        # getattr because pep8 doesn't like calls to has_key
        self.assertTrue(getattr(self.mp, 'has_key')('abc'))
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
        self.mp.render([1, 2])
        self.mp.properties.render.assert_called_with([1, 2])


class TestProperty(unittest.TestCase):

    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(props=self.props)

    @defer.inlineCallbacks
    def testIntProperty(self):
        self.props.setProperty("do-tests", 1, "scheduler")
        value = Property("do-tests")

        res = yield self.build.render(value)
        self.assertEqual(res, 1)

    @defer.inlineCallbacks
    def testStringProperty(self):
        self.props.setProperty("do-tests", "string", "scheduler")
        value = Property("do-tests")

        res = yield self.build.render(value)
        self.assertEqual(res, "string")

    @defer.inlineCallbacks
    def testMissingProperty(self):
        value = Property("do-tests")

        res = yield self.build.render(value)
        self.assertEqual(res, None)

    @defer.inlineCallbacks
    def testDefaultValue(self):
        value = Property("do-tests", default="Hello!")

        res = yield self.build.render(value)
        self.assertEqual(res, "Hello!")

    @defer.inlineCallbacks
    def testDefaultValueNested(self):
        self.props.setProperty("xxx", 'yyy', "scheduler")
        value = Property("do-tests",
                         default=WithProperties("a-%(xxx)s-b"))

        res = yield self.build.render(value)
        self.assertEqual(res, "a-yyy-b")

    @defer.inlineCallbacks
    def testIgnoreDefaultValue(self):
        self.props.setProperty("do-tests", "string", "scheduler")
        value = Property("do-tests", default="Hello!")

        res = yield self.build.render(value)
        self.assertEqual(res, "string")

    @defer.inlineCallbacks
    def testIgnoreFalseValue(self):
        self.props.setProperty("do-tests-string", "", "scheduler")
        self.props.setProperty("do-tests-int", 0, "scheduler")
        self.props.setProperty("do-tests-list", [], "scheduler")
        self.props.setProperty("do-tests-None", None, "scheduler")

        value = [Property("do-tests-string", default="Hello!"),
                 Property("do-tests-int", default="Hello!"),
                 Property("do-tests-list", default="Hello!"),
                 Property("do-tests-None", default="Hello!")]

        res = yield self.build.render(value)
        self.assertEqual(res, ["Hello!"] * 4)

    @defer.inlineCallbacks
    def testDefaultWhenFalse(self):
        self.props.setProperty("do-tests-string", "", "scheduler")
        self.props.setProperty("do-tests-int", 0, "scheduler")
        self.props.setProperty("do-tests-list", [], "scheduler")
        self.props.setProperty("do-tests-None", None, "scheduler")

        value = [Property("do-tests-string", default="Hello!", defaultWhenFalse=False),
                 Property(
                     "do-tests-int", default="Hello!", defaultWhenFalse=False),
                 Property(
                     "do-tests-list", default="Hello!", defaultWhenFalse=False),
                 Property("do-tests-None", default="Hello!", defaultWhenFalse=False)]

        res = yield self.build.render(value)
        self.assertEqual(res, ["", 0, [], None])

    def testDeferredDefault(self):
        default = DeferredRenderable()
        value = Property("no-such-property", default)
        d = self.build.render(value)
        d.addCallback(self.assertEqual,
                      "default-value")
        default.callback("default-value")
        return d

    @defer.inlineCallbacks
    def testFlattenList(self):
        self.props.setProperty("do-tests", "string", "scheduler")
        value = FlattenList([Property("do-tests"), ["bla"]])

        res = yield self.build.render(value)
        self.assertEqual(res, ["string", "bla"])

    @defer.inlineCallbacks
    def testFlattenListAdd(self):
        self.props.setProperty("do-tests", "string", "scheduler")
        value = FlattenList([Property("do-tests"), ["bla"]])
        value = value + FlattenList([Property("do-tests"), ["bla"]])

        res = yield self.build.render(value)
        self.assertEqual(res, ["string", "bla", "string", "bla"])

    @defer.inlineCallbacks
    def testFlattenListAdd2(self):
        self.props.setProperty("do-tests", "string", "scheduler")
        value = FlattenList([Property("do-tests"), ["bla"]])
        value = value + [Property("do-tests"), ["bla"]]

        res = yield self.build.render(value)
        self.assertEqual(res, ["string", "bla", "string", "bla"])

    @defer.inlineCallbacks
    def testCompEq(self):
        self.props.setProperty("do-tests", "string", "scheduler")
        result = yield self.build.render(Property("do-tests") == "string")
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testCompNe(self):
        self.props.setProperty("do-tests", "not-string", "scheduler")
        result = yield self.build.render(Property("do-tests") != "string")
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testCompLt(self):
        self.props.setProperty("do-tests", 1, "scheduler")
        result = yield self.build.render(Property("do-tests") < 2)
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testCompLe(self):
        self.props.setProperty("do-tests", 1, "scheduler")
        result = yield self.build.render(Property("do-tests") <= 2)
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testCompGt(self):
        self.props.setProperty("do-tests", 3, "scheduler")
        result = yield self.build.render(Property("do-tests") > 2)
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testCompGe(self):
        self.props.setProperty("do-tests", 3, "scheduler")
        result = yield self.build.render(Property("do-tests") >= 2)
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testStringCompEq(self):
        self.props.setProperty("do-tests", "string", "scheduler")
        test_string = "string"
        result = yield self.build.render(test_string == Property("do-tests"))
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testIntCompLe(self):
        self.props.setProperty("do-tests", 1, "scheduler")
        test_int = 1
        result = yield self.build.render(test_int <= Property("do-tests"))
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testPropCompGe(self):
        self.props.setProperty("do-tests", 1, "scheduler")
        result = yield self.build.render(Property("do-tests") >= Property("do-tests"))
        self.assertEqual(result, True)


class TestRenderableAdapters(unittest.TestCase):

    """
    Tests for list, tuple and dict renderers.
    """

    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(props=self.props)

    def test_list_deferred(self):
        r1 = DeferredRenderable()
        r2 = DeferredRenderable()
        d = self.build.render([r1, r2])
        d.addCallback(self.assertEqual,
                      ["lispy", "lists"])
        r2.callback("lists")
        r1.callback("lispy")
        return d

    def test_tuple_deferred(self):
        r1 = DeferredRenderable()
        r2 = DeferredRenderable()
        d = self.build.render((r1, r2))
        d.addCallback(self.assertEqual,
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
        d.addCallback(self.assertEqual,
                      {"lock": "load", "dict": "lookup"})
        k1.callback("lock")
        r1.callback("load")
        k2.callback("dict")
        r2.callback("lookup")
        return d


class Renderer(unittest.TestCase):

    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(props=self.props)

    @defer.inlineCallbacks
    def test_renderer(self):
        self.props.setProperty("x", "X", "test")

        def rend(p):
            return 'x%sx' % p.getProperty('x')

        res = yield self.build.render(renderer(rend))
        self.assertEqual('xXx', res)

    @defer.inlineCallbacks
    def test_renderer_called(self):
        # it's tempting to try to call the decorated function.  Don't do that.
        # It's not a function anymore.

        def rend(p):
            return 'x'

        with self.assertRaises(TypeError):
            yield self.build.render(renderer(rend)('y'))

    @defer.inlineCallbacks
    def test_renderer_decorator(self):
        self.props.setProperty("x", "X", "test")

        @renderer
        def rend(p):
            return 'x%sx' % p.getProperty('x')

        res = yield self.build.render(rend)
        self.assertEqual('xXx', res)

    @defer.inlineCallbacks
    def test_renderer_deferred(self):
        self.props.setProperty("x", "X", "test")

        def rend(p):
            return defer.succeed('y%sy' % p.getProperty('x'))

        res = yield self.build.render(renderer(rend))
        self.assertEqual('yXy', res)

    @defer.inlineCallbacks
    def test_renderer_fails(self):

        @defer.inlineCallbacks
        def rend(p):
            raise RuntimeError("oops")

        with self.assertRaises(RuntimeError):
            yield self.build.render(renderer(rend))

    @defer.inlineCallbacks
    def test_renderer_recursive(self):
        self.props.setProperty("x", "X", "test")

        def rend(p):
            return Interpolate("x%(prop:x)sx")

        ret = yield self.build.render(renderer(rend))
        self.assertEqual('xXx', ret)

    def test_renderer_repr(self):
        @renderer
        def myrend(p):
            pass
        self.assertIn('renderer(', repr(myrend))
        # py3 and py2 do not have the same way of repr functions
        # but they always contain the name of function
        self.assertIn('myrend', repr(myrend))

    @defer.inlineCallbacks
    def test_renderer_with_state(self):
        self.props.setProperty("x", "X", "test")

        def rend(p, arg, kwarg='y'):
            return 'x-%s-%s-%s' % (p.getProperty('x'), arg, kwarg)

        res = yield self.build.render(renderer(rend).withArgs('a', kwarg='kw'))
        self.assertEqual('x-X-a-kw', res)

    @defer.inlineCallbacks
    def test_renderer_with_state_called(self):
        # it's tempting to try to call the decorated function.  Don't do that.
        # It's not a function anymore.

        def rend(p, arg, kwarg='y'):
            return 'x'

        with self.assertRaises(TypeError):
            rend_with_args = renderer(rend).withArgs('a', kwarg='kw')
            yield self.build.render(rend_with_args('y'))

    @defer.inlineCallbacks
    def test_renderer_with_state_renders_args(self):
        self.props.setProperty("x", "X", "test")
        self.props.setProperty('arg', 'ARG', 'test2')
        self.props.setProperty('kw', 'KW', 'test3')

        def rend(p, arg, kwarg='y'):
            return 'x-%s-%s-%s' % (p.getProperty('x'), arg, kwarg)

        res = yield self.build.render(
            renderer(rend).withArgs(Property('arg'), kwarg=Property('kw')))
        self.assertEqual('x-X-ARG-KW', res)

    @defer.inlineCallbacks
    def test_renderer_decorator_with_state(self):
        self.props.setProperty("x", "X", "test")

        @renderer
        def rend(p, arg, kwarg='y'):
            return 'x-%s-%s-%s' % (p.getProperty('x'), arg, kwarg)

        res = yield self.build.render(rend.withArgs('a', kwarg='kw'))
        self.assertEqual('x-X-a-kw', res)

    @defer.inlineCallbacks
    def test_renderer_decorator_with_state_does_not_share_state(self):
        self.props.setProperty("x", "X", "test")

        @renderer
        def rend(p, *args, **kwargs):
            return 'x-%s-%s-%s' % (p.getProperty('x'), str(args), str(kwargs))

        rend1 = rend.withArgs('a', kwarg1='kw1')
        rend2 = rend.withArgs('b', kwarg2='kw2')

        res1 = yield self.build.render(rend1)
        res2 = yield self.build.render(rend2)

        self.assertEqual('x-X-(\'a\',)-{\'kwarg1\': \'kw1\'}', res1)
        self.assertEqual('x-X-(\'b\',)-{\'kwarg2\': \'kw2\'}', res2)

    @defer.inlineCallbacks
    def test_renderer_deferred_with_state(self):
        self.props.setProperty("x", "X", "test")

        def rend(p, arg, kwarg='y'):
            return defer.succeed('x-%s-%s-%s' %
                    (p.getProperty('x'), arg, kwarg))

        res = yield self.build.render(renderer(rend).withArgs('a', kwarg='kw'))
        self.assertEqual('x-X-a-kw', res)

    @defer.inlineCallbacks
    def test_renderer_fails_with_state(self):
        self.props.setProperty("x", "X", "test")

        def rend(p, arg, kwarg='y'):
            raise RuntimeError('oops')

        with self.assertRaises(RuntimeError):
            yield self.build.render(renderer(rend).withArgs('a', kwarg='kw'))

    @defer.inlineCallbacks
    def test_renderer_recursive_with_state(self):
        self.props.setProperty("x", "X", "test")

        def rend(p, arg, kwarg='y'):
            return Interpolate('x-%(prop:x)s-%(kw:arg)s-%(kw:kwarg)s',
                    arg=arg, kwarg=kwarg)

        res = yield self.build.render(renderer(rend).withArgs('a', kwarg='kw'))
        self.assertEqual('x-X-a-kw', res)

    def test_renderer_repr_with_state(self):
        @renderer
        def rend(p):
            pass

        rend = rend.withArgs('a', kwarg='kw')  # pylint: disable=assignment-from-no-return

        self.assertIn('renderer(', repr(rend))
        # py3 and py2 do not have the same way of repr functions
        # but they always contain the name of function
        self.assertIn('args=[\'a\']', repr(rend))
        self.assertIn('kwargs={\'kwarg\': \'kw\'}', repr(rend))

    @defer.inlineCallbacks
    def test_interpolate_worker(self):
        rend = yield self.build.render(Interpolate("%(worker:test)s"))
        self.assertEqual(rend, "test")


class Compare(unittest.TestCase):

    def test_WithProperties_lambda(self):
        self.assertNotEqual(WithProperties("%(key)s", key=lambda p: 'val'), WithProperties(
            "%(key)s", key=lambda p: 'val'))

        def rend(p):
            return "val"
        self.assertEqual(
            WithProperties("%(key)s", key=rend),
            WithProperties("%(key)s", key=rend))
        self.assertNotEqual(
            WithProperties("%(key)s", key=rend),
            WithProperties("%(key)s", otherkey=rend))

    def test_WithProperties_positional(self):
        self.assertNotEqual(
            WithProperties("%s", 'key'),
            WithProperties("%s", 'otherkey'))
        self.assertEqual(
            WithProperties("%s", 'key'),
            WithProperties("%s", 'key'))
        self.assertNotEqual(
            WithProperties("%s", 'key'),
            WithProperties("k%s", 'key'))

    def test_Interpolate_constant(self):
        self.assertNotEqual(
            Interpolate('some text here'),
            Interpolate('and other text there'))
        self.assertEqual(
            Interpolate('some text here'),
            Interpolate('some text here'))

    def test_Interpolate_positional(self):
        self.assertNotEqual(
            Interpolate('%s %s', "test", "text"),
            Interpolate('%s %s', "other", "text"))
        self.assertEqual(
            Interpolate('%s %s', "test", "text"),
            Interpolate('%s %s', "test", "text"))

    def test_Interpolate_kwarg(self):
        self.assertNotEqual(
            Interpolate("%(kw:test)s", test=object(), other=2),
            Interpolate("%(kw:test)s", test=object(), other=2))
        self.assertEqual(
            Interpolate('testing: %(kw:test)s', test="test", other=3),
            Interpolate('testing: %(kw:test)s', test="test", other=3))

    def test_Interpolate_worker(self):
        self.assertEqual(
            Interpolate('testing: %(worker:test)s'),
            Interpolate('testing: %(worker:test)s'))

    def test_renderer(self):
        self.assertNotEqual(
            renderer(lambda p: 'val'),
            renderer(lambda p: 'val'))

        def rend(p):
            return "val"
        self.assertEqual(
            renderer(rend),
            renderer(rend))

    def test_Lookup_simple(self):
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'other'),
            _Lookup({'test': 5, 'other': 6}, 'test'))
        self.assertEqual(
            _Lookup({'test': 5, 'other': 6}, 'test'),
            _Lookup({'test': 5, 'other': 6}, 'test'))

    def test_Lookup_default(self):
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', default='default'),
            _Lookup({'test': 5, 'other': 6}, 'test'))
        self.assertEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', default='default'),
            _Lookup({'test': 5, 'other': 6}, 'test', default='default'))

    def test_Lookup_defaultWhenFalse(self):
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', defaultWhenFalse=False),
            _Lookup({'test': 5, 'other': 6}, 'test'))
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', defaultWhenFalse=False),
            _Lookup({'test': 5, 'other': 6}, 'test', defaultWhenFalse=True))
        self.assertEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', defaultWhenFalse=True),
            _Lookup({'test': 5, 'other': 6}, 'test', defaultWhenFalse=True))
        self.assertEqual(
            _Lookup({'test': 5, 'other': 6}, 'test'),
            _Lookup({'test': 5, 'other': 6}, 'test', defaultWhenFalse=True))

    def test_Lookup_hasKey(self):
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', hasKey=None),
            _Lookup({'test': 5, 'other': 6}, 'test'))
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', hasKey='has-key'),
            _Lookup({'test': 5, 'other': 6}, 'test'))
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', hasKey='has-key'),
            _Lookup({'test': 5, 'other': 6}, 'test', hasKey='other-key'))
        self.assertEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', hasKey='has-key'),
            _Lookup({'test': 5, 'other': 6}, 'test', hasKey='has-key'))

    def test_Lookup_elideNoneAs(self):
        self.assertEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', elideNoneAs=None),
            _Lookup({'test': 5, 'other': 6}, 'test'))
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', elideNoneAs=''),
            _Lookup({'test': 5, 'other': 6}, 'test'))
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', elideNoneAs='got None'),
            _Lookup({'test': 5, 'other': 6}, 'test', elideNoneAs=''))
        self.assertEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', elideNoneAs='got None'),
            _Lookup({'test': 5, 'other': 6}, 'test', elideNoneAs='got None'))

    def test_Lazy(self):
        self.assertNotEqual(
            _Lazy(5),
            _Lazy(6))
        self.assertEqual(
            _Lazy(5),
            _Lazy(5))

    def test_SourceStampDict(self):
        self.assertNotEqual(
            _SourceStampDict('binary'),
            _SourceStampDict('library'))
        self.assertEqual(
            _SourceStampDict('binary'),
            _SourceStampDict('binary'))


class TestTransform(unittest.TestCase, ConfigErrorsMixin):

    def setUp(self):
        self.props = Properties(propname='propvalue')

    def test_invalid_first_arg(self):
        with self.assertRaisesConfigError(
                "function given to Transform neither callable nor renderable"):
            Transform(None)

    @defer.inlineCallbacks
    def test_argless(self):
        t = Transform(lambda: 'abc')
        res = yield self.props.render(t)
        self.assertEqual(res, 'abc')

    @defer.inlineCallbacks
    def test_argless_renderable(self):
        @renderer
        def function(iprops):
            return lambda: iprops.getProperty('propname')

        t = Transform(function)
        res = yield self.props.render(t)
        self.assertEqual(res, 'propvalue')

    @defer.inlineCallbacks
    def test_args(self):
        t = Transform(lambda x, y: x + '|' + y,
                      'abc', Property('propname'))
        res = yield self.props.render(t)
        self.assertEqual(res, 'abc|propvalue')

    @defer.inlineCallbacks
    def test_kwargs(self):
        t = Transform(lambda x, y: x + '|' + y,
                      x='abc', y=Property('propname'))
        res = yield self.props.render(t)
        self.assertEqual(res, 'abc|propvalue')

    def test_deferred(self):
        function = DeferredRenderable()
        arg = DeferredRenderable()
        kwarg = DeferredRenderable()

        t = Transform(function, arg, y=kwarg)
        d = self.props.render(t)
        d.addCallback(self.assertEqual, 'abc|def')

        function.callback(lambda x, y: x + '|' + y)
        arg.callback('abc')
        kwarg.callback('def')

        return d
