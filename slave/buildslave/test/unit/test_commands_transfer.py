import os

from twisted.trial import unittest
from twisted.internet import task, defer
from twisted.python import runtime

from buildslave.test.fake.runprocess import Expect
from buildslave.test.fake.remote import FakeRemote
from buildslave.test.util.command import CommandTestMixin
from buildslave.commands import transfer

class FakeWriter(object):
    def __init__(self):
        self.actions = []

    def remote_write(self, data):
        self.actions.append('write %d' % len(data))

    def remote_close(self):
        self.actions.append('close')

class TestUploadFile(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        writer = FakeWriter()

        self.make_command(transfer.SlaveFileUploadCommand, dict(
            workdir='workdir',
            slavesrc='data',
            writer=FakeRemote(writer),
            maxsize=1000,
            blocksize=64,
        ))

        # write the data it should upload
        datadir = os.path.join(self.basedir, 'workdir')
        if not os.path.exists(datadir):
            os.makedirs(datadir)
        open(os.path.join(datadir, 'data'), "w").write("this is some data\n" * 10)

        d = self.run_command()

        # note that SlaveShellCommand does not add any extra updates of it own
        def check(_):
            self.assertEqual(self.get_updates(), [
                    {'header': 'sending %s' % os.path.join(self.basedir, 'workdir', 'data')},
                    {'rc': 0}
                ],
                self.builder.show())
            self.assertEqual(writer.actions,
                [ 'write 64', 'write 64', 'write 52', 'close' ])
        d.addCallback(check)
        return d
