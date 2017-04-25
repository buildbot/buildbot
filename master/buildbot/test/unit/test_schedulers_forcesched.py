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
from __future__ import division
from __future__ import print_function
from future.utils import iteritems

import json

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.schedulers.forcesched import AnyPropertyParameter
from buildbot.schedulers.forcesched import BaseParameter
from buildbot.schedulers.forcesched import BooleanParameter
from buildbot.schedulers.forcesched import ChoiceStringParameter
from buildbot.schedulers.forcesched import CodebaseParameter
from buildbot.schedulers.forcesched import CollectedValidationError
from buildbot.schedulers.forcesched import FixedParameter
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.schedulers.forcesched import IntParameter
from buildbot.schedulers.forcesched import NestedParameter
from buildbot.schedulers.forcesched import StringParameter
from buildbot.schedulers.forcesched import UserNameParameter
from buildbot.schedulers.forcesched import oneCodebase
from buildbot.test.util import scheduler
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning


class TestForceScheduler(scheduler.SchedulerMixin, ConfigErrorsMixin, unittest.TestCase):

    OBJECTID = 19
    SCHEDULERID = 9

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    def makeScheduler(self, name='testsched', builderNames=['a', 'b'],
                      **kw):
        sched = self.attachScheduler(
            ForceScheduler(name=name, builderNames=builderNames, **kw),
            self.OBJECTID, self.SCHEDULERID,
            overrideBuildsetMethods=True,
            createBuilderDB=True)
        sched.master.config = config.MasterConfig()

        self.assertEqual(sched.name, name)

        return sched

    # tests

    def test_compare_branch(self):
        self.assertNotEqual(
            ForceScheduler(name="testched", builderNames=[]),
            ForceScheduler(
                name="testched", builderNames=[],
                codebases=oneCodebase(
                    branch=FixedParameter("branch", "fishing/pole"))))

    def test_compare_reason(self):
        self.assertNotEqual(
            ForceScheduler(name="testched", builderNames=[],
                           reason=FixedParameter("reason", "no fish for you!")),
            ForceScheduler(name="testched", builderNames=[],
                           reason=FixedParameter("reason", "thanks for the fish!")))

    def test_compare_revision(self):
        self.assertNotEqual(
            ForceScheduler(
                name="testched", builderNames=[],
                codebases=oneCodebase(
                    revision=FixedParameter("revision", "fish-v1"))),
            ForceScheduler(
                name="testched", builderNames=[],
                codebases=oneCodebase(
                    revision=FixedParameter("revision", "fish-v2"))))

    def test_compare_repository(self):
        self.assertNotEqual(
            ForceScheduler(
                name="testched", builderNames=[],
                codebases=oneCodebase(
                    repository=FixedParameter("repository", "git://pond.org/fisher.git"))),
            ForceScheduler(
                name="testched", builderNames=[],
                codebases=oneCodebase(
                    repository=FixedParameter("repository", "svn://ocean.com/trawler/"))))

    def test_compare_project(self):
        self.assertNotEqual(
            ForceScheduler(
                name="testched", builderNames=[],
                codebases=oneCodebase(
                    project=FixedParameter("project", "fisher"))),
            ForceScheduler(
                name="testched", builderNames=[],
                codebases=oneCodebase(
                    project=FixedParameter("project", "trawler"))))

    def test_compare_username(self):
        self.assertNotEqual(
            ForceScheduler(name="testched", builderNames=[]),
            ForceScheduler(name="testched", builderNames=[],
                           username=FixedParameter("username", "The Fisher King <avallach@atlantis.al>")))

    def test_compare_properties(self):
        self.assertNotEqual(
            ForceScheduler(name="testched", builderNames=[],
                           properties=[]),
            ForceScheduler(name="testched", builderNames=[],
                           properties=[FixedParameter("prop", "thanks for the fish!")]))

    def test_compare_codebases(self):
        self.assertNotEqual(
            ForceScheduler(name="testched", builderNames=[],
                           codebases=['bar']),
            ForceScheduler(name="testched", builderNames=[],
                           codebases=['foo']))

    @defer.inlineCallbacks
    def test_basicForce(self):
        sched = self.makeScheduler()

        res = yield sched.force('user', builderNames=['a'], branch='a', reason='because', revision='c',
                                repository='d', project='p'
                                )

        # only one builder forced, so there should only be one brid
        self.assertEqual(res, (500, {1000: 100}))
        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForSourceStampsWithDefaults', dict(
                builderNames=['a'],
                waited_for=False,
                properties={
                    u'owner': ('user', u'Force Build Form'),
                    u'reason': ('because', u'Force Build Form'),
                },
                reason=u"A build was forced by 'user': because",
                sourcestamps=[
                    {'codebase': '', 'branch': 'a', 'revision': 'c',
                     'repository': 'd', 'project': 'p'},
                ])),
        ])

    @defer.inlineCallbacks
    def test_basicForce_reasonString(self):
        """Same as above, but with a reasonString"""
        sched = self.makeScheduler(
            reasonString='%(owner)s wants it %(reason)s')

        res = yield sched.force('user', builderNames=['a'], branch='a', reason='because', revision='c',
                                repository='d', project='p'
                                )
        bsid, brids = res

        # only one builder forced, so there should only be one brid
        self.assertEqual(len(brids), 1)

        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForSourceStampsWithDefaults', {
                'builderNames': ['a'],
                'properties': {u'owner': ('user', u'Force Build Form'),
                               u'reason': ('because', u'Force Build Form')},
                'reason': 'user wants it because',
                'sourcestamps': [{'branch': 'a',
                                  'codebase': '',
                                  'project': 'p',
                                  'repository': 'd',
                                  'revision': 'c'}],
                'waited_for': False}),
        ])
        (bsid,
         dict(reason="user wants it because",
              brids=brids,
              external_idstring=None,
              properties=[('owner', ('user', 'Force Build Form')),
                          ('reason', ('because', 'Force Build Form')),
                          ('scheduler', ('testsched', 'Scheduler')),
                          ],
              sourcestampsetid=100),
         {'':
          dict(branch='a', revision='c', repository='d', codebase='',
               project='p', sourcestampsetid=100)
          })

    @defer.inlineCallbacks
    def test_force_allBuilders(self):
        sched = self.makeScheduler()

        res = yield sched.force('user', branch='a', reason='because', revision='c',
                                repository='d', project='p',
                                )
        self.assertEqual(res, (500, {1000: 100, 1001: 101}))
        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForSourceStampsWithDefaults', dict(
                builderNames=['a', 'b'],
                waited_for=False,
                properties={
                    u'owner': ('user', u'Force Build Form'),
                    u'reason': ('because', u'Force Build Form'),
                },
                reason=u"A build was forced by 'user': because",
                sourcestamps=[
                    {'codebase': '', 'branch': 'a', 'revision': 'c',
                     'repository': 'd', 'project': 'p'},
                ])),
        ])

    @defer.inlineCallbacks
    def test_force_someBuilders(self):
        sched = self.makeScheduler(builderNames=['a', 'b', 'c'])

        res = yield sched.force('user', builderNames=['a', 'b'],
                                branch='a', reason='because', revision='c',
                                repository='d', project='p',
                                )
        self.assertEqual(res, (500, {1000: 100, 1001: 101}))
        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForSourceStampsWithDefaults', dict(
                builderNames=['a', 'b'],
                waited_for=False,
                properties={
                    u'owner': ('user', u'Force Build Form'),
                    u'reason': ('because', u'Force Build Form'),
                },
                reason=u"A build was forced by 'user': because",
                sourcestamps=[
                    {'codebase': '', 'branch': 'a', 'revision': 'c',
                     'repository': 'd', 'project': 'p'},
                ])),
        ])

    def test_bad_codebases(self):

        # codebases must be a list of either string or BaseParameter types
        self.assertRaisesConfigError("ForceScheduler 'foo': 'codebases' must be a list of strings or CodebaseParameter objects:",
                                     lambda: ForceScheduler(name='foo', builderNames=['bar'],
                                                            codebases=[123],))
        self.assertRaisesConfigError("ForceScheduler 'foo': 'codebases' must be a list of strings or CodebaseParameter objects:",
                                     lambda: ForceScheduler(name='foo', builderNames=['bar'],
                                                            codebases=[IntParameter('foo')],))

        # codebases cannot be empty
        self.assertRaisesConfigError("ForceScheduler 'foo': 'codebases' cannot be empty; use [CodebaseParameter(codebase='', hide=True)] if needed:",
                                     lambda: ForceScheduler(name='foo',
                                                            builderNames=[
                                                                'bar'],
                                                            codebases=[]))

        # codebases cannot be a dictionary
        # dictType on Python 3 is: "<class 'dict'>"
        # dictType on Python 2 is: "<type 'dict'>"
        dictType = str(type({}))
        errMsg = ("ForceScheduler 'foo': 'codebases' should be a list "
                  "of strings or CodebaseParameter, "
                  "not {}".format(dictType))
        self.assertRaisesConfigError(errMsg,
                                     lambda: ForceScheduler(name='foo',
                                                            builderNames=['bar'],
                                                            codebases={'cb': {'branch': 'trunk'}}))

    @defer.inlineCallbacks
    def test_good_codebases(self):
        sched = self.makeScheduler(codebases=['foo', CodebaseParameter('bar')])
        res = yield sched.force('user', builderNames=['a'], reason='because',
                                foo_branch='a', foo_revision='c', foo_repository='d', foo_project='p',
                                bar_branch='a2', bar_revision='c2', bar_repository='d2', bar_project='p2'
                                )

        bsid, brids = res
        expProperties = {
            u'owner': ('user', 'Force Build Form'),
            u'reason': ('because', 'Force Build Form'),
        }
        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForSourceStampsWithDefaults', dict(
                builderNames=['a'],
                waited_for=False,
                properties=expProperties,
                reason=u"A build was forced by 'user': because",
                sourcestamps=[
                    {'branch': 'a', 'project': 'p', 'repository': 'd',
                        'revision': 'c', 'codebase': 'foo'},
                    {'branch': 'a2', 'project': 'p2', 'repository': 'd2',
                        'revision': 'c2', 'codebase': 'bar'},
                ])),
        ])

    def formatJsonForTest(self, gotJson):
        ret = ""
        linestart = "expectJson='"
        spaces = 7 * 4 + 2
        while len(gotJson) > (90 - spaces):
            gotJson = " " * spaces + linestart + gotJson
            pos = gotJson[:100].rfind(",")
            if pos > 0:
                pos += 2
            ret += gotJson[:pos] + "'\n"
            gotJson = gotJson[pos:]
            linestart = "'"
        ret += " " * spaces + linestart + gotJson + "')\n"
        return ret

    # value = the value to be sent with the parameter (ignored if req is set)
    # expect = the expected result (can be an exception type)
    # klass = the parameter class type
    # req = use this request instead of the auto-generated one based on value
    @defer.inlineCallbacks
    def do_ParameterTest(self,
                         expect,
                         klass,
                         # None=one prop, Exception=exception, dict=many props
                         expectKind=None,
                         owner='user',
                         value=None, req=None,
                         expectJson=None,
                         **kwargs):

        name = kwargs.setdefault('name', 'p1')

        # construct one if needed
        if isinstance(klass, type):
            prop = klass(**kwargs)
        else:
            prop = klass

        self.assertEqual(prop.name, name)
        self.assertEqual(prop.label, kwargs.get('label', prop.name))
        if expectJson is not None:
            gotSpec = prop.getSpec()
            gotJson = json.dumps(gotSpec)
            expectSpec = json.loads(expectJson)
            if gotSpec != expectSpec:
                try:
                    import xerox
                    formated = self.formatJsonForTest(gotJson)
                    print(
                        "You may update the test with (copied to clipboard):\n" + formated)
                    xerox.copy(formated)
                    input()
                except ImportError:
                    print("Note: for quick fix, pip install xerox")
            self.assertEqual(gotSpec, expectSpec)

        sched = self.makeScheduler(properties=[prop])

        if not req:
            req = {name: value, 'reason': 'because'}
        try:
            bsid, brids = yield sched.force(owner, builderNames=['a'], **req)
        except Exception as e:
            if expectKind is not Exception:
                # an exception is not expected
                raise
            if not isinstance(e, expect):
                # the exception is the wrong kind
                raise
            defer.returnValue(None)  # success

        expect_props = {
            'owner': ('user', 'Force Build Form'),
            'reason': ('because', 'Force Build Form'),
        }

        if expectKind is None:
            expect_props[name] = (expect, 'Force Build Form')
        elif expectKind is dict:
            for k, v in iteritems(expect):
                expect_props[k] = (v, 'Force Build Form')
        else:
            self.fail("expectKind is wrong type!")

        # only forced on 'a'
        self.assertEqual((bsid, brids), (500, {1000: 100}))
        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForSourceStampsWithDefaults', dict(
                builderNames=['a'],
                waited_for=False,
                properties=expect_props,
                reason=u"A build was forced by 'user': because",
                sourcestamps=[
                    {'branch': '', 'project': '', 'repository': '',
                     'revision': '', 'codebase': ''},
                ])),
        ])

    def test_StringParameter(self):
        self.do_ParameterTest(value="testedvalue", expect="testedvalue",
                              klass=StringParameter,
                              expectJson='{"regex": null, "multiple": false, "name": "p1", '
                              '"default": "", "required": false, "label": "p1", "tablabel": "p1", '
                              '"hide": false, "fullName": "p1", "type": "text", "size": 10}')

    def test_StringParameter_Required(self):
        self.do_ParameterTest(value=" ", expect=CollectedValidationError,
                              expectKind=Exception,
                              klass=StringParameter, required=True)

    def test_IntParameter(self):
        self.do_ParameterTest(value="123", expect=123, klass=IntParameter,
                              expectJson='{"regex": null, "multiple": false, "name": "p1", '
                              '"default": 0, "required": false, "label": "p1", "tablabel": "p1", '
                              '"hide": false, "fullName": "p1", "type": "int", "size": 10}')

    def test_FixedParameter(self):
        self.do_ParameterTest(value="123", expect="321", klass=FixedParameter,
                              default="321",
                              expectJson='{"regex": null, "multiple": false, "name": "p1", '
                              '"default": "321", "required": false, "label": "p1", "tablabel": "p1", '
                              '"hide": true, "fullName": "p1", "type": "fixed"}')

    def test_BooleanParameter_True(self):
        req = dict(p1=True, reason='because')
        self.do_ParameterTest(value="123", expect=True, klass=BooleanParameter,
                              req=req,
                              expectJson='{"regex": null, "multiple": false, "name": "p1", '
                              '"default": "", "required": false, "label": "p1", "tablabel": "p1", '
                              '"hide": false, "fullName": "p1", "type": "bool"}')

    def test_BooleanParameter_False(self):
        req = dict(p2=True, reason='because')
        self.do_ParameterTest(value="123", expect=False,
                              klass=BooleanParameter, req=req)

    def test_UserNameParameter(self):
        email = "test <test@buildbot.net>"
        self.do_ParameterTest(value=email, expect=email,
                              klass=UserNameParameter(),
                              name="username", label="Your name:",
                              expectJson='{"regex": null, "need_email": true, "multiple": false, '
                              '"name": "username", "default": "", "required": false, '
                              '"label": "Your name:", "tablabel": "Your name:", "hide": false, '
                              '"fullName": "username", "type": "username", "size": 30}')

    def test_UserNameParameterIsValidMail(self):
        email = "test@buildbot.net"
        self.do_ParameterTest(value=email, expect=email,
                              klass=UserNameParameter(),
                              name="username", label="Your name:",
                              expectJson='{"regex": null, "need_email": true, "multiple": false, '
                              '"name": "username", "default": "", "required": false, '
                              '"label": "Your name:", "tablabel": "Your name:", "hide": false, '
                              '"fullName": "username", "type": "username", "size": 30}')

    def test_UserNameParameterIsValidMailBis(self):
        email = "<test@buildbot.net>"
        self.do_ParameterTest(value=email, expect=email,
                              klass=UserNameParameter(),
                              name="username", label="Your name:",
                              expectJson='{"regex": null, "need_email": true, "multiple": false, '
                              '"name": "username", "default": "", "required": false, '
                              '"label": "Your name:", "tablabel": "Your name:", "hide": false, '
                              '"fullName": "username", "type": "username", "size": 30}')

    def test_ChoiceParameter(self):
        self.do_ParameterTest(value='t1', expect='t1',
                              klass=ChoiceStringParameter, choices=[
                                  't1', 't2'],
                              expectJson='{"regex": null, "multiple": false, "name": "p1", '
                              '"default": "", "required": false, "label": "p1", "strict": true, '
                              '"tablabel": "p1", "hide": false, "fullName": "p1", "choices": ["t1", '
                              '"t2"], "type": "list"}')

    def test_ChoiceParameterError(self):
        self.do_ParameterTest(value='t3',
                              expect=CollectedValidationError,
                              expectKind=Exception,
                              klass=ChoiceStringParameter, choices=[
                                  't1', 't2'],
                              debug=False)

    def test_ChoiceParameterError_notStrict(self):
        self.do_ParameterTest(value='t1', expect='t1',
                              strict=False,
                              klass=ChoiceStringParameter, choices=['t1', 't2'])

    def test_ChoiceParameterMultiple(self):
        self.do_ParameterTest(value=['t1', 't2'], expect=['t1', 't2'],
                              klass=ChoiceStringParameter, choices=['t1', 't2'], multiple=True,
                              expectJson='{"regex": null, "multiple": true, "name": "p1", '
                              '"default": "", "required": false, "label": "p1", "strict": true, '
                              '"tablabel": "p1", "hide": false, "fullName": "p1", "choices": ["t1", '
                              '"t2"], "type": "list"}')

    def test_ChoiceParameterMultipleError(self):
        self.do_ParameterTest(value=['t1', 't3'],
                              expect=CollectedValidationError,
                              expectKind=Exception,
                              klass=ChoiceStringParameter, choices=[
                                  't1', 't2'],
                              multiple=True, debug=False)

    def test_NestedParameter(self):
        fields = [
            IntParameter(name="foo")
        ]
        self.do_ParameterTest(req=dict(p1_foo='123', reason="because"),
                              expect=dict(foo=123),
                              klass=NestedParameter, fields=fields,
                              expectJson='{"regex": null, "multiple": false, "name": "p1", '
                              '"default": "", "fields": [{"regex": null, "multiple": false, '
                              '"name": "foo", "default": 0, "required": false, "label": "foo", '
                              '"tablabel": "foo", "hide": false, "fullName": "p1_foo", '
                              '"type": "int", "size": 10}], "required": false, "label": "p1", '
                              '"tablabel": "p1", "hide": false, "fullName": "p1", "type": "nested", '
                              '"columns": 1, "layout": "vertical"}')

    def test_NestedNestedParameter(self):
        fields = [
            NestedParameter(name="inner", fields=[
                StringParameter(name='str'),
                AnyPropertyParameter(name='any')
            ]),
            IntParameter(name="foo")
        ]
        self.do_ParameterTest(req=dict(p1_foo='123',
                                       p1_inner_str="bar",
                                       p1_inner_any_name="hello",
                                       p1_inner_any_value="world",
                                       reason="because"),
                              expect=dict(
                                  foo=123, inner=dict(str="bar", hello="world")),
                              klass=NestedParameter, fields=fields)

    def test_NestedParameter_nullname(self):
        # same as above except "p1" and "any" are skipped
        fields = [
            NestedParameter(name="inner", fields=[
                StringParameter(name='str'),
                AnyPropertyParameter(name='')
            ]),
            IntParameter(name="foo"),
            NestedParameter(name='bar', fields=[
                NestedParameter(
                    name='', fields=[AnyPropertyParameter(name='a')]),
                NestedParameter(
                    name='', fields=[AnyPropertyParameter(name='b')])
            ])
        ]
        self.do_ParameterTest(req=dict(foo='123',
                                       inner_str="bar",
                                       inner_name="hello",
                                       inner_value="world",
                                       reason="because",
                                       bar_a_name="a",
                                       bar_a_value="7",
                                       bar_b_name="b",
                                       bar_b_value="8"),
                              expect=dict(foo=123,
                                          inner=dict(str="bar", hello="world"),
                                          bar={'a': '7', 'b': '8'}),
                              expectKind=dict,
                              klass=NestedParameter, fields=fields, name='')

    def test_bad_reason(self):
        self.assertRaisesConfigError("ForceScheduler 'testsched': reason must be a StringParameter",
                                     lambda: ForceScheduler(name='testsched', builderNames=[],
                                                            codebases=['bar'], reason="foo"))

    def test_bad_username(self):
        self.assertRaisesConfigError("ForceScheduler 'testsched': username must be a StringParameter",
                                     lambda: ForceScheduler(name='testsched', builderNames=[],
                                                            codebases=['bar'], username="foo"))

    def test_notstring_name(self):
        self.assertRaisesConfigError("ForceScheduler name must be a unicode string:",
                                     lambda: ForceScheduler(name=1234, builderNames=[],
                                                            codebases=['bar'], username="foo"))

    def test_notidentifier_name(self):
        # FIXME: this test should be removed eventually when bug 3460 gets a
        # real fix
        self.assertRaisesConfigError("ForceScheduler name must be an identifier: 'my scheduler'",
                                     lambda: ForceScheduler(name='my scheduler', builderNames=[],
                                                            codebases=['bar'], username="foo"))

    def test_emptystring_name(self):
        self.assertRaisesConfigError("ForceScheduler name must not be empty:",
                                     lambda: ForceScheduler(name='', builderNames=[],
                                                            codebases=['bar'], username="foo"))

    def test_integer_builderNames(self):
        self.assertRaisesConfigError("ForceScheduler 'testsched': builderNames must be a list of strings:",
                                     lambda: ForceScheduler(name='testsched', builderNames=1234,
                                                            codebases=['bar'], username="foo"))

    def test_listofints_builderNames(self):
        self.assertRaisesConfigError("ForceScheduler 'testsched': builderNames must be a list of strings:",
                                     lambda: ForceScheduler(name='testsched', builderNames=[1234],
                                                            codebases=['bar'], username="foo"))

    def test_listofunicode_builderNames(self):
        ForceScheduler(name='testsched', builderNames=[u'a', u'b'])

    def test_listofmixed_builderNames(self):
        self.assertRaisesConfigError("ForceScheduler 'testsched': builderNames must be a list of strings:",
                                     lambda: ForceScheduler(name='testsched',
                                                            builderNames=[
                                                                'test', 1234],
                                                            codebases=['bar'], username="foo"))

    def test_integer_properties(self):
        self.assertRaisesConfigError("ForceScheduler 'testsched': properties must be a list of BaseParameters:",
                                     lambda: ForceScheduler(name='testsched', builderNames=[],
                                                            codebases=['bar'], username="foo",
                                                            properties=1234))

    def test_listofints_properties(self):
        self.assertRaisesConfigError("ForceScheduler 'testsched': properties must be a list of BaseParameters:",
                                     lambda: ForceScheduler(name='testsched', builderNames=[],
                                                            codebases=['bar'], username="foo",
                                                            properties=[1234, 2345]))

    def test_listofmixed_properties(self):
        self.assertRaisesConfigError("ForceScheduler 'testsched': properties must be a list of BaseParameters:",
                                     lambda: ForceScheduler(name='testsched', builderNames=[],
                                                            codebases=['bar'], username="foo",
                                                            properties=[BaseParameter(name="test",),
                                                                        4567]))

    def test_novalue_to_parameter(self):
        self.assertRaisesConfigError("Use default='1234' instead of value=... to give a default Parameter value",
                                     lambda: BaseParameter(name="test", value="1234"))


class TestWorkerTransition(unittest.TestCase):

    def test_BuildslaveChoiceParameter_deprecated(self):
        from buildbot.schedulers.forcesched import WorkerChoiceParameter

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="BuildslaveChoiceParameter was deprecated"):
            from buildbot.schedulers.forcesched import BuildslaveChoiceParameter

        self.assertIdentical(BuildslaveChoiceParameter, WorkerChoiceParameter)
