from twisted.trial import unittest
from buildbot.steps.source.custom import hg
from twisted.internet import defer
from buildbot.test.fake import fakemaster, fakedb, fakebuild
from buildbot.status import master
from mock import Mock
from buildbot.status.results import SUCCESS
from buildbot.sourcestamp import SourceStamp
from buildbot.changes.changes import Change

class TestCustomSource(unittest.TestCase):

    @defer.inlineCallbacks
    def test_MercuriaIncomingChanges(self):
        self.step = hg.Hg(repourl="repo", codebase='c', mode='full', method='fresh', branchType='inrepo',
                          clobberOnBranchChange=False)

        m = fakemaster.FakeMaster()
        m.status = master.Status(m)
        m.db = fakedb.FakeDBConnector(self)
        m.db.sourcestamps.findLastBuildRev = lambda n, i, c, r, b: 'bwadk'
        m.db.sourcestamps.updateSourceStamps = lambda ss: True
        self.step.build = fakebuild.FakeBuild()
        self.step.build.build_status.getAllGotRevisions = lambda: {'c': 'abzw'}
        build_ss = [SourceStamp(branch='b1', codebase='c', repository='repo')]
        self.step.build.build_status.getSourceStamps = lambda: build_ss
        self.step.update_branch = 'b1'
        self.step.build.getProperty = lambda x, y: True
        request = Mock()
        request.id = 3
        request.sources = {'c': SourceStamp(branch='b1', codebase='c', repository='repo')}
        self.step.build.requests = [request]
        self.step.build.builder.botmaster = m.botmaster
        def logRev(num):
            return ['log', '-r', num, '--template={date|hgdate}\\n{author}\\n{desc|strip}']

        expected_commands = [{'command': ['pull', 'repo', '--rev', 'bwadk'],
                             'stdout': 'pulling from repo\nno changes found\n'},
                             {'command': ['log', '-b', 'b1',
                                          '-r', '::abzw-::bwadk', '--template={rev}:{node}\\n'],
                             'stdout':
                                 '189944:5553a6194a6393dfbec82f96654d52a76ddf844d\n' +
                                 '190056:b2e48cbab3f0753f99db833acff6ca18096854bd\n' +
                                 '190057:117b9a27b5bf65d7e7b5edb48f7fd59dc4170486\n'},
                             {'command': logRev('117b9a27b5bf65d7e7b5edb48f7fd59dc4170486'),
                              'stdout': defer.succeed('1421667230 -3600\ndev1 <dev1@mail.com>\nlist of changes1')},
                             {'command': logRev('b2e48cbab3f0753f99db833acff6ca18096854bd'),
                              'stdout': defer.succeed('1421667112 -3600\ndev2 <dev2@mail.com>\nlist of changes2')},
                             {'command': logRev('5553a6194a6393dfbec82f96654d52a76ddf844d'),
                              'stdout': defer.succeed('1421583649 -3600\ndev3 <dev3@mail.com>\nlist of changes3')}
                             ]

        #mock the output of running hg command
        def _dovccmd(command, collectStdout=False, initialStdin=None, decodeRC={0:SUCCESS}):
            for cmd in expected_commands:
                if command == cmd['command']:
                    return cmd['stdout']
            return ''
            
        self.step._dovccmd = _dovccmd

        yield self.step.parseChanges(None)

        def checkChanges(ss, changes):
            self.assertEqual(ss.revision, 'abzw')
            self.assertEqual(ss.changes, changes)

        checkChanges(request.sources['c'], ())
        checkChanges(build_ss[0],
                         [Change(revision=u'117b9a27b5bf65d7e7b5edb48f7fd59dc4170486', files=None,
                                 who=u'dev1 <dev1@mail.com>', branch=u'b1', comments=u'list of changes1',
                                 when=1421667230.0, repository='repo', codebase='c'),
                          Change(revision=u'b2e48cbab3f0753f99db833acff6ca18096854bd', files=None,
                                 who=u'dev2 <dev2@mail.com>', branch=u'b1', comments=u'list of changes2',
                                 when=1421667112.0, category=None, project='',
                                 repository='repo', codebase='c'),
                          Change(revision=u'5553a6194a6393dfbec82f96654d52a76ddf844d', files=None,
                                 who=u'dev3 <dev3@mail.com>', branch=u'b1', comments=u'list of changes3',
                                 when=1421583649.0, category=None, project='', repository='repo', codebase='c')

                         ])
