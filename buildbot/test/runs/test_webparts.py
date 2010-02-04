# -*- test-case-name: buildbot.test.test_webparts -*-
# -*- coding: utf-8 -*-

import os
import re
import time
import urlparse

from twisted.trial import unittest
from twisted.internet import defer
from twisted.python import util
from twisted.web import client
from twisted.web.error import Error as WebError
from buildbot import sourcestamp
from buildbot.slave.commands import rmdirRecursive
from buildbot.status import html, builder
from buildbot.scripts import runner
from buildbot.changes.changes import Change
from buildbot.process import base
from buildbot.process.buildstep import BuildStep
from test_web import BaseWeb, base_config, ConfiguredMaster


class _WebpartsTest(BaseWeb, unittest.TestCase):
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

class Webparts(_WebpartsTest):
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
        d.addCallback(self._check, "buildslaves", "Buildslaves")
        d.addCallback(self._check, "one_line_per_build",
                      "Last 20 finished builds")
        d.addCallback(self._check, "one_box_per_builder", "Latest builds")
        d.addCallback(self._check, "builders", "Builders")
        d.addCallback(self._check, "builders/builder1", "Builder builder1")
        d.addCallback(self._check, "builders/builder1/builds", "") # dummy
        d.addCallback(self._check, "console", "Console")
        d.addCallback(self._check, "grid", 'class="Grid"')
        d.addCallback(self._check, "tgrid", 'class="Grid"')
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


class WebpartsRecursive(_WebpartsTest):
    '''A rather big test that attempts to fill the buildbot
       state with as much info as possible, then walk all
       reachable pages from the root url and make sure
       they all are accessible w/o errors and that they
       validate according to the given doctype

       This test  accesses the network the first time around.
       (This can be avoided if we include the cached dtd:s in
        the repo.)

       Lxml (http://codespeak.net/lxml/) is used to parse
       and validate all, so this test is skipped if lxml
       is not installed.
    '''

    log = False # Set to True to list pages being checked

    def setUp(self):
        try:
            from lxml import etree
        except ImportError:
            raise unittest.SkipTest("lxml not installed")

        class CustomResolver(etree.Resolver):
            '''Use cached DTDs to avoid network access

               from http://www.hoboes.com/Mimsy/hacks/caching-dtds-using-lxml-and-etree/
            '''

            if WebpartsRecursive.log:
                print "\nCaching DTDs in: %s" % cache

            def resolve(self, URL, id, context):
                #determine cache filename
                url = urlparse.urlparse(URL)
                dtdPath = util.sibpath(__file__,
                            url.hostname + '.' + url.path.replace('/', '.'))
                #cache if necessary
                if not os.path.exists(dtdPath):
                    raise ValueError("URL '%s' is not cached in '%s'" % (URL, dtdPath))

                #resolve the cached file
                return self.resolve_file(open(dtdPath), context, base_url=URL)

        self.CustomResolver = CustomResolver

        extraconfig = """
from buildbot.status import html
from buildbot.changes import mail
from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.scheduler import Scheduler
from buildbot.changes.base import ChangeSource
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig
s = factory.s

class DiscardScheduler(Scheduler):
    def addChange(self, change):
        pass
class DummyChangeSource(ChangeSource):
    def describe(self):
        return "dummy"

ws = html.WebStatus(http_port=0, allowForce=True,
                    revlink="http://server.net/webrepo/%s",
                    changecommentlink=(r"#(\\d+)", r"http://server.net/trac/ticket/\\1"))
c['status'] = [ws]

c['slaves'] = [BuildSlave('bot1', 'sekrit'), BuildSlave('bot2', 'sekrit')]
c['change_source'] = DummyChangeSource()
c['schedulers'] = [DiscardScheduler('discard1', None, 60, ['builder1']),
                   DiscardScheduler('discard2', 'release', 30, ['builder1'])]
c['slavePortnum'] = 0

f = factory.BuildFactory([s(dummy.RemoteDummy, timeout=1)])

c['builders'] = [
    BuilderConfig(name='builder1', slavenames=['bot1', 'bot2'], factory=f),
    BuilderConfig(name='builder2', slavenames=['bot1'], factory=f),
    BuilderConfig(name='builder3', slavenames=['bot2'], factory=f),
]
c['buildbotURL'] = 'http://dummy.example.org:8010/'
c['projectName'] = 'BuildBot Trial Test'
c['projectURL'] = 'http://server.net/home'

"""
        self.startMaster(extraconfig)

        for i in range(5):
            if i % 2 == 0:
                branch = "release"
            else:
                branch = None
            c = Change("user", ["foo.c"] * i, "see ticket #%i" % i,
                       revision=str(42+i), when=0.1*i, branch=branch)
            self.master.change_svc.addChange(c)

        ss = sourcestamp.SourceStamp(revision=42)
        req = base.BuildRequest("reason", ss, 'test_builder')
        build1 = base.Build([req])
        bs = self.master.status.getBuilder("builder1").newBuild()
        bs.setReason("reason")
        bs.buildStarted(build1)

        bs.setSourceStamp(ss)

        bs.setProperty("revision", "42", "testcase")
        bs.setProperty("got_revision", "47", "testcase")
        bs.setProperty("branch", "release", "testcase")

        step1 = BuildStep(name="setup")
        step1.setBuild(build1)
        bss = bs.addStepWithName("setup")
        step1.setStepStatus(bss)
        bss.stepStarted()

        step2 = BuildStep(name="build")
        step2.setBuild(build1)
        bss = bs.addStepWithName("build")
        step2.setStepStatus(bss)
        bss.stepStarted()

        step1.addURL("url1", "http://logurl.net/1")
        step1.addURL("url2", "http://logurl.net/2")
        step1.addURL("url3", "http://logurl.net/3")

        log1 = step1.addLog("output")
        log1.addStdout(u"some stdout\n") # FIXME: Unicode here fails validation
        log1.finish()

        # this has to validate too for the test to pass
        log2 = step1.addHTMLLog("error", '''
            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
              "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
            <html>
                <head><title>Teh Log</title></head>
                <body>Aaaiight</body>
            </html>''')

        log3 = step1.addLog("big")
        log3.addStdout("somewhat big log\n")
        for i in range(50):
            log3.addStdout("a" * 50 + "\n")
            log3.addStderr("b" * 50 + "\n")
        log3.finish()

        log5 = step1.addLog("mixed")
        log5.addHeader("header content")
        log5.addStdout("this is stdout content")
        log5.addStderr("errors go here")
        log5.addEntry(5, "non-standard content on channel 5")
        log5.addStderr(" and some trailing stderr")


        d = defer.succeed(None)

        for i in range(1,3):
            ss = sourcestamp.SourceStamp(revision=42+i, branch='release')
            req = base.BuildRequest("reason", ss, 'test_builder')
            build = base.Build([req] * i)
            bs = self.master.status.getBuilder("builder%i" % i).newBuild()
            bs.setReason("reason")
            bs.buildStarted(build)
            bs.setSourceStamp(ss)

            s = BuildStep(name="setup")
            s.setBuild(build1)
            bss = bs.addStepWithName("setup")
            s.setStepStatus(bss)
            bss.stepStarted()
            log = s.addLog("stdio")
            log.finish()


        d.chainDeferred(defer.maybeDeferred(step1.step_status.stepFinished,
                                builder.SUCCESS))
        bs.buildFinished()
        return d

    def testAllPagesValidate(self):
        '''Fetch all pages, follow all links'''

        from lxml import html

        self.parser = html.XHTMLParser(dtd_validation=True, no_network=True)
        self.parser.resolvers.add(self.CustomResolver())
        self.errors = []
        self.error_count = 0
        self.link_count = 0
        self.visited_urls = [self.baseurl]
        self.skipped_urls = []
        # self.log = True # uncomment to see logs

        d = defer.succeed(None)
        d.addCallback(self._check_pages, [self.baseurl], "<testcase>")
        d.addCallback(self._reporterrors)
        return d

    def _reporterrors(self, _):
        url_count = len(self.visited_urls)
        skip_count = len(self.skipped_urls)

        if self.errors or self.error_count:
            fail_summary = u"%i/%i urls contains errors:\n  %s" % \
                (self.error_count, url_count, u"\n  ".join(self.errors))
            self.fail(fail_summary)
        elif self.log:
            print "%i urls ok, %i urls skipped in %i links" % \
                (url_count, skip_count, self.link_count)

        # these numbers need adjustment when web layout changes
        # but should catch empty pages
        self.failIf(url_count < 55,
                    "Only %i urls visited, expected at least 55" % url_count)
        self.failIf(skip_count < 15,
                    "Only %i urls skipped, expected at least 15" % skip_count)
        self.failIf(self.link_count < 770,
                    "Only %i links encountered, expected at least 770" % self.link_count)

    def _getpage(self, _, url):
        return client.getPage(url)

    def _show_weberror(self, why, url, source):
        self.error_count += 1
        why.trap(WebError)
        url = url.replace(self.baseurl, '')
        source = source.replace(self.baseurl, '')
        self.errors.append("*** %s: %s" % (url, why.getErrorMessage()))
        self.errors.append("  * from: %s" % source)

    def _check_links(self, res, urls, source):
        d = defer.succeed(None)

        for url in urls:
            d.addCallback(self._getpage, url)
            d.addErrback(self._show_weberror, url, source)

        return d

    def _check_pages(self, _, urls, source):
        d = defer.succeed(None)

        for url in urls:
            d.addCallback(self._getpage, url)
            d.addErrback(self._show_weberror, url, source)
            d.addCallback(self._validate_and_recurse, url)
            from twisted.python import log
            d.addErrback(log.err)

        return d

    def _validate_and_recurse(self, page, url):
        if not page:
            # this happens mostly on errors, which are reported elsewhere
            if self.log:
                print "Empty: %s" % url
            return

        from lxml import etree, html

        try:
            # parse & validate xhtml
            xhtml = html.fromstring(page, url, self.parser)
        except etree.XMLSyntaxError, e:
            self.error_count += 1
            self.errors.append("***** %s: %s *****" %
                               (url.replace(self.baseurl, '/'), e.msg))

            # print some context around each line mentioned in error message
            cxt = 3
            lines = []
            for m in re.finditer("line (\d+)(, column (\d+))?", e.msg):
                l,c = m.group(1,3)
                lines.append((int(l)-1,c))

            for i, txt in enumerate(page.split('\n')):
                line_n = i+1 # line numbering in err msg starts at 1
                if any(map(lambda (l,_): l-cxt-2 < i < l+cxt, lines)):
                    self.errors.append(u"  %i: %s" % (line_n, txt))

                    # print column marker
                    for l,c in lines:
                        if l == i and c:
                            t = u"  %i: " % line_n + " " * int(c) + "^"
                            self.errors.append(t)
                            break

            return None

        xhtml.make_links_absolute()

        # extract links
        pages = []
        links = []
        for element, attr, link, pos in xhtml.iterlinks():
            self.link_count += 1

            if link.endswith('/None'):
                continue

            if link in self.visited_urls:
                continue

            # skip non-local links
            if not link.startswith(self.baseurl):
                if link not in self.skipped_urls:
                    self.skipped_urls.append(link)
                    if self.log:
                        print "Skipping: %s" % link
                continue

            # remove namespace (assume only xhtml namespace)
            tag = element.tag.split('}')[1]

            # FIXME: rebuild redirects to a bad place in this test
            untestable = ['/rebuild', '/stop']
            if any (map(lambda e: link.endswith(e), untestable)):
                continue

            # follow anchor links to other pages
            # FIXME: text logs aren't html, check content-type in getPage
            unvalidatable = ['/text']
            if tag == 'a' and not any (map(lambda e: link.endswith(e), unvalidatable)):
                if self.log:
                    print "Validating: %s" % link
                pages.append(link)
            else:
                if self.log:
                    print "Checking: %s" % link
                links.append(link)

            self.visited_urls.append(link)

        d = None
        if pages or links:
            d = defer.succeed(None)
        if pages:
            d.addCallback(self._check_pages, pages, url)
        if links:
            d.addCallback(self._check_links, links, url)
        return d

