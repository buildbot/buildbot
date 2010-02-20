from twisted.trial import unittest
from twisted.internet import reactor, defer
from twisted.python import log

from buildbot.broken_test.runutils import MasterMixin
from buildbot.sourcestamp import SourceStamp

config_base = """
from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave
from buildbot.scheduler import Triggerable, Dependent
from buildbot.config import BuilderConfig

BuildmasterConfig = c = {}

f = factory.BuildFactory()
f.addStep(dummy.Dummy, timeout=%d)

c['slaves'] = [BuildSlave('bot1', 'sekrit')]

upstream = Triggerable('s_upstream', ['upstream'], {'prop': '%s'})
dep = Dependent('s_dep', upstream, ['depend'], {'dep prop': '%s'})
c['schedulers'] = [upstream, dep]
c['builders'] = [
    BuilderConfig(name='upstream', slavename='bot1', factory=f),
    BuilderConfig(name='depend', slavename='bot1', factory=f),
]
c['slavePortnum'] = 0
"""

class DependingScheduler(MasterMixin, unittest.TestCase):
    '''Test an upstream and a dependent scheduler while reconfiguring.'''

    def testReconfig(self):
        self.prop_value = 'prop value'
        self.dep_prop_value = 'dep prop value'
        self.basedir = "reconfig/DependingScheduler/Reconfig"
        self.reconfigured = 0

        self.create_master()
        d = self.master.loadConfig(config_base % (1, self.prop_value, self.dep_prop_value))
        d.addCallback(lambda ign: self.connectSlave(builders=['upstream', 'depend']))
        d.addCallback(self._triggerUpstream)
        return d

    def _triggerUpstream(self, res):
        log.msg("trigger upstream")
        ss = SourceStamp()
        upstream = [s for s in self.master.allSchedulers()
                    if s.name == 's_upstream'][0]
        d = upstream.trigger(ss)
        d.addCallback(self._gotBuild)
        return d

    def _gotBuild(self, res):
        log.msg("done")
        d = defer.Deferred()
        d.addCallback(self._doChecks)
        reactor.callLater(2, d.callback, None)
        return d

    def _doChecks(self, res):
        log.msg("starting tests")
        ub = self.status.getBuilder('upstream').getLastFinishedBuild()
        tb = self.status.getBuilder('depend').getLastFinishedBuild()
        self.assert_(ub.getProperties().has_key('prop'), ub.getProperties().asList())
        self.assertEqual(ub.getProperty('prop'), self.prop_value, ub.getProperties().asList())
        self.assertEqual(ub.getNumber(), self.reconfigured)
        self.assert_(tb.getProperties().has_key('dep prop'), ub.getProperties().asList())
        self.assertEqual(tb.getProperty('dep prop'), self.dep_prop_value)
        self.assertEqual(tb.getNumber(), self.reconfigured)

        # now further on to the reconfig
        if self.reconfigured > 2:
            # actually, we're done,
            return
        if self.reconfigured == 0:
            # reconfig without changes now
            d = self.master.loadConfig(config_base% (1, 'prop value',
                                                     'dep prop value'))
        elif self.reconfigured == 1:
            # reconfig with changes to upstream now
            d = self.master.loadConfig(config_base% (1, 'other prop value',
                                                     'dep prop value'))
            self.prop_value = 'other prop value'
            self.dep_prop_value = 'dep prop value'
        else:
            # reconfig with changes to dep now
            d = self.master.loadConfig(config_base% (1, 'other prop value',
                                                     'other dep prop value'))
            self.prop_value = 'other prop value'
            self.dep_prop_value = 'other dep prop value'
        self.reconfigured += 1
        d.addCallback(self._triggerUpstream)
        return d
