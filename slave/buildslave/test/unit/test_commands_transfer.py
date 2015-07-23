# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import io
import os
import shutil
import sys
import tarfile

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import failure
from twisted.python import runtime
from twisted.trial import unittest

from buildslave.commands import transfer
from buildslave.test.fake.remote import FakeRemote
from buildslave.test.util.command import CommandTestMixin


class FakeMasterMethods(object):
    # a fake to represent any of:
    # - FileWriter
    # - FileDirectoryWriter
    # - FileReader

    def __init__(self, add_update):
        self.add_update = add_update

        self.delay_write = False
        self.count_writes = False
        self.keep_data = False
        self.write_out_of_space_at = None

        self.delay_read = False
        self.count_reads = False

        self.unpack_fail = False

        self.written = False
        self.read = False
        self.data = ''

    def remote_write(self, data):
        if self.write_out_of_space_at is not None:
            self.write_out_of_space_at -= len(data)
            if self.write_out_of_space_at <= 0:
                f = failure.Failure(RuntimeError("out of space"))
                return defer.fail(f)
        if self.count_writes:
            self.add_update('write %d' % len(data))
        elif not self.written:
            self.add_update('write(s)')
            self.written = True

        if self.keep_data:
            self.data += data

        if self.delay_write:
            d = defer.Deferred()
            reactor.callLater(0.01, d.callback, None)
            return d

    def remote_read(self, length):
        if self.count_reads:
            self.add_update('read %d' % length)
        elif not self.read:
            self.add_update('read(s)')
            self.read = True

        if not self.data:
            return ''

        slice, self.data = self.data[:length], self.data[length:]
        if self.delay_read:
            d = defer.Deferred()
            reactor.callLater(0.01, d.callback, slice)
            return d
        else:
            return slice

    def remote_unpack(self):
        self.add_update('unpack')
        if self.unpack_fail:
            return defer.fail(failure.Failure(RuntimeError("out of space")))

    def remote_utime(self, accessed_modified):
        self.add_update('utime - %s' % accessed_modified[0])

    def remote_close(self):
        self.add_update('close')


class TestUploadFile(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

        self.fakemaster = FakeMasterMethods(self.add_update)

        # write 180 bytes of data to upload
        self.datadir = os.path.join(self.basedir, 'workdir')
        if os.path.exists(self.datadir):
            shutil.rmtree(self.datadir)
        os.makedirs(self.datadir)

        self.datafile = os.path.join(self.datadir, 'data')
        # note: use of 'wb' here ensures newlines aren't translated on the upload
        open(self.datafile, "wb").write("this is some data\n" * 10)

    def tearDown(self):
        self.tearDownCommand()

        if os.path.exists(self.datadir):
            shutil.rmtree(self.datadir)

    def test_simple(self):
        self.fakemaster.count_writes = True    # get actual byte counts

        self.make_command(transfer.SlaveFileUploadCommand, dict(
            workdir='workdir',
            slavesrc='data',
            writer=FakeRemote(self.fakemaster),
            maxsize=1000,
            blocksize=64,
            keepstamp=False,
        ))

        d = self.run_command()

        def check(_):
            self.assertUpdates([
                {'header': 'sending %s' % self.datafile},
                'write 64', 'write 64', 'write 52', 'close',
                {'rc': 0}
            ])
        d.addCallback(check)
        return d

    def test_truncated(self):
        self.fakemaster.count_writes = True    # get actual byte counts

        self.make_command(transfer.SlaveFileUploadCommand, dict(
            workdir='workdir',
            slavesrc='data',
            writer=FakeRemote(self.fakemaster),
            maxsize=100,
            blocksize=64,
            keepstamp=False,
        ))

        d = self.run_command()

        def check(_):
            self.assertUpdates([
                {'header': 'sending %s' % self.datafile},
                'write 64', 'write 36', 'close',
                {'rc': 1,
                 'stderr': "Maximum filesize reached, truncating file '%s'" % self.datafile}
            ])
        d.addCallback(check)
        return d

    def test_missing(self):
        self.make_command(transfer.SlaveFileUploadCommand, dict(
            workdir='workdir',
            slavesrc='data-nosuch',
            writer=FakeRemote(self.fakemaster),
            maxsize=100,
            blocksize=64,
            keepstamp=False,
        ))

        d = self.run_command()

        def check(_):
            df = self.datafile + "-nosuch"
            self.assertUpdates([
                {'header': 'sending %s' % df},
                'close',
                {'rc': 1,
                 'stderr': "Cannot open file '%s' for upload" % df}
            ])
        d.addCallback(check)
        return d

    def test_out_of_space(self):
        self.fakemaster.write_out_of_space_at = 70
        self.fakemaster.count_writes = True    # get actual byte counts

        self.make_command(transfer.SlaveFileUploadCommand, dict(
            workdir='workdir',
            slavesrc='data',
            writer=FakeRemote(self.fakemaster),
            maxsize=1000,
            blocksize=64,
            keepstamp=False,
        ))

        d = self.run_command()
        self.assertFailure(d, RuntimeError)

        def check(_):
            self.assertUpdates([
                {'header': 'sending %s' % self.datafile},
                'write 64', 'close',
                {'rc': 1}
            ])
        d.addCallback(check)
        return d

    def test_interrupted(self):
        self.fakemaster.delay_write = True  # write veery slowly

        self.make_command(transfer.SlaveFileUploadCommand, dict(
            workdir='workdir',
            slavesrc='data',
            writer=FakeRemote(self.fakemaster),
            maxsize=100,
            blocksize=2,
            keepstamp=False,
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
            self.assertUpdates([
                {'header': 'sending %s' % self.datafile},
                'write(s)', 'close', {'rc': 1}
            ])
        dl.addCallback(check)
        return dl

    def test_timestamp(self):
        self.fakemaster.count_writes = True    # get actual byte counts
        timestamp = (os.path.getatime(self.datafile),
                     os.path.getmtime(self.datafile))

        self.make_command(transfer.SlaveFileUploadCommand, dict(
            workdir='workdir',
            slavesrc='data',
            writer=FakeRemote(self.fakemaster),
            maxsize=1000,
            blocksize=64,
            keepstamp=True,
        ))

        d = self.run_command()

        def check(_):
            self.assertUpdates([
                {'header': 'sending %s' % self.datafile},
                'write 64', 'write 64', 'write 52',
                'close', 'utime - %s' % timestamp[0],
                {'rc': 0}
            ])
        d.addCallback(check)
        return d


class TestSlaveDirectoryUpload(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

        self.fakemaster = FakeMasterMethods(self.add_update)

        # write a directory to upload
        self.datadir = os.path.join(self.basedir, 'workdir', 'data')
        if os.path.exists(self.datadir):
            shutil.rmtree(self.datadir)
        os.makedirs(self.datadir)
        open(os.path.join(self.datadir, "aa"), "wb").write("lots of a" * 100)
        open(os.path.join(self.datadir, "bb"), "wb").write("and a little b" * 17)

    def tearDown(self):
        self.tearDownCommand()

        if os.path.exists(self.datadir):
            shutil.rmtree(self.datadir)

    def test_simple(self, compress=None):
        self.fakemaster.keep_data = True

        self.make_command(transfer.SlaveDirectoryUploadCommand, dict(
            workdir='workdir',
            slavesrc='data',
            writer=FakeRemote(self.fakemaster),
            maxsize=None,
            blocksize=512,
            compress=compress,
        ))

        d = self.run_command()

        def check(_):
            self.assertUpdates([
                {'header': 'sending %s' % self.datadir},
                'write(s)', 'unpack',  # note no 'close"
                {'rc': 0}
            ])
        d.addCallback(check)

        def check_tarfile(_):
            f = io.BytesIO(self.fakemaster.data)
            a = tarfile.open(fileobj=f, name='check.tar')
            exp_names = ['.', 'aa', 'bb']
            got_names = [n.rstrip('/') for n in a.getnames()]
            got_names = sorted([n or '.' for n in got_names])  # py27 uses '' instead of '.'
            self.assertEqual(got_names, exp_names, "expected archive contents")
            a.close()
            f.close()
        d.addCallback(check_tarfile)

        return d

    # try it again with bz2 and gzip
    def test_simple_bz2(self):
        return self.test_simple('bz2')

    def test_simple_gz(self):
        return self.test_simple('gz')

    # except bz2 can't operate in stream mode on py24
    if sys.version_info[:2] <= (2, 4):
        test_simple_bz2.skip = "bz2 stream decompression not supported on Python-2.4"

    def test_out_of_space_unpack(self):
        self.fakemaster.keep_data = True
        self.fakemaster.unpack_fail = True

        self.make_command(transfer.SlaveDirectoryUploadCommand, dict(
            workdir='workdir',
            slavesrc='data',
            writer=FakeRemote(self.fakemaster),
            maxsize=None,
            blocksize=512,
            compress=None
        ))

        d = self.run_command()
        self.assertFailure(d, RuntimeError)

        def check(_):
            self.assertUpdates([
                {'header': 'sending %s' % self.datadir},
                'write(s)', 'unpack',
                {'rc': 1}
            ])
        d.addCallback(check)

        return d

    # this is just a subclass of SlaveUpload, so the remaining permutations
    # are already tested


class TestDownloadFile(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

        self.fakemaster = FakeMasterMethods(self.add_update)

        # the command will write to the basedir, so make sure it exists
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

    def tearDown(self):
        self.tearDownCommand()

        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)

    def test_simple(self):
        self.fakemaster.count_reads = True    # get actual byte counts
        self.fakemaster.data = test_data = '1234' * 13
        assert(len(self.fakemaster.data) == 52)

        self.make_command(transfer.SlaveFileDownloadCommand, dict(
            workdir='.',
            slavedest='data',
            reader=FakeRemote(self.fakemaster),
            maxsize=None,
            blocksize=32,
            mode=0o777,
        ))

        d = self.run_command()

        def check(_):
            self.assertUpdates([
                'read 32', 'read 32', 'read 32', 'close',
                {'rc': 0}
            ])
            datafile = os.path.join(self.basedir, 'data')
            self.assertTrue(os.path.exists(datafile))
            self.assertEqual(open(datafile).read(), test_data)
            if runtime.platformType != 'win32':
                self.assertEqual(os.stat(datafile).st_mode & 0o777, 0o777)
        d.addCallback(check)
        return d

    def test_mkdir(self):
        self.fakemaster.data = test_data = 'hi'

        self.make_command(transfer.SlaveFileDownloadCommand, dict(
            workdir='workdir',
            slavedest=os.path.join('subdir', 'data'),
            reader=FakeRemote(self.fakemaster),
            maxsize=None,
            blocksize=32,
            mode=0o777,
        ))

        d = self.run_command()

        def check(_):
            self.assertUpdates([
                'read(s)', 'close',
                {'rc': 0}
            ])
            datafile = os.path.join(self.basedir, 'workdir', 'subdir', 'data')
            self.assertTrue(os.path.exists(datafile))
            self.assertEqual(open(datafile).read(), test_data)
        d.addCallback(check)
        return d

    def test_failure(self):
        self.fakemaster.data = 'hi'

        os.makedirs(os.path.join(self.basedir, 'dir'))
        self.make_command(transfer.SlaveFileDownloadCommand, dict(
            workdir='.',
            slavedest='dir',  # but that's a directory!
            reader=FakeRemote(self.fakemaster),
            maxsize=None,
            blocksize=32,
            mode=0o777,
        ))

        d = self.run_command()

        def check(_):
            self.assertUpdates([
                'close',
                {'rc': 1,
                 'stderr': "Cannot open file '%s' for download"
                 % os.path.join(self.basedir, '.', 'dir')}
            ])
        d.addCallback(check)
        return d

    def test_truncated(self):
        self.fakemaster.data = test_data = 'tenchars--' * 10

        self.make_command(transfer.SlaveFileDownloadCommand, dict(
            workdir='.',
            slavedest='data',
            reader=FakeRemote(self.fakemaster),
            maxsize=50,
            blocksize=32,
            mode=0o777,
        ))

        d = self.run_command()

        def check(_):
            self.assertUpdates([
                'read(s)', 'close',
                {'rc': 1,
                 'stderr': "Maximum filesize reached, truncating file '%s'"
                 % os.path.join(self.basedir, '.', 'data')}
            ])
            datafile = os.path.join(self.basedir, 'data')
            self.assertTrue(os.path.exists(datafile))
            self.assertEqual(open(datafile).read(), test_data[:50])
        d.addCallback(check)
        return d

    def test_interrupted(self):
        self.fakemaster.data = 'tenchars--' * 100  # 1k
        self.fakemaster.delay_read = True  # read veery slowly

        self.make_command(transfer.SlaveFileDownloadCommand, dict(
            workdir='.',
            slavedest='data',
            reader=FakeRemote(self.fakemaster),
            maxsize=100,
            blocksize=2,
            mode=0o777,
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
            self.assertUpdates([
                'read(s)', 'close', {'rc': 1}
            ])
        dl.addCallback(check)
        return dl
