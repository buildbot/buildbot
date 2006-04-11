# -*- test-case-name: buildbot.test.test_vc -*-

from __future__ import generators

import sys, os, signal, shutil, time, re
from email.Utils import mktime_tz, parsedate_tz

from twisted.trial import unittest
from twisted.internet import defer, reactor, utils
try:
    from twisted.python.procutils import which
except ImportError:
    # copied from Twisted circa 2.2.0
    def which(name, flags=os.X_OK):
        """Search PATH for executable files with the given name.

        @type name: C{str}
        @param name: The name for which to search.

        @type flags: C{int}
        @param flags: Arguments to L{os.access}.

        @rtype: C{list}
        @param: A list of the full paths to files found, in the
        order in which they were found.
        """
        result = []
        exts = filter(None, os.environ.get('PATHEXT', '').split(os.pathsep))
        for p in os.environ['PATH'].split(os.pathsep):
            p = os.path.join(p, name)
            if os.access(p, flags):
                result.append(p)
            for e in exts:
                pext = p + e
                if os.access(pext, flags):
                    result.append(pext)
        return result

#defer.Deferred.debug = True

from twisted.python import log
#log.startLogging(sys.stderr)

from buildbot import master, interfaces
from buildbot.slave import bot
from buildbot.slave.commands import rmdirRecursive
from buildbot.status.builder import SUCCESS, FAILURE
from buildbot.process import step, base
from buildbot.changes import changes
from buildbot.sourcestamp import SourceStamp
from buildbot.twcompat import maybeWait
from buildbot.scripts import tryclient

# buildbot.twcompat will patch these into t.i.defer if necessary
from twisted.internet.defer import waitForDeferred, deferredGenerator

# Most of these tests (all but SourceStamp) depend upon having a set of
# repositories from which we can perform checkouts. These repositories are
# created by the setUp method at the start of each test class. In earlier
# versions these repositories were created offline and distributed with a
# separate tarball named 'buildbot-test-vc-1.tar.gz'. This is no longer
# necessary.

# CVS requires a local file repository. Providing remote access is beyond
# the feasible abilities of this test program (needs pserver or ssh).

# SVN requires a local file repository. To provide remote access over HTTP
# requires an apache server with DAV support and mod_svn, way beyond what we
# can test from here.

# Arch and Darcs both allow remote (read-only) operation with any web
# server. We test both local file access and HTTP access (by spawning a
# small web server to provide access to the repository files while the test
# is running).


VCS = {}


config_vc = """
from buildbot.process import factory, step
s = factory.s

f1 = factory.BuildFactory([
    %s,
    ])
c = {}
c['bots'] = [['bot1', 'sekrit']]
c['sources'] = []
c['schedulers'] = []
c['builders'] = [{'name': 'vc', 'slavename': 'bot1',
                  'builddir': 'vc-dir', 'factory': f1}]
c['slavePortnum'] = 0
BuildmasterConfig = c
"""

p0_diff = r"""
Index: subdir/subdir.c
===================================================================
RCS file: /home/warner/stuff/Projects/BuildBot/code-arch/_trial_temp/test_vc/repositories/CVS-Repository/sample/subdir/subdir.c,v
retrieving revision 1.1.1.1
diff -u -r1.1.1.1 subdir.c
--- subdir/subdir.c	14 Aug 2005 01:32:49 -0000	1.1.1.1
+++ subdir/subdir.c	14 Aug 2005 01:36:15 -0000
@@ -4,6 +4,6 @@
 int
 main(int argc, const char *argv[])
 {
-    printf("Hello subdir.\n");
+    printf("Hello patched subdir.\n");
     return 0;
 }
"""

# this patch does not include the filename headers, so it is
# patchlevel-neutral
TRY_PATCH = '''
@@ -5,6 +5,6 @@
 int
 main(int argc, const char *argv[])
 {
-    printf("Hello subdir.\\n");
+    printf("Hello try.\\n");
     return 0;
 }
'''

MAIN_C = '''
// this is main.c
#include <stdio.h>

int
main(int argc, const char *argv[])
{
    printf("Hello world.\\n");
    return 0;
}
'''

BRANCH_C = '''
// this is main.c
#include <stdio.h>

int
main(int argc, const char *argv[])
{
    printf("Hello branch.\\n");
    return 0;
}
'''

VERSION_C = '''
// this is version.c
#include <stdio.h>

int
main(int argc, const char *argv[])
{
    printf("Hello world, version=%d\\n");
    return 0;
}
'''

SUBDIR_C = '''
// this is subdir/subdir.c
#include <stdio.h>

int
main(int argc, const char *argv[])
{
    printf("Hello subdir.\\n");
    return 0;
}
'''

TRY_C = '''
// this is subdir/subdir.c
#include <stdio.h>

int
main(int argc, const char *argv[])
{
    printf("Hello try.\\n");
    return 0;
}
'''


class SignalMixin:
    sigchldHandler = None
    
    def setUpClass(self):
        # make sure SIGCHLD handler is installed, as it should be on
        # reactor.run(). problem is reactor may not have been run when this
        # test runs.
        if hasattr(reactor, "_handleSigchld") and hasattr(signal, "SIGCHLD"):
            self.sigchldHandler = signal.signal(signal.SIGCHLD,
                                                reactor._handleSigchld)
    
    def tearDownClass(self):
        if self.sigchldHandler:
            signal.signal(signal.SIGCHLD, self.sigchldHandler)


# the overall plan here:
#
# Each VC system is tested separately, all using the same source tree defined
# in the 'files' dictionary above. Each VC system gets its own TestCase
# subclass. The first test case that is run will create the repository during
# setUp(), making two branches: 'trunk' and 'branch'. The trunk gets a copy
# of all the files in 'files'. The variant of good.c is committed on the
# branch.
#
# then testCheckout is run, which does a number of checkout/clobber/update
# builds. These all use trunk r1. It then runs self.fix(), which modifies
# 'fixable.c', then performs another build and makes sure the tree has been
# updated.
#
# testBranch uses trunk-r1 and branch-r1, making sure that we clobber the
# tree properly when we switch between them
#
# testPatch does a trunk-r1 checkout and applies a patch.
#
# testTryGetPatch performs a trunk-r1 checkout, modifies some files, then
# verifies that tryclient.getSourceStamp figures out the base revision and
# what got changed.


# vc_create makes a repository at r1 with three files: main.c, version.c, and
# subdir/foo.c . It also creates a branch from r1 (called b1) in which main.c
# says "hello branch" instead of "hello world". self.trunk[] contains
# revision stamps for everything on the trunk, and self.branch[] does the
# same for the branch.

# vc_revise() checks out a tree at HEAD, changes version.c, then checks it
# back in. The new version stamp is appended to self.trunk[]. The tree is
# removed afterwards.

# vc_try_checkout(workdir, rev) checks out a tree at REV, then changes
# subdir/subdir.c to say 'Hello try'
# vc_try_finish(workdir) removes the tree and cleans up any VC state
# necessary (like deleting the Arch archive entry).



class VCBase(SignalMixin):
    metadir = None
    createdRepository = False
    master = None
    slave = None
    httpServer = None
    httpPort = None
    skip = None

    def failUnlessIn(self, substring, string, msg=None):
        # trial provides a version of this that requires python-2.3 to test
        # strings.
        if msg is None:
            msg = ("did not see the expected substring '%s' in string '%s'" %
                   (substring, string))
        self.failUnless(string.find(substring) != -1, msg)

    def setUp(self):
        # capable() should (eventually )raise SkipTest if the VC tools it
        # needs are not available
        d = defer.maybeDeferred(self.capable)
        d.addCallback(self._setUp1)
        return maybeWait(d)

    def _setUp1(self, res):
        if os.path.exists("basedir"):
            rmdirRecursive("basedir")
        os.mkdir("basedir")
        self.master = master.BuildMaster("basedir")
        self.slavebase = os.path.abspath("slavebase")
        if os.path.exists(self.slavebase):
            rmdirRecursive(self.slavebase)
        os.mkdir("slavebase")
        # NOTE: self.createdRepository survives from one test method to the
        # next, and we use this fact to avoid repeating the (expensive)
        # repository-build step
        if self.createdRepository:
            d = defer.succeed(None)
        else:
            self.createdRepository = True
            self.trunk = []
            self.branch = []
            self.allrevs = []
            self.repbase = os.path.abspath(os.path.join("test_vc",
                                                        "repositories"))
            if not os.path.isdir(self.repbase):
                os.makedirs(self.repbase)
            d = self.vc_create()
            d.addCallback(self.postCreate)
        d.addCallback(self.setUp2)
        return d

    def setUp2(self, res):
        pass

    def addTrunkRev(self, rev):
        self.trunk.append(rev)
        self.allrevs.append(rev)
    def addBranchRev(self, rev):
        self.branch.append(rev)
        self.allrevs.append(rev)

    def postCreate(self, res):
        pass

    def connectSlave(self):
        port = self.master.slavePort._port.getHost().port
        slave = bot.BuildSlave("localhost", port, "bot1", "sekrit",
                               self.slavebase, keepalive=0, usePTY=1)
        self.slave = slave
        slave.startService()
        d = self.master.botmaster.waitUntilBuilderAttached("vc")
        return d

    def loadConfig(self, config):
        # reloading the config file causes a new 'listDirs' command to be
        # sent to the slave. To synchronize on this properly, it is easiest
        # to stop and restart the slave.
        d = defer.succeed(None)
        if self.slave:
            d = self.master.botmaster.waitUntilBuilderDetached("vc")
            self.slave.stopService()
        d.addCallback(lambda res: self.master.loadConfig(config))
        d.addCallback(lambda res: self.connectSlave())
        return d

    def serveHTTP(self):
        # launch an HTTP server to serve the repository files
        from twisted.web import static, server
        from twisted.internet import reactor
        self.root = static.File(self.repbase)
        self.site = server.Site(self.root)
        self.httpServer = reactor.listenTCP(0, self.site)
        self.httpPort = self.httpServer.getHost().port

    def runCommand(self, basedir, command, failureIsOk=False):
        # all commands passed to do() should be strings or lists. If they are
        # strings, none of the arguments may have spaces. This makes the
        # commands less verbose at the expense of restricting what they can
        # specify.
        if type(command) not in (list, tuple):
            command = command.split(" ")
        #print "do %s" % command
        d = utils.getProcessOutputAndValue(command[0], command[1:],
                                           env=os.environ, path=basedir)
        def check((out, err, code)):
            #print "out: %s" % out
            if code != 0 and not failureIsOk:
                log.msg("command %s finished with exit code %d" %
                        (command, code))
                log.msg(" and stdout %s" % (out,))
                log.msg(" and stderr %s" % (err,))
                raise RuntimeError("command %s finished with exit code %d"
                                   % (command, code)
                                   + ": see logs for stdout")
            return out
        d.addCallback(check)
        return d

    def do(self, basedir, command, failureIsOk=False):
        d = self.runCommand(basedir, command, failureIsOk=failureIsOk)
        return waitForDeferred(d)

    def dovc(self, basedir, command, failureIsOk=False):
        """Like do(), but the VC binary will be prepended to COMMAND."""
        command = self.vcexe + " " + command
        return self.do(basedir, command, failureIsOk)

    def populate(self, basedir):
        os.makedirs(basedir)
        os.makedirs(os.path.join(basedir, "subdir"))
        open(os.path.join(basedir, "main.c"), "w").write(MAIN_C)
        self.version = 1
        version_c = VERSION_C % self.version
        open(os.path.join(basedir, "version.c"), "w").write(version_c)
        open(os.path.join(basedir, "main.c"), "w").write(MAIN_C)
        open(os.path.join(basedir, "subdir", "subdir.c"), "w").write(SUBDIR_C)

    def populate_branch(self, basedir):
        open(os.path.join(basedir, "main.c"), "w").write(BRANCH_C)

    def doBuild(self, shouldSucceed=True, ss=None):
        c = interfaces.IControl(self.master)

        if ss is None:
            ss = SourceStamp()
        #print "doBuild(ss: b=%s rev=%s)" % (ss.branch, ss.revision)
        req = base.BuildRequest("test_vc forced build", ss)
        d = req.waitUntilFinished()
        c.getBuilder("vc").requestBuild(req)
        d.addCallback(self._doBuild_1, shouldSucceed)
        return d
    def _doBuild_1(self, bs, shouldSucceed):
        r = bs.getResults()
        if r != SUCCESS and shouldSucceed:
            assert bs.isFinished()
            print
            print
            print "Build did not succeed:", r, bs.getText()
            for s in bs.getSteps():
                for l in s.getLogs():
                    print "--- START step %s / log %s ---" % (s.getName(),
                                                              l.getName())
                    print l.getTextWithHeaders()
                    print "--- STOP ---"
                    print
            self.fail("build did not succeed")
        return bs

    def touch(self, d, f):
        open(os.path.join(d,f),"w").close()
    def shouldExist(self, *args):
        self.failUnless(os.path.exists(os.path.join(*args)))
    def shouldNotExist(self, *args):
        self.failIf(os.path.exists(os.path.join(*args)))
    def shouldContain(self, d, f, contents):
        c = open(os.path.join(d, f), "r").read()
        self.failUnlessIn(contents, c)

    def do_vctest(self, testRetry=True):
        vctype = self.vctype
        args = self.vcargs
        m = self.master
        self.vcdir = os.path.join(self.slavebase, "vc-dir", "source")
        self.workdir = os.path.join(self.slavebase, "vc-dir", "build")
        # woo double-substitution
        s = "s(%s, timeout=200, workdir='build', mode='%%s'" % (vctype,)
        for k,v in args.items():
            s += ", %s=%s" % (k, repr(v))
        s += ")"
        config = config_vc % s

        m.loadConfig(config % 'clobber')
        m.readConfig = True
        m.startService()

        d = self.connectSlave()
        d.addCallback(lambda res: log.msg("testing clobber"))
        d.addCallback(self._do_vctest_clobber)
        d.addCallback(lambda res: log.msg("doing update"))
        d.addCallback(lambda res: self.loadConfig(config % 'update'))
        d.addCallback(lambda res: log.msg("testing update"))
        d.addCallback(self._do_vctest_update)
        if testRetry:
            d.addCallback(lambda res: log.msg("testing update retry"))
            d.addCallback(self._do_vctest_update_retry)
        d.addCallback(lambda res: log.msg("doing copy"))
        d.addCallback(lambda res: self.loadConfig(config % 'copy'))
        d.addCallback(lambda res: log.msg("testing copy"))
        d.addCallback(self._do_vctest_copy)
        if self.metadir:
            d.addCallback(lambda res: log.msg("doing export"))
            d.addCallback(lambda res: self.loadConfig(config % 'export'))
            d.addCallback(lambda res: log.msg("testing export"))
            d.addCallback(self._do_vctest_export)
        return d

    def _do_vctest_clobber(self, res):
        d = self.doBuild() # initial checkout
        d.addCallback(self._do_vctest_clobber_1)
        return d
    def _do_vctest_clobber_1(self, res):
        self.shouldExist(self.workdir, "main.c")
        self.shouldExist(self.workdir, "version.c")
        self.shouldExist(self.workdir, "subdir", "subdir.c")
        if self.metadir:
            self.shouldExist(self.workdir, self.metadir)

        self.touch(self.workdir, "newfile")
        self.shouldExist(self.workdir, "newfile")
        d = self.doBuild() # rebuild clobbers workdir
        d.addCallback(self._do_vctest_clobber_2)
        return d
    def _do_vctest_clobber_2(self, res):
        self.shouldNotExist(self.workdir, "newfile")

    def _do_vctest_update(self, res):
        log.msg("_do_vctest_update")
        d = self.doBuild() # rebuild with update
        d.addCallback(self._do_vctest_update_1)
        return d
    def _do_vctest_update_1(self, res):
        log.msg("_do_vctest_update_1")
        self.shouldExist(self.workdir, "main.c")
        self.shouldExist(self.workdir, "version.c")
        self.shouldContain(self.workdir, "version.c",
                           "version=%d" % self.version)
        if self.metadir:
            self.shouldExist(self.workdir, self.metadir)

        self.touch(self.workdir, "newfile")
        d = self.doBuild() # update rebuild leaves new files
        d.addCallback(self._do_vctest_update_2)
        return d
    def _do_vctest_update_2(self, res):
        log.msg("_do_vctest_update_2")
        self.shouldExist(self.workdir, "main.c")
        self.shouldExist(self.workdir, "version.c")
        self.touch(self.workdir, "newfile")
        # now make a change to the repository and make sure we pick it up
        d = self.vc_revise()
        d.addCallback(lambda res: self.doBuild())
        d.addCallback(self._do_vctest_update_3)
        return d
    def _do_vctest_update_3(self, res):
        log.msg("_do_vctest_update_3")
        self.shouldExist(self.workdir, "main.c")
        self.shouldExist(self.workdir, "version.c")
        self.shouldContain(self.workdir, "version.c",
                           "version=%d" % self.version)
        self.shouldExist(self.workdir, "newfile")
        # now "update" to an older revision
        d = self.doBuild(ss=SourceStamp(revision=self.trunk[-2]))
        d.addCallback(self._do_vctest_update_4)
        return d
    def _do_vctest_update_4(self, res):
        log.msg("_do_vctest_update_4")
        self.shouldExist(self.workdir, "main.c")
        self.shouldExist(self.workdir, "version.c")
        self.shouldContain(self.workdir, "version.c",
                           "version=%d" % (self.version-1))
        # now update to the newer revision
        d = self.doBuild(ss=SourceStamp(revision=self.trunk[-1]))
        d.addCallback(self._do_vctest_update_5)
        return d
    def _do_vctest_update_5(self, res):
        log.msg("_do_vctest_update_5")
        self.shouldExist(self.workdir, "main.c")
        self.shouldExist(self.workdir, "version.c")
        self.shouldContain(self.workdir, "version.c",
                           "version=%d" % self.version)


    def _do_vctest_update_retry(self, res):
        # certain local changes will prevent an update from working. The
        # most common is to replace a file with a directory, or vice
        # versa. The slave code should spot the failure and do a
        # clobber/retry.
        os.unlink(os.path.join(self.workdir, "main.c"))
        os.mkdir(os.path.join(self.workdir, "main.c"))
        self.touch(os.path.join(self.workdir, "main.c"), "foo")
        self.touch(self.workdir, "newfile")

        d = self.doBuild() # update, but must clobber to handle the error
        d.addCallback(self._do_vctest_update_retry_1)
        return d
    def _do_vctest_update_retry_1(self, res):
        self.shouldNotExist(self.workdir, "newfile")

    def _do_vctest_copy(self, res):
        d = self.doBuild() # copy rebuild clobbers new files
        d.addCallback(self._do_vctest_copy_1)
        return d
    def _do_vctest_copy_1(self, res):
        if self.metadir:
            self.shouldExist(self.workdir, self.metadir)
        self.shouldNotExist(self.workdir, "newfile")
        self.touch(self.workdir, "newfile")
        self.touch(self.vcdir, "newvcfile")

        d = self.doBuild() # copy rebuild clobbers new files
        d.addCallback(self._do_vctest_copy_2)
        return d
    def _do_vctest_copy_2(self, res):
        if self.metadir:
            self.shouldExist(self.workdir, self.metadir)
        self.shouldNotExist(self.workdir, "newfile")
        self.shouldExist(self.vcdir, "newvcfile")
        self.shouldExist(self.workdir, "newvcfile")
        self.touch(self.workdir, "newfile")

    def _do_vctest_export(self, res):
        d = self.doBuild() # export rebuild clobbers new files
        d.addCallback(self._do_vctest_export_1)
        return d
    def _do_vctest_export_1(self, res):
        self.shouldNotExist(self.workdir, self.metadir)
        self.shouldNotExist(self.workdir, "newfile")
        self.touch(self.workdir, "newfile")

        d = self.doBuild() # export rebuild clobbers new files
        d.addCallback(self._do_vctest_export_2)
        return d
    def _do_vctest_export_2(self, res):
        self.shouldNotExist(self.workdir, self.metadir)
        self.shouldNotExist(self.workdir, "newfile")

    def do_patch(self):
        vctype = self.vctype
        args = self.vcargs
        m = self.master
        self.vcdir = os.path.join(self.slavebase, "vc-dir", "source")
        self.workdir = os.path.join(self.slavebase, "vc-dir", "build")
        s = "s(%s, timeout=200, workdir='build', mode='%%s'" % (vctype,)
        for k,v in args.items():
            s += ", %s=%s" % (k, repr(v))
        s += ")"
        self.config = config_vc % s

        m.loadConfig(self.config % "clobber")
        m.readConfig = True
        m.startService()

        ss = SourceStamp(revision=self.trunk[-1], patch=(0, p0_diff))

        d = self.connectSlave()
        d.addCallback(lambda res: self.doBuild(ss=ss))
        d.addCallback(self._doPatch_1)
        return d
    def _doPatch_1(self, res):
        self.shouldContain(self.workdir, "version.c",
                           "version=%d" % self.version)
        # make sure the file actually got patched
        subdir_c = os.path.join(self.slavebase, "vc-dir", "build",
                                "subdir", "subdir.c")
        data = open(subdir_c, "r").read()
        self.failUnlessIn("Hello patched subdir.\\n", data)

        # make sure that a rebuild does not use the leftover patched workdir
        d = self.master.loadConfig(self.config % "update")
        d.addCallback(lambda res: self.doBuild(ss=None))
        d.addCallback(self._doPatch_2)
        return d
    def _doPatch_2(self, res):
        # make sure the file is back to its original
        subdir_c = os.path.join(self.slavebase, "vc-dir", "build",
                                "subdir", "subdir.c")
        data = open(subdir_c, "r").read()
        self.failUnlessIn("Hello subdir.\\n", data)

        # now make sure we can patch an older revision. We need at least two
        # revisions here, so we might have to create one first
        if len(self.trunk) < 2:
            d = self.vc_revise()
            d.addCallback(self._doPatch_3)
            return d
        return self._doPatch_3()

    def _doPatch_3(self, res=None):
        ss = SourceStamp(revision=self.trunk[-2], patch=(0, p0_diff))
        d = self.doBuild(ss=ss)
        d.addCallback(self._doPatch_4)
        return d
    def _doPatch_4(self, res):
        self.shouldContain(self.workdir, "version.c",
                           "version=%d" % (self.version-1))
        # and make sure the file actually got patched
        subdir_c = os.path.join(self.slavebase, "vc-dir", "build",
                                "subdir", "subdir.c")
        data = open(subdir_c, "r").read()
        self.failUnlessIn("Hello patched subdir.\\n", data)

        # now check that we can patch a branch
        ss = SourceStamp(branch=self.branchname, revision=self.branch[-1],
                         patch=(0, p0_diff))
        d = self.doBuild(ss=ss)
        d.addCallback(self._doPatch_5)
        return d
    def _doPatch_5(self, res):
        self.shouldContain(self.workdir, "version.c",
                           "version=%d" % 1)
        self.shouldContain(self.workdir, "main.c", "Hello branch.")
        subdir_c = os.path.join(self.slavebase, "vc-dir", "build",
                                "subdir", "subdir.c")
        data = open(subdir_c, "r").read()
        self.failUnlessIn("Hello patched subdir.\\n", data)


    def do_vctest_once(self, shouldSucceed):
        m = self.master
        vctype = self.vctype
        args = self.vcargs
        vcdir = os.path.join(self.slavebase, "vc-dir", "source")
        workdir = os.path.join(self.slavebase, "vc-dir", "build")
        # woo double-substitution
        s = "s(%s, timeout=200, workdir='build', mode='clobber'" % (vctype,)
        for k,v in args.items():
            s += ", %s=%s" % (k, repr(v))
        s += ")"
        config = config_vc % s

        m.loadConfig(config)
        m.readConfig = True
        m.startService()

        self.connectSlave()
        d = self.doBuild(shouldSucceed) # initial checkout
        return d

    def do_branch(self):
        vctype = self.vctype
        args = self.vcargs
        m = self.master
        self.vcdir = os.path.join(self.slavebase, "vc-dir", "source")
        self.workdir = os.path.join(self.slavebase, "vc-dir", "build")
        s = "s(%s, timeout=200, workdir='build', mode='%%s'" % (vctype,)
        for k,v in args.items():
            s += ", %s=%s" % (k, repr(v))
        s += ")"
        self.config = config_vc % s

        m.loadConfig(self.config % "update")
        m.readConfig = True
        m.startService()

        # first we do a build of the trunk
        d = self.connectSlave()
        d.addCallback(lambda res: self.doBuild(ss=SourceStamp()))
        d.addCallback(self._doBranch_1)
        return d
    def _doBranch_1(self, res):
        # make sure the checkout was of the trunk
        main_c = os.path.join(self.slavebase, "vc-dir", "build", "main.c")
        data = open(main_c, "r").read()
        self.failUnlessIn("Hello world.", data)

        # now do a checkout on the branch. The change in branch name should
        # trigger a clobber.
        self.touch(self.workdir, "newfile")
        d = self.doBuild(ss=SourceStamp(branch=self.branchname))
        d.addCallback(self._doBranch_2)
        return d
    def _doBranch_2(self, res):
        # make sure it was on the branch
        main_c = os.path.join(self.slavebase, "vc-dir", "build", "main.c")
        data = open(main_c, "r").read()
        self.failUnlessIn("Hello branch.", data)
        # and make sure the tree was clobbered
        self.shouldNotExist(self.workdir, "newfile")

        # doing another build on the same branch should not clobber the tree
        self.touch(self.workdir, "newbranchfile")
        d = self.doBuild(ss=SourceStamp(branch=self.branchname))
        d.addCallback(self._doBranch_3)
        return d
    def _doBranch_3(self, res):
        # make sure it is still on the branch
        main_c = os.path.join(self.slavebase, "vc-dir", "build", "main.c")
        data = open(main_c, "r").read()
        self.failUnlessIn("Hello branch.", data)
        # and make sure the tree was not clobbered
        self.shouldExist(self.workdir, "newbranchfile")

        # now make sure that a non-branch checkout clobbers the tree
        d = self.doBuild(ss=SourceStamp())
        d.addCallback(self._doBranch_4)
        return d
    def _doBranch_4(self, res):
        # make sure it was on the trunk
        main_c = os.path.join(self.slavebase, "vc-dir", "build", "main.c")
        data = open(main_c, "r").read()
        self.failUnlessIn("Hello world.", data)
        self.shouldNotExist(self.workdir, "newbranchfile")

    def do_getpatch(self, doBranch=True):
        # prepare a buildslave to do checkouts
        vctype = self.vctype
        args = self.vcargs
        m = self.master
        self.vcdir = os.path.join(self.slavebase, "vc-dir", "source")
        self.workdir = os.path.join(self.slavebase, "vc-dir", "build")
        # woo double-substitution
        s = "s(%s, timeout=200, workdir='build', mode='%%s'" % (vctype,)
        for k,v in args.items():
            s += ", %s=%s" % (k, repr(v))
        s += ")"
        config = config_vc % s

        m.loadConfig(config % 'clobber')
        m.readConfig = True
        m.startService()

        d = self.connectSlave()

        # then set up the "developer's tree". first we modify a tree from the
        # head of the trunk
        tmpdir = "try_workdir"
        self.trydir = os.path.join(self.repbase, tmpdir)
        d.addCallback(self.do_getpatch_trunkhead)
        d.addCallback(self.do_getpatch_trunkold)
        if doBranch:
            d.addCallback(self.do_getpatch_branch)
        d.addBoth(self.do_getpatch_finish)
        return d

    def do_getpatch_finish(self, res):
        self.vc_try_finish(self.trydir)
        return res

    def try_shouldMatch(self, filename):
        devfilename = os.path.join(self.trydir, filename)
        devfile = open(devfilename, "r").read()
        slavefilename = os.path.join(self.workdir, filename)
        slavefile = open(slavefilename, "r").read()
        self.failUnlessEqual(devfile, slavefile,
                             ("slavefile (%s) contains '%s'. "
                              "developer's file (%s) contains '%s'. "
                              "These ought to match") %
                             (slavefilename, slavefile,
                              devfilename, devfile))

    def do_getpatch_trunkhead(self, res):
        d = self.vc_try_checkout(self.trydir, self.trunk[-1])
        d.addCallback(self._do_getpatch_trunkhead_1)
        return d
    def _do_getpatch_trunkhead_1(self, res):
        d = tryclient.getSourceStamp(self.vctype_try, self.trydir, None)
        d.addCallback(self._do_getpatch_trunkhead_2)
        return d
    def _do_getpatch_trunkhead_2(self, ss):
        d = self.doBuild(ss=ss)
        d.addCallback(self._do_getpatch_trunkhead_3)
        return d
    def _do_getpatch_trunkhead_3(self, res):
        # verify that the resulting buildslave tree matches the developer's
        self.try_shouldMatch("main.c")
        self.try_shouldMatch("version.c")
        self.try_shouldMatch(os.path.join("subdir", "subdir.c"))

    def do_getpatch_trunkold(self, res):
        # now try a tree from an older revision. We need at least two
        # revisions here, so we might have to create one first
        if len(self.trunk) < 2:
            d = self.vc_revise()
            d.addCallback(self._do_getpatch_trunkold_1)
            return d
        return self._do_getpatch_trunkold_1()
    def _do_getpatch_trunkold_1(self, res=None):
        d = self.vc_try_checkout(self.trydir, self.trunk[-2])
        d.addCallback(self._do_getpatch_trunkold_2)
        return d
    def _do_getpatch_trunkold_2(self, res):
        d = tryclient.getSourceStamp(self.vctype_try, self.trydir, None)
        d.addCallback(self._do_getpatch_trunkold_3)
        return d
    def _do_getpatch_trunkold_3(self, ss):
        d = self.doBuild(ss=ss)
        d.addCallback(self._do_getpatch_trunkold_4)
        return d
    def _do_getpatch_trunkold_4(self, res):
        # verify that the resulting buildslave tree matches the developer's
        self.try_shouldMatch("main.c")
        self.try_shouldMatch("version.c")
        self.try_shouldMatch(os.path.join("subdir", "subdir.c"))

    def do_getpatch_branch(self, res):
        # now try a tree from a branch
        d = self.vc_try_checkout(self.trydir, self.branch[-1], self.branchname)
        d.addCallback(self._do_getpatch_branch_1)
        return d
    def _do_getpatch_branch_1(self, res):
        d = tryclient.getSourceStamp(self.vctype_try, self.trydir,
                                     self.try_branchname)
        d.addCallback(self._do_getpatch_branch_2)
        return d
    def _do_getpatch_branch_2(self, ss):
        d = self.doBuild(ss=ss)
        d.addCallback(self._do_getpatch_branch_3)
        return d
    def _do_getpatch_branch_3(self, res):
        # verify that the resulting buildslave tree matches the developer's
        self.try_shouldMatch("main.c")
        self.try_shouldMatch("version.c")
        self.try_shouldMatch(os.path.join("subdir", "subdir.c"))


    def dumpPatch(self, patch):
        # this exists to help me figure out the right 'patchlevel' value
        # should be returned by tryclient.getSourceStamp
        n = self.mktemp()
        open(n,"w").write(patch)
        d = self.runCommand(".", ["lsdiff", n])
        def p(res): print "lsdiff:", res.strip().split("\n")
        d.addCallback(p)
        return d


    def tearDown(self):
        d = defer.succeed(None)
        if self.slave:
            d2 = self.master.botmaster.waitUntilBuilderDetached("vc")
            d.addCallback(lambda res: self.slave.stopService())
            d.addCallback(lambda res: d2)
        if self.master:
            d.addCallback(lambda res: self.master.stopService())
        if self.httpServer:
            d.addCallback(lambda res: self.httpServer.stopListening())
            def stopHTTPTimer():
                try:
                    from twisted.web import http # Twisted-2.0
                except ImportError:
                    from twisted.protocols import http # Twisted-1.3
                http._logDateTimeStop() # shut down the internal timer. DUMB!
            d.addCallback(lambda res: stopHTTPTimer())
        d.addCallback(lambda res: self.tearDown2())
        return maybeWait(d)

    def tearDown2(self):
        pass

class CVSSupport(VCBase):
    metadir = "CVS"
    branchname = "branch"
    try_branchname = "branch"
    vctype = "step.CVS"
    vctype_try = "cvs"

    def capable(self):
        global VCS
        if not VCS.has_key("cvs"):
            VCS["cvs"] = False
            cvspaths = which('cvs')
            if cvspaths:
                VCS["cvs"] = True
                self.vcexe = cvspaths[0]
        if not VCS["cvs"]:
            raise unittest.SkipTest("CVS is not installed")

    def postCreate(self, res):
        self.vcargs = { 'cvsroot': self.cvsrep, 'cvsmodule': "sample" }

    def getdate(self):
        return time.strftime("%Y-%m-%d %H:%M:%S %z", time.gmtime())

    def vc_create(self):
        self.cvsrep = cvsrep = os.path.join(self.repbase, "CVS-Repository")
        tmp = os.path.join(self.repbase, "cvstmp")

        w = self.dovc(self.repbase, "-d %s init" % cvsrep)
        yield w; w.getResult() # we must getResult() to raise any exceptions

        self.populate(tmp)
        cmd = ("-d %s import" % cvsrep +
               " -m sample_project_files sample vendortag start")
        w = self.dovc(tmp, cmd)
        yield w; w.getResult()
        rmdirRecursive(tmp)
        # take a timestamp as the first revision number
        time.sleep(2)
        self.addTrunkRev(self.getdate())
        time.sleep(2)

        w = self.dovc(self.repbase,
                      "-d %s checkout -d cvstmp sample" % self.cvsrep)
        yield w; w.getResult()

        w = self.dovc(tmp, "tag -b %s" % self.branchname)
        yield w; w.getResult()
        self.populate_branch(tmp)
        w = self.dovc(tmp,
                      "commit -m commit_on_branch -r %s" % self.branchname)
        yield w; w.getResult()
        rmdirRecursive(tmp)
        time.sleep(2)
        self.addBranchRev(self.getdate())
        time.sleep(2)
    vc_create = deferredGenerator(vc_create)


    def vc_revise(self):
        tmp = os.path.join(self.repbase, "cvstmp")

        w = self.dovc(self.repbase,
                      "-d %s checkout -d cvstmp sample" % self.cvsrep)
        yield w; w.getResult()
        self.version += 1
        version_c = VERSION_C % self.version
        open(os.path.join(tmp, "version.c"), "w").write(version_c)
        w = self.dovc(tmp,
                      "commit -m revised_to_%d version.c" % self.version)
        yield w; w.getResult()
        rmdirRecursive(tmp)
        time.sleep(2)
        self.addTrunkRev(self.getdate())
        time.sleep(2)
    vc_revise = deferredGenerator(vc_revise)

    def vc_try_checkout(self, workdir, rev, branch=None):
        # 'workdir' is an absolute path
        assert os.path.abspath(workdir) == workdir

        # get rid of timezone info, which might not be parsed # TODO
        #rev =  re.sub("[^0-9 :-]","",rev)
        #rev =  re.sub("  ","",rev)
        #print "res is now <"+rev+">"
        cmd = [self.vcexe, "-d", self.cvsrep, "checkout",
               "-d", workdir,
               "-D", rev]
        if branch is not None:
            cmd.append("-r")
            cmd.append(branch)
        cmd.append("sample")
        w = self.do(self.repbase, cmd)
        yield w; w.getResult()
        open(os.path.join(workdir, "subdir", "subdir.c"), "w").write(TRY_C)
    vc_try_checkout = deferredGenerator(vc_try_checkout)

    def vc_try_finish(self, workdir):
        rmdirRecursive(workdir)

class CVS(CVSSupport, unittest.TestCase):

    def testCheckout(self):
        d = self.do_vctest()
        return maybeWait(d)

    def testPatch(self):
        d = self.do_patch()
        return maybeWait(d)

    def testBranch(self):
        d = self.do_branch()
        return maybeWait(d)
        
    def testTry(self):
        d = self.do_getpatch(doBranch=False)
        return maybeWait(d)


class SVNSupport(VCBase):
    metadir = ".svn"
    branchname = "sample/branch"
    try_branchname = "sample/branch"
    vctype = "step.SVN"
    vctype_try = "svn"

    def capable(self):
        global VCS
        if not VCS.has_key("svn"):
            VCS["svn"] = False
            svnpaths = which('svn')
            svnadminpaths = which('svnadmin')
            if svnpaths and svnadminpaths:
                self.vcexe = svnpaths[0]
                self.svnadmin = svnadminpaths[0]
                # we need svn to be compiled with the ra_local access
                # module
                log.msg("running svn --version..")
                d = utils.getProcessOutput(self.vcexe, ["--version"],
                                           env=os.environ)
                d.addCallback(self._capable)
                return d
        if not VCS["svn"]:
            raise unittest.SkipTest("No usable Subversion was found")

    def _capable(self, v):
        if v.find("handles 'file' schem") != -1:
            # older versions say 'schema', 1.2.0 and beyond say 'scheme'
            VCS['svn'] = True
        else:
            log.msg(("%s found but it does not support 'file:' " +
                     "schema, skipping svn tests") %
                    os.path.join(p, "svn"))
            VCS['svn'] = False
            raise unittest.SkipTest("Found SVN, but it can't use file: schema")

    def vc_create(self):
        self.svnrep = os.path.join(self.repbase,
                                   "SVN-Repository").replace('\\','/')
        tmp = os.path.join(self.repbase, "svntmp")
        if sys.platform == 'win32':
            # On Windows Paths do not start with a /
            self.svnurl = "file:///%s" % self.svnrep
        else:
            self.svnurl = "file://%s" % self.svnrep
        self.svnurl_trunk = self.svnurl + "/sample/trunk"
        self.svnurl_branch = self.svnurl + "/sample/branch"

        w = self.do(self.repbase, self.svnadmin+" create %s" % self.svnrep)
        yield w; w.getResult()

        self.populate(tmp)
        w = self.dovc(tmp,
                      "import -m sample_project_files %s" %
                      self.svnurl_trunk)
        yield w; out = w.getResult()
        rmdirRecursive(tmp)
        m = re.search(r'Committed revision (\d+)\.', out)
        assert m.group(1) == "1" # first revision is always "1"
        self.addTrunkRev(int(m.group(1)))

        w = self.dovc(self.repbase,
                      "checkout %s svntmp" % self.svnurl_trunk)
        yield w; w.getResult()

        w = self.dovc(tmp, "cp -m make_branch %s %s" % (self.svnurl_trunk,
                                                        self.svnurl_branch))
        yield w; w.getResult()
        w = self.dovc(tmp, "switch %s" % self.svnurl_branch)
        yield w; w.getResult()
        self.populate_branch(tmp)
        w = self.dovc(tmp, "commit -m commit_on_branch")
        yield w; out = w.getResult()
        rmdirRecursive(tmp)
        m = re.search(r'Committed revision (\d+)\.', out)
        self.addBranchRev(int(m.group(1)))
    vc_create = deferredGenerator(vc_create)

    def vc_revise(self):
        tmp = os.path.join(self.repbase, "svntmp")
        rmdirRecursive(tmp)
        log.msg("vc_revise" +  self.svnurl_trunk)
        w = self.dovc(self.repbase,
                      "checkout %s svntmp" % self.svnurl_trunk)
        yield w; w.getResult()
        self.version += 1
        version_c = VERSION_C % self.version
        open(os.path.join(tmp, "version.c"), "w").write(version_c)
        w = self.dovc(tmp, "commit -m revised_to_%d" % self.version)
        yield w; out = w.getResult()
        m = re.search(r'Committed revision (\d+)\.', out)
        self.addTrunkRev(int(m.group(1)))
        rmdirRecursive(tmp)
    vc_revise = deferredGenerator(vc_revise)

    def vc_try_checkout(self, workdir, rev, branch=None):
        assert os.path.abspath(workdir) == workdir
        if os.path.exists(workdir):
            rmdirRecursive(workdir)
        if not branch:
            svnurl = self.svnurl_trunk
        else:
            # N.B.: this is *not* os.path.join: SVN URLs use slashes
            # regardless of the host operating system's filepath separator
            svnurl = self.svnurl + "/" + branch
        w = self.dovc(self.repbase,
                      "checkout %s %s" % (svnurl, workdir))
        yield w; w.getResult()
        open(os.path.join(workdir, "subdir", "subdir.c"), "w").write(TRY_C)
    vc_try_checkout = deferredGenerator(vc_try_checkout)
    def vc_try_finish(self, workdir):
        rmdirRecursive(workdir)


class SVN(SVNSupport, unittest.TestCase):

    def testCheckout(self):
        # we verify this one with the svnurl style of vcargs. We test the
        # baseURL/defaultBranch style in testPatch and testBranch.
        self.vcargs = { 'svnurl': self.svnurl_trunk }
        d = self.do_vctest()
        return maybeWait(d)

    def testPatch(self):
        self.vcargs = { 'baseURL': self.svnurl + "/",
                        'defaultBranch': "sample/trunk",
                        }
        d = self.do_patch()
        return maybeWait(d)

    def testBranch(self):
        self.vcargs = { 'baseURL': self.svnurl + "/",
                        'defaultBranch': "sample/trunk",
                        }
        d = self.do_branch()
        return maybeWait(d)

    def testTry(self):
        # extract the base revision and patch from a modified tree, use it to
        # create the same contents on the buildslave
        self.vcargs = { 'baseURL': self.svnurl + "/",
                        'defaultBranch': "sample/trunk",
                        }
        d = self.do_getpatch()
        return maybeWait(d)


class DarcsSupport(VCBase):
    # Darcs has a metadir="_darcs", but it does not have an 'export'
    # mode
    metadir = None
    branchname = "branch"
    try_branchname = "branch"
    vctype = "step.Darcs"
    vctype_try = "darcs"

    def capable(self):
        global VCS
        if not VCS.has_key("darcs"):
            VCS["darcs"] = False
            for p in os.environ['PATH'].split(os.pathsep):
                if os.path.exists(os.path.join(p, 'darcs')):
                    VCS["darcs"] = True
        if not VCS["darcs"]:
            raise unittest.SkipTest("Darcs is not installed")

    def vc_create(self):
        self.darcs_base = os.path.join(self.repbase, "Darcs-Repository")
        self.rep_trunk = os.path.join(self.darcs_base, "trunk")
        self.rep_branch = os.path.join(self.darcs_base, "branch")
        tmp = os.path.join(self.repbase, "darcstmp")

        os.makedirs(self.rep_trunk)
        w = self.do(self.rep_trunk, "darcs initialize")
        yield w; w.getResult()
        os.makedirs(self.rep_branch)
        w = self.do(self.rep_branch, "darcs initialize")
        yield w; w.getResult()

        self.populate(tmp)
        w = self.do(tmp, "darcs initialize")
        yield w; w.getResult()
        w = self.do(tmp, "darcs add -r .")
        yield w; w.getResult()
        w = self.do(tmp, "darcs record -a -m initial_import --skip-long-comment -A test@buildbot.sf.net")
        yield w; w.getResult()
        w = self.do(tmp, "darcs push -a %s" % self.rep_trunk)
        yield w; w.getResult()
        w = self.do(tmp, "darcs changes --context")
        yield w; out = w.getResult()
        self.addTrunkRev(out)

        self.populate_branch(tmp)
        w = self.do(tmp, "darcs record -a --ignore-times -m commit_on_branch --skip-long-comment -A test@buildbot.sf.net")
        yield w; w.getResult()
        w = self.do(tmp, "darcs push -a %s" % self.rep_branch)
        yield w; w.getResult()
        w = self.do(tmp, "darcs changes --context")
        yield w; out = w.getResult()
        self.addBranchRev(out)
        rmdirRecursive(tmp)
    vc_create = deferredGenerator(vc_create)

    def vc_revise(self):
        tmp = os.path.join(self.repbase, "darcstmp")
        os.makedirs(tmp)
        w = self.do(tmp, "darcs initialize")
        yield w; w.getResult()
        w = self.do(tmp, "darcs pull -a %s" % self.rep_trunk)
        yield w; w.getResult()

        self.version += 1
        version_c = VERSION_C % self.version
        open(os.path.join(tmp, "version.c"), "w").write(version_c)
        w = self.do(tmp, "darcs record -a --ignore-times -m revised_to_%d --skip-long-comment -A test@buildbot.sf.net" % self.version)
        yield w; w.getResult()
        w = self.do(tmp, "darcs push -a %s" % self.rep_trunk)
        yield w; w.getResult()
        w = self.do(tmp, "darcs changes --context")
        yield w; out = w.getResult()
        self.addTrunkRev(out)
        rmdirRecursive(tmp)
    vc_revise = deferredGenerator(vc_revise)

    def vc_try_checkout(self, workdir, rev, branch=None):
        assert os.path.abspath(workdir) == workdir
        if os.path.exists(workdir):
            rmdirRecursive(workdir)
        os.makedirs(workdir)
        w = self.do(workdir, "darcs initialize")
        yield w; w.getResult()
        if not branch:
            rep = self.rep_trunk
        else:
            rep = os.path.join(self.darcs_base, branch)
        w = self.do(workdir, "darcs pull -a %s" % rep)
        yield w; w.getResult()
        open(os.path.join(workdir, "subdir", "subdir.c"), "w").write(TRY_C)
    vc_try_checkout = deferredGenerator(vc_try_checkout)

    def vc_try_finish(self, workdir):
        rmdirRecursive(workdir)


class Darcs(DarcsSupport, unittest.TestCase):
    def testCheckout(self):
        self.vcargs = { 'repourl': self.rep_trunk }
        d = self.do_vctest(testRetry=False)

        # TODO: testRetry has the same problem with Darcs as it does for
        # Arch
        return maybeWait(d)

    def testPatch(self):
        self.vcargs = { 'baseURL': self.darcs_base + "/",
                        'defaultBranch': "trunk" }
        d = self.do_patch()
        return maybeWait(d)

    def testBranch(self):
        self.vcargs = { 'baseURL': self.darcs_base + "/",
                        'defaultBranch': "trunk" }
        d = self.do_branch()
        return maybeWait(d)

    def testCheckoutHTTP(self):
        self.serveHTTP()
        repourl = "http://localhost:%d/Darcs-Repository/trunk" % self.httpPort
        self.vcargs =  { 'repourl': repourl }
        d = self.do_vctest(testRetry=False)
        return maybeWait(d)
        
    def testTry(self):
        self.vcargs = { 'baseURL': self.darcs_base + "/",
                        'defaultBranch': "trunk" }
        d = self.do_getpatch()
        return maybeWait(d)


class ArchCommon:

    def registerRepository(self, coordinates):
        a = self.archname
        w = self.do(self.repbase, "%s archives %s" % (self.archcmd, a))
        yield w; out = w.getResult()
        if out:
            w = self.do(self.repbase,
                        "%s register-archive -d %s" % (self.archcmd, a))
            yield w; w.getResult()
        w = self.do(self.repbase,
                    "%s register-archive %s" % (self.archcmd, coordinates))
        yield w; w.getResult()
    registerRepository = deferredGenerator(registerRepository)

    def unregisterRepository(self):
        a = self.archname
        w = self.do(self.repbase, "%s archives %s" % (self.archcmd, a))
        yield w; out = w.getResult()
        if out:
            w = self.do(self.repbase,
                        "%s register-archive -d %s" % (self.archcmd, a))
            yield w; out = w.getResult()
    unregisterRepository = deferredGenerator(unregisterRepository)

class TlaSupport(VCBase, ArchCommon):
    metadir = None
    # Arch has a metadir="{arch}", but it does not have an 'export' mode.
    fixtimer = None
    defaultbranch = "testvc--mainline--1"
    branchname = "testvc--branch--1"
    try_branchname = None # TlaExtractor can figure it out by itself
    vctype = "step.Arch"
    vctype_try = "tla"
    archcmd = "tla"

    def capable(self):
        global VCS
        if not VCS.has_key("tla"):
            VCS["tla"] = False
	    exe = which('tla')
            if len(exe) > 0:
                VCS["tla"] = True
        # we need to check for bazaar here too, since vc_create needs to know
        # about the presence of /usr/bin/baz even if we're running the tla
        # tests.
        if not VCS.has_key("baz"):
            VCS["baz"] = False
	    exe = which('baz')
            if len(exe) > 0:
                VCS["baz"] = True
        if not VCS["tla"]:
            raise unittest.SkipTest("Arch (tla) is not installed")

    def setUp2(self, res):
        # these are the coordinates of the read-write archive used by all the
        # non-HTTP tests. testCheckoutHTTP overrides these.
        self.vcargs = {'url': self.archrep,
                       'version': self.defaultbranch }
        # we unregister the repository each time, because we might have
        # changed the coordinates (since we switch from a file: URL to an
        # http: URL for various tests). The buildslave code doesn't forcibly
        # unregister the archive, so we have to do it here.
        d = self.unregisterRepository()
        return d

    def postCreate(self, res):
        pass

    def tearDown2(self):
        if self.fixtimer:
            self.fixtimer.cancel()
        # tell tla to get rid of the leftover archive this test leaves in the
        # user's 'tla archives' listing. The name of this archive is provided
        # by the repository tarball, so the following command must use the
        # same name. We could use archive= to set it explicitly, but if you
        # change it from the default, then 'tla update' won't work.
        d = self.unregisterRepository()
        return d

    def vc_create(self):
        # pick a hopefully unique string for the archive name, in the form
        # test-%d@buildbot.sf.net--testvc, since otherwise multiple copies of
        # the unit tests run in the same user account will collide (since the
        # archive names are kept in the per-user ~/.arch-params/ directory).
        pid = os.getpid()
        self.archname = "test-%s-%d@buildbot.sf.net--testvc" % (self.archcmd,
                                                                pid)
        trunk = self.defaultbranch
        branch = self.branchname

        repword = self.archcmd.capitalize()
        self.archrep = os.path.join(self.repbase, "%s-Repository" % repword)
        tmp = os.path.join(self.repbase, "archtmp")
        a = self.archname

        self.populate(tmp)

        w = self.do(tmp, "tla my-id", failureIsOk=True)
        yield w; res = w.getResult()
        if not res:
            # tla will fail a lot of operations if you have not set an ID
            w = self.do(tmp, ["tla", "my-id",
                              "Buildbot Test Suite <test@buildbot.sf.net>"])
            yield w; w.getResult()

        if VCS['baz']:
            # bazaar keeps a cache of revisions, but this test creates a new
            # archive each time it is run, so the cache causes errors.
            # Disable the cache to avoid these problems. This will be
            # slightly annoying for people who run the buildbot tests under
            # the same UID as one which uses baz on a regular basis, but
            # bazaar doesn't give us a way to disable the cache just for this
            # one archive.
            cmd = "baz cache-config --disable"
            w = self.do(tmp, cmd)
            yield w; w.getResult()

        w = waitForDeferred(self.unregisterRepository())
        yield w; w.getResult()

        # these commands can be run in any directory
        w = self.do(tmp, "tla make-archive -l %s %s" % (a, self.archrep))
        yield w; w.getResult()
        w = self.do(tmp, "tla archive-setup -A %s %s" % (a, trunk))
        yield w; w.getResult()
        w = self.do(tmp, "tla archive-setup -A %s %s" % (a, branch))
        yield w; w.getResult()

        # these commands must be run in the directory that is to be imported
        w = self.do(tmp, "tla init-tree --nested %s/%s" % (a, trunk))
        yield w; w.getResult()
        files = " ".join(["main.c", "version.c", "subdir",
                          os.path.join("subdir", "subdir.c")])
        w = self.do(tmp, "tla add-id %s" % files)
        yield w; w.getResult()

        w = self.do(tmp, "tla import %s/%s" % (a, trunk))
        yield w; out = w.getResult()
        self.addTrunkRev("base-0")

        # create the branch
        branchstart = "%s--base-0" % trunk
        w = self.do(tmp,
                    "tla tag -A %s %s %s" % (a, branchstart, branch))
        yield w; w.getResult()

        rmdirRecursive(tmp)

        # check out the branch
        w = self.do(self.repbase,
                    "tla get -A %s %s archtmp" % (a, branch))
        yield w; w.getResult()
        # and edit the file
        self.populate_branch(tmp)
        logfile = "++log.%s--%s" % (branch, a)
        logmsg = "Summary: commit on branch\nKeywords:\n\n"
        open(os.path.join(tmp, logfile), "w").write(logmsg)
        w = self.do(tmp, "tla commit")
        yield w; out = w.getResult()
        m = re.search(r'committed %s/%s--([\S]+)' % (a, branch),
                      out)
        assert (m.group(1) == "base-0" or m.group(1).startswith("patch-"))
        self.addBranchRev(m.group(1))

        w = waitForDeferred(self.unregisterRepository())
        yield w; w.getResult()
        rmdirRecursive(tmp)
    vc_create = deferredGenerator(vc_create)

    def vc_revise(self):
        # the fix needs to be done in a workspace that is linked to a
        # read-write version of the archive (i.e., using file-based
        # coordinates instead of HTTP ones), so we re-register the repository
        # before we begin. We unregister it when we're done to make sure the
        # build will re-register the correct one for whichever test is
        # currently being run.

        # except, that step.Bazaar really doesn't like it when the archive
        # gets unregistered behind its back. The slave tries to do a 'baz
        # replay' in a tree with an archive that is no longer recognized, and
        # baz aborts with a botched invariant exception. This causes
        # mode=update to fall back to clobber+get, which flunks one of the
        # tests (the 'newfile' check in _do_vctest_update_3 fails)

        # to avoid this, we take heroic steps here to leave the archive
        # registration in the same state as we found it.

        tmp = os.path.join(self.repbase, "archtmp")
        a = self.archname

        cmd = "%s archives %s" % (self.archcmd, a)
        w = self.do(self.repbase, cmd)
        yield w; out = w.getResult()
        assert out
        lines = out.split("\n")
        coordinates = lines[1].strip()

        # now register the read-write location
        w = waitForDeferred(self.registerRepository(self.archrep))
        yield w; w.getResult()

        trunk = self.defaultbranch

        # the 'get' syntax is different between tla and baz. baz, while
        # claiming to honor an --archive argument, in fact ignores it. The
        # correct invocation is 'baz get archive/revision newdir'.
        if self.archcmd == 'tla':
            cmd = "tla get -A %s %s archtmp" % (a, trunk)
        else:
            cmd = "baz get %s/%s archtmp" % (a, trunk)
        w = self.do(self.repbase, cmd)
                    
        yield w; w.getResult()

        # tla appears to use timestamps to determine which files have
        # changed, so wait long enough for the new file to have a different
        # timestamp
        time.sleep(2)
        self.version += 1
        version_c = VERSION_C % self.version
        open(os.path.join(tmp, "version.c"), "w").write(version_c)

        logfile = "++log.%s--%s" % (trunk, a)
        logmsg = "Summary: revised_to_%d\nKeywords:\n\n" % self.version
        open(os.path.join(tmp, logfile), "w").write(logmsg)
        w = self.do(tmp, "%s commit" % self.archcmd)
        yield w; out = w.getResult()
        m = re.search(r'committed %s/%s--([\S]+)' % (a, trunk),
                      out)
        assert (m.group(1) == "base-0" or m.group(1).startswith("patch-"))
        self.addTrunkRev(m.group(1))

        # now re-register the original coordinates
        w = waitForDeferred(self.registerRepository(coordinates))
        yield w; w.getResult()
        rmdirRecursive(tmp)
    vc_revise = deferredGenerator(vc_revise)

    def vc_try_checkout(self, workdir, rev, branch=None):
        assert os.path.abspath(workdir) == workdir
        if os.path.exists(workdir):
            rmdirRecursive(workdir)

        a = self.archname

        # register the read-write location, if it wasn't already registered
        w = waitForDeferred(self.registerRepository(self.archrep))
        yield w; w.getResult()

        # the 'get' syntax is different between tla and baz. baz, while
        # claiming to honor an --archive argument, in fact ignores it. The
        # correct invocation is 'baz get archive/revision newdir'.
        if self.archcmd == 'tla':
            cmd = "tla get -A %s testvc--mainline--1 %s" % (a, workdir)
        else:
            cmd = "baz get %s/testvc--mainline--1 %s" % (a, workdir)
        w = self.do(self.repbase, cmd)
        yield w; w.getResult()

        # timestamps. ick.
        time.sleep(2)
        open(os.path.join(workdir, "subdir", "subdir.c"), "w").write(TRY_C)
    vc_try_checkout = deferredGenerator(vc_try_checkout)

    def vc_try_finish(self, workdir):
        rmdirRecursive(workdir)

class Arch(TlaSupport, unittest.TestCase):
    def testCheckout(self):
        d = self.do_vctest(testRetry=False)
        # the current testRetry=True logic doesn't have the desired effect:
        # "update" is a no-op because arch knows that the repository hasn't
        # changed. Other VC systems will re-checkout missing files on
        # update, arch just leaves the tree untouched. TODO: come up with
        # some better test logic, probably involving a copy of the
        # repository that has a few changes checked in.

        return maybeWait(d)

    def testCheckoutHTTP(self):
        self.serveHTTP()
        url = "http://localhost:%d/Tla-Repository" % self.httpPort
        self.vcargs = { 'url': url,
                        'version': "testvc--mainline--1" }
        d = self.do_vctest(testRetry=False)
        return maybeWait(d)

    def testPatch(self):
        d = self.do_patch()
        return maybeWait(d)

    def testBranch(self):
        d = self.do_branch()
        return maybeWait(d)

    def testTry(self):
        d = self.do_getpatch()
        return maybeWait(d)

class BazaarSupport(TlaSupport):
    vctype = "step.Bazaar"
    vctype_try = "baz"
    archcmd = "baz"

    def capable(self):
        global VCS
        if not VCS.has_key("baz"):
            VCS["baz"] = False
            for p in os.environ['PATH'].split(os.pathsep):
                if os.path.exists(os.path.join(p, 'baz')):
                    VCS["baz"] = True
        if not VCS["baz"]:
            raise unittest.SkipTest("Arch (baz) is not installed")

    def setUp2(self, res):
        self.vcargs = {'url': self.archrep,
                       # Baz adds the required 'archive' argument
                       'archive': self.archname,
                       'version': self.defaultbranch,
                       }
        # we unregister the repository each time, because we might have
        # changed the coordinates (since we switch from a file: URL to an
        # http: URL for various tests). The buildslave code doesn't forcibly
        # unregister the archive, so we have to do it here.
        d = self.unregisterRepository()
        return d


class Bazaar(BazaarSupport, unittest.TestCase):
    def testCheckout(self):
        d = self.do_vctest(testRetry=False)
        # the current testRetry=True logic doesn't have the desired effect:
        # "update" is a no-op because arch knows that the repository hasn't
        # changed. Other VC systems will re-checkout missing files on
        # update, arch just leaves the tree untouched. TODO: come up with
        # some better test logic, probably involving a copy of the
        # repository that has a few changes checked in.

        return maybeWait(d)

    def testCheckoutHTTP(self):
        self.serveHTTP()
        url = "http://localhost:%d/Baz-Repository" % self.httpPort
        self.vcargs = { 'url': url,
                        'archive': self.archname,
                        'version': self.defaultbranch,
                        }
        d = self.do_vctest(testRetry=False)
        return maybeWait(d)

    def testPatch(self):
        d = self.do_patch()
        return maybeWait(d)

    def testBranch(self):
        d = self.do_branch()
        return maybeWait(d)

    def testTry(self):
        d = self.do_getpatch()
        return maybeWait(d)

    def fixRepository(self):
        self.fixtimer = None
        self.site.resource = self.root

    def testRetry(self):
        # we want to verify that step.Source(retry=) works, and the easiest
        # way to make VC updates break (temporarily) is to break the HTTP
        # server that's providing the repository. Anything else pretty much
        # requires mutating the (read-only) BUILDBOT_TEST_VC repository, or
        # modifying the buildslave's checkout command while it's running.

        # this test takes a while to run, so don't bother doing it with
        # anything other than baz

        self.serveHTTP()

        # break the repository server
        from twisted.web import static
        self.site.resource = static.Data("Sorry, repository is offline",
                                         "text/plain")
        # and arrange to fix it again in 5 seconds, while the test is
        # running.
        self.fixtimer = reactor.callLater(5, self.fixRepository)
        
        url = "http://localhost:%d/Baz-Repository" % self.httpPort
        self.vcargs = { 'url': url,
                        'archive': self.archname,
                        'version': self.defaultbranch,
                        'retry': (5.0, 4),
                        }
        d = self.do_vctest_once(True)
        d.addCallback(self._testRetry_1)
        return maybeWait(d)
    def _testRetry_1(self, bs):
        # make sure there was mention of the retry attempt in the logs
        l = bs.getLogs()[0]
        self.failUnlessIn("unable to access URL", l.getText(),
                          "funny, VC operation didn't fail at least once")
        self.failUnlessIn("update failed, trying 4 more times after 5 seconds",
                          l.getTextWithHeaders(),
                          "funny, VC operation wasn't reattempted")

    def testRetryFails(self):
        # make sure that the build eventually gives up on a repository which
        # is completely unavailable

        self.serveHTTP()

        # break the repository server, and leave it broken
        from twisted.web import static
        self.site.resource = static.Data("Sorry, repository is offline",
                                         "text/plain")

        url = "http://localhost:%d/Baz-Repository" % self.httpPort
        self.vcargs = {'url': url,
                       'archive': self.archname,
                       'version': self.defaultbranch,
                       'retry': (0.5, 3),
                       }
        d = self.do_vctest_once(False)
        d.addCallback(self._testRetryFails_1)
        return maybeWait(d)
    def _testRetryFails_1(self, bs):
        self.failUnlessEqual(bs.getResults(), FAILURE)

    

class Sources(unittest.TestCase):
    # TODO: this needs serious rethink
    def makeChange(self, when=None, revision=None):
        if when:
            when = mktime_tz(parsedate_tz(when))
        return changes.Change("fred", [], "", when=when, revision=revision)

    def testCVS1(self):
        r = base.BuildRequest("forced build", SourceStamp())
        b = base.Build([r])
        s = step.CVS(cvsroot=None, cvsmodule=None, workdir=None, build=b)
        self.failUnlessEqual(s.computeSourceRevision(b.allChanges()), None)

    def testCVS2(self):
        c = []
        c.append(self.makeChange("Wed, 08 Sep 2004 09:00:00 -0700"))
        c.append(self.makeChange("Wed, 08 Sep 2004 09:01:00 -0700"))
        c.append(self.makeChange("Wed, 08 Sep 2004 09:02:00 -0700"))
        r = base.BuildRequest("forced", SourceStamp(changes=c))
        submitted = "Wed, 08 Sep 2004 09:04:00 -0700"
        r.submittedAt = mktime_tz(parsedate_tz(submitted))
        b = base.Build([r])
        s = step.CVS(cvsroot=None, cvsmodule=None, workdir=None, build=b)
        self.failUnlessEqual(s.computeSourceRevision(b.allChanges()),
                             "Wed, 08 Sep 2004 16:03:00 -0000")

    def testCVS3(self):
        c = []
        c.append(self.makeChange("Wed, 08 Sep 2004 09:00:00 -0700"))
        c.append(self.makeChange("Wed, 08 Sep 2004 09:01:00 -0700"))
        c.append(self.makeChange("Wed, 08 Sep 2004 09:02:00 -0700"))
        r = base.BuildRequest("forced", SourceStamp(changes=c))
        submitted = "Wed, 08 Sep 2004 09:04:00 -0700"
        r.submittedAt = mktime_tz(parsedate_tz(submitted))
        b = base.Build([r])
        s = step.CVS(cvsroot=None, cvsmodule=None, workdir=None, build=b,
                     checkoutDelay=10)
        self.failUnlessEqual(s.computeSourceRevision(b.allChanges()),
                             "Wed, 08 Sep 2004 16:02:10 -0000")

    def testCVS4(self):
        c = []
        c.append(self.makeChange("Wed, 08 Sep 2004 09:00:00 -0700"))
        c.append(self.makeChange("Wed, 08 Sep 2004 09:01:00 -0700"))
        c.append(self.makeChange("Wed, 08 Sep 2004 09:02:00 -0700"))
        r1 = base.BuildRequest("forced", SourceStamp(changes=c))
        submitted = "Wed, 08 Sep 2004 09:04:00 -0700"
        r1.submittedAt = mktime_tz(parsedate_tz(submitted))

        c = []
        c.append(self.makeChange("Wed, 08 Sep 2004 09:05:00 -0700"))
        r2 = base.BuildRequest("forced", SourceStamp(changes=c))
        submitted = "Wed, 08 Sep 2004 09:07:00 -0700"
        r2.submittedAt = mktime_tz(parsedate_tz(submitted))

        b = base.Build([r1, r2])
        s = step.CVS(cvsroot=None, cvsmodule=None, workdir=None, build=b)
        self.failUnlessEqual(s.computeSourceRevision(b.allChanges()),
                             "Wed, 08 Sep 2004 16:06:00 -0000")

    def testSVN1(self):
        r = base.BuildRequest("forced", SourceStamp())
        b = base.Build([r])
        s = step.SVN(svnurl="dummy", workdir=None, build=b)
        self.failUnlessEqual(s.computeSourceRevision(b.allChanges()), None)

    def testSVN2(self):
        c = []
        c.append(self.makeChange(revision=4))
        c.append(self.makeChange(revision=10))
        c.append(self.makeChange(revision=67))
        r = base.BuildRequest("forced", SourceStamp(changes=c))
        b = base.Build([r])
        s = step.SVN(svnurl="dummy", workdir=None, build=b)
        self.failUnlessEqual(s.computeSourceRevision(b.allChanges()), 67)
