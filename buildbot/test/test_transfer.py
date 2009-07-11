# -*- test-case-name: buildbot.test.test_transfer -*-

import os
from stat import ST_MODE
from twisted.trial import unittest
from buildbot.process.buildstep import WithProperties
from buildbot.steps.transfer import FileUpload, FileDownload, DirectoryUpload
from buildbot.test.runutils import StepTester
from buildbot.status.builder import SUCCESS, FAILURE

# these steps pass a pb.Referenceable inside their arguments, so we have to
# catch and wrap them. If the LocalAsRemote wrapper were a proper membrane,
# we wouldn't have to do this.

class UploadFile(StepTester, unittest.TestCase):

    def filterArgs(self, args):
        if "writer" in args:
            args["writer"] = self.wrap(args["writer"])
        return args

    def testSuccess(self):
        self.slavebase = "UploadFile.testSuccess.slave"
        self.masterbase = "UploadFile.testSuccess.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        # the buildmaster normally runs chdir'ed into masterbase, so uploaded
        # files will appear there. Under trial, we're chdir'ed into
        # _trial_temp instead, so use a different masterdest= to keep the
        # uploaded file in a test-local directory
        masterdest = os.path.join(self.masterbase, "dest.text")
        step = self.makeStep(FileUpload,
                             slavesrc="source.txt",
                             masterdest=masterdest)
        slavesrc = os.path.join(self.slavebase,
                                self.slavebuilderbase,
                                "build",
                                "source.txt")
        contents = "this is the source file\n" * 1000
        open(slavesrc, "w").write(contents)
        f = open(masterdest, "w")
        f.write("overwrite me\n")
        f.close()

        d = self.runStep(step)
        def _checkUpload(results):
            step_status = step.step_status
            #l = step_status.getLogs()
            #if l:
            #    logtext = l[0].getText()
            #    print logtext
            self.failUnlessEqual(results, SUCCESS)
            self.failUnless(os.path.exists(masterdest))
            masterdest_contents = open(masterdest, "r").read()
            self.failUnlessEqual(masterdest_contents, contents)
        d.addCallback(_checkUpload)
        return d

    def testMaxsize(self):
        self.slavebase = "UploadFile.testMaxsize.slave"
        self.masterbase = "UploadFile.testMaxsize.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        masterdest = os.path.join(self.masterbase, "dest2.text")
        step = self.makeStep(FileUpload,
                             slavesrc="source.txt",
                             masterdest=masterdest,
                             maxsize=12345)
        slavesrc = os.path.join(self.slavebase,
                                self.slavebuilderbase,
                                "build",
                                "source.txt")
        contents = "this is the source file\n" * 1000
        open(slavesrc, "w").write(contents)
        f = open(masterdest, "w")
        f.write("overwrite me\n")
        f.close()

        d = self.runStep(step)
        def _checkUpload(results):
            step_status = step.step_status
            #l = step_status.getLogs()
            #if l:
            #    logtext = l[0].getText()
            #    print logtext
            self.failUnlessEqual(results, FAILURE)
            self.failUnless(os.path.exists(masterdest))
            masterdest_contents = open(masterdest, "r").read()
            self.failUnlessEqual(len(masterdest_contents), 12345)
            self.failUnlessEqual(masterdest_contents, contents[:12345])
        d.addCallback(_checkUpload)
        return d

    def testMode(self):
        self.slavebase = "UploadFile.testMode.slave"
        self.masterbase = "UploadFile.testMode.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        masterdest = os.path.join(self.masterbase, "dest3.text")
        step = self.makeStep(FileUpload,
                             slavesrc="source.txt",
                             masterdest=masterdest,
                             mode=0755)
        slavesrc = os.path.join(self.slavebase,
                                self.slavebuilderbase,
                                "build",
                                "source.txt")
        contents = "this is the source file\n"
        open(slavesrc, "w").write(contents)
        f = open(masterdest, "w")
        f.write("overwrite me\n")
        f.close()

        d = self.runStep(step)
        def _checkUpload(results):
            step_status = step.step_status
            #l = step_status.getLogs()
            #if l:
            #    logtext = l[0].getText()
            #    print logtext
            self.failUnlessEqual(results, SUCCESS)
            self.failUnless(os.path.exists(masterdest))
            masterdest_contents = open(masterdest, "r").read()
            self.failUnlessEqual(masterdest_contents, contents)
            # and with 0777 to ignore sticky bits
            dest_mode = os.stat(masterdest)[ST_MODE] & 0777
            self.failUnlessEqual(dest_mode, 0755,
                                 "target mode was %o, we wanted %o" %
                                 (dest_mode, 0755))
        d.addCallback(_checkUpload)
        return d

    def testMissingFile(self):
        self.slavebase = "UploadFile.testMissingFile.slave"
        self.masterbase = "UploadFile.testMissingFile.master"
        sb = self.makeSlaveBuilder()
        step = self.makeStep(FileUpload,
                             slavesrc="MISSING.txt",
                             masterdest="dest.txt")
        masterdest = os.path.join(self.masterbase, "dest4.txt")

        d = self.runStep(step)
        def _checkUpload(results):
            step_status = step.step_status
            self.failUnlessEqual(results, FAILURE)
            self.failIf(os.path.exists(masterdest))
            l = step_status.getLogs()
            logtext = l[0].getText().strip()
            self.failUnless(logtext.startswith("Cannot open file"))
            self.failUnless(logtext.endswith("for upload"))
        d.addCallback(_checkUpload)
        return d

    def testLotsOfBlocks(self):
        self.slavebase = "UploadFile.testLotsOfBlocks.slave"
        self.masterbase = "UploadFile.testLotsOfBlocks.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        # the buildmaster normally runs chdir'ed into masterbase, so uploaded
        # files will appear there. Under trial, we're chdir'ed into
        # _trial_temp instead, so use a different masterdest= to keep the
        # uploaded file in a test-local directory
        masterdest = os.path.join(self.masterbase, "dest.text")
        step = self.makeStep(FileUpload,
                             slavesrc="source.txt",
                             masterdest=masterdest,
                             blocksize=15)
        slavesrc = os.path.join(self.slavebase,
                                self.slavebuilderbase,
                                "build",
                                "source.txt")
        contents = "".join(["this is the source file #%d\n" % i
                            for i in range(1000)])
        open(slavesrc, "w").write(contents)
        f = open(masterdest, "w")
        f.write("overwrite me\n")
        f.close()

        d = self.runStep(step)
        def _checkUpload(results):
            step_status = step.step_status
            #l = step_status.getLogs()
            #if l:
            #    logtext = l[0].getText()
            #    print logtext
            self.failUnlessEqual(results, SUCCESS)
            self.failUnless(os.path.exists(masterdest))
            masterdest_contents = open(masterdest, "r").read()
            self.failUnlessEqual(masterdest_contents, contents)
        d.addCallback(_checkUpload)
        return d

    def testWorkdir(self):
        self.slavebase = "Upload.testWorkdir.slave"
        self.masterbase = "Upload.testWorkdir.master"
        sb = self.makeSlaveBuilder()

        self.workdir = "mybuild"        # override default in StepTest
        full_workdir = os.path.join(
            self.slavebase, self.slavebuilderbase, self.workdir)
        os.mkdir(full_workdir)

        masterdest = os.path.join(self.masterbase, "dest.txt")
        
        step = self.makeStep(FileUpload,
                             slavesrc="source.txt",
                             masterdest=masterdest)

        # Testing that the FileUpload's workdir is set when makeStep()
        # calls setDefaultWorkdir() is actually enough; carrying on and
        # making sure the upload actually succeeds is pure gravy.
        self.failUnlessEqual(self.workdir, step.workdir)

        slavesrc = os.path.join(full_workdir, "source.txt")
        open(slavesrc, "w").write("upload me\n")

        def _checkUpload(results):
            self.failUnlessEqual(results, SUCCESS)
            self.failUnless(os.path.isfile(masterdest))

        d = self.runStep(step)
        d.addCallback(_checkUpload)
        return d

    def testWithProperties(self):
        # test that workdir can be a WithProperties object
        self.slavebase = "Upload.testWithProperties.slave"
        self.masterbase = "Upload.testWithProperties.master"
        sb = self.makeSlaveBuilder()

        step = self.makeStep(FileUpload,
                             slavesrc="src.txt",
                             masterdest="dest.txt")
        step.workdir = WithProperties("build.%s", "buildnumber")

        self.failUnlessEqual(step._getWorkdir(), "build.1")

class DownloadFile(StepTester, unittest.TestCase):

    def filterArgs(self, args):
        if "reader" in args:
            args["reader"] = self.wrap(args["reader"])
        return args

    def testSuccess(self):
        self.slavebase = "DownloadFile.testSuccess.slave"
        self.masterbase = "DownloadFile.testSuccess.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        mastersrc = os.path.join(self.masterbase, "source.text")
        slavedest = os.path.join(self.slavebase,
                                 self.slavebuilderbase,
                                 "build",
                                 "dest.txt")
        step = self.makeStep(FileDownload,
                             mastersrc=mastersrc,
                             slavedest="dest.txt")
        contents = "this is the source file\n" * 1000  # 24kb, so two blocks
        open(mastersrc, "w").write(contents)
        f = open(slavedest, "w")
        f.write("overwrite me\n")
        f.close()

        d = self.runStep(step)
        def _checkDownload(results):
            step_status = step.step_status
            self.failUnlessEqual(results, SUCCESS)
            self.failUnless(os.path.exists(slavedest))
            slavedest_contents = open(slavedest, "r").read()
            self.failUnlessEqual(slavedest_contents, contents)
        d.addCallback(_checkDownload)
        return d

    def testMaxsize(self):
        self.slavebase = "DownloadFile.testMaxsize.slave"
        self.masterbase = "DownloadFile.testMaxsize.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        mastersrc = os.path.join(self.masterbase, "source.text")
        slavedest = os.path.join(self.slavebase,
                                 self.slavebuilderbase,
                                 "build",
                                 "dest.txt")
        step = self.makeStep(FileDownload,
                             mastersrc=mastersrc,
                             slavedest="dest.txt",
                             maxsize=12345)
        contents = "this is the source file\n" * 1000  # 24kb, so two blocks
        open(mastersrc, "w").write(contents)
        f = open(slavedest, "w")
        f.write("overwrite me\n")
        f.close()

        d = self.runStep(step)
        def _checkDownload(results):
            step_status = step.step_status
            # the file should be truncated, and the step a FAILURE
            self.failUnlessEqual(results, FAILURE)
            self.failUnless(os.path.exists(slavedest))
            slavedest_contents = open(slavedest, "r").read()
            self.failUnlessEqual(len(slavedest_contents), 12345)
            self.failUnlessEqual(slavedest_contents, contents[:12345])
        d.addCallback(_checkDownload)
        return d

    def testMode(self):
        self.slavebase = "DownloadFile.testMode.slave"
        self.masterbase = "DownloadFile.testMode.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        mastersrc = os.path.join(self.masterbase, "source.text")
        slavedest = os.path.join(self.slavebase,
                                 self.slavebuilderbase,
                                 "build",
                                 "dest.txt")
        step = self.makeStep(FileDownload,
                             mastersrc=mastersrc,
                             slavedest="dest.txt",
                             mode=0755)
        contents = "this is the source file\n"
        open(mastersrc, "w").write(contents)
        f = open(slavedest, "w")
        f.write("overwrite me\n")
        f.close()

        d = self.runStep(step)
        def _checkDownload(results):
            step_status = step.step_status
            self.failUnlessEqual(results, SUCCESS)
            self.failUnless(os.path.exists(slavedest))
            slavedest_contents = open(slavedest, "r").read()
            self.failUnlessEqual(slavedest_contents, contents)
            # and with 0777 to ignore sticky bits
            dest_mode = os.stat(slavedest)[ST_MODE] & 0777
            self.failUnlessEqual(dest_mode, 0755,
                                 "target mode was %o, we wanted %o" %
                                 (dest_mode, 0755))
        d.addCallback(_checkDownload)
        return d

    def testMissingFile(self):
        self.slavebase = "DownloadFile.testMissingFile.slave"
        self.masterbase = "DownloadFile.testMissingFile.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        mastersrc = os.path.join(self.masterbase, "MISSING.text")
        slavedest = os.path.join(self.slavebase,
                                 self.slavebuilderbase,
                                 "build",
                                 "dest.txt")
        step = self.makeStep(FileDownload,
                             mastersrc=mastersrc,
                             slavedest="dest.txt")

        d = self.runStep(step)
        def _checkDownload(results):
            step_status = step.step_status
            self.failUnlessEqual(results, FAILURE)
            self.failIf(os.path.exists(slavedest))
            l = step_status.getLogs()
            logtext = l[0].getText().strip()
            self.failUnless(logtext.endswith(" not available at master"))
        d.addCallbacks(_checkDownload)

        return d

    def testLotsOfBlocks(self):
        self.slavebase = "DownloadFile.testLotsOfBlocks.slave"
        self.masterbase = "DownloadFile.testLotsOfBlocks.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        mastersrc = os.path.join(self.masterbase, "source.text")
        slavedest = os.path.join(self.slavebase,
                                 self.slavebuilderbase,
                                 "build",
                                 "dest.txt")
        step = self.makeStep(FileDownload,
                             mastersrc=mastersrc,
                             slavedest="dest.txt",
                             blocksize=15)
        contents = "".join(["this is the source file #%d\n" % i
                            for i in range(1000)])
        open(mastersrc, "w").write(contents)
        f = open(slavedest, "w")
        f.write("overwrite me\n")
        f.close()

        d = self.runStep(step)
        def _checkDownload(results):
            step_status = step.step_status
            self.failUnlessEqual(results, SUCCESS)
            self.failUnless(os.path.exists(slavedest))
            slavedest_contents = open(slavedest, "r").read()
            self.failUnlessEqual(slavedest_contents, contents)
        d.addCallback(_checkDownload)
        return d

    def testWorkdir(self):
        self.slavebase = "Download.testWorkdir.slave"
        self.masterbase = "Download.testWorkdir.master"
        sb = self.makeSlaveBuilder()

        # As in Upload.testWorkdir(), it's enough to test that makeStep()'s
        # call of setDefaultWorkdir() actually sets step.workdir.
        self.workdir = "mybuild"
        step = self.makeStep(FileDownload,
                             mastersrc="foo",
                             slavedest="foo")
        self.failUnlessEqual(step.workdir, self.workdir)

    def testWithProperties(self):
        # test that workdir can be a WithProperties object
        self.slavebase = "Download.testWithProperties.slave"
        self.masterbase = "Download.testWithProperties.master"
        sb = self.makeSlaveBuilder()

        step = self.makeStep(FileDownload,
                             mastersrc="src.txt",
                             slavedest="dest.txt")
        step.workdir = WithProperties("build.%s", "buildnumber")

        self.failUnlessEqual(step._getWorkdir(), "build.1")

        

class UploadDirectory(StepTester, unittest.TestCase):

    def filterArgs(self, args):
        if "writer" in args:
            args["writer"] = self.wrap(args["writer"])
        return args

    def testSuccess(self):
        self.slavebase = "UploadDirectory.testSuccess.slave"
        self.masterbase = "UploadDirectory.testSuccess.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        # the buildmaster normally runs chdir'ed into masterbase, so uploaded
        # files will appear there. Under trial, we're chdir'ed into
        # _trial_temp instead, so use a different masterdest= to keep the
        # uploaded file in a test-local directory
        masterdest = os.path.join(self.masterbase, "dest_dir")
        step = self.makeStep(DirectoryUpload,
                             slavesrc="source_dir",
                             masterdest=masterdest)
        slavesrc = os.path.join(self.slavebase,
                                self.slavebuilderbase,
                                "build",
                                "source_dir")
        dircount = 5
        content = []
        content.append("this is one source file\n" * 1000)
        content.append("this is a second source file\n" * 978)
        content.append("this is a third source file\n" * 473)
        os.mkdir(slavesrc)
        for i in range(dircount):
            os.mkdir(os.path.join(slavesrc, "d%i" % (i)))
            for j in range(dircount):
                curdir = os.path.join("d%i" % (i), "e%i" % (j))
                os.mkdir(os.path.join(slavesrc, curdir))
                for h in range(3):
                    open(os.path.join(slavesrc, curdir, "file%i" % (h)), "w").write(content[h])
            for j in range(dircount):
                #empty dirs, must be uploaded too
                curdir = os.path.join("d%i" % (i), "f%i" % (j))
                os.mkdir(os.path.join(slavesrc, curdir))

        d = self.runStep(step)
        def _checkUpload(results):
            step_status = step.step_status
            #l = step_status.getLogs()
            #if l:
            #    logtext = l[0].getText()
            #    print logtext
            self.failUnlessEqual(results, SUCCESS)
            self.failUnless(os.path.exists(masterdest))
            for i in range(dircount):
                for j in range(dircount):
                    curdir = os.path.join("d%i" % (i), "e%i" % (j))
                    self.failUnless(os.path.exists(os.path.join(masterdest, curdir)))
                    for h in range(3):
                        masterdest_contents = open(os.path.join(masterdest, curdir, "file%i" % (h)), "r").read()
                        self.failUnlessEqual(masterdest_contents, content[h])
                for j in range(dircount):
                    curdir = os.path.join("d%i" % (i), "f%i" % (j))
                    self.failUnless(os.path.exists(os.path.join(masterdest, curdir)))
        d.addCallback(_checkUpload)
        return d

    def testOneEmptyDir(self):
        self.slavebase = "UploadDirectory.testOneEmptyDir.slave"
        self.masterbase = "UploadDirectory.testOneEmptyDir.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        # the buildmaster normally runs chdir'ed into masterbase, so uploaded
        # files will appear there. Under trial, we're chdir'ed into
        # _trial_temp instead, so use a different masterdest= to keep the
        # uploaded file in a test-local directory
        masterdest = os.path.join(self.masterbase, "dest_dir")
        step = self.makeStep(DirectoryUpload,
                             slavesrc="source_dir",
                             masterdest=masterdest)
        slavesrc = os.path.join(self.slavebase,
                                self.slavebuilderbase,
                                "build",
                                "source_dir")
        os.mkdir(slavesrc)

        d = self.runStep(step)
        def _checkUpload(results):
            step_status = step.step_status
            #l = step_status.getLogs()
            #if l:
            #    logtext = l[0].getText()
            #    print logtext
            self.failUnlessEqual(results, SUCCESS)
            self.failUnless(os.path.exists(masterdest))
        d.addCallback(_checkUpload)
        return d

    def testManyEmptyDirs(self):
        self.slavebase = "UploadDirectory.testManyEmptyDirs.slave"
        self.masterbase = "UploadDirectory.testManyEmptyDirs.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        # the buildmaster normally runs chdir'ed into masterbase, so uploaded
        # files will appear there. Under trial, we're chdir'ed into
        # _trial_temp instead, so use a different masterdest= to keep the
        # uploaded file in a test-local directory
        masterdest = os.path.join(self.masterbase, "dest_dir")
        step = self.makeStep(DirectoryUpload,
                             slavesrc="source_dir",
                             masterdest=masterdest)
        slavesrc = os.path.join(self.slavebase,
                                self.slavebuilderbase,
                                "build",
                                "source_dir")
        dircount = 25
        os.mkdir(slavesrc)
        for i in range(dircount):
            os.mkdir(os.path.join(slavesrc, "d%i" % (i)))
            for j in range(dircount):
                curdir = os.path.join("d%i" % (i), "e%i" % (j))
                os.mkdir(os.path.join(slavesrc, curdir))
                curdir = os.path.join("d%i" % (i), "f%i" % (j))
                os.mkdir(os.path.join(slavesrc, curdir))

        d = self.runStep(step)
        def _checkUpload(results):
            step_status = step.step_status
            #l = step_status.getLogs()
            #if l:
            #    logtext = l[0].getText()
            #    print logtext
            self.failUnlessEqual(results, SUCCESS)
            self.failUnless(os.path.exists(masterdest))
            for i in range(dircount):
                for j in range(dircount):
                    curdir = os.path.join("d%i" % (i), "e%i" % (j))
                    self.failUnless(os.path.exists(os.path.join(masterdest, curdir)))
                    curdir = os.path.join("d%i" % (i), "f%i" % (j))
                    self.failUnless(os.path.exists(os.path.join(masterdest, curdir)))
        d.addCallback(_checkUpload)
        return d

    def testOneDirOneFile(self):
        self.slavebase = "UploadDirectory.testOneDirOneFile.slave"
        self.masterbase = "UploadDirectory.testOneDirOneFile.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        # the buildmaster normally runs chdir'ed into masterbase, so uploaded
        # files will appear there. Under trial, we're chdir'ed into
        # _trial_temp instead, so use a different masterdest= to keep the
        # uploaded file in a test-local directory
        masterdest = os.path.join(self.masterbase, "dest_dir")
        step = self.makeStep(DirectoryUpload,
                             slavesrc="source_dir",
                             masterdest=masterdest)
        slavesrc = os.path.join(self.slavebase,
                                self.slavebuilderbase,
                                "build",
                                "source_dir")
        os.mkdir(slavesrc)
        content = "this is one source file\n" * 1000
        open(os.path.join(slavesrc, "srcfile"), "w").write(content)

        d = self.runStep(step)
        def _checkUpload(results):
            step_status = step.step_status
            #l = step_status.getLogs()
            #if l:
            #    logtext = l[0].getText()
            #    print logtext
            self.failUnlessEqual(results, SUCCESS)
            self.failUnless(os.path.exists(masterdest))
            masterdest_contents = open(os.path.join(masterdest, "srcfile"), "r").read()
            self.failUnlessEqual(masterdest_contents, content)
        d.addCallback(_checkUpload)
        return d

    def testOneDirManyFiles(self):
        self.slavebase = "UploadDirectory.testOneDirManyFile.slave"
        self.masterbase = "UploadDirectory.testOneDirManyFile.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        # the buildmaster normally runs chdir'ed into masterbase, so uploaded
        # files will appear there. Under trial, we're chdir'ed into
        # _trial_temp instead, so use a different masterdest= to keep the
        # uploaded file in a test-local directory
        masterdest = os.path.join(self.masterbase, "dest_dir")
        step = self.makeStep(DirectoryUpload,
                             slavesrc="source_dir",
                             masterdest=masterdest)
        slavesrc = os.path.join(self.slavebase,
                                self.slavebuilderbase,
                                "build",
                                "source_dir")
        filecount = 20
        os.mkdir(slavesrc)
        content = []
        content.append("this is one source file\n" * 1000)
        content.append("this is a second source file\n" * 978)
        content.append("this is a third source file\n" * 473)
        for i in range(3):
            for j in range(filecount):
                open(os.path.join(slavesrc, "srcfile%i_%i" % (i, j)), "w").write(content[i])

        d = self.runStep(step)
        def _checkUpload(results):
            step_status = step.step_status
            #l = step_status.getLogs()
            #if l:
            #    logtext = l[0].getText()
            #    print logtext
            self.failUnlessEqual(results, SUCCESS)
            self.failUnless(os.path.exists(masterdest))
            for i in range(3):
                for j in range(filecount):
                    masterdest_contents = open(os.path.join(masterdest, "srcfile%i_%i" % (i, j)), "r").read()
                    self.failUnlessEqual(masterdest_contents, content[i])
        d.addCallback(_checkUpload)
        return d

    def testManyDirsManyFiles(self):
        self.slavebase = "UploadDirectory.testManyDirsManyFile.slave"
        self.masterbase = "UploadDirectory.testManyDirsManyFile.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        # the buildmaster normally runs chdir'ed into masterbase, so uploaded
        # files will appear there. Under trial, we're chdir'ed into
        # _trial_temp instead, so use a different masterdest= to keep the
        # uploaded file in a test-local directory
        masterdest = os.path.join(self.masterbase, "dest_dir")
        step = self.makeStep(DirectoryUpload,
                             slavesrc="source_dir",
                             masterdest=masterdest)
        slavesrc = os.path.join(self.slavebase,
                                self.slavebuilderbase,
                                "build",
                                "source_dir")
        dircount = 10
        os.mkdir(slavesrc)
        for i in range(dircount):
            os.mkdir(os.path.join(slavesrc, "d%i" % (i)))
            for j in range(dircount):
                curdir = os.path.join("d%i" % (i), "e%i" % (j))
                os.mkdir(os.path.join(slavesrc, curdir))
                curdir = os.path.join("d%i" % (i), "f%i" % (j))
                os.mkdir(os.path.join(slavesrc, curdir))

        filecount = 5
        content = []
        content.append("this is one source file\n" * 1000)
        content.append("this is a second source file\n" * 978)
        content.append("this is a third source file\n" * 473)
        for i in range(dircount):
            for j in range(dircount):
                for k in range(3):
                    for l in range(filecount):
                        open(os.path.join(slavesrc, "d%i" % (i), "e%i" % (j), "srcfile%i_%i" % (k, l)), "w").write(content[k])

        d = self.runStep(step)
        def _checkUpload(results):
            step_status = step.step_status
            #l = step_status.getLogs()
            #if l:
            #    logtext = l[0].getText()
            #    print logtext
            self.failUnlessEqual(results, SUCCESS)
            self.failUnless(os.path.exists(masterdest))
            for i in range(dircount):
                for j in range(dircount):
                    for k in range(3):
                        for l in range(filecount):
                            masterdest_contents = open(os.path.join(masterdest, "d%i" % (i), "e%i" % (j), "srcfile%i_%i" % (k, l)), "r").read()
                            self.failUnlessEqual(masterdest_contents, content[k])
        d.addCallback(_checkUpload)
        return d


    def testBigFile(self):
        self.slavebase = "UploadDirectory.testBigFile.slave"
        self.masterbase = "UploadDirectory.testBigFile.master"
        sb = self.makeSlaveBuilder()
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase,
                              "build"))
        # the buildmaster normally runs chdir'ed into masterbase, so uploaded
        # files will appear there. Under trial, we're chdir'ed into
        # _trial_temp instead, so use a different masterdest= to keep the
        # uploaded file in a test-local directory
        masterdest = os.path.join(self.masterbase, "dest_dir")
        step = self.makeStep(DirectoryUpload,
                             slavesrc="source_dir",
                             masterdest=masterdest)
        slavesrc = os.path.join(self.slavebase,
                                self.slavebuilderbase,
                                "build",
                                "source_dir")
        content = 'x' * 1024*1024*8
        os.mkdir(slavesrc)
        open(os.path.join(slavesrc, "file"), "w").write(content)

        d = self.runStep(step)
        def _checkUpload(results):
            step_status = step.step_status
            self.failUnlessEqual(results, SUCCESS)
            self.failUnless(os.path.exists(masterdest))
            masterdest_contents = open(os.path.join(masterdest, "file"), "r").read()
            self.failUnlessEqual(masterdest_contents, content)
        d.addCallback(_checkUpload)
        return d


# TODO:
#  test relative paths, ~/paths
#   need to implement expanduser() for slave-side
#  test error message when master-side file is in a missing directory
#  remove workdir= default?

