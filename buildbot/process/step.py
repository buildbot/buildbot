# -*- test-case-name: buildbot.test.test_steps.ReorgCompatibility -*-

# legacy compatibility

from buildbot.steps.shell import ShellCommand, WithProperties, TreeSize, Configure, Compile, Test
from buildbot.steps.source import CVS, SVN, Darcs, Git, Arch, Bazaar, Mercurial, P4, P4Sync
from buildbot.steps.dummy import Dummy, FailingDummy, RemoteDummy


