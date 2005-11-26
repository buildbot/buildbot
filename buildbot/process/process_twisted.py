#! /usr/bin/python

# Build classes specific to the Twisted codebase

from buildbot.process.base import Build
from buildbot.process.factory import BuildFactory, s
from buildbot.process import step
from buildbot.process.step_twisted import HLint, ProcessDocs, BuildDebs, \
     Trial, RemovePYCs

class TwistedBuild(Build):
    workdir = "Twisted" # twisted's bin/trial expects to live in here
    def isFileImportant(self, filename):
        if filename.find("doc/fun/") == 0:
            return 0
        if filename.find("sandbox/") == 0:
            return 0
        return 1

class TwistedTrial(Trial):
    tests = "twisted"
    # the Trial in Twisted >=2.1.0 has --recurse on by default, and -to
    # turned into --reporter=bwverbose .
    recurse = False
    trialMode = ["--reporter=bwverbose"]
    testpath = None
    trial = "./bin/trial"

class TwistedBaseFactory(BuildFactory):
    buildClass = TwistedBuild
    # bin/trial expects its parent directory to be named "Twisted": it uses
    # this to add the local tree to PYTHONPATH during tests
    workdir = "Twisted"

    def __init__(self, svnurl, steps):
        self.steps = []
        self.steps.append(s(step.SVN, svnurl=svnurl, mode=self.mode))
        self.steps.extend(steps)

class QuickTwistedBuildFactory(TwistedBaseFactory):
    treeStableTimer = 30
    useProgress = 0

    def __init__(self, source, python="python"):
        if type(python) is str:
            python = [python]
        self.steps = []
        self.steps.append(source)
        self.steps.append(s(HLint, python=python[0]))
        self.steps.append(s(RemovePYCs))
        for p in python:
            cmd = [p, "setup.py", "all", "build_ext", "-i"]
            self.steps.append(s(step.Compile, command=cmd,
                                flunkOnFailure=True))
            self.steps.append(s(TwistedTrial,
                                python=p, # can be a list
                                testChanges=True))

class FullTwistedBuildFactory(TwistedBaseFactory):
    treeStableTimer = 5*60

    def __init__(self, source, python="python",
                 processDocs=False, runTestsRandomly=False,
                 compileOpts=[], compileOpts2=[]):
        self.steps = []
        self.steps.append(source)
        if processDocs:
            self.steps.append(s(ProcessDocs))

        if type(python) == str:
            python = [python]
        assert type(compileOpts) is list
        assert type(compileOpts2) is list
        cmd = (python + compileOpts + ["setup.py", "all", "build_ext"]
               + compileOpts2 + ["-i"])

        self.steps.append(s(step.Compile, command=cmd, flunkOnFailure=True))
        self.steps.append(s(RemovePYCs))
        self.steps.append(s(TwistedTrial, python=python,
                            randomly=runTestsRandomly))

class TwistedDebsBuildFactory(TwistedBaseFactory):
    treeStableTimer = 10*60

    def __init__(self, source, python="python"):
        self.steps = []
        self.steps.append(source)
        self.steps.append(s(ProcessDocs, haltOnFailure=True))
        self.steps.append(s(BuildDebs, warnOnWarnings=True))

class TwistedReactorsBuildFactory(TwistedBaseFactory):
    treeStableTimer = 5*60

    def __init__(self, source,
                 python="python", compileOpts=[], compileOpts2=[],
                 reactors=None):
        self.steps = []
        self.steps.append(source)

        if type(python) == str:
            python = [python]
        assert type(compileOpts) is list
        assert type(compileOpts2) is list
        cmd = (python + compileOpts + ["setup.py", "all", "build_ext"]
               + compileOpts2 + ["-i"])

        self.steps.append(s(step.Compile, command=cmd, warnOnFailure=True))

        if reactors == None:
            reactors = [
                'gtk2',
                'gtk',
                #'kqueue',
                'poll',
                'c',
                'qt',
                #'win32',
                ]
        for reactor in reactors:
            flunkOnFailure = 1
            warnOnFailure = 0
            #if reactor in ['c', 'qt', 'win32']:
            #    # these are buggy, so tolerate failures for now
            #    flunkOnFailure = 0
            #    warnOnFailure = 1
            self.steps.append(s(RemovePYCs)) # TODO: why?
            self.steps.append(s(TwistedTrial, name=reactor,
                                python=python, reactor=reactor,
                                flunkOnFailure=flunkOnFailure,
                                warnOnFailure=warnOnFailure))
