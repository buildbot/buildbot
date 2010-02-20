from twisted.trial import unittest
from twisted.internet import defer

from buildbot.sourcestamp import SourceStamp
from buildbot.process.properties import Properties
from buildbot.changes.changes import Change

from buildbot.broken_test.runutils import RunMixin

"""Testcases for master.botmaster.shouldMergeRequests.

"""

master_cfg = """from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig

f = factory.BuildFactory([
   dummy.Dummy(timeout=0),
   ])

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit')]
c['schedulers'] = []
c['builders'] = [
    BuilderConfig(name='dummy', slavename='bot1', factory=f),
]
c['slavePortnum'] = 0

%s
c['mergeRequests'] = mergeRequests
"""

class MergeRequestsTest(RunMixin, unittest.TestCase):
    def do_test(self, mergefun, expected, reqs = None):
        S = SourceStamp
        c1 = Change("alice", [], "changed stuff", branch="branch1")
        c2 = Change("alice", [], "changed stuff", branch="branch1")
        c3 = Change("alice", [], "changed stuff", branch="branch1")
        c4 = Change("alice", [], "changed stuff", branch="branch1")
        c5 = Change("alice", [], "changed stuff", branch="branch1")
        c6 = Change("alice", [], "changed stuff", branch="branch1")
        for c in [c1,c2,c3,c4,c5,c6]:
            self.master.addChange(c)
        if reqs is None:
            reqs = [("why", S("branch1", None, None, None), None),
                    ("why2", S("branch1", "rev1", None, None), None),
                    ("why not", S("branch1", "rev1", None, None), None),
                    ("why3", S("branch1", "rev2", None, None), None),
                    ("why4", S("branch2", "rev2", None, None), None),
                    ("why5", S("branch1", "rev1", (3, "diff"), None), None),
                    ("changes", S("branch1", None, None, [c1,c2,c3]), None),
                    ("changes", S("branch1", None, None, [c4,c5,c6]), None),
                    ]

        d = self.master.loadConfig(master_cfg % mergefun)
        def request_builds(_):
            dl = []
            for reason,ss,props in reqs:
                bss = self.master.submitBuildSet(["dummy"], ss, reason,
                                                 props, False)
                dl.append(bss.waitUntilFinished())
            self.connectSlave()
            return defer.DeferredList(dl)
        d.addCallback(request_builds)
        #d.addCallback(lambda res : self.connectSlave())
        #d.addCallback(self.waitForBuilds, expected)
        d.addCallback(self.checkresults, expected)

        return d

    def waitForBuilds(self, r, expected):
        d = self.master.botmaster.waitUntilBuilderIdle('dummy')
        d.addCallback(self.checkresults, expected)
        return d

    def checkresults(self, ign, expected):
        s = self.master.status.getBuilder("dummy")
        builds = list(s.generateFinishedBuilds())
        builds.reverse()
        self.assertEqual(len(builds), len(expected))
        for i in xrange(len(builds)):
            b = builds[i]
            r = expected[i]
            ss = b.getSourceStamp()
            self.assertEquals(b.getReason(), r['reason'])
            self.assertEquals(ss.branch, r['branch'])
            self.assertEquals(len(ss.changes), r['changecount'])
            # print b.getReason(), ss.branch, len(ss.changes), ss.revision

    def testDefault(self):
        return self.do_test('mergeRequests = None',
                            ({'reason': 'why',
                              'branch': 'branch1',
                              'changecount': 0},
                             {'reason': 'why2, why not',
                              'branch': 'branch1',
                              'changecount': 0},
                             {'reason': 'why3',
                              'branch': 'branch1',
                              'changecount': 0},
                             {'reason': 'why4',
                              'branch': 'branch2',
                              'changecount': 0},
                             {'reason': 'why5',
                              'branch': 'branch1',
                              'changecount': 0},
                             {'reason': 'changes',
                              'branch': 'branch1',
                              'changecount': 6},
                             ))

    def testNoMerges(self):
        mergefun = """def mergeRequests(builder, req1, req2):
    return False
"""
        return self.do_test(mergefun,
                            ({'reason': 'why',
                              'branch': 'branch1',
                              'changecount': 0},
                             {'reason': 'why2',
                              'branch': 'branch1',
                              'changecount': 0},
                             {'reason': 'why not',
                              'branch': 'branch1',
                              'changecount': 0},
                             {'reason': 'why3',
                              'branch': 'branch1',
                              'changecount': 0},
                             {'reason': 'why4',
                              'branch': 'branch2',
                              'changecount': 0},
                             {'reason': 'why5',
                              'branch': 'branch1',
                              'changecount': 0},
                             {'reason': 'changes',
                              'branch': 'branch1',
                              'changecount': 3},
                             {'reason': 'changes',
                              'branch': 'branch1',
                              'changecount': 3},
                             ))

    def testReasons(self):
        mergefun = """def mergeRequests(builder, req1, req2):
    return req1.reason == req2.reason
"""
        return self.do_test(mergefun,
                            ({'reason': 'why',
                              'branch': 'branch1',
                              'changecount': 0},
                             {'reason': 'why2',
                              'branch': 'branch1',
                              'changecount': 0},
                             {'reason': 'why not',
                              'branch': 'branch1',
                              'changecount': 0},
                             {'reason': 'why3',
                              'branch': 'branch1',
                              'changecount': 0},
                             {'reason': 'why4',
                              'branch': 'branch2',
                              'changecount': 0},
                             {'reason': 'why5',
                              'branch': 'branch1',
                              'changecount': 0},
                             {'reason': 'changes',
                              'branch': 'branch1',
                              'changecount': 6},
                             ))


    def testProperties(self):
        mergefun = """def mergeRequests(builder, req1, req2):
    return req1.properties == req2.properties
"""
        S = SourceStamp
        p1 = Properties(first="value")
        p2 = Properties(first="other value")
        reqs = [("why", S("branch1", None, None, None), p1),
                ("why", S("branch1", None, None, None), p1),
                ("why", S("branch2", None, None, None), p2),
                ("why", S("branch2", None, None, None), p2),
                ]
        return self.do_test(mergefun,
                            ({'reason': 'why',
                              'branch': 'branch1',
                              'changecount': 0},
                             {'reason': 'why',
                              'branch': 'branch2',
                              'changecount': 0},
                             ),
                            reqs=reqs)
