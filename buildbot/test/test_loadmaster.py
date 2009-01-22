from twisted.internet import defer, reactor
from twisted.trial import unittest

from buildbot.sourcestamp import SourceStamp
from buildbot.process.base import BuildRequest
from buildbot.process.properties import Properties
from buildbot.status import builder, base, words
from buildbot.changes.changes import Change

from buildbot.test.runutils import RunMixin

"""Testcases for master.LoadMaster.

"""

master_cfg = """from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave

from buildbot.master import LoadMaster

f = factory.BuildFactory([
   dummy.Dummy(timeout=0),
   ])

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit')]
c['schedulers'] = []
c['builders'] = []
c['builders'].append({'name':'dummy', 'slavename':'bot1',
                      'builddir': 'dummy', 'factory': f})
c['slavePortnum'] = 0

c['%s'] = %s
"""

class LoadMasterTest(RunMixin, unittest.TestCase):
    def do_test(self, param, value, results, reqs = None):
        R = BuildRequest
        S = SourceStamp
        c1 = Change("alice", [], "changed stuff", branch="branch1")
        c2 = Change("alice", [], "changed stuff", branch="branch1")
        c3 = Change("alice", [], "changed stuff", branch="branch1")
        c4 = Change("alice", [], "changed stuff", branch="branch1")
        c5 = Change("alice", [], "changed stuff", branch="branch1")
        c6 = Change("alice", [], "changed stuff", branch="branch1")
        if reqs is None:
            reqs = (R("why", S("branch1", None, None, None)),
                    R("why2", S("branch1", "rev1", None, None)),
                    R("why not", S("branch1", "rev1", None, None)),
                    R("why3", S("branch1", "rev2", None, None)),
                    R("why4", S("branch2", "rev2", None, None)),
                    R("why5", S("branch1", "rev1", (3, "diff"), None)),
                    R("changes", S("branch1", None, None, [c1,c2,c3])),
                    R("changes", S("branch1", None, None, [c4,c5,c6])),
                    )

        m = self.master
        m.loadConfig(master_cfg % (param, value))
        m.readConfig = True
        m.startService()
        builder = self.control.getBuilder('dummy')
        for req in reqs:
            builder.requestBuild(req)

        d = self.connectSlave()
        d.addCallback(self.waitForBuilds, results)

        return d

    def waitForBuilds(self, r, results):
        d = self.master.botmaster.waitUntilBuilderIdle('dummy')
        d.addCallback(self.checkresults, results)
        return d

    def checkresults(self, builder, results):
        s = builder.builder_status
        builds = list(s.generateFinishedBuilds())
        builds.reverse()
        self.assertEqual(len(builds), len(results))
        for i in xrange(len(builds)):
            b = builds[i]
            r = results[i]
            ss = b.getSourceStamp()
            self.assertEquals(b.getReason(), r['reason'])
            self.assertEquals(ss.branch, r['branch'])
            self.assertEquals(len(ss.changes), r['changecount'])
            # print b.getReason(), ss.branch, len(ss.changes), ss.revision

    def testDefault(self):
        return self.do_test('mergeMatchingRequests', 'True',
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
        return self.do_test('mergeMatchingRequests', 'False',
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
        return self.do_test('mergeMatchingReasons', 'True',
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
        R = BuildRequest
        S = SourceStamp
        p1 = Properties(first="value")
        p2 = Properties(first="other value")
        reqs = (R("why", S("branch1", None, None, None),
                  properties = p1),
                R("why", S("branch1", None, None, None),
                  properties = p1),
                R("why", S("branch1", None, None, None),
                  properties = p2),
                R("why", S("branch1", None, None, None),
                  properties = p2),
                )
        return self.do_test('mergeMatchingProperties', 'True',
                            ({'reason': 'why',
                              'branch': 'branch1',
                              'changecount': 0},
                             {'reason': 'why',
                              'branch': 'branch1',
                              'changecount': 0},
                             ),
                            reqs=reqs)

    def testCustomLoadMaster(self):
        return self.do_test('loadMaster', 'LoadMaster()',
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
