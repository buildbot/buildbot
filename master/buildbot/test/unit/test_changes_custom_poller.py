from twisted.trial import unittest
from buildbot.changes.custom.hgpoller import HgPoller
from twisted.internet import defer, utils
from mock import Mock
from buildbot.util import datetime2epoch
from buildbot.changes.changes import Change

class TestCustomSource(unittest.TestCase):

    def getProcessOutput(self, executable, args=(), env={}, path=None, reactor=None,
                 errortoo=0):
        for cmd in self.expected_commands:
            if args == cmd['command']:
                return cmd['stdout']
        return ''

    def checkChangesList(self, changes_added, expected_changes):
        self.assertEqual(len(changes_added), len(expected_changes))
        for i in range(len(changes_added)):
            self.assertEqual(changes_added[i].asDict(), expected_changes[i].asDict())

    @defer.inlineCallbacks
    def test_mercurialPollsAnyBranch(self):
        poller = HgPoller(repourl='http://hg.repo.org/src',
                                   branches={'include': [r'.*'],
                                             'exclude': [r'default', '5.0/*']},
                                   workdir='hgpoller-mercurial', pollInterval=60)

        poller._absWorkdir = lambda: "dir/"
        poller.lastRev = {"1.0/dev": "1:835be7494fb4", "stable": "3:05bbe2605e10"}
        poller.master = Mock()
        changes_added = []

        def addChange(files=None, comments=None, author=None, revision=None,
                      when_timestamp=None, branch=None, repository='', codebase=None,
                      category='', project='', src=None):
            changes_added.append(Change(revision=revision, files=files,
                                 who=author, branch=branch, comments=comments,
                                 when=datetime2epoch(when_timestamp), repository=repository, codebase=codebase))
            return defer.succeed(None)

        poller.master.addChange = addChange

        self.expected_commands = [{'command': ['log', '-r',
                                               'last(:tip,10000) and head() and not closed() or bookmark()',
                                               '--template', '{branch} {bookmarks} {rev}:{node|short}\n'],
                             'stdout': 'default defaultbookmark 44213:5cf71f97924e\n' +
                                       '5.0/dev  194367:960963s2fde7\n' +
                                       '1.0/dev  194362:960963s2fda7\n' +
                                       'trunk  trunkbookmark 194362:70fc4de2ff38\n'}]

        self.patch(utils, "getProcessOutput", self.getProcessOutput)

        yield poller._processBranches(None)

        self.assertEqual(poller.currentRev, {'1.0/dev': '194362:960963s2fda7', 'trunkbookmark': '194362:70fc4de2ff38'})

        self.expected_commands.append({'command': ['heads', '1.0/dev', '--template={node}\n'],
                                       'stdout': defer.succeed('960963s2fda7d029eb33ef2f1e4aac4e963a4164')})

        self.expected_commands.append({'command': ['heads', 'trunkbookmark', '--template={node}\n'],
                                       'stdout': defer.succeed('70fc4de2ff3828a587d80f7528c1b5314c51550e7')})

        self.expected_commands.append({'command': ['log', '-b', 'trunkbookmark', '-r',
                                                   '70fc4de2ff3828a587d80f7528c1b5314c51550e7:' +
                                                   '70fc4de2ff3828a587d80f7528c1b5314c51550e7',
                                                   '--template={rev}:{node}\\n'],
                                       'stdout': defer.succeed('194446:70fc4de2ff3828a587d80f7528c1b5314c51550e7')})

        self.expected_commands.append({'command': ['log', '-r', '70fc4de2ff3828a587d80f7528c1b5314c51550e7',
                                                   '--template={date|hgdate}\\n{author}\\n{desc|strip}'],
                                       'stdout':
                                           defer.succeed('1422983233 -3600\ndev4 <dev4@mail.com>\nlist of changes4')})

        self.expected_commands.append({'command':  ['log', '-b', '1.0/dev', '-r',
                                                    '2:960963s2fda7d029eb33ef2f1e4aac4e963a4164',
                                                    '--template={rev}:{node}\\n'],
                                       'stdout': defer.succeed('3:5553a6194a6393dfbec82f96654d52a76ddf844d\n' +
                                                               '4:b2e48cbab3f0753f99db833acff6ca18096854bd\n' +
                                                               '5:117b9a27b5bf65d7e7b5edb48f7fd59dc4170486\n')})

        self.expected_commands.append({'command': ['log', '-r', '5553a6194a6393dfbec82f96654d52a76ddf844d',
                                                   '--template={date|hgdate}\\n{author}\\n{desc|strip}'],
                                       'stdout':
                                           defer.succeed('1421583649 -3600\ndev3 <dev3@mail.com>\nlist of changes3')})

        self.expected_commands.append({'command': ['log', '-r', 'b2e48cbab3f0753f99db833acff6ca18096854bd',
                                                   '--template={date|hgdate}\\n{author}\\n{desc|strip}'],
                                       'stdout':
                                           defer.succeed('1421667112 -3600\ndev2 <dev2@mail.com>\nlist of changes2')})

        self.expected_commands.append({'command': ['log', '-r', '117b9a27b5bf65d7e7b5edb48f7fd59dc4170486',
                                                   '--template={date|hgdate}\\n{author}\\n{desc|strip}'],
                                       'stdout':
                                           defer.succeed('1421667230 -3600\ndev1 <dev1@mail.com>\nlist of changes1')})

        yield poller._processChangesAllBranches(None)

        self.assertEqual(poller.lastRev, {'1.0/dev': '194362:960963s2fda7', 'trunkbookmark': '194362:70fc4de2ff38'})

        expected_changes = [Change(revision=u'5553a6194a6393dfbec82f96654d52a76ddf844d', files=None,
                                 who=u'dev3 <dev3@mail.com>', branch=u'1.0/dev', comments=u'list of changes3',
                                 when=1421583649, category=None, project='',
                                 repository='http://hg.repo.org/src', codebase=None),
                            Change(revision=u'b2e48cbab3f0753f99db833acff6ca18096854bd', files=None,
                                 who=u'dev2 <dev2@mail.com>', branch=u'1.0/dev', comments=u'list of changes2',
                                 when=1421667112, category=None, project='',
                                 repository='http://hg.repo.org/src', codebase=None),
                            Change(revision=u'117b9a27b5bf65d7e7b5edb48f7fd59dc4170486', files=None,
                                 who=u'dev1 <dev1@mail.com>', branch=u'1.0/dev', comments=u'list of changes1',
                                 when=1421667230, repository='http://hg.repo.org/src', codebase=None),
                            Change(revision=u'70fc4de2ff3828a587d80f7528c1b5314c51550e7', files=None,
                                 who=u'dev4 <dev4@mail.com>', branch=u'trunkbookmark',
                                 comments=u'list of changes4', when=1422983233,
                                 category=None, project='', repository='http://hg.repo.org/src',
                                 codebase=None)]

        self.checkChangesList(changes_added, expected_changes)
