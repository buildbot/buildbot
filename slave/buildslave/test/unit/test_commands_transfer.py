import os

from twisted.trial import unittest
from twisted.internet import task, defer
from twisted.python import runtime

from buildslave.test.fake.runprocess import Expect
from buildslave.test.fake.remote import FakeRemote
from buildslave.test.util.command import CommandTestMixin
from buildslave.commands import transfer

class FakeWriter(object):
    def __init__(self, add_update):
        self.add_update = add_update

    def remote_write(self, data):
        self.add_update('write %d' % len(data))

    def remote_close(self):
        self.add_update('close')

class TestUploadFile(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

        self.writer = FakeWriter(self.add_update)

        # write 180 bytes of data to upload
        datadir = os.path.join(self.basedir, 'workdir')
        if not os.path.exists(datadir):
            os.makedirs(datadir)

        self.datafile = os.path.join(datadir, 'data')
        # note: use of 'wb' here ensures newlines aren't translated on the upload
        open(self.datafile, "wb").write("this is some data\n" * 10)

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.make_command(transfer.SlaveFileUploadCommand, dict(
            workdir='workdir',
            slavesrc='data',
            writer=FakeRemote(self.writer),
            maxsize=1000,
            blocksize=64,
        ))

        d = self.run_command()

        # note that SlaveShellCommand does not add any extra updates of it own
        def check(_):
            self.assertEqual(self.get_updates(), [
                    {'header': 'sending %s' % self.datafile},
                    'write 64', 'write 64', 'write 52', 'close',
                    {'rc': 0}
                ],
                self.builder.show())
        d.addCallback(check)
        return d

    def test_truncated(self):
        self.make_command(transfer.SlaveFileUploadCommand, dict(
            workdir='workdir',
            slavesrc='data',
            writer=FakeRemote(self.writer),
            maxsize=100,
            blocksize=64,
        ))

        d = self.run_command()

        # note that SlaveShellCommand does not add any extra updates of it own
        def check(_):
            self.assertEqual(self.get_updates(), [
                    {'header': 'sending %s' % self.datafile},
                    'write 64', 'write 36', 'close',
                    {'rc': 1,
                     'stderr': "Maximum filesize reached, truncating file '%s'" % self.datafile}
                ],
                self.builder.show())
        d.addCallback(check)
        return d

