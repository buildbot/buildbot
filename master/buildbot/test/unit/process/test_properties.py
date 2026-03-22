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

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING
from typing import Callable
from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest
from zope.interface import implementer

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

if TYPE_CHECKING:
    from buildbot.interfaces import IProperties
    from buildbot.util.twisted import InlineCallbacksType


class FakeSource:
    def __init__(self) -> None:
        self.branch = None
        self.codebase = ''
        self.project = ''
        self.repository = ''
        self.revision = None

    def asDict(self) -> dict[str, str | None]:
        ds = {
            'branch': self.branch,
            'codebase': self.codebase,
            'project': self.project,
            'repository': self.repository,
            'revision': self.revision,
        }
        return ds


@implementer(IRenderable)
class DeferredRenderable:
    def __init__(self) -> None:
        self.d = defer.Deferred()  # type: ignore[var-annotated]

    def getRenderingFor(self, build: IProperties) -> defer.Deferred[object]:
        return self.d

    def callback(self, value: object) -> None:
        self.d.callback(value)


class TestPropertyMap(unittest.TestCase):
    """
    Test the behavior of PropertyMap, using the external interface
    provided by WithProperties.
    """

    def setUp(self) -> None:
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
    def doTestSimpleWithProperties(
        self, fmtstring: str, expect: object, **kwargs: Callable[[IProperties], object]
    ) -> InlineCallbacksType[None]:
        res = yield self.build.render(WithProperties(fmtstring, **kwargs))
        self.assertEqual(res, f"{expect}")

    def testSimpleStr(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_str)s', 'a-string')

    def testSimpleNone(self) -> defer.Deferred[None]:
        # None is special-cased to become an empty string
        return self.doTestSimpleWithProperties('%(prop_none)s', '')

    def testSimpleList(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_list)s', ['a', 'b'])

    def testSimpleZero(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_zero)s', 0)

    def testSimpleOne(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_one)s', 1)

    def testSimpleFalse(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_false)s', False)

    def testSimpleTrue(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_true)s', True)

    def testSimpleEmpty(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_empty)s', '')

    @defer.inlineCallbacks
    def testSimpleUnset(self) -> InlineCallbacksType[None]:
        with self.assertRaises(KeyError):
            yield self.build.render(WithProperties('%(prop_nosuch)s'))

    def testColonMinusSet(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_str:-missing)s', 'a-string')

    def testColonMinusNone(self) -> defer.Deferred[None]:
        # None is special-cased here, too
        return self.doTestSimpleWithProperties('%(prop_none:-missing)s', '')

    def testColonMinusZero(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_zero:-missing)s', 0)

    def testColonMinusOne(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_one:-missing)s', 1)

    def testColonMinusFalse(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_false:-missing)s', False)

    def testColonMinusTrue(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_true:-missing)s', True)

    def testColonMinusEmpty(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_empty:-missing)s', '')

    def testColonMinusUnset(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_nosuch:-missing)s', 'missing')

    def testColonTildeSet(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_str:~missing)s', 'a-string')

    def testColonTildeNone(self) -> defer.Deferred[None]:
        # None is special-cased *differently* for ~:
        return self.doTestSimpleWithProperties('%(prop_none:~missing)s', 'missing')

    def testColonTildeZero(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_zero:~missing)s', 'missing')

    def testColonTildeOne(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_one:~missing)s', 1)

    def testColonTildeFalse(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_false:~missing)s', 'missing')

    def testColonTildeTrue(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_true:~missing)s', True)

    def testColonTildeEmpty(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_empty:~missing)s', 'missing')

    def testColonTildeUnset(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_nosuch:~missing)s', 'missing')

    def testColonPlusSet(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_str:+present)s', 'present')

    def testColonPlusNone(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_none:+present)s', 'present')

    def testColonPlusZero(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_zero:+present)s', 'present')

    def testColonPlusOne(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_one:+present)s', 'present')

    def testColonPlusFalse(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_false:+present)s', 'present')

    def testColonPlusTrue(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_true:+present)s', 'present')

    def testColonPlusEmpty(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_empty:+present)s', 'present')

    def testColonPlusUnset(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_nosuch:+present)s', '')

    @defer.inlineCallbacks
    def testClearTempValues(self) -> InlineCallbacksType[None]:
        yield self.doTestSimpleWithProperties('', '', prop_temp=lambda b: 'present')
        yield self.doTestSimpleWithProperties('%(prop_temp:+present)s', '')

    def testTempValue(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties(
            '%(prop_temp)s', 'present', prop_temp=lambda b: 'present'
        )

    def testTempValueOverrides(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_one)s', 2, prop_one=lambda b: 2)

    def testTempValueColonMinusSet(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_one:-missing)s', 2, prop_one=lambda b: 2)

    def testTempValueColonMinusUnset(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties(
            '%(prop_nosuch:-missing)s', 'temp', prop_nosuch=lambda b: 'temp'
        )

    def testTempValueColonTildeTrueSet(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties(
            '%(prop_false:~nontrue)s', 'temp', prop_false=lambda b: 'temp'
        )

    def testTempValueColonTildeTrueUnset(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties(
            '%(prop_nosuch:~nontrue)s', 'temp', prop_nosuch=lambda b: 'temp'
        )

    def testTempValueColonTildeFalseFalse(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties(
            '%(prop_false:~nontrue)s', 'nontrue', prop_false=lambda b: False
        )

    def testTempValueColonTildeTrueFalse(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties(
            '%(prop_true:~nontrue)s', True, prop_true=lambda b: False
        )

    def testTempValueColonTildeNoneFalse(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties(
            '%(prop_nosuch:~nontrue)s', 'nontrue', prop_nosuch=lambda b: False
        )

    def testTempValueColonTildeFalseZero(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties(
            '%(prop_false:~nontrue)s', 'nontrue', prop_false=lambda b: 0
        )

    def testTempValueColonTildeTrueZero(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties(
            '%(prop_true:~nontrue)s', True, prop_true=lambda b: 0
        )

    def testTempValueColonTildeNoneZero(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties(
            '%(prop_nosuch:~nontrue)s', 'nontrue', prop_nosuch=lambda b: 0
        )

    def testTempValueColonTildeFalseBlank(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties(
            '%(prop_false:~nontrue)s', 'nontrue', prop_false=lambda b: ''
        )

    def testTempValueColonTildeTrueBlank(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties(
            '%(prop_true:~nontrue)s', True, prop_true=lambda b: ''
        )

    def testTempValueColonTildeNoneBlank(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties(
            '%(prop_nosuch:~nontrue)s', 'nontrue', prop_nosuch=lambda b: ''
        )

    def testTempValuePlusSetSet(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties('%(prop_one:+set)s', 'set', prop_one=lambda b: 2)

    def testTempValuePlusUnsetSet(self) -> defer.Deferred[None]:
        return self.doTestSimpleWithProperties(
            '%(prop_nosuch:+set)s', 'set', prop_nosuch=lambda b: 1
        )


class TestInterpolateConfigure(unittest.TestCase, ConfigErrorsMixin):
    """
    Test that Interpolate reports errors in the interpolation string
    at configure time.
    """

    def test_invalid_args_and_kwargs(self) -> None:
        with self.assertRaisesConfigError("Interpolate takes either positional"):
            Interpolate("%s %(foo)s", 1, foo=2)

    def test_invalid_selector(self) -> None:
        with self.assertRaisesConfigError("invalid Interpolate selector 'garbage'"):
            Interpolate("%(garbage:test)s")

    def test_no_selector(self) -> None:
        with self.assertRaisesConfigError(
            "invalid Interpolate substitution without selector 'garbage'"
        ):
            Interpolate("%(garbage)s")

    def test_invalid_default_type(self) -> None:
        with self.assertRaisesConfigError("invalid Interpolate default type '@'"):
            Interpolate("%(prop:some_prop:@wacky)s")

    def test_nested_invalid_selector(self) -> None:
        with self.assertRaisesConfigError("invalid Interpolate selector 'garbage'"):
            Interpolate("%(prop:some_prop:~%(garbage:test)s)s")

    def test_colon_ternary_missing_delimeter(self) -> None:
        with self.assertRaisesConfigError(
            "invalid Interpolate ternary expression 'one' with delimiter ':'"
        ):
            Interpolate("echo '%(prop:P:?:one)s'")

    def test_colon_ternary_paren_delimiter(self) -> None:
        with self.assertRaisesConfigError(
            "invalid Interpolate ternary expression 'one(:)' with delimiter ':'"
        ):
            Interpolate("echo '%(prop:P:?:one(:))s'")

    def test_colon_ternary_hash_bad_delimeter(self) -> None:
        with self.assertRaisesConfigError(
            "invalid Interpolate ternary expression 'one' with delimiter '|'"
        ):
            Interpolate("echo '%(prop:P:#?|one)s'")

    def test_prop_invalid_character(self) -> None:
        with self.assertRaisesConfigError(
            "Property name must be alphanumeric for prop Interpolation 'a+a'"
        ):
            Interpolate("echo '%(prop:a+a)s'")

    def test_kw_invalid_character(self) -> None:
        with self.assertRaisesConfigError(
            "Keyword must be alphanumeric for kw Interpolation 'a+a'"
        ):
            Interpolate("echo '%(kw:a+a)s'")

    def test_src_codebase_invalid_character(self) -> None:
        with self.assertRaisesConfigError(
            "Codebase must be alphanumeric for src Interpolation 'a+a:a'"
        ):
            Interpolate("echo '%(src:a+a:a)s'")

    def test_src_attr_invalid_character(self) -> None:
        with self.assertRaisesConfigError(
            "Attribute must be alphanumeric for src Interpolation 'a:a+a'"
        ):
            Interpolate("echo '%(src:a:a+a)s'")

    def test_src_missing_attr(self) -> None:
        with self.assertRaisesConfigError("Must specify both codebase and attr"):
            Interpolate("echo '%(src:a)s'")


class TestInterpolatePositional(unittest.TestCase):
    def setUp(self) -> None:
        self.props = Properties()
        self.build = FakeBuild(props=self.props)

    @defer.inlineCallbacks
    def test_string(self) -> InlineCallbacksType[None]:
        command = Interpolate("test %s", "one fish")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "test one fish")

    @defer.inlineCallbacks
    def test_twoString(self) -> InlineCallbacksType[None]:
        command = Interpolate("test %s, %s", "one fish", "two fish")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "test one fish, two fish")

    def test_deferred(self) -> defer.Deferred[None]:
        renderable = DeferredRenderable()
        command = Interpolate("echo '%s'", renderable)
        d = self.build.render(command)
        d.addCallback(self.assertEqual, "echo 'red fish'")
        renderable.callback("red fish")
        return d

    @defer.inlineCallbacks
    def test_renderable(self) -> InlineCallbacksType[None]:
        self.props.setProperty("buildername", "blue fish", "test")
        command = Interpolate("echo '%s'", Property("buildername"))
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'blue fish'")


class TestInterpolateProperties(unittest.TestCase):
    def setUp(self) -> None:
        self.props = Properties()
        self.build = FakeBuild(props=self.props)

    @defer.inlineCallbacks
    def test_properties(self) -> InlineCallbacksType[None]:
        self.props.setProperty("buildername", "winbld", "test")
        command = Interpolate("echo buildby-%(prop:buildername)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo buildby-winbld")

    @defer.inlineCallbacks
    def test_properties_newline(self) -> InlineCallbacksType[None]:
        self.props.setProperty("buildername", "winbld", "test")
        command = Interpolate("aa\n%(prop:buildername)s\nbb")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "aa\nwinbld\nbb")

    @defer.inlineCallbacks
    def test_property_not_set(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo buildby-%(prop:buildername)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo buildby-")

    @defer.inlineCallbacks
    def test_property_colon_minus(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo buildby-%(prop:buildername:-blddef)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo buildby-blddef")

    @defer.inlineCallbacks
    def test_deepcopy(self) -> InlineCallbacksType[None]:
        # After a deepcopy, Interpolate instances used to lose track
        # that they didn't have a ``hasKey`` value
        # see http://trac.buildbot.net/ticket/3505
        self.props.setProperty("buildername", "linux4", "test")
        command = deepcopy(Interpolate("echo buildby-%(prop:buildername:-blddef)s"))
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo buildby-linux4")

    @defer.inlineCallbacks
    def test_property_colon_tilde_true(self) -> InlineCallbacksType[None]:
        self.props.setProperty("buildername", "winbld", "test")
        command = Interpolate("echo buildby-%(prop:buildername:~blddef)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo buildby-winbld")

    @defer.inlineCallbacks
    def test_property_colon_tilde_false(self) -> InlineCallbacksType[None]:
        self.props.setProperty("buildername", "", "test")
        command = Interpolate("echo buildby-%(prop:buildername:~blddef)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo buildby-blddef")

    @defer.inlineCallbacks
    def test_property_colon_plus(self) -> InlineCallbacksType[None]:
        self.props.setProperty("project", "proj1", "test")
        command = Interpolate("echo %(prop:project:+projectdefined)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo projectdefined")

    @defer.inlineCallbacks
    def test_nested_property(self) -> InlineCallbacksType[None]:
        self.props.setProperty("project", "so long!", "test")
        command = Interpolate("echo '%(prop:missing:~%(prop:project)s)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'so long!'")

    @defer.inlineCallbacks
    def test_property_substitute_recursively(self) -> InlineCallbacksType[None]:
        self.props.setProperty("project", "proj1", "test")
        command = Interpolate("echo '%(prop:no_such:-%(prop:project)s)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'proj1'")

    @defer.inlineCallbacks
    def test_property_colon_ternary_present(self) -> InlineCallbacksType[None]:
        self.props.setProperty("project", "proj1", "test")
        command = Interpolate("echo %(prop:project:?:defined:missing)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo defined")

    @defer.inlineCallbacks
    def test_property_colon_ternary_missing(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(prop:project:?|defined|missing)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo missing")

    @defer.inlineCallbacks
    def test_property_colon_ternary_hash_true(self) -> InlineCallbacksType[None]:
        self.props.setProperty("project", "winbld", "test")
        command = Interpolate("echo buildby-%(prop:project:#?:T:F)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo buildby-T")

    @defer.inlineCallbacks
    def test_property_colon_ternary_hash_false(self) -> InlineCallbacksType[None]:
        self.props.setProperty("project", "", "test")
        command = Interpolate("echo buildby-%(prop:project:#?|T|F)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo buildby-F")

    @defer.inlineCallbacks
    def test_property_colon_ternary_substitute_recursively_true(self) -> InlineCallbacksType[None]:
        self.props.setProperty("P", "present", "test")
        self.props.setProperty("one", "proj1", "test")
        self.props.setProperty("two", "proj2", "test")
        command = Interpolate("echo '%(prop:P:?|%(prop:one)s|%(prop:two)s)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'proj1'")

    @defer.inlineCallbacks
    def test_property_colon_ternary_substitute_recursively_false(self) -> InlineCallbacksType[None]:
        self.props.setProperty("one", "proj1", "test")
        self.props.setProperty("two", "proj2", "test")
        command = Interpolate("echo '%(prop:P:?|%(prop:one)s|%(prop:two)s)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'proj2'")

    @defer.inlineCallbacks
    def test_property_colon_ternary_substitute_recursively_delimited_true(
        self,
    ) -> InlineCallbacksType[None]:
        self.props.setProperty("P", "present", "test")
        self.props.setProperty("one", "proj1", "test")
        self.props.setProperty("two", "proj2", "test")
        command = Interpolate(
            "echo '%(prop:P:?|%(prop:one:?|true|false)s|%(prop:two:?|false|true)s)s'"
        )
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'true'")

    @defer.inlineCallbacks
    def test_property_colon_ternary_substitute_recursively_delimited_false(
        self,
    ) -> InlineCallbacksType[None]:
        self.props.setProperty("one", "proj1", "test")
        self.props.setProperty("two", "proj2", "test")
        command = Interpolate(
            "echo '%(prop:P:?|%(prop:one:?|true|false)s|%(prop:two:?|false|true)s)s'"
        )
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'false'")


class TestInterpolateSrc(unittest.TestCase):
    def setUp(self) -> None:
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
        sc.project = None  # type: ignore[assignment]
        self.build.sources['cbC'] = sc

    @defer.inlineCallbacks
    def test_src(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(src:cbB:repository)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://B..")

    @defer.inlineCallbacks
    def test_src_src(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(src:cbB:repository)s %(src:cbB:project)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://B.. Project")

    @defer.inlineCallbacks
    def test_src_attr_empty(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(src:cbC:project)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo ")

    @defer.inlineCallbacks
    def test_src_attr_codebase_notfound(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(src:unknown_codebase:project)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo ")

    @defer.inlineCallbacks
    def test_src_colon_plus_false(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo '%(src:cbD:project:+defaultrepo)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo ''")

    @defer.inlineCallbacks
    def test_src_colon_plus_true(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo '%(src:cbB:project:+defaultrepo)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'defaultrepo'")

    @defer.inlineCallbacks
    def test_src_colon_minus(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(src:cbB:nonattr:-defaultrepo)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo defaultrepo")

    @defer.inlineCallbacks
    def test_src_colon_minus_false(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo '%(src:cbC:project:-noproject)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo ''")

    @defer.inlineCallbacks
    def test_src_colon_minus_true(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo '%(src:cbB:project:-noproject)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'Project'")

    @defer.inlineCallbacks
    def test_src_colon_minus_codebase_notfound(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo '%(src:unknown_codebase:project:-noproject)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'noproject'")

    @defer.inlineCallbacks
    def test_src_colon_tilde_true(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo '%(src:cbB:project:~noproject)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'Project'")

    @defer.inlineCallbacks
    def test_src_colon_tilde_false(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo '%(src:cbC:project:~noproject)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'noproject'")

    @defer.inlineCallbacks
    def test_src_colon_tilde_false_src_as_replacement(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo '%(src:cbC:project:~%(src:cbA:project)s)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'Project'")

    @defer.inlineCallbacks
    def test_src_colon_tilde_codebase_notfound(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo '%(src:unknown_codebase:project:~noproject)s'")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'noproject'")


class TestInterpolateKwargs(unittest.TestCase):
    def setUp(self) -> None:
        self.props = Properties()
        self.build = FakeBuild(props=self.props)
        sa = FakeSource()

        sa.repository = 'cvs://A..'
        sa.codebase = 'cbA'
        sa.project = None  # type: ignore[assignment]
        sa.branch = "default"  # type: ignore[assignment]
        self.build.sources['cbA'] = sa

    @defer.inlineCallbacks
    def test_kwarg(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(kw:repository)s", repository="cvs://A..")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://A..")

    @defer.inlineCallbacks
    def test_kwarg_kwarg(self) -> InlineCallbacksType[None]:
        command = Interpolate(
            "echo %(kw:repository)s %(kw:branch)s", repository="cvs://A..", branch="default"
        )
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://A.. default")

    @defer.inlineCallbacks
    def test_kwarg_not_mapped(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(kw:repository)s", project="projectA")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo ")

    @defer.inlineCallbacks
    def test_kwarg_colon_minus_not_available(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(kw:repository)s", project="projectA")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo ")

    @defer.inlineCallbacks
    def test_kwarg_colon_minus_not_available_default(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(kw:repository:-cvs://A..)s", project="projectA")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://A..")

    @defer.inlineCallbacks
    def test_kwarg_colon_minus_available(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(kw:repository:-cvs://A..)s", repository="cvs://B..")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://B..")

    @defer.inlineCallbacks
    def test_kwarg_colon_tilde_true(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(kw:repository:~cvs://B..)s", repository="cvs://A..")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://A..")

    @defer.inlineCallbacks
    def test_kwarg_colon_tilde_false(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(kw:repository:~cvs://B..)s", repository="")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://B..")

    @defer.inlineCallbacks
    def test_kwarg_colon_tilde_none(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(kw:repository:~cvs://B..)s", repository=None)
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://B..")

    @defer.inlineCallbacks
    def test_kwarg_colon_plus_false(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(kw:repository:+cvs://B..)s", project="project")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo ")

    @defer.inlineCallbacks
    def test_kwarg_colon_plus_true(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(kw:repository:+cvs://B..)s", repository=None)
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo cvs://B..")

    @defer.inlineCallbacks
    def test_kwargs_colon_minus_false_src_as_replacement(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo '%(kw:text:-%(src:cbA:branch)s)s'", notext='ddd')
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'default'")

    @defer.inlineCallbacks
    def test_kwargs_renderable(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo '%(kw:test)s'", test=ConstantRenderable('testing'))
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo 'testing'")

    def test_kwargs_deferred(self) -> None:
        renderable = DeferredRenderable()
        command = Interpolate("echo '%(kw:test)s'", test=renderable)
        d = self.build.render(command)
        d.addCallback(self.assertEqual, "echo 'testing'")
        renderable.callback('testing')

    def test_kwarg_deferred(self) -> None:
        renderable = DeferredRenderable()
        command = Interpolate("echo '%(kw:project)s'", project=renderable)
        d = self.build.render(command)
        d.addCallback(self.assertEqual, "echo 'testing'")
        renderable.callback('testing')

    def test_nested_kwarg_deferred(self) -> defer.Deferred[None]:
        renderable = DeferredRenderable()
        command = Interpolate(
            "echo '%(kw:missing:~%(kw:fishy)s)s'", missing=renderable, fishy="so long!"
        )
        d = self.build.render(command)
        d.addCallback(self.assertEqual, "echo 'so long!'")
        renderable.callback(False)
        return d


class TestWithProperties(unittest.TestCase):
    def setUp(self) -> None:
        self.props = Properties()
        self.build = FakeBuild(props=self.props)

    def testInvalidParams(self) -> None:
        with self.assertRaises(ValueError):
            WithProperties("%s %(foo)s", 1, foo=2)  # type: ignore[arg-type]

    @defer.inlineCallbacks
    def testBasic(self) -> InlineCallbacksType[None]:
        # test basic substitution with WithProperties
        self.props.setProperty("revision", "47", "test")
        command = WithProperties("build-%s.tar.gz", "revision")
        res = yield self.build.render(command)
        self.assertEqual(res, "build-47.tar.gz")

    @defer.inlineCallbacks
    def testDict(self) -> InlineCallbacksType[None]:
        # test dict-style substitution with WithProperties
        self.props.setProperty("other", "foo", "test")
        command = WithProperties("build-%(other)s.tar.gz")
        res = yield self.build.render(command)
        self.assertEqual(res, "build-foo.tar.gz")

    @defer.inlineCallbacks
    def testDictColonMinus(self) -> InlineCallbacksType[None]:
        # test dict-style substitution with WithProperties
        self.props.setProperty("prop1", "foo", "test")
        command = WithProperties("build-%(prop1:-empty)s-%(prop2:-empty)s.tar.gz")
        res = yield self.build.render(command)
        self.assertEqual(res, "build-foo-empty.tar.gz")

    @defer.inlineCallbacks
    def testDictColonPlus(self) -> InlineCallbacksType[None]:
        # test dict-style substitution with WithProperties
        self.props.setProperty("prop1", "foo", "test")
        command = WithProperties("build-%(prop1:+exists)s-%(prop2:+exists)s.tar.gz")
        res = yield self.build.render(command)
        self.assertEqual(res, "build-exists-.tar.gz")

    @defer.inlineCallbacks
    def testEmpty(self) -> InlineCallbacksType[None]:
        # None should render as ''
        self.props.setProperty("empty", None, "test")
        command = WithProperties("build-%(empty)s.tar.gz")
        res = yield self.build.render(command)
        self.assertEqual(res, "build-.tar.gz")

    @defer.inlineCallbacks
    def testRecursiveList(self) -> InlineCallbacksType[None]:
        self.props.setProperty("x", 10, "test")
        self.props.setProperty("y", 20, "test")
        command = [WithProperties("%(x)s %(y)s"), "and", WithProperties("%(y)s %(x)s")]
        res = yield self.build.render(command)
        self.assertEqual(res, ["10 20", "and", "20 10"])

    @defer.inlineCallbacks
    def testRecursiveTuple(self) -> InlineCallbacksType[None]:
        self.props.setProperty("x", 10, "test")
        self.props.setProperty("y", 20, "test")
        command = (WithProperties("%(x)s %(y)s"), "and", WithProperties("%(y)s %(x)s"))
        res = yield self.build.render(command)
        self.assertEqual(res, ("10 20", "and", "20 10"))

    @defer.inlineCallbacks
    def testRecursiveDict(self) -> InlineCallbacksType[None]:
        self.props.setProperty("x", 10, "test")
        self.props.setProperty("y", 20, "test")
        command = {WithProperties("%(x)s %(y)s"): WithProperties("%(y)s %(x)s")}
        res = yield self.build.render(command)
        self.assertEqual(res, {"10 20": "20 10"})

    @defer.inlineCallbacks
    def testLambdaSubst(self) -> InlineCallbacksType[None]:
        command = WithProperties('%(foo)s', foo=lambda _: 'bar')
        res = yield self.build.render(command)
        self.assertEqual(res, 'bar')

    @defer.inlineCallbacks
    def testLambdaHasattr(self) -> InlineCallbacksType[None]:
        command = WithProperties('%(foo)s', foo=lambda b: (b.hasProperty('x') and 'x') or 'y')
        res = yield self.build.render(command)
        self.assertEqual(res, 'y')

    @defer.inlineCallbacks
    def testLambdaOverride(self) -> InlineCallbacksType[None]:
        self.props.setProperty('x', 10, 'test')
        command = WithProperties('%(x)s', x=lambda _: 20)
        res = yield self.build.render(command)
        self.assertEqual(res, '20')

    def testLambdaCallable(self) -> None:
        with self.assertRaises(ValueError):
            WithProperties('%(foo)s', foo='bar')  # type: ignore[arg-type]

    @defer.inlineCallbacks
    def testLambdaUseExisting(self) -> InlineCallbacksType[None]:
        self.props.setProperty('x', 10, 'test')
        self.props.setProperty('y', 20, 'test')
        command = WithProperties(
            '%(z)s', z=lambda props: props.getProperty('x') + props.getProperty('y')
        )
        res = yield self.build.render(command)
        self.assertEqual(res, '30')

    @defer.inlineCallbacks
    def testColon(self) -> InlineCallbacksType[None]:
        self.props.setProperty('some:property', 10, 'test')
        command = WithProperties('%(some:property:-with-default)s')
        res = yield self.build.render(command)
        self.assertEqual(res, '10')

    @defer.inlineCallbacks
    def testColon_default(self) -> InlineCallbacksType[None]:
        command = WithProperties('%(some:property:-with-default)s')
        res = yield self.build.render(command)
        self.assertEqual(res, 'with-default')

    @defer.inlineCallbacks
    def testColon_colon(self) -> InlineCallbacksType[None]:
        command = WithProperties('%(some:property:-with:default)s')
        res = yield self.build.render(command)
        self.assertEqual(res, 'with:default')


class TestProperties(unittest.TestCase):
    def setUp(self) -> None:
        self.props = Properties()

    def testDictBehavior(self) -> None:
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

    def testAsList(self) -> None:
        self.props.setProperty("happiness", 7, "builder")
        self.props.setProperty("flames", True, "tester")

        self.assertEqual(
            sorted(self.props.asList()), [('flames', True, 'tester'), ('happiness', 7, 'builder')]
        )

    def testAsDict(self) -> None:
        self.props.setProperty("msi_filename", "product.msi", 'packager')
        self.props.setProperty("dmg_filename", "product.dmg", 'packager')

        self.assertEqual(
            self.props.asDict(),
            {
                "msi_filename": ('product.msi', 'packager'),
                "dmg_filename": ('product.dmg', 'packager'),
            },
        )

    def testUpdate(self) -> None:
        self.props.setProperty("x", 24, "old")
        newprops = {'a': 1, 'b': 2}
        self.props.update(newprops, "new")

        self.assertEqual(self.props.getProperty('x'), 24)
        self.assertEqual(self.props.getPropertySource('x'), 'old')
        self.assertEqual(self.props.getProperty('a'), 1)
        self.assertEqual(self.props.getPropertySource('a'), 'new')

    def testUpdateRuntime(self) -> None:
        self.props.setProperty("x", 24, "old")
        newprops = {'a': 1, 'b': 2}
        self.props.update(newprops, "new", runtime=True)

        self.assertEqual(self.props.getProperty('x'), 24)
        self.assertEqual(self.props.getPropertySource('x'), 'old')
        self.assertEqual(self.props.getProperty('a'), 1)
        self.assertEqual(self.props.getPropertySource('a'), 'new')
        self.assertEqual(self.props.runtime, set(['a', 'b']))

    def testUpdateFromProperties(self) -> None:
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

    def testUpdateFromPropertiesNoRuntime(self) -> None:
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

    def test_setProperty_notJsonable(self) -> None:
        with self.assertRaises(TypeError):
            self.props.setProperty("project", object, "test")

    # IProperties methods

    def test_getProperty(self) -> None:
        self.props.properties['p1'] = (['p', 1], 'test')
        self.assertEqual(self.props.getProperty('p1'), ['p', 1])

    def test_getProperty_default_None(self) -> None:
        self.assertEqual(self.props.getProperty('p1'), None)

    def test_getProperty_default(self) -> None:
        self.assertEqual(self.props.getProperty('p1', 2), 2)

    def test_hasProperty_false(self) -> None:
        self.assertFalse(self.props.hasProperty('x'))

    def test_hasProperty_true(self) -> None:
        self.props.properties['x'] = (False, 'test')
        self.assertTrue(self.props.hasProperty('x'))

    def test_has_key_false(self) -> None:
        self.assertFalse('x' in self.props)

    def test_setProperty(self) -> None:
        self.props.setProperty('x', 'y', 'test')
        self.assertEqual(self.props.properties['x'], ('y', 'test'))
        self.assertNotIn('x', self.props.runtime)

    def test_setProperty_runtime(self) -> None:
        self.props.setProperty('x', 'y', 'test', runtime=True)
        self.assertEqual(self.props.properties['x'], ('y', 'test'))
        self.assertIn('x', self.props.runtime)

    def test_setProperty_no_source(self) -> None:
        # pylint: disable=no-value-for-parameter
        with self.assertRaises(TypeError):
            self.props.setProperty('x', 'y')  # type: ignore[call-arg]

    def test_getProperties(self) -> None:
        self.assertIdentical(self.props.getProperties(), self.props)

    def test_getBuild(self) -> None:
        self.assertIdentical(self.props.getBuild(), self.props.build)

    def test_unset_sourcestamps(self) -> None:
        with self.assertRaises(AttributeError):
            self.props.sourcestamps()  # type: ignore[operator]

    def test_unset_changes(self) -> None:
        with self.assertRaises(AttributeError):
            self.props.changes()  # type: ignore[operator]
        with self.assertRaises(AttributeError):
            self.props.files()  # type: ignore[operator]

    def test_build_attributes(self) -> None:
        build = FakeBuild(self.props)
        change = TempChange({'author': 'me', 'files': ['main.c']})
        ss = TempSourceStamp({'branch': 'master'})
        ss.changes = [change]
        build.sources[''] = ss
        self.assertEqual(self.props.sourcestamps[0]['branch'], 'master')
        self.assertEqual(self.props.changes[0]['author'], 'me')
        self.assertEqual(self.props.files[0], 'main.c')

    def test_own_attributes(self) -> None:
        self.props.sourcestamps = [{'branch': 'master'}]
        self.props.changes = [{'author': 'me', 'files': ['main.c']}]
        self.assertEqual(self.props.sourcestamps[0]['branch'], 'master')
        self.assertEqual(self.props.changes[0]['author'], 'me')
        self.assertEqual(self.props.files[0], 'main.c')

    @defer.inlineCallbacks
    def test_render(self) -> InlineCallbacksType[None]:
        @implementer(IRenderable)
        class Renderable:
            def getRenderingFor(self, props: IProperties) -> None:  # type: ignore[override]
                return props.getProperty('x') + 'z'  # type: ignore[operator]

        self.props.setProperty('x', 'y', 'test')
        res = yield self.props.render(Renderable())
        self.assertEqual(res, 'yz')


class MyPropertiesThing(PropertiesMixin):
    set_runtime_properties = True

    def getProperties(self) -> None:  # type: ignore[override]
        return self.properties  # type: ignore[attr-defined]


class TestPropertiesMixin(unittest.TestCase):
    def setUp(self) -> None:
        self.mp = MyPropertiesThing()
        self.mp.properties = mock.Mock()  # type: ignore[attr-defined]

    def test_getProperty(self) -> None:
        self.mp.getProperty('abc')
        self.mp.properties.getProperty.assert_called_with('abc', None)  # type: ignore[attr-defined]

    def xtest_getProperty_default(self) -> None:
        self.mp.getProperty('abc', 'def')
        self.mp.properties.getProperty.assert_called_with('abc', 'def')  # type: ignore[attr-defined]

    def test_hasProperty(self) -> None:
        self.mp.properties.hasProperty.return_value = True  # type: ignore[attr-defined]
        self.assertTrue(self.mp.hasProperty('abc'))
        self.mp.properties.hasProperty.assert_called_with('abc')  # type: ignore[attr-defined]

    def test_has_key(self) -> None:
        self.mp.properties.hasProperty.return_value = True  # type: ignore[attr-defined]
        # getattr because pep8 doesn't like calls to has_key
        self.assertTrue(self.mp.has_key('abc'))
        self.mp.properties.hasProperty.assert_called_with('abc')  # type: ignore[attr-defined]

    def test_setProperty(self) -> None:
        self.mp.setProperty('abc', 'def', 'src')
        self.mp.properties.setProperty.assert_called_with('abc', 'def', 'src', runtime=True)  # type: ignore[attr-defined]

    def test_setProperty_no_source(self) -> None:
        # this compatibility is maintained for old code
        self.mp.setProperty('abc', 'def')
        self.mp.properties.setProperty.assert_called_with('abc', 'def', 'Unknown', runtime=True)  # type: ignore[attr-defined]

    def test_render(self) -> None:
        self.mp.render([1, 2])
        self.mp.properties.render.assert_called_with([1, 2])  # type: ignore[attr-defined]


class TestProperty(unittest.TestCase):
    def setUp(self) -> None:
        self.props = Properties()
        self.build = FakeBuild(props=self.props)

    @defer.inlineCallbacks
    def testIntProperty(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", 1, "scheduler")
        value = Property("do-tests")

        res = yield self.build.render(value)
        self.assertEqual(res, 1)

    @defer.inlineCallbacks
    def testStringProperty(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", "string", "scheduler")
        value = Property("do-tests")

        res = yield self.build.render(value)
        self.assertEqual(res, "string")

    @defer.inlineCallbacks
    def testMissingProperty(self) -> InlineCallbacksType[None]:
        value = Property("do-tests")

        res = yield self.build.render(value)
        self.assertEqual(res, None)

    @defer.inlineCallbacks
    def testDefaultValue(self) -> InlineCallbacksType[None]:
        value = Property("do-tests", default="Hello!")

        res = yield self.build.render(value)
        self.assertEqual(res, "Hello!")

    @defer.inlineCallbacks
    def testDefaultValueNested(self) -> InlineCallbacksType[None]:
        self.props.setProperty("xxx", 'yyy', "scheduler")
        value = Property("do-tests", default=WithProperties("a-%(xxx)s-b"))

        res = yield self.build.render(value)
        self.assertEqual(res, "a-yyy-b")

    @defer.inlineCallbacks
    def testIgnoreDefaultValue(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", "string", "scheduler")
        value = Property("do-tests", default="Hello!")

        res = yield self.build.render(value)
        self.assertEqual(res, "string")

    @defer.inlineCallbacks
    def testIgnoreFalseValue(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests-string", "", "scheduler")
        self.props.setProperty("do-tests-int", 0, "scheduler")
        self.props.setProperty("do-tests-list", [], "scheduler")
        self.props.setProperty("do-tests-None", None, "scheduler")

        value = [
            Property("do-tests-string", default="Hello!"),
            Property("do-tests-int", default="Hello!"),
            Property("do-tests-list", default="Hello!"),
            Property("do-tests-None", default="Hello!"),
        ]

        res = yield self.build.render(value)
        self.assertEqual(res, ["Hello!"] * 4)

    @defer.inlineCallbacks
    def testDefaultWhenFalse(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests-string", "", "scheduler")
        self.props.setProperty("do-tests-int", 0, "scheduler")
        self.props.setProperty("do-tests-list", [], "scheduler")
        self.props.setProperty("do-tests-None", None, "scheduler")

        value = [
            Property("do-tests-string", default="Hello!", defaultWhenFalse=False),
            Property("do-tests-int", default="Hello!", defaultWhenFalse=False),
            Property("do-tests-list", default="Hello!", defaultWhenFalse=False),
            Property("do-tests-None", default="Hello!", defaultWhenFalse=False),
        ]

        res = yield self.build.render(value)
        self.assertEqual(res, ["", 0, [], None])

    def testDeferredDefault(self) -> defer.Deferred[None]:
        default = DeferredRenderable()
        value = Property("no-such-property", default)
        d = self.build.render(value)
        d.addCallback(self.assertEqual, "default-value")
        default.callback("default-value")
        return d

    @defer.inlineCallbacks
    def testFlattenList(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", "string", "scheduler")
        value = FlattenList([Property("do-tests"), ["bla"]])

        res = yield self.build.render(value)
        self.assertEqual(res, ["string", "bla"])

    @defer.inlineCallbacks
    def testFlattenListAdd(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", "string", "scheduler")
        value = FlattenList([Property("do-tests"), ["bla"]])
        value = value + FlattenList([Property("do-tests"), ["bla"]])

        res = yield self.build.render(value)
        self.assertEqual(res, ["string", "bla", "string", "bla"])

    @defer.inlineCallbacks
    def testFlattenListAdd2(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", "string", "scheduler")
        value = FlattenList([Property("do-tests"), ["bla"]])
        value = value + [Property('do-tests'), ['bla']]  # noqa: RUF005

        res = yield self.build.render(value)
        self.assertEqual(res, ["string", "bla", "string", "bla"])

    @defer.inlineCallbacks
    def testCompEq(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", "string", "scheduler")
        result = yield self.build.render(Property("do-tests") == "string")
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testCompNe(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", "not-string", "scheduler")
        result = yield self.build.render(Property("do-tests") != "string")
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testCompLt(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", 1, "scheduler")
        x = Property("do-tests") < 2
        self.assertEqual(repr(x), 'Property(do-tests) < 2')
        result = yield self.build.render(x)
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testCompLe(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", 1, "scheduler")
        result = yield self.build.render(Property("do-tests") <= 2)
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testCompGt(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", 3, "scheduler")
        result = yield self.build.render(Property("do-tests") > 2)
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testCompGe(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", 3, "scheduler")
        result = yield self.build.render(Property("do-tests") >= 2)
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testStringCompEq(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", "string", "scheduler")
        test_string = "string"
        result = yield self.build.render(test_string == Property("do-tests"))
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testIntCompLe(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", 1, "scheduler")
        test_int = 1
        result = yield self.build.render(test_int <= Property("do-tests"))
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testPropCompGe(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", 1, "scheduler")
        result = yield self.build.render(Property("do-tests") >= Property("do-tests"))
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testPropAdd(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", 1, "scheduler")
        result = yield self.build.render(Property("do-tests") + Property("do-tests"))
        self.assertEqual(result, 2)

    @defer.inlineCallbacks
    def testPropSub(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", 1, "scheduler")
        result = yield self.build.render(Property("do-tests") - Property("do-tests"))
        self.assertEqual(result, 0)

    @defer.inlineCallbacks
    def testPropDiv(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", 1, "scheduler")
        self.props.setProperty("do-tests2", 3, "scheduler")
        result = yield self.build.render(Property("do-tests") / Property("do-tests2"))
        self.assertEqual(result, 1 / 3)

    @defer.inlineCallbacks
    def testPropFDiv(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", 5, "scheduler")
        self.props.setProperty("do-tests2", 2, "scheduler")
        result = yield self.build.render(Property("do-tests") // Property("do-tests2"))
        self.assertEqual(result, 2)

    @defer.inlineCallbacks
    def testPropMod(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", 5, "scheduler")
        self.props.setProperty("do-tests2", 3, "scheduler")
        result = yield self.build.render(Property("do-tests") % Property("do-tests2"))
        self.assertEqual(result, 2)

    @defer.inlineCallbacks
    def testPropMult(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", 2, "scheduler")
        result = yield self.build.render(Property("do-tests") * Interpolate("%(prop:do-tests)s"))
        self.assertEqual(result, '22')

    @defer.inlineCallbacks
    def testPropIn(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", 2, "scheduler")
        result = yield self.build.render(Property("do-tests").in_([1, 2]))
        self.assertEqual(result, True)

    @defer.inlineCallbacks
    def testPropIn2(self) -> InlineCallbacksType[None]:
        self.props.setProperty("do-tests", 2, "scheduler")
        result = yield self.build.render(Property("do-tests").in_([1, 3]))
        self.assertEqual(result, False)


class TestRenderableAdapters(unittest.TestCase):
    """
    Tests for list, tuple and dict renderers.
    """

    def setUp(self) -> None:
        self.props = Properties()
        self.build = FakeBuild(props=self.props)

    def test_list_deferred(self) -> defer.Deferred[None]:
        r1 = DeferredRenderable()
        r2 = DeferredRenderable()
        d = self.build.render([r1, r2])
        d.addCallback(self.assertEqual, ["lispy", "lists"])
        r2.callback("lists")
        r1.callback("lispy")
        return d

    def test_tuple_deferred(self) -> defer.Deferred[None]:
        r1 = DeferredRenderable()
        r2 = DeferredRenderable()
        d = self.build.render((r1, r2))
        d.addCallback(self.assertEqual, ("totally", "tupled"))
        r2.callback("tupled")
        r1.callback("totally")
        return d

    def test_dict(self) -> defer.Deferred[None]:
        r1 = DeferredRenderable()
        r2 = DeferredRenderable()
        k1 = DeferredRenderable()
        k2 = DeferredRenderable()
        d = self.build.render({k1: r1, k2: r2})
        d.addCallback(self.assertEqual, {"lock": "load", "dict": "lookup"})
        k1.callback("lock")
        r1.callback("load")
        k2.callback("dict")
        r2.callback("lookup")
        return d


class Renderer(unittest.TestCase):
    def setUp(self) -> None:
        self.props = Properties()
        self.build = FakeBuild(props=self.props)

    @defer.inlineCallbacks
    def test_renderer(self) -> InlineCallbacksType[None]:
        self.props.setProperty("x", "X", "test")

        def rend(p: IProperties) -> str:
            return f"x{p.getProperty('x')}x"

        res = yield self.build.render(renderer(rend))
        self.assertEqual('xXx', res)

    @defer.inlineCallbacks
    def test_renderer_called(self) -> InlineCallbacksType[None]:
        # it's tempting to try to call the decorated function.  Don't do that.
        # It's not a function anymore.

        def rend(p: IProperties) -> str:
            return 'x'

        with self.assertRaises(TypeError):
            yield self.build.render(renderer(rend)('y'))  # type: ignore[operator]

    @defer.inlineCallbacks
    def test_renderer_decorator(self) -> InlineCallbacksType[None]:
        self.props.setProperty("x", "X", "test")

        @renderer
        def rend(p: IProperties) -> str:
            return f"x{p.getProperty('x')}x"

        res = yield self.build.render(rend)
        self.assertEqual('xXx', res)

    @defer.inlineCallbacks
    def test_renderer_deferred(self) -> InlineCallbacksType[None]:
        self.props.setProperty("x", "X", "test")

        def rend(p: IProperties) -> defer.Deferred[str]:
            return defer.succeed(f"y{p.getProperty('x')}y")

        res = yield self.build.render(renderer(rend))
        self.assertEqual('yXy', res)

    @defer.inlineCallbacks
    def test_renderer_fails(self) -> InlineCallbacksType[None]:
        @defer.inlineCallbacks  # type: ignore[arg-type]
        def rend(p: IProperties) -> None:
            raise RuntimeError("oops")

        with self.assertRaises(RuntimeError):
            yield self.build.render(renderer(rend))

    @defer.inlineCallbacks
    def test_renderer_recursive(self) -> InlineCallbacksType[None]:
        self.props.setProperty("x", "X", "test")

        def rend(p: IProperties) -> IRenderable:
            return Interpolate("x%(prop:x)sx")

        ret = yield self.build.render(renderer(rend))
        self.assertEqual('xXx', ret)

    def test_renderer_repr(self) -> None:
        @renderer
        def myrend(p: IProperties) -> None:
            pass

        self.assertIn('renderer(', repr(myrend))
        # py3 and py2 do not have the same way of repr functions
        # but they always contain the name of function
        self.assertIn('myrend', repr(myrend))

    @defer.inlineCallbacks
    def test_renderer_with_state(self) -> InlineCallbacksType[None]:
        self.props.setProperty("x", "X", "test")

        def rend(p: IProperties, arg: object, kwarg: object = 'y') -> str:
            return f"x-{p.getProperty('x')}-{arg}-{kwarg}"

        res = yield self.build.render(renderer(rend).withArgs('a', kwarg='kw'))
        self.assertEqual('x-X-a-kw', res)

    @defer.inlineCallbacks
    def test_renderer_with_state_called(self) -> InlineCallbacksType[None]:
        # it's tempting to try to call the decorated function.  Don't do that.
        # It's not a function anymore.

        def rend(p: IProperties, arg: object, kwarg: object = 'y') -> str:
            return 'x'

        with self.assertRaises(TypeError):
            rend_with_args = renderer(rend).withArgs('a', kwarg='kw')
            yield self.build.render(rend_with_args('y'))  # type: ignore[operator]

    @defer.inlineCallbacks
    def test_renderer_with_state_renders_args(self) -> InlineCallbacksType[None]:
        self.props.setProperty("x", "X", "test")
        self.props.setProperty('arg', 'ARG', 'test2')
        self.props.setProperty('kw', 'KW', 'test3')

        def rend(p: IProperties, arg: object, kwarg: object = 'y') -> str:
            return f"x-{p.getProperty('x')}-{arg}-{kwarg}"

        res = yield self.build.render(
            renderer(rend).withArgs(Property('arg'), kwarg=Property('kw'))
        )
        self.assertEqual('x-X-ARG-KW', res)

    @defer.inlineCallbacks
    def test_renderer_decorator_with_state(self) -> InlineCallbacksType[None]:
        self.props.setProperty("x", "X", "test")

        @renderer
        def rend(p: IProperties, arg: object, kwarg: object = 'y') -> str:
            return f"x-{p.getProperty('x')}-{arg}-{kwarg}"

        res = yield self.build.render(rend.withArgs('a', kwarg='kw'))
        self.assertEqual('x-X-a-kw', res)

    @defer.inlineCallbacks
    def test_renderer_decorator_with_state_does_not_share_state(self) -> InlineCallbacksType[None]:
        self.props.setProperty("x", "X", "test")

        @renderer
        def rend(p: IProperties, *args: object, **kwargs: object) -> str:
            return f"x-{p.getProperty('x')}-{args!s}-{kwargs!s}"

        rend1 = rend.withArgs('a', kwarg1='kw1')
        rend2 = rend.withArgs('b', kwarg2='kw2')

        res1 = yield self.build.render(rend1)
        res2 = yield self.build.render(rend2)

        self.assertEqual('x-X-(\'a\',)-{\'kwarg1\': \'kw1\'}', res1)
        self.assertEqual('x-X-(\'b\',)-{\'kwarg2\': \'kw2\'}', res2)

    @defer.inlineCallbacks
    def test_renderer_deferred_with_state(self) -> InlineCallbacksType[None]:
        self.props.setProperty("x", "X", "test")

        def rend(p: IProperties, arg: object, kwarg: object = 'y') -> defer.Deferred[str]:
            return defer.succeed(f"x-{p.getProperty('x')}-{arg}-{kwarg}")

        res = yield self.build.render(renderer(rend).withArgs('a', kwarg='kw'))
        self.assertEqual('x-X-a-kw', res)

    @defer.inlineCallbacks
    def test_renderer_fails_with_state(self) -> InlineCallbacksType[None]:
        self.props.setProperty("x", "X", "test")

        def rend(p: IProperties, arg: object, kwarg: object = 'y') -> None:
            raise RuntimeError('oops')

        with self.assertRaises(RuntimeError):
            yield self.build.render(renderer(rend).withArgs('a', kwarg='kw'))

    @defer.inlineCallbacks
    def test_renderer_recursive_with_state(self) -> InlineCallbacksType[None]:
        self.props.setProperty("x", "X", "test")

        def rend(p: IProperties, arg: object, kwarg: object = 'y') -> IRenderable:
            return Interpolate('x-%(prop:x)s-%(kw:arg)s-%(kw:kwarg)s', arg=arg, kwarg=kwarg)

        res = yield self.build.render(renderer(rend).withArgs('a', kwarg='kw'))
        self.assertEqual('x-X-a-kw', res)

    def test_renderer_repr_with_state(self) -> None:
        @renderer
        def rend(p: IProperties) -> None:
            pass

        rend = rend.withArgs('a', kwarg='kw')  # pylint: disable=assignment-from-no-return

        self.assertIn('renderer(', repr(rend))
        # py3 and py2 do not have the same way of repr functions
        # but they always contain the name of function
        self.assertIn('args=[\'a\']', repr(rend))
        self.assertIn('kwargs={\'kwarg\': \'kw\'}', repr(rend))

    @defer.inlineCallbacks
    def test_interpolate_worker(self) -> InlineCallbacksType[None]:
        self.build.workerforbuilder.worker.info.setProperty('test', 'testvalue', 'Worker')
        rend = yield self.build.render(Interpolate("%(worker:test)s"))
        self.assertEqual(rend, "testvalue")


class Compare(unittest.TestCase):
    def test_WithProperties_lambda(self) -> None:
        self.assertNotEqual(
            WithProperties("%(key)s", key=lambda p: 'val'),
            WithProperties("%(key)s", key=lambda p: 'val'),
        )

        def rend(p: IProperties) -> str:
            return "val"

        self.assertEqual(WithProperties("%(key)s", key=rend), WithProperties("%(key)s", key=rend))
        self.assertNotEqual(
            WithProperties("%(key)s", key=rend), WithProperties("%(key)s", otherkey=rend)
        )

    def test_WithProperties_positional(self) -> None:
        self.assertNotEqual(WithProperties("%s", 'key'), WithProperties("%s", 'otherkey'))
        self.assertEqual(WithProperties("%s", 'key'), WithProperties("%s", 'key'))
        self.assertNotEqual(WithProperties("%s", 'key'), WithProperties("k%s", 'key'))

    def test_Interpolate_constant(self) -> None:
        self.assertNotEqual(Interpolate('some text here'), Interpolate('and other text there'))
        self.assertEqual(Interpolate('some text here'), Interpolate('some text here'))

    def test_Interpolate_positional(self) -> None:
        self.assertNotEqual(
            Interpolate('%s %s', "test", "text"), Interpolate('%s %s', "other", "text")
        )
        self.assertEqual(Interpolate('%s %s', "test", "text"), Interpolate('%s %s', "test", "text"))

    def test_Interpolate_kwarg(self) -> None:
        self.assertNotEqual(
            Interpolate("%(kw:test)s", test=object(), other=2),
            Interpolate("%(kw:test)s", test=object(), other=2),
        )
        self.assertEqual(
            Interpolate('testing: %(kw:test)s', test="test", other=3),
            Interpolate('testing: %(kw:test)s', test="test", other=3),
        )

    def test_Interpolate_worker(self) -> None:
        self.assertEqual(
            Interpolate('testing: %(worker:test)s'), Interpolate('testing: %(worker:test)s')
        )

    def test_renderer(self) -> None:
        self.assertNotEqual(renderer(lambda p: 'val'), renderer(lambda p: 'val'))

        def rend(p: IProperties) -> str:
            return "val"

        self.assertEqual(renderer(rend), renderer(rend))

    def test_Lookup_simple(self) -> None:
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'other'), _Lookup({'test': 5, 'other': 6}, 'test')
        )
        self.assertEqual(
            _Lookup({'test': 5, 'other': 6}, 'test'), _Lookup({'test': 5, 'other': 6}, 'test')
        )

    def test_Lookup_default(self) -> None:
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', default='default'),
            _Lookup({'test': 5, 'other': 6}, 'test'),
        )
        self.assertEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', default='default'),
            _Lookup({'test': 5, 'other': 6}, 'test', default='default'),
        )

    def test_Lookup_defaultWhenFalse(self) -> None:
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', defaultWhenFalse=False),
            _Lookup({'test': 5, 'other': 6}, 'test'),
        )
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', defaultWhenFalse=False),
            _Lookup({'test': 5, 'other': 6}, 'test', defaultWhenFalse=True),
        )
        self.assertEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', defaultWhenFalse=True),
            _Lookup({'test': 5, 'other': 6}, 'test', defaultWhenFalse=True),
        )
        self.assertEqual(
            _Lookup({'test': 5, 'other': 6}, 'test'),
            _Lookup({'test': 5, 'other': 6}, 'test', defaultWhenFalse=True),
        )

    def test_Lookup_hasKey(self) -> None:
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', hasKey=None),
            _Lookup({'test': 5, 'other': 6}, 'test'),
        )
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', hasKey='has-key'),
            _Lookup({'test': 5, 'other': 6}, 'test'),
        )
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', hasKey='has-key'),
            _Lookup({'test': 5, 'other': 6}, 'test', hasKey='other-key'),
        )
        self.assertEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', hasKey='has-key'),
            _Lookup({'test': 5, 'other': 6}, 'test', hasKey='has-key'),
        )

    def test_Lookup_elideNoneAs(self) -> None:
        self.assertEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', elideNoneAs=None),
            _Lookup({'test': 5, 'other': 6}, 'test'),
        )
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', elideNoneAs=''),
            _Lookup({'test': 5, 'other': 6}, 'test'),
        )
        self.assertNotEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', elideNoneAs='got None'),
            _Lookup({'test': 5, 'other': 6}, 'test', elideNoneAs=''),
        )
        self.assertEqual(
            _Lookup({'test': 5, 'other': 6}, 'test', elideNoneAs='got None'),
            _Lookup({'test': 5, 'other': 6}, 'test', elideNoneAs='got None'),
        )

    def test_Lazy(self) -> None:
        self.assertNotEqual(_Lazy(5), _Lazy(6))
        self.assertEqual(_Lazy(5), _Lazy(5))

    def test_SourceStampDict(self) -> None:
        self.assertNotEqual(_SourceStampDict('binary'), _SourceStampDict('library'))
        self.assertEqual(_SourceStampDict('binary'), _SourceStampDict('binary'))


class TestTransform(unittest.TestCase, ConfigErrorsMixin):
    def setUp(self) -> None:
        self.props = Properties(propname='propvalue')

    def test_invalid_first_arg(self) -> None:
        with self.assertRaisesConfigError(
            "function given to Transform neither callable nor renderable"
        ):
            Transform(None)

    @defer.inlineCallbacks
    def test_argless(self) -> InlineCallbacksType[None]:
        t = Transform(lambda: 'abc')
        res = yield self.props.render(t)
        self.assertEqual(res, 'abc')

    @defer.inlineCallbacks
    def test_argless_renderable(self) -> InlineCallbacksType[None]:
        @renderer
        def function(iprops: IProperties) -> Callable[[], object]:
            return lambda: iprops.getProperty('propname')

        t = Transform(function)
        res = yield self.props.render(t)
        self.assertEqual(res, 'propvalue')

    @defer.inlineCallbacks
    def test_args(self) -> InlineCallbacksType[None]:
        t = Transform(lambda x, y: x + '|' + y, 'abc', Property('propname'))
        res = yield self.props.render(t)
        self.assertEqual(res, 'abc|propvalue')

    @defer.inlineCallbacks
    def test_kwargs(self) -> InlineCallbacksType[None]:
        t = Transform(lambda x, y: x + '|' + y, x='abc', y=Property('propname'))
        res = yield self.props.render(t)
        self.assertEqual(res, 'abc|propvalue')

    def test_deferred(self) -> defer.Deferred[None]:
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
