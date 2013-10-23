from fiximports import FixImports
from textwrap import dedent
from twisted.trial import unittest

class TestFixImports(unittest.TestCase):
    def setUp(self):
        self.fiximports = FixImports()
        self.fiximports.printErrorMsg = lambda *_:None

    def oneTest(self, src, expected):
        src = dedent(src)
        expected = dedent(expected)

        res, content = self.fiximports.sortImportGroups("testedfn", src)
        self.assertEqual(content, expected)

    def testBasic(self):
        self.oneTest("""
            from twisted.internet import defer
            from twisted.trial import unittest
            from fiximports import FixImports
            ""","""
            from fiximports import FixImports
            from twisted.internet import defer
            from twisted.trial import unittest
            """)

    def testGroups(self):
        self.oneTest("""
            from twisted.internet import defer
            from twisted.trial import unittest

            from fiximports import FixImports
            ""","""
            from twisted.internet import defer
            from twisted.trial import unittest

            from fiximports import FixImports
            """)

    def testMixImports(self):
        self.oneTest("""
            from twisted.internet import defer
            from twisted.trial import unittest
            import fiximports
            ""","""
            import fiximports

            from twisted.internet import defer
            from twisted.trial import unittest
            """)

    def testDontSort(self):
        self.oneTest("""
            from twisted.internet import defer,\\
                 reactor
            from twisted.trial import unittest
            import fiximports
            ""","""
            from twisted.internet import defer,\\
                 reactor
            from twisted.trial import unittest
            import fiximports
            """)

    def testFutureFirst(self):
        self.oneTest("""
            from __future__ import with_statement
            from twisted.internet import defer
            from twisted.trial import unittest
            import fiximports
            ""","""
            from __future__ import with_statement

            import fiximports

            from twisted.internet import defer
            from twisted.trial import unittest
            """)