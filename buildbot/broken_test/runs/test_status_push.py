# -*- test-case-name: buildbot.broke_test.runs.test_status_push -*-

import re
import os

try:
    import simplejson as json
except ImportError:
    import json

from twisted.internet import defer, reactor
from twisted.python import log
from twisted.trial import unittest
from twisted.web import server, resource
from twisted.web.error import Error
from zope.interface import implements, Interface

from buildbot import master
from buildbot.changes import changes
from buildbot.slave import bot
from buildbot.sourcestamp import SourceStamp
from buildbot.status import status_push
from buildbot.status.persistent_queue import IQueue, ReadFile
from buildbot.broken_test.runutils import MasterMixin
from buildbot.broken_test.status_push_server import EventsHandler


config_base = """
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig
from buildbot.process import factory
from buildbot.schedulers import basic
from buildbot.status import html
from buildbot.status.status_push import StatusPush, HttpStatusPush
from buildbot.steps import dummy

BuildmasterConfig = c = {
    'slaves': [BuildSlave('bot1', 'sekrit')],
    'schedulers': [basic.Scheduler(name='dummy', branch=None,
                                   treeStableTimer=60, builderNames=['dummy'])],
    'builders': [
            BuilderConfig(name='dummy',
                slavename='bot1',
                factory=factory.QuickBuildFactory('fakerep', 'cvsmodule',
                                                  configure=None),
                builddir='quickdir',
                slavebuilddir='slavequickdir'),
            #BuilderConfig(name='builder1', slavename='bot1name',
            #              factory=BuildFactory()),
        ],
    'status': [html.WebStatus(http_port=0)],
    'slavePortnum': 0,
    'projectUrl': 'example.com/yay',
    'projectName': 'Pouet',
    'buildbotURL': 'build.example.com/yo',
}
"""

config_no_http = (config_base + """
def doNothing():
    pass
c['status'] = [StatusPush(serverPushCb=doNothing)]
""")

config_http = (config_base + """
c['status'] = [HttpStatusPush('http://127.0.0.1:<PORT>/receiver')]
""")

config_no_http_no_filter = (config_base + """
def doNothing():
    pass
c['status'] = [StatusPush(serverPushCb=doNothing, filter=False)]
""")

config_http_no_filter = (config_base + """
c['status'] = [HttpStatusPush('http://127.0.0.1:<PORT>/receiver', filter=False)]
""")

EXPECTED = [
    {
        'event': 'builderAdded',
        'payload': {
            'builder': {
                "category": None,
                "cachedBuilds": [],
                "basedir": "quickdir",
                "pendingBuilds": [],
                "state": "offline",
                "slaves": ["bot1"],
                "currentBuilds": []
            },
            'builderName': 'dummy',
        }
    },
    {
        "event": "builderChangedState",
        "payload": {
            'state': 'offline',
            'builderName': 'dummy'
        }
    },
    {
        "event": "start",
        "payload": {
            'status': {
                "buildbotURL": 'build.example.com/yo',
                "projectName": 'Pouet',
                'projectURL': None,
            }
        }
    },
    {
        'event': 'slaveConnected',
        'payload': {
            'slave': {
                'access_uri': None,
                'admin': 'one',
                'connected': True,
                'host': None,
                'name': 'bot1',
                'runningBuilds': [],
                'version': 'latest'
            }
        }
    },
    {
        "event": "changeAdded",
        "payload": {
            'change': {
                "category": None,
                "files": ["Makefile", "foo/bar.c"],
                "who": "bob",
                "when": "n0w",
                "number": 1,
                "comments": "changed stuff",
                "branch": None,
                "revlink": "",
                "properties": [],
                "revision": None,
                "project": "",
                "repository": "",
            }
        }
    },
    {
        'event': 'builderChangedState',
        'payload': {
            'state': 'building',
            'builderName': 'dummy'
        }
    },
    {
        'event': 'buildStarted',
        'payload': {
            'build': {
                'blame': ['bob'],
                'builderName': 'dummy',
                'currentStep': None,
                'eta': None,
                'number': 0,
                'properties': [
                    ['branch', None, 'Build'],
                    ['buildername', 'dummy', 'Build'],
                    ['buildnumber', 0, 'Build'],
                    ['project', '', 'Build'],
                    ['repository', '', 'Build'],
                    ['revision', 'None', 'Build'],
                    ['slavename', 'bot1', 'BuildSlave']
                ],
                'reason': 'Reason 0',
                'results': None,
                'slave': 'bot1',
                'sourceStamp': {
                    'branch': None,
                    'changes': [
                        {
                            'branch': None,
                            'category': None,
                            'comments': 'changed stuff',
                            'files': ['Makefile', 'foo/bar.c'],
                            'number': 1,
                            'project': '',
                            'properties': [],
                            'repository': '',
                            'revision': None,
                            'revlink': '',
                            'when': 'yesterday',
                            'who': 'bob'
                        },
                    ],
                    'project': '',
                    'repository': '',
                    # BUG!!
                    'revision': 'None'
                },
                'steps': [
                    {
                        'eta': None,
                        'expectations': [],
                        'isFinished': False,
                        'isStarted': False,
                        'name': 'cvs',
                        'results': [[None, []], []],
                        'statistics': {},
                        'text': [],
                        'times': [None, None],
                        'urls': {}
                    },
                    {
                        'eta': None,
                        'expectations': [],
                        'isFinished': False,
                        'isStarted': False,
                        'name': 'compile',
                        'results': [[None, []], []],
                        'statistics': {},
                        'text': [],
                        'times': [None, None],
                        'urls': {}
                    },
                    {
                        'eta': None,
                        'expectations': [],
                        'isFinished': False,
                        'isStarted': False,
                        'name': 'test',
                        'results': [[None, []], []],
                        'statistics': {},
                        'text': [],
                        'times': [None, None],
                        'urls': {}
                    }
                ],
                'text': [],
                'times': [123, None]
            }
        }
    },
    {
        'event': 'stepStarted',
        'payload': {
            'step': {
                'eta': None,
                'expectations': [],
                'isFinished': False,
                'isStarted': True,
                'name': 'cvs',
                'results': [[None, []], []],
                'statistics': {},
                'text': ['updating'],
                'times': [123, None],
                'urls': {}
            },
            'properties': [
                ['branch', None, 'Build'],
                ['buildername', 'dummy', 'Build'],
                ['buildnumber', 0, 'Build'],
                ['project', '', 'Build'],
                ['repository', '', 'Build'],
                ['revision', 'None', 'Build'],
                ['slavename', 'bot1', 'BuildSlave']
            ],
        }
    },
    {
        'event': 'stepFinished',
        'payload': {
            'step': {
                'eta': None,
                'expectations': [],
                'isFinished': True,
                'isStarted': True,
                'name': 'cvs',
                'results': [2, ['cvs']],
                'statistics': {},
                'text': ['update', 'failed'],
                'times': [123, None],
                'urls': {}
            },
            'properties': [
                ['branch', None, 'Build'],
                ['buildername', 'dummy', 'Build'],
                ['buildnumber', 0, 'Build'],
                ['project', '', 'Build'],
                ['repository', '', 'Build'],
                ['revision', 'None', 'Build'],
                ['slavename', 'bot1', 'BuildSlave']
            ],
        }
    },
    {
        'event': 'buildFinished',
        'payload': {
            'build': {
                'blame': ['bob'],
                'builderName': 'dummy',
                'currentStep': None,
                'eta': None,
                'number': 0,
                'properties': [
                    ['branch', None, 'Build'],
                    ['buildername', 'dummy', 'Build'],
                    ['buildnumber', 0, 'Build'],
                    ['project', '', 'Build'],
                    ['repository', '', 'Build'],
                    ['revision', 'None', 'Build'],
                    ['slavename', 'bot1', 'BuildSlave']
                ],
                'reason': 'Reason 0',
                'results': 2,
                'slave': 'bot1',
                'sourceStamp': {
                    'branch': None,
                    'changes': [
                        {
                            'branch': None,
                            'category': None,
                            'comments': 'changed stuff',
                            'files': ['Makefile', 'foo/bar.c'],
                            'number': 1,
                            'project': '',
                            'properties': [],
                            'repository': '',
                            'revision': None,
                            'revlink': '',
                            'when': 'yesterday',
                            'who': 'bob'
                        },
                    ],
                    'project': '',
                    'repository': '',
                    # BUG!!
                    'revision': 'None'
                },
                'steps': [
                    {
                        'eta': None,
                        'expectations': [],
                        'isFinished': True,
                        'isStarted': True,
                        'name': 'cvs',
                        'results': [2, ['cvs']],
                        'statistics': {},
                        'text': ['update', 'failed'],
                        'times': [345, None],
                        'urls': {}
                    },
                    {
                        'eta': None,
                        'expectations': [],
                        'isFinished': False,
                        'isStarted': False,
                        'name': 'compile',
                        'results': [[None, []], []],
                        'statistics': {},
                        'text': [],
                        'times': [345, None],
                        'urls': {}
                    },
                    {
                        'eta': None,
                        'expectations': [],
                        'isFinished': False,
                        'isStarted': False,
                        'name': 'test',
                        'results': [[None, []], []],
                        'statistics': {},
                        'text': [],
                        'times': [345, None],
                        'urls': {}
                    }
                ],
                'text': ['failed', 'cvs'],
                'times': [123, None]
            },
        }
    },
    {
        'event': 'builderChangedState',
        'payload': {
            'state': 'idle',
            'builderName': 'dummy'
        }
    },
    {
        'event': 'slaveDisconnected',
        'payload': {
            'slavename': 'bot1'
        }
    },
    {
        'event': 'builderChangedState',
        'payload': {
            'state': 'offline',
            'builderName': 'dummy',
        }
    },
    {
        "event": "shutdown",
        "payload": {
            'status': {
                "buildbotURL": 'build.example.com/yo',
                "projectName": 'Pouet',
                'projectURL': None,
            }
        }
    },
]

EXPECTED_SHORT = [
    {
        'event': 'builderAdded',
        'payload': {
            'builder': {
                "basedir": "quickdir",
                "state": "offline",
                "slaves": ["bot1"],
            },
            'builderName': 'dummy',
        }
    },
    {
        "event": "builderChangedState",
        "payload": {
            'state': 'offline',
            'builderName': 'dummy'
        }
    },
    {
        "event": "start",
        "payload": {
            'status': {
                "buildbotURL": 'build.example.com/yo',
                "projectName": 'Pouet',
            }
        }
    },
    {
        'event': 'slaveConnected',
        'payload': {
            'slave': {
                'admin': 'one',
                'connected': True,
                'name': 'bot1',
                'version': 'latest'
            }
        }
    },
    {
        "event": "changeAdded",
        "payload": {
            'change': {
                "files": ["Makefile", "foo/bar.c"],
                "who": "bob",
                "when": "n0w",
                "number": 1,
                "comments": "changed stuff",
            }
        }
    },
    {
        'event': 'builderChangedState',
        'payload': {
            'state': 'building',
            'builderName': 'dummy'
        }
    },
    {
        'event': 'buildStarted',
        'payload': {
            'build': {
                'blame': ['bob'],
                'builderName': 'dummy',
                'properties': [
                    ['branch', None, 'Build'],
                    ['buildername', 'dummy', 'Build'],
                    ['buildnumber', 0, 'Build'],
                    ['project', '', 'Build'],
                    ['repository', '', 'Build'],
                    # BUG!!
                    ['revision', 'None', 'Build'],
                    ['slavename', 'bot1', 'BuildSlave']
                ],
                'reason': 'Reason 0',
                'slave': 'bot1',
                'sourceStamp': {
                    'changes': [
                        {
                            'comments': 'changed stuff',
                            'files': ['Makefile', 'foo/bar.c'],
                            'number': 1,
                            'when': 'yesterday',
                            'who': 'bob'
                        }
                    ],
                    # BUG!!
                    'revision': 'None'
                },
                'steps': [
                    {
                        'name': 'cvs',
                    },
                    {
                        'name': 'compile',
                    },
                    {
                        'name': 'test',
                    }
                ],
                'times': [123, None]
            }
        }
    },
    {
        'event': 'stepStarted',
        'payload': {
            'step': {
                'isStarted': True,
                'name': 'cvs',
                'text': ['updating'],
                'times': [123, None],
            },
            'properties': [
                ['branch', None, 'Build'],
                ['buildername', 'dummy', 'Build'],
                ['buildnumber', 0, 'Build'],
                ['project', '', 'Build'],
                ['repository', '', 'Build'],
                ['revision', 'None', 'Build'],
                ['slavename', 'bot1', 'BuildSlave']
            ],
        }
    },
    {
        'event': 'stepFinished',
        'payload': {
            'step': {
                'isFinished': True,
                'isStarted': True,
                'name': 'cvs',
                'results': [2, ['cvs']],
                'text': ['update', 'failed'],
                'times': [123, None],
            },
            'properties': [
                ['branch', None, 'Build'],
                ['buildername', 'dummy', 'Build'],
                ['buildnumber', 0, 'Build'],
                ['project', '', 'Build'],
                ['repository', '', 'Build'],
                ['revision', 'None', 'Build'],
                ['slavename', 'bot1', 'BuildSlave']
            ],
        }
    },
    {
        'event': 'buildFinished',
        'payload': {
            'build': {
                'blame': ['bob'],
                'builderName': 'dummy',
                'properties': [
                    ['branch', None, 'Build'],
                    ['buildername', 'dummy', 'Build'],
                    ['buildnumber', 0, 'Build'],
                    ['project', '', 'Build'],
                    ['repository', '', 'Build'],
                    ['revision', 'None', 'Build'],
                    ['slavename', 'bot1', 'BuildSlave']
                ],
                'reason': 'Reason 0',
                'results': 2,
                'slave': 'bot1',
                'sourceStamp': {
                    'changes': [
                        {
                            'comments': 'changed stuff',
                            'files': ['Makefile', 'foo/bar.c'],
                            'number': 1,
                            'when': 'yesterday',
                            'who': 'bob'
                        }
                    ],
                    'revision': 'None'
                },
                'steps': [
                    {
                        'isFinished': True,
                        'isStarted': True,
                        'name': 'cvs',
                        'results': [2, ['cvs']],
                        'text': ['update', 'failed'],
                        'times': [345, None],
                    },
                    {
                        'name': 'compile',
                    },
                    {
                        'name': 'test',
                    }
                ],
                'text': ['failed', 'cvs'],
                'times': [123, None]
            },
        }
    },
    {
        'event': 'builderChangedState',
        'payload': {
            'state': 'idle',
            'builderName': 'dummy'
        }
    },
    {
        'event': 'slaveDisconnected',
        'payload': {
            'slavename': 'bot1'
        }
    },
    {
        'event': 'builderChangedState',
        'payload': {
            'state': 'offline',
            'builderName': 'dummy',
        }
    },
    {
        "event": "shutdown",
        "payload": {
            'status': {
                "buildbotURL": 'build.example.com/yo',
                "projectName": 'Pouet',
            }
        }
    },
]

class Receiver(resource.Resource):
    isLeaf = True
    def __init__(self):
        self.packets = []

    def render_POST(self, request):
        for packet in request.args['packets']:
            data = json.loads(packet)
            for p in data:
                self.packets.append(p)
        return "ok"


class StatusPushTestBase(MasterMixin, unittest.TestCase):
    def getStatusPush(self):
        for i in self.master.services:
            if isinstance(i, status_push.StatusPush):
                return i

    def generateActivity(self, config):
        self.rmtree("status_push")
        self.basedir = "status_push"
        self.create_master()
        d = self.master.loadConfig(config)
        d.addCallback(lambda res: self.connectSlave(slavename='bot1'))
        NB_CHANGES = 1
        def _send(res):
            cm = self.master.change_svc
            c = changes.Change("bob", ["Makefile", "foo/bar.c"], "changed stuff")
            cm.addChange(c)
            # send some build requests
            reqs = []
            ss = SourceStamp(changes=[c])
            for i in range(NB_CHANGES):
                bss = self.control.submitBuildSet(["dummy"], ss,
                                                  reason='Reason %d' %i)
                reqs.append(bss.waitUntilFinished())
            return defer.DeferredList(reqs)
        d.addCallback(_send)

        def check(res):
            builder = self.status.getBuilder("dummy")
            self.failUnlessEqual(len(builder.slavenames), 1)
            for i in range(NB_CHANGES):
                build = builder.getBuild(i)
                self.assertTrue(build != None, str(i))
                self.failUnlessEqual(build.slavename, 'bot1')
        d.addCallback(check)
        return d

    def shutdownMaster(self):
        d = self.shutdownAllSlaves()
        d.addCallback(self.wait_until_idle)
        d.addCallback(lambda ign: self.master.stopService())
        d.addCallback(self.wait_until_idle)
        # Unset our master instance so that future invocations of this TestCase
        # will work as expected (e.g. when doing trial -u)
        def _done(_):
            self.master = None
        d.addCallback(_done)
        return d

    def verifyItems(self, items, expected):
        def QuickFix(item, *args):
            """Strips time-specific values.

            None means an array.
            Anything else is a key to a dict."""
            args = list(args)
            value = args.pop()

            def Loop(item, value, *args):
                args = list(args)
                arg = args.pop(0)
                if isinstance(item, list) and arg is None:
                    for i in item:
                        Loop(i, value, *args)
                elif isinstance(item, dict):
                    if len(args) == 0 and arg in item:
                        item[arg] = value
                    elif arg in item:
                        Loop(item[arg], value, *args)

            Loop(item, value, *args)

        def FindItem(items, event, *args):
            for i in items:
                if i['event'] == event:
                    QuickFix(i, *args)

        # Cleanup time dependent values.
        # TODO(maruel) Mock datetime instead!
        for i in range(len(items)):
            item = items[i]
            del item['started']
            del item['timestamp']
            self.assertEqual('Pouet', item.pop('project'))
            self.assertEqual(i + 1, item.pop('id'))

        FindItem(items, 'changeAdded', 'payload', 'change', 'when',
                'n0w')
        FindItem(items, 'requestSubmitted', 'payload', 'request',
                'submittedAt', 'yesterday')

        FindItem(items, 'buildStarted', 'payload', 'build', 'sourceStamp',
                'changes', None, 'when', 'yesterday')
        FindItem(items, 'buildFinished', 'payload', 'build', 'sourceStamp',
                'changes', None, 'when', 'yesterday')

        FindItem(items, 'buildStarted', 'payload', 'build', 'requests',
                None, 'submittedAt', 'yesterday')
        FindItem(items, 'stepStarted', 'payload', 'build', 'requests',
                None, 'submittedAt', 'yesterday')
        FindItem(items, 'stepFinished', 'payload', 'build', 'requests',
                None, 'submittedAt', 'yesterday')
        FindItem(items, 'buildFinished', 'payload', 'build', 'requests',
                None, 'submittedAt', 'yesterday')

        FindItem(items, 'buildStarted', 'payload', 'build', 'times',
                [123, None])
        FindItem(items, 'stepStarted', 'payload', 'build', 'times',
                [123, None])
        FindItem(items, 'stepStarted', 'payload', 'step', 'times',
                [123, None])
        FindItem(items, 'stepFinished', 'payload', 'build', 'times',
                [123, None])
        FindItem(items, 'stepFinished', 'payload', 'step', 'times',
                [123, None])
        FindItem(items, 'buildFinished', 'payload', 'build', 'times',
                [123, None])

        FindItem(items, 'stepStarted', 'payload', 'build',
                'current_step', 'times', [234, None])
        FindItem(items, 'stepFinished', 'payload', 'build',
                'current_step', 'times', [234, None])
        FindItem(items, 'buildFinished', 'payload', 'build',
                'current_step', 'times', [234, None])

        FindItem(items, 'stepStarted', 'payload', 'build', 'steps', None,
                'times', [345, None])
        FindItem(items, 'stepFinished', 'payload', 'build', 'steps',
                None, 'times', [345, None])
        FindItem(items, 'buildFinished', 'payload', 'build', 'steps',
                None, 'times', [345, None])

        for i in range(len(expected)):
            self.assertEqual(expected[i], items[i], str(i))
        self.assertEqual(len(expected), len(items))


class StatusPushTest(StatusPushTestBase):
    def _runTest(self, expected, config):
        self.expected = expected
        d = self.generateActivity(config)
        d.addCallback(self._testPhase1)
        return d

    def testNotFiltered(self):
        return self._runTest(EXPECTED, config_no_http_no_filter)

    def testFiltered(self):
        return self._runTest(EXPECTED_SHORT, config_no_http)

    def _testPhase1(self, _):
        self.status_push = self.getStatusPush()
        d = self.shutdownMaster()
        d.addCallback(self._testPhase2)
        return d

    def _testPhase2(self, _):
        def TupleToList(items):
            if isinstance(items, (list, tuple)):
                return [TupleToList(i) for i in items]
            if isinstance(items, dict):
                return dict([(k, TupleToList(v))
                             for (k, v) in items.iteritems()])
            else:
                return items
        self.verifyItems(TupleToList(self.status_push.queue.items()),
                         self.expected)


class HttpStatusPushTest(StatusPushTestBase):
    def tearDown(self):
        StatusPushTestBase.tearDown(self)
        state_path = os.path.join(self.path, 'state')
        state = json.loads(ReadFile(state_path))
        del state['started']
        EXPECTED_STATE = {"last_id_pushed": 0, "next_id": len(EXPECTED_SHORT)+1}
        self.assertEqual(EXPECTED_STATE, state)
        os.remove(state_path)
        self.assertEqual([], os.listdir(self.path))

    def _runTest(self, expected, config):
        self.expected = expected
        path = os.path.join(os.path.dirname(__file__), 'status_push_server.py')
        self.site = server.Site(Receiver())
        self.fake_http_server = reactor.listenTCP(0, self.site)
        self.port = self.fake_http_server.getHost().port
        d = self.generateActivity(config.replace('<PORT>', str(self.port)))
        d.addCallback(self._testPhase1)
        return d

    def testNotFiltered(self):
        return self._runTest(EXPECTED, config_http_no_filter)

    def testFiltered(self):
        return self._runTest(EXPECTED_SHORT, config_http)

    def _testPhase1(self, _):
        self.status_push = self.getStatusPush()
        self.path = self.status_push.path
        d = self.shutdownMaster()
        d.addCallback(self._testPhase2)
        return d

    def _testPhase2(self, _):
        # Assert all the items were pushed.
        self.assertEqual(0, self.status_push.queue.nbItems())
        self.verifyItems(self.site.resource.packets, self.expected)
        return self.fake_http_server.stopListening()

# vim: set ts=4 sts=4 sw=4 et:
