# -*- test-case-name: buildbot.test.test_web_status_json -*-
# -*- coding: utf-8 -*-

import os, shutil

from twisted.python import components
from twisted.trial import unittest
from twisted.web import client, error

from buildbot import master, interfaces
from buildbot.status import html
from buildbot.status.web.status_json import JsonStatusResource

try:
    import simplejson as json
except ImportError:
    import json


class ConfiguredMaster(master.BuildMaster):
    """This BuildMaster variant has a static config file, provided as a
    string when it is created."""

    def __init__(self, basedir, config):
        self.config = config
        master.BuildMaster.__init__(self, basedir)

    def loadTheConfigFile(self):
        self.loadConfig(self.config)


components.registerAdapter(master.Control, ConfiguredMaster,
                           interfaces.IControl)


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
"""


class TestStatusJson(unittest.TestCase):
    def setUp(self):
        config = base_config + "c['status'] = [html.WebStatus(http_port=0)]\n"
        if os.path.isdir('test_web1'):
            shutil.rmtree('test_web1')
        os.mkdir('test_web1')
        self.master = ConfiguredMaster('test_web1', config)
        self.master.startService()
        self.web_status = self.find(html.WebStatus)
        self.status_json = self.find(
            JsonStatusResource,
            self.web_status.site.resource.children.itervalues())
        # Hack to find out what randomly-assigned port it is listening on.
        self.port = self.web_status.getPortnum()

    def tearDown(self):
        self.master.stopService()
        shutil.rmtree('test_web1')

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
        def _check(page):
            data = json.loads(page)
            self.assertEqual(len(data), 4)
            self.assertEqual(len(data['builders']), 1)
            self.assertEqual(len(data['change_sources']), 1)
            self.assertEqual(len(data['project']), 2)
            self.assertEqual(len(data['slaves']), 1)
        return self.getPage('/json', _check)

    def testHelp(self):
        def _check(page):
            self.failUnless(page)
        return self.getPage('/json/help', _check)

    def testNonPresence(self):
        def _checkOk(page):
            self.assertFalse(page)
        def _checkFail(result):
            self.assertEqual(result.type, error.Error)
        return self.getPage('/json2', _checkOk, _checkFail)

# vim: set ts=4 sts=4 sw=4 et:
