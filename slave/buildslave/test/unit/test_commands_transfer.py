import os
import shutil
import tarfile
import StringIO

from twisted.trial import unittest
from twisted.internet import task, defer, reactor
from twisted.python import runtime

from buildslave.test.fake.runprocess import Expect
from buildslave.test.fake.remote import FakeRemote
from buildslave.test.util.command import CommandTestMixin
from buildslave.commands import transfer

class FakeDirectoryWriter(object):
    # this works as a Writer for UplaodFile as well
    def __init__(self, add_update):
        self.add_update = add_update
        self.delay_write = False
        self.count_writes = False
        self.keep_data = False

        self.written = False
        self.data = ''

    def remote_write(self, data):
        if self.count_writes:
            self.add_update('write %d' % len(data))
        elif not self.written:
            self.add_update('write(s)')
            self.written = True

        if self.keep_data:
            self.data += data

        if self.delay_write:
            # note that writes are not logged in this case, as
            # an arbitrary number of writes may occur before interrupt
            d = defer.Deferred()
            reactor.callLater(0.01, d.callback, None)
            return d

    def remote_unpack(self):
        self.add_update('unpack')

    def remote_close(self):
        self.add_update('close')

class TestUploadFile(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

        self.writer = FakeDirectoryWriter(self.add_update)

        # write 180 bytes of data to upload
        datadir = os.path.join(self.basedir, 'workdir')
        if os.path.exists(datadir):
            shutil.rmtree(datadir)
        os.makedirs(datadir)

        self.datafile = os.path.join(datadir, 'data')
        # note: use of 'wb' here ensures newlines aren't translated on the upload
        open(self.datafile, "wb").write("this is some data\n" * 10)

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.writer.count_writes = True    # get actual byte counts

        self.make_command(transfer.SlaveFileUploadCommand, dict(
            workdir='workdir',
            slavesrc='data',
            writer=FakeRemote(self.writer),
            maxsize=1000,
            blocksize=64,
        ))

        d = self.run_command()

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
        self.writer.count_writes = True    # get actual byte counts

        self.make_command(transfer.SlaveFileUploadCommand, dict(
            workdir='workdir',
            slavesrc='data',
            writer=FakeRemote(self.writer),
            maxsize=100,
            blocksize=64,
        ))

        d = self.run_command()

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

    def test_missing(self):
        self.make_command(transfer.SlaveFileUploadCommand, dict(
            workdir='workdir',
            slavesrc='data-nosuch',
            writer=FakeRemote(self.writer),
            maxsize=100,
            blocksize=64,
        ))

        d = self.run_command()

        def check(_):
            df = self.datafile + "-nosuch"
            self.assertEqual(self.get_updates(), [
                    {'header': 'sending %s' % df},
                    'close',
                    {'rc': 1,
                     'stderr': "Cannot open file '%s' for upload" % df}
                ],
                self.builder.show())
        d.addCallback(check)
        return d

    def test_interrupted(self):
        self.writer.delay_write = True # write veery slowly

        self.make_command(transfer.SlaveFileUploadCommand, dict(
            workdir='workdir',
            slavesrc='data',
            writer=FakeRemote(self.writer),
            maxsize=100,
            blocksize=2,
        ))

        d = self.run_command()

        # wait a jiffy..
        interrupt_d = defer.Deferred()
        reactor.callLater(0.01, interrupt_d.callback, None)

        # and then interrupt the step
        def do_interrupt(_):
            return self.cmd.interrupt()
        interrupt_d.addCallback(do_interrupt)

        dl = defer.DeferredList([d, interrupt_d])
        def check(_):
            self.assertEqual(self.get_updates(), [
                    {'header': 'sending %s' % self.datafile},
                    'write(s)', 'close',
                    {'rc': 1,
                     'stderr': "Upload of '%s' interrupted" % self.datafile}
                ],
                self.builder.show())
        dl.addCallback(check)
        return dl

class TestSlaveDirectoryUpload(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

        self.writer = FakeDirectoryWriter(self.add_update)

        # write a directory to upload
        self.datadir = os.path.join(self.basedir, 'workdir', 'data')
        if os.path.exists(self.datadir):
            shutil.rmtree(self.datadir)
        os.makedirs(self.datadir)
        open(os.path.join(self.datadir, "aa"), "wb").write("lots of a" * 100)
        open(os.path.join(self.datadir, "bb"), "wb").write("and a little b" * 17)

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.writer.keep_data = True 

        self.make_command(transfer.SlaveDirectoryUploadCommand, dict(
            workdir='workdir',
            slavesrc='data',
            writer=FakeRemote(self.writer),
            maxsize=None,
            blocksize=512,
            compress=0,
        ))

        d = self.run_command()

        def check(_):
            self.assertEqual(self.get_updates(), [
                    {'header': 'sending %s' % self.datadir},
                    'write(s)', 'unpack', # note no 'close"
                    {'rc': 0}
                ],
                self.builder.show())
        d.addCallback(check)

        def check_tarfile(_):
            f = StringIO.StringIO(self.writer.data)
            a = tarfile.open(fileobj=f)
            self.assertEqual(sorted(a.getnames()), [ '.', 'aa', 'bb' ])
        d.addCallback(check_tarfile)

        return d

    # this is just a subclass of SlaveUpload, so the remaining permutations
    # are already tested
