# -*- test-case-name: buildbot.broken_test.test_sourcestamp -*-

from twisted.trial import unittest

from buildbot.sourcestamp import SourceStamp
from buildbot.changes.changes import Change

class SourceStampTest(unittest.TestCase):
    def testAsDictEmpty(self):
        s = SourceStamp()
        r = s.asDict()
        self.assertEqual(r, {
            'revision': None,
            'patch': None,
            'branch':  None,
            'changes': [],
          })

    def testAsDictBranch(self):
        s = SourceStamp(branch='Br', revision='Rev')
        r = s.asDict()
        self.assertEqual(r, {
            'revision': 'Rev',
            'patch': None,
            'branch':  'Br',
            'changes': [],
          })

    def testAsDictChanges(self):
        changes = [
            Change('nobody', [], 'Comment', branch='br2', revision='rev2'),
            Change('nob', ['file2', 'file3'], 'Com', branch='br3',
                   revision='rev3'),
        ]
        s = SourceStamp(branch='Br', revision='Rev', patch=(1,'Pat'),
                        changes=changes)
        r = s.asDict()
        r['changes'][0]['when'] = 23
        r['changes'][1]['when'] = 42
        self.assertEqual(r, {
            'revision': 'rev3',
            'patch': (1,'Pat'),
            'branch': 'br3',
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
                    'when': 23,
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
                    'when': 42,
                    'who': 'nob'
                }
            ],
          })

# vim: set ts=4 sts=4 sw=4 et:
