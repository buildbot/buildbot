# -*- test-case-name: buildbot.broken_test.test_web_status_json -*-
# -*- coding: utf-8 -*-

from twisted.trial import unittest
from twisted.web import client, error

from buildbot.status import html
from buildbot.status.web.status_json import JsonStatusResource
from buildbot.broken_test.runutils import MasterMixin
from buildbot.util import json


base_config = """
from buildbot.changes.pb import PBChangeSource
from buildbot.status import html
from buildbot.buildslave import BuildSlave
from buildbot.scheduler import Scheduler
from buildbot.process.factory import BuildFactory
from buildbot.config import BuilderConfig

BuildmasterConfig = c = {
    'change_source': PBChangeSource(),
    'slaves': [BuildSlave('bot1name', 'bot1passwd')],
    'schedulers': [Scheduler('name', None, 60, ['builder1'])],
    'slavePortnum': 0,
    }
c['builders'] = [
    BuilderConfig(name='builder1', slavename='bot1name', factory=BuildFactory()),
]
c['status'] = [html.WebStatus(http_port=0)]
"""


class TestStatusJson(MasterMixin, unittest.TestCase):
    def startup(self):
        self.create_master()
        d = self.master.loadConfig(base_config)
        def _then(ign):
            self.web_status = self.find(html.WebStatus)
            self.status_json = self.find(
                JsonStatusResource,
                self.web_status.site.resource.children.itervalues())
            # Hack to find out what randomly-assigned port it is listening on.
            self.port = self.web_status.getPortnum()
        d.addCallback(_then)
        return d

    def find(self, type=None, obj=None):
        obj = obj or self.master
        for child in list(obj):
            if isinstance(child, type):
                return child
        self.assertTrue(False)

    def getPage(self, url, cb=None, err=None):
        d = client.getPage('http://localhost:%d%s' % (self.port, url))
        if cb:
            d.addCallback(cb)
        if err:
            d.addErrback(err)
        return d

    def testPresence(self):
        self.basedir = "web_status_json/TestStatusJson/Presence"
        d = self.startup()
        def _check(page):
            data = json.loads(page)
            self.assertEqual(len(data), 4)
            self.assertEqual(len(data['builders']), 1)
            self.assertEqual(len(data['change_sources']), 1)
            self.assertEqual(len(data['project']), 2)
            self.assertEqual(len(data['slaves']), 1)
        d.addCallback(lambda ign: self.getPage('/json', _check))
        return d

    def testHelp(self):
        self.basedir = "web_status_json/TestStatusJson/Help"
        d = self.startup()
        def _check(page):
            self.failUnless(page)
        d.addCallback(lambda ign: self.getPage('/json/help', _check))
        return d

    def testNonPresence(self):
        self.basedir = "web_status_json/TestStatusJson/NonPresence"
        d = self.startup()
        def _checkOk(page):
            self.assertFalse(page)
        def _checkFail(result):
            self.assertEqual(result.type, error.Error)
        d.addCallback(lambda ign: self.getPage('/json2', _checkOk, _checkFail))
        return d

# vim: set ts=4 sts=4 sw=4 et:
