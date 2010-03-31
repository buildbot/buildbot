# -*- test-case-name: buildbot.broken_test.test_sourcestamp -*-

from twisted.trial import unittest

from buildbot.sourcestamp import SourceStamp
from buildbot.changes.changes import Change

class SourceStampTest(unittest.TestCase):
    def testAsDictEmpty(self):
        EXPECTED = {
            'revision': None,
            'branch':  None,
            'hasPatch': False,
            'changes': [],
            'project': '',
            'repository': '',
          }
        self.assertEqual(EXPECTED, SourceStamp().asDict())

    def testAsDictBranch(self):
        EXPECTED = {
            'revision': 'Rev',
            'branch':  'Br',
            'hasPatch': False,
            'changes': [],
            'project': '',
            'repository': '',
          }
        self.assertEqual(EXPECTED,
                         SourceStamp(branch='Br', revision='Rev').asDict())

    def testAsDictChanges(self):
        changes = [
            Change('nobody', [], 'Comment', branch='br2', revision='rev2'),
            Change('nob', ['file2', 'file3'], 'Com', branch='br3',
                   revision='rev3'),
        ]
        s = SourceStamp(branch='Br', revision='Rev', patch=(1,'Pat'),
                        changes=changes)
        r = s.asDict()
        del r['changes'][0]['when']
        del r['changes'][1]['when']
        EXPECTED = {
            'revision': 'rev3',
            'branch': 'br3',
            'hasPatch': True,
            'project': '',
            'repository':'',
            'changes': [
                {
                    'branch': 'br2',
                    'category': None,
                    'comments': 'Comment',
                    'files': [],
                    'number': None,
                    'properties': [],
                    'revision': 'rev2',
                    'revlink': '',
                    'project' : '',
                    'repository' : '',
                    'who': 'nobody'
                },
                {
                    'branch': 'br3',
                    'category': None,
                    'comments': 'Com',
                    'files': ['file2', 'file3'],
                    'number': None,
                    'properties': [],
                    'revision': 'rev3',
                    'revlink': '',
                    'who': 'nob',
                    'project' : '',
                    'repository' : '',
                }
            ],
          }
        self.assertEqual(EXPECTED, r)

# vim: set ts=4 sts=4 sw=4 et:
