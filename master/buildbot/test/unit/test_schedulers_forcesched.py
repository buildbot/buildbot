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
from twisted.internet import defer
from buildbot import config
from buildbot.schedulers.forcesched import ForceScheduler, StringParameter
from buildbot.schedulers.forcesched import IntParameter, FixedParameter
from buildbot.schedulers.forcesched import BooleanParameter, UserNameParameter
from buildbot.schedulers.forcesched import ChoiceStringParameter, ValidationError
from buildbot.schedulers.forcesched import NestedParameter, AnyPropertyParameter
from buildbot.schedulers.forcesched import CodebaseParameter, BaseParameter
from buildbot.test.util import scheduler
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.util import json

class TestForceScheduler(scheduler.SchedulerMixin, ConfigErrorsMixin, unittest.TestCase):

    OBJECTID = 19

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    def makeScheduler(self, name='testsched', builderNames=['a', 'b'],
                            **kw):
        sched = self.attachScheduler(
                ForceScheduler(name=name, builderNames=builderNames,**kw),
                self.OBJECTID, overrideBuildsetMethods=True)
        sched.master.config = config.MasterConfig()

        self.assertEquals(sched.name, name)

        return sched

    # tests

    def test_compare_branch(self):
        self.assertNotEqual(
                ForceScheduler(name="testched", builderNames=[]),
                ForceScheduler(name="testched", builderNames=[],
                    branch=FixedParameter("branch","fishing/pole")))


    def test_compare_reason(self):
        self.assertNotEqual(
                ForceScheduler(name="testched", builderNames=[],
                    reason=FixedParameter("reason","no fish for you!")),
                ForceScheduler(name="testched", builderNames=[],
                    reason=FixedParameter("reason","thanks for the fish!")))


    def test_compare_revision(self):
        self.assertNotEqual(
                ForceScheduler(name="testched", builderNames=[],
                    revision=FixedParameter("revision","fish-v1")),
                ForceScheduler(name="testched", builderNames=[],
                    revision=FixedParameter("revision","fish-v2")))


    def test_compare_repository(self):
        self.assertNotEqual(
                ForceScheduler(name="testched", builderNames=[],
                    repository=FixedParameter("repository","git://pond.org/fisher.git")),
                ForceScheduler(name="testched", builderNames=[],
                    repository=FixedParameter("repository","svn://ocean.com/trawler/")))


    def test_compare_project(self):
        self.assertNotEqual(
                ForceScheduler(name="testched", builderNames=[],
                    project=FixedParameter("project","fisher")),
                ForceScheduler(name="testched", builderNames=[],
                    project=FixedParameter("project","trawler")))


    def test_compare_username(self):
        self.assertNotEqual(
                ForceScheduler(name="testched", builderNames=[]),
                ForceScheduler(name="testched", builderNames=[],
                    project=FixedParameter("username","The Fisher King <avallach@atlantis.al>")))


    def test_compare_properties(self):
        self.assertNotEqual(
                ForceScheduler(name="testched", builderNames=[],
                    properties=[]),
                ForceScheduler(name="testched", builderNames=[],
                    properties=[FixedParameter("prop","thanks for the fish!")]))

    def test_compare_codebases(self):
        self.assertNotEqual(
                ForceScheduler(name="testched", builderNames=[],
                    codebases=['bar']),
                ForceScheduler(name="testched", builderNames=[],
                    codebases=['foo']))


    @defer.inlineCallbacks
    def test_basicForce(self):
        sched = self.makeScheduler()

        res = yield sched.force('user', builderNames=['a'], branch='a', reason='because',revision='c',
                        repository='d', project='p',
                        property1_name='p1',property1_value='e',
                        property2_name='p2',property2_value='f',
                        property3_name='p3',property3_value='g',
                        property4_name='p4',property4_value='h'
                        )

        # only one builder forced, so there should only be one brid
        self.assertEqual(res, (500, {'a':100}))
        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForSourceStampsWithDefaults', dict(
                builderNames=['a'],
                waited_for=False,
                properties={
                    u'owner': ('user', u'Force Build Form'),
                    u'p1': ('e', u'Force Build Form'),
                    u'p2': ('f', u'Force Build Form'),
                    u'p3': ('g', u'Force Build Form'),
                    u'p4': ('h', u'Force Build Form'),
                    u'reason': ('because', u'Force Build Form'),
                },
                reason=u"A build was forced by 'user': because",
                sourcestamps=[
                    { 'codebase': '', 'branch': 'a', 'revision': 'c',
                      'repository': 'd', 'project': 'p' },
                ])),
        ])


    @defer.inlineCallbacks
    def test_basicForce_reasonString(self):
        """Same as above, but with a reasonString"""
        sched = self.makeScheduler(reasonString='%(owner)s wants it %(reason)s')

        res = yield sched.force('user', builderNames=['a'], branch='a', reason='because',revision='c',
                        repository='d', project='p',
                        property1_name='p1',property1_value='e',
                        property2_name='p2',property2_value='f',
                        property3_name='p3',property3_value='g',
                        property4_name='p4',property4_value='h'
                        )
        bsid,brids = res

        # only one builder forced, so there should only be one brid
        self.assertEqual(len(brids), 1)

        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForSourceStampsWithDefaults', {
                'builderNames': ['a'],
                'properties': {u'owner': ('user', u'Force Build Form'),
                                u'p1': ('e', u'Force Build Form'),
                                u'p2': ('f', u'Force Build Form'),
                                u'p3': ('g', u'Force Build Form'),
                                u'p4': ('h', u'Force Build Form'),
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
                  properties=[ ('owner', ('user', 'Force Build Form')),
                               ('p1', ('e', 'Force Build Form')),
                               ('p2', ('f', 'Force Build Form')),
                               ('p3', ('g', 'Force Build Form')),
                               ('p4', ('h', 'Force Build Form')),
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

        res = yield sched.force('user', branch='a', reason='because',revision='c',
                        repository='d', project='p',
                        )
        self.assertEqual(res, (500, {'a': 100, 'b': 101}))
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
                    { 'codebase': '', 'branch': 'a', 'revision': 'c',
                      'repository': 'd', 'project': 'p' },
                ])),
        ])

    @defer.inlineCallbacks
    def test_force_someBuilders(self):
        sched = self.makeScheduler(builderNames=['a','b','c'])

        res = yield sched.force('user', builderNames=['a','b'],
                        branch='a', reason='because',revision='c',
                        repository='d', project='p',
                        )
        self.assertEqual(res, (500, {'a': 100, 'b': 101}))
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
                    { 'codebase': '', 'branch': 'a', 'revision': 'c',
                      'repository': 'd', 'project': 'p' },
                ])),
        ])

    def test_bad_codebases(self):
        # cant specify both codebases and branch/revision/project/repository:
        self.assertRaisesConfigError("ForceScheduler: Must either specify 'codebases' or the 'branch/revision/repository/project' parameters:",
             lambda: ForceScheduler(name='foo', builderNames=['bar'],
                                    codebases=['foo'], branch=StringParameter('name')))
        self.assertRaisesConfigError("ForceScheduler: Must either specify 'codebases' or the 'branch/revision/repository/project' parameters:",
             lambda: ForceScheduler(name='foo', builderNames=['bar'],
                                    codebases=['foo'], revision=StringParameter('name')))
        self.assertRaisesConfigError("ForceScheduler: Must either specify 'codebases' or the 'branch/revision/repository/project' parameters:",
             lambda: ForceScheduler(name='foo', builderNames=['bar'],
                                    codebases=['foo'], project=StringParameter('name')))
        self.assertRaisesConfigError("ForceScheduler: Must either specify 'codebases' or the 'branch/revision/repository/project' parameters:",
             lambda: ForceScheduler(name='foo', builderNames=['bar'],
                                    codebases=['foo'], repository=StringParameter('name')))

        # codebases must be a list of either string or BaseParameter types
        self.assertRaisesConfigError("ForceScheduler: 'codebases' must be a list of strings or CodebaseParameter objects:",
             lambda: ForceScheduler(name='foo', builderNames=['bar'],
                                    codebases=[123],))
        self.assertRaisesConfigError("ForceScheduler: 'codebases' must be a list of strings or CodebaseParameter objects:",
             lambda: ForceScheduler(name='foo', builderNames=['bar'],
                                    codebases=[IntParameter('foo')],))

        # codebases cannot be empty
        self.assertRaisesConfigError("ForceScheduler: 'codebases' cannot be empty; use CodebaseParameter(codebase='', hide=True) if needed:",
                                     lambda: ForceScheduler(name='foo',
                                                            builderNames=['bar'],
                                                            codebases=[]))

    @defer.inlineCallbacks
    def test_good_codebases(self):
        sched = self.makeScheduler(codebases=['foo', CodebaseParameter('bar')])
        res = yield sched.force('user', builderNames=['a'], reason='because',
                        foo_branch='a', foo_revision='c', foo_repository='d', foo_project='p',
                        bar_branch='a2', bar_revision='c2', bar_repository='d2', bar_project='p2',
                        property1_name='p1',property1_value='e',
                        property2_name='p2',property2_value='f',
                        property3_name='p3',property3_value='g',
                        property4_name='p4',property4_value='h'
                        )

        bsid,brids = res
        expProperties = {
            u'owner' : ('user', 'Force Build Form'),
            u'p1' : ('e', 'Force Build Form'),
            u'p2' : ('f', 'Force Build Form'),
            u'p3' : ('g', 'Force Build Form'),
            u'p4' : ('h', 'Force Build Form'),
            u'reason' : ('because', 'Force Build Form'),
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

    # value = the value to be sent with the parameter (ignored if req is set)
    # expect = the expected result (can be an exception type)
    # klass = the parameter class type
    # req = use this request instead of the auto-generated one based on value
    @defer.inlineCallbacks
    def do_ParameterTest(self,
                         expect,
                         klass,
                         expectKind=None, # None=one prop, Exception=exception, dict=many props
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
            self.assertEqual(json.dumps(prop.toJsonDict()), expectJson)

        sched = self.makeScheduler(properties=[prop])

        if not req:
            req = {name:value, 'reason':'because'}
        try:
            bsid, brids = yield sched.force(owner, builderNames=['a'], **req)
        except Exception,e:
            if expectKind is not Exception:
                # an exception is not expected
                raise
            if not isinstance(e, expect):
                # the exception is the wrong kind
                raise
            defer.returnValue(None) # success

        expect_props = {
            'owner' : ('user', 'Force Build Form'),
            'reason' : ('because', 'Force Build Form'),
        }

        if expectKind is None:
            expect_props[name] = (expect, 'Force Build Form')
        elif expectKind is dict:
            for k,v in expect.iteritems():
                expect_props[k] =  (v, 'Force Build Form')
        else:
            self.fail("expectKind is wrong type!")

        self.assertEqual((bsid, brids), (500, {'a':100})) # only forced on 'a'
        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForSourceStampsWithDefaults', dict(
                builderNames=['a'],
                waited_for=False,
                properties=expect_props,
                reason=u"A build was forced by 'user': because",
                sourcestamps=[
                    { 'branch': '', 'project': '', 'repository': '',
                      'revision': '', 'codebase': '' },
                ])),
        ])

    def test_StringParameter(self):
        self.do_ParameterTest(value="testedvalue", expect="testedvalue",
                              klass=StringParameter,
                              expectJson='{"regex": null, "required": false, "hide": false, '
                              '"name": "p1", "default": "", "css_class": "", '
                              '"parentName": null, "label": "p1", "subtype": "", '
                              '"debug": true, "multiple": false, "fullName": "p1", "type": "text", '
                              '"size": 10}')

    def test_IntParameter(self):
        self.do_ParameterTest(value="123", expect=123, klass=IntParameter,
                              expectJson='{"regex": null, "required": false, "hide": false, '
                              '"name": "p1", "default": "", "css_class": "", '
                              '"parentName": null, "label": "p1", "subtype": "", '
                              '"debug": true, "multiple": false, "fullName": "p1", "type": "int", '
                              '"size": 10}')


    def test_FixedParameter(self):
        self.do_ParameterTest(value="123", expect="321", klass=FixedParameter,
                              default="321",
                              expectJson='{"regex": null, "required": false, "hide": true, '
                              '"name": "p1", "default": "321", "css_class": "", '
                              '"parentName": null, "label": "p1", "subtype": "", '
                              '"debug": true, "multiple": false, "fullName": "p1", "type": "fixed"}')

    def test_BooleanParameter_True(self):
        req = dict(p1=True,reason='because')
        self.do_ParameterTest(value="123", expect=True, klass=BooleanParameter,
                              req=req,
                              expectJson='{"regex": null, "required": false, "hide": false, '
                              '"name": "p1", "default": "", "css_class": "", '
                              '"parentName": null, "label": "p1", "subtype": "", '
                              '"debug": true, "multiple": false, "fullName": "p1", "type": "bool"}')

    def test_BooleanParameter_False(self):
        req = dict(p2=True,reason='because')
        self.do_ParameterTest(value="123", expect=False,
                              klass=BooleanParameter, req=req)

    def test_UserNameParameter(self):
        email = "test <test@buildbot.net>"
        self.do_ParameterTest(value=email, expect=email,
                              klass=UserNameParameter(),
                              name="username", label="Your name:",
                              expectJson='{"regex": null, "parentName": null, "hide": false, '
                              '"name": "username", "default": "", "css_class": "", '
                              '"need_email": true, "label": "Your name:", "subtype": "", '
                              '"debug": true, "multiple": false, "fullName": "username", '
                              '"size": 30, "type": "text", "required": false}')

    def test_UserNameParameterError(self):
        for value in ["test","test@buildbot.net","<test@buildbot.net>"]:
            self.do_ParameterTest(value=value,
                    expect=ValidationError,
                    expectKind=Exception,
                    klass=UserNameParameter(debug=False),
                    name="username", label="Your name:")

    def test_ChoiceParameter(self):
        self.do_ParameterTest(value='t1', expect='t1',
                klass=ChoiceStringParameter, choices=['t1','t2'],
                expectJson='{"regex": null, "required": false, "hide": false, '
                '"name": "p1", "subtype": "", "default": "", "css_class": "", '
                '"parentName": null, "choices": ["t1", "t2"], "strict": true, '
                '"debug": true, "multiple": false, "fullName": "p1", '
                '"label": "p1", "type": "list"}')

    def test_ChoiceParameterError(self):
        self.do_ParameterTest(value='t3',
                expect=ValidationError,
                expectKind=Exception,
                klass=ChoiceStringParameter, choices=['t1','t2'],
                debug=False)

    def test_ChoiceParameterError_notStrict(self):
        self.do_ParameterTest(value='t1', expect='t1',
                strict=False,
                klass=ChoiceStringParameter, choices=['t1','t2'])



    def test_ChoiceParameterMultiple(self):
        self.do_ParameterTest(value=['t1','t2'], expect=['t1','t2'],
                klass=ChoiceStringParameter,choices=['t1','t2'], multiple=True,
                expectJson='{"regex": null, "required": false, "hide": false, '
                '"name": "p1", "subtype": "", "default": "", "css_class": "", '
                '"parentName": null, "choices": ["t1", "t2"], "strict": true, '
                '"debug": true, "multiple": true, "fullName": "p1", '
                '"label": "p1", "type": "list"}')



    def test_ChoiceParameterMultipleError(self):
        self.do_ParameterTest(value=['t1','t3'],
                expect=ValidationError,
                expectKind=Exception,
                klass=ChoiceStringParameter, choices=['t1','t2'],
                multiple=True, debug=False)

    def test_NestedParameter(self):
        fields = [
            IntParameter(name="foo")
        ]
        self.do_ParameterTest(req=dict(p1_foo='123', reason="because"),
                              expect=dict(foo=123),
                              klass=NestedParameter, fields=fields,
                              expectJson='{"regex": null, "required": false, "hide": false, '
                              '"name": "p1", "default": "", "css_class": "", '
                              '"parentName": null, "label": "p1", "subtype": "", '
                              '"fields": [{"regex": null, "required": false, "hide": false, '
                              '"name": "foo", "default": "", "css_class": "", '
                              '"parentName": "p1", "label": "foo", "subtype": "", "debug": true, '
                              '"multiple": false, "fullName": "p1_foo", "type": "int", '
                              '"size": 10}], "debug": true, "multiple": false, '
                              '"fullName": "p1", "type": "nested", "columns": 1}')

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
                              expect=dict(foo=123, inner=dict(str="bar", hello="world")),
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
                NestedParameter(name='', fields=[AnyPropertyParameter(name='a')]),
                NestedParameter(name='', fields=[AnyPropertyParameter(name='b')])
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
                                          bar={'a':'7', 'b':'8'}),
                              expectKind=dict,
                              klass=NestedParameter, fields=fields, name='')

    def test_bad_reason(self):
        self.assertRaisesConfigError("ForceScheduler reason must be a StringParameter",
             lambda: ForceScheduler(name='testsched', builderNames=[],
                                    codebases=['bar'], reason="foo"))

    def test_bad_username(self):
        self.assertRaisesConfigError("ForceScheduler username must be a StringParameter",
             lambda: ForceScheduler(name='testsched', builderNames=[],
                                    codebases=['bar'], username="foo"))

    def test_notstring_name(self):
        self.assertRaisesConfigError("ForceScheduler name must be a unicode string:",
             lambda: ForceScheduler(name=1234, builderNames=[],
                                    codebases=['bar'], username="foo"))

    def test_emptystring_name(self):
        self.assertRaisesConfigError("ForceScheduler name must not be empty:",
             lambda: ForceScheduler(name='', builderNames=[],
                                    codebases=['bar'], username="foo"))

    def test_integer_builderNames(self):
        self.assertRaisesConfigError("ForceScheduler builderNames must be a list of strings:",
             lambda: ForceScheduler(name='testsched', builderNames=1234,
                                    codebases=['bar'], username="foo"))

    def test_listofints_builderNames(self):
        self.assertRaisesConfigError("ForceScheduler builderNames must be a list of strings:",
             lambda: ForceScheduler(name='testsched', builderNames=[1234],
                                    codebases=['bar'], username="foo"))

    def test_listofmixed_builderNames(self):
        self.assertRaisesConfigError("ForceScheduler builderNames must be a list of strings:",
             lambda: ForceScheduler(name='testsched',
                                    builderNames=['test', 1234],
                                    codebases=['bar'], username="foo"))

    def test_integer_properties(self):
        self.assertRaisesConfigError("ForceScheduler properties must be a list of BaseParameters:",
             lambda: ForceScheduler(name='testsched', builderNames=[],
                                    codebases=['bar'], username="foo",
                                    properties=1234))

    def test_listofints_properties(self):
        self.assertRaisesConfigError("ForceScheduler properties must be a list of BaseParameters:",
             lambda: ForceScheduler(name='testsched', builderNames=[],
                                    codebases=['bar'], username="foo",
                                    properties=[1234, 2345]))

    def test_listofmixed_properties(self):
        self.assertRaisesConfigError("ForceScheduler properties must be a list of BaseParameters:",
             lambda: ForceScheduler(name='testsched', builderNames=[],
                                    codebases=['bar'], username="foo",
                                    properties=[BaseParameter(name="test",),
                                                4567]))
