import os

from twisted.trial import unittest
from twisted.python import runtime

from buildslave.test.util.command import CommandTestMixin
from buildslave.commands import fs

class TestRemoveDirectory(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.make_command(fs.RemoveDirectory, dict(
            dir='workdir',
        ), True)
        d = self.run_command()

        def check(_):
            self.assertFalse(os.path.exists(os.path.abspath(os.path.join(self.basedir,'workdir'))))
            self.assertIn({'rc': 0},
                    self.get_updates(),
                    self.builder.show())
        d.addCallback(check)
        return d

class TestCopyDirectory(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.make_command(fs.CopyDirectory, dict(
            fromdir='workdir',
            todir='copy',
        ), True)
        d = self.run_command()

        def check(_):
            self.assertTrue(os.path.exists(os.path.abspath(os.path.join(self.basedir,'copy'))))
            self.assertIn({'rc': 0},
                    self.get_updates(),
                    self.builder.show())
        d.addCallback(check)
        return d

class TestMakeDirectory(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.make_command(fs.MakeDirectory, dict(
            dir='test-dir',
        ), True)
        d = self.run_command()

        def check(_):
            self.assertTrue(os.path.exists(os.path.abspath(os.path.join(self.basedir,'test-dir'))))
            self.assertEqual(self.get_updates(),
                    [{'rc': 0}],
                    self.builder.show())
        d.addCallback(check)
        return d

    def test_already_exists(self):
        self.make_command(fs.MakeDirectory, dict(
            dir='workdir',
        ), True)
        d = self.run_command()

        def check(_):
            self.assertEqual(self.get_updates(),
                    [{'rc': 0}],
                    self.builder.show())
        d.addCallback(check)
        return d

    def test_existing_file(self):
        self.make_command(fs.MakeDirectory, dict(
            dir='test-file',
        ), True)
        open(os.path.join(self.basedir, 'test-file'), "w")
        d = self.run_command()

        def check(_):
            self.assertEqual(self.get_updates(), [{'rc': 1}], self.builder.show())
        d.addErrback(check)
        return d
