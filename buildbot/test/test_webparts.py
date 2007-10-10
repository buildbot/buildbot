
import os
from twisted.trial import unittest
from twisted.internet import defer
from twisted.web import client
from twisted.web.error import Error as WebError
from buildbot.slave.commands import rmdirRecursive
from buildbot.status import html
from test_web import BaseWeb, base_config, ConfiguredMaster
from buildbot.scripts import runner

class Webparts(BaseWeb, unittest.TestCase):

    def find_webstatus(self, master):
        return filter(lambda child: isinstance(child, html.WebStatus),
                      list(master))

    def startMaster(self, extraconfig):
        config = base_config + extraconfig
        rmdirRecursive("test_webparts")
        os.mkdir("test_webparts")
        runner.upgradeMaster({'basedir': "test_webparts",
                              'quiet': True,
                              })
        self.master = m = ConfiguredMaster("test_webparts", config)
        m.startService()
        # hack to find out what randomly-assigned port it is listening on
        port = list(self.find_webstatus(m)[0])[0]._port.getHost().port
        self.baseurl = "http://localhost:%d/" % port

    def reconfigMaster(self, extraconfig):
        config = base_config + extraconfig
        d = self.master.loadConfig(config)
        def _done(res):
            m = self.master
            port = list(self.find_webstatus(m)[0])[0]._port.getHost().port
            self.baseurl = "http://localhost:%d/" % port
        d.addCallback(_done)
        return d

    def getAndCheck(self, url, substring, show=False):
        d = client.getPage(url)
        def _show_weberror(why):
            why.trap(WebError)
            self.fail("error for %s: %s" % (url, why))
        d.addErrback(_show_weberror)
        d.addCallback(self._getAndCheck, substring, show)
        return d
    def _getAndCheck(self, page, substring, show):
        if show:
            print page
        self.failUnlessIn(substring, page,
                          "Couldn't find substring '%s' in page:\n%s" %
                          (substring, page))

    def testInit(self):
        extraconfig = """
from twisted.web import static
ws = html.WebStatus(http_port=0)
c['status'] = [ws]
ws.putChild('child.html', static.Data('I am the child', 'text/plain'))
"""
        self.startMaster(extraconfig)
        d = self.getAndCheck(self.baseurl + "child.html",
                             "I am the child")
        return d
    testInit.timeout = 10

    def testStatic(self):
        extraconfig = """
from twisted.web import static
ws = html.WebStatus(http_port=0)
c['status'] = [ws]
ws.putChild('child.html', static.Data('I am the child', 'text/plain'))
"""
        self.startMaster(extraconfig)
        os.mkdir(os.path.join("test_webparts", "public_html", "subdir"))
        f = open(os.path.join("test_webparts", "public_html", "foo.html"), "wt")
        f.write("see me foo\n")
        f.close()
        f = open(os.path.join("test_webparts", "public_html", "subdir",
                              "bar.html"), "wt")
        f.write("see me subdir/bar\n")
        f.close()
        d = self.getAndCheck(self.baseurl + "child.html", "I am the child")
        d.addCallback(lambda res:
                      self.getAndCheck(self.baseurl+"foo.html",
                                       "see me foo"))
        d.addCallback(lambda res:
                      self.getAndCheck(self.baseurl+"subdir/bar.html",
                                       "see me subdir/bar"))
        return d

    def _check(self, res, suburl, substring, show=False):
        d = self.getAndCheck(self.baseurl + suburl, substring, show)
        return d

    def testPages(self):
        extraconfig = """
ws = html.WebStatus(http_port=0)
c['status'] = [ws]
"""
        self.startMaster(extraconfig)
        d = defer.succeed(None)
        d.addCallback(self._do_page_tests)
        extraconfig2 = """
ws = html.WebStatus(http_port=0, allowForce=True)
c['status'] = [ws]
"""
        d.addCallback(lambda res: self.reconfigMaster(extraconfig2))
        d.addCallback(self._do_page_tests)
        return d

    def _do_page_tests(self, res):
        d = defer.succeed(None)
        d.addCallback(self._check, "", "Welcome to the Buildbot")
        d.addCallback(self._check, "waterfall", "current activity")
        d.addCallback(self._check, "about", "Buildbot is a free software")
        d.addCallback(self._check, "changes", "PBChangeSource listener")
        d.addCallback(self._check, "buildslaves", "Build Slaves")
        d.addCallback(self._check, "one_line_per_build",
                      "Last 20 finished builds")
        d.addCallback(self._check, "one_box_per_builder", "Latest builds")
        d.addCallback(self._check, "builders", "Builders")
        d.addCallback(self._check, "builders/builder1", "Builder: builder1")
        d.addCallback(self._check, "builders/builder1/builds", "") # dummy
        # TODO: the pages beyond here would be great to test, but that would
        # require causing a build to complete.
        #d.addCallback(self._check, "builders/builder1/builds/1", "")
        # it'd be nice to assert that the Build page has a "Stop Build" button
        #d.addCallback(self._check, "builders/builder1/builds/1/steps", "")
        #d.addCallback(self._check,
        #              "builders/builder1/builds/1/steps/compile", "")
        #d.addCallback(self._check,
        #              "builders/builder1/builds/1/steps/compile/logs", "")
        #d.addCallback(self._check,
        #              "builders/builder1/builds/1/steps/compile/logs/stdio","")
        #d.addCallback(self._check,
        #              "builders/builder1/builds/1/steps/compile/logs/stdio/text", "")
        return d

