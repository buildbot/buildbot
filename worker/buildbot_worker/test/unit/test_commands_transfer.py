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
from __future__ import annotations

import io
import os
import re
import shutil
import tarfile
from typing import TYPE_CHECKING
from typing import cast

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import failure
from twisted.python import runtime
from twisted.trial import unittest

from buildbot_worker.commands import transfer
from buildbot_worker.test.fake.remote import FakeRemote
from buildbot_worker.test.util.command import CommandTestMixin

if TYPE_CHECKING:
    from typing import Any
    from typing import Callable

    from twisted.internet.interfaces import IReactorTime

    from buildbot_worker.util.twisted import InlineCallbacksType


class FakeMasterMethods:
    # a fake to represent any of:
    # - FileWriter
    # - FileDirectoryWriter
    # - FileReader

    def __init__(self, add_update: Callable[[tuple[str, Any] | str], None]) -> None:
        self.add_update = add_update

        self.delay_write = False
        self.count_writes = False
        self.keep_data = False
        self.write_out_of_space_at: int | None = None

        self.delay_read = False
        self.count_reads = False

        self.unpack_fail = False

        self.written = False
        self.read = False
        self.data = b''

    def remote_write(self, data: bytes) -> defer.Deferred[None] | None:
        if self.write_out_of_space_at is not None:
            self.write_out_of_space_at -= len(data)
            if self.write_out_of_space_at <= 0:
                f = failure.Failure(RuntimeError("out of space"))
                return defer.fail(f)
        if self.count_writes:
            self.add_update(f'write {len(data)}')
        elif not self.written:
            self.add_update('write(s)')
            self.written = True

        if self.keep_data:
            self.data += data

        if self.delay_write:
            d: defer.Deferred[None] = defer.Deferred()
            cast("IReactorTime", reactor).callLater(0.01, d.callback, None)
            return d
        return None

    def remote_read(self, length: int) -> defer.Deferred[bytes] | bytes | str:
        if self.count_reads:
            self.add_update(f'read {length}')
        elif not self.read:
            self.add_update('read(s)')
            self.read = True

        if not self.data:
            return ''

        _slice, self.data = self.data[:length], self.data[length:]
        if self.delay_read:
            d: defer.Deferred[bytes] = defer.Deferred()
            cast("IReactorTime", reactor).callLater(0.01, d.callback, _slice)
            return d
        return _slice

    def remote_unpack(self) -> defer.Deferred[None] | None:
        self.add_update('unpack')
        if self.unpack_fail:
            return defer.fail(failure.Failure(RuntimeError("out of space")))
        return None

    def remote_utime(self, accessed_modified: tuple[float]) -> None:
        self.add_update(f'utime - {accessed_modified[0]}')

    def remote_close(self) -> None:
        self.add_update('close')


class TestUploadFile(CommandTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.setUpCommand()

        self.fakemaster = FakeMasterMethods(self.add_update)

        # write 180 bytes of data to upload
        self.datadir = os.path.join(self.basedir, 'workdir')
        if os.path.exists(self.datadir):
            shutil.rmtree(self.datadir)
        os.makedirs(self.datadir)

        self.datafile = os.path.join(self.datadir, 'data')
        # note: use of 'wb' here ensures newlines aren't translated on the
        # upload
        with open(self.datafile, mode="wb") as f:
            f.write(b"this is some data\n" * 10)

    def tearDown(self) -> None:
        if os.path.exists(self.datadir):
            shutil.rmtree(self.datadir)

    @defer.inlineCallbacks
    def test_simple(self) -> InlineCallbacksType[None]:
        self.fakemaster.count_writes = True  # get actual byte counts

        path = os.path.join(self.basedir, 'workdir', os.path.expanduser('data'))
        self.make_command(
            transfer.WorkerFileUploadCommand,
            {
                'path': path,
                'writer': FakeRemote(self.fakemaster),
                'maxsize': 1000,
                'blocksize': 64,
                'keepstamp': False,
            },
        )

        yield self.run_command()

        self.assertUpdates([
            ('header', f'sending {self.datafile}\n'),
            'write 64',
            'write 64',
            'write 52',
            'close',
            ('rc', 0),
        ])

    @defer.inlineCallbacks
    def test_truncated(self) -> InlineCallbacksType[None]:
        self.fakemaster.count_writes = True  # get actual byte counts

        path = os.path.join(self.basedir, 'workdir', os.path.expanduser('data'))
        self.make_command(
            transfer.WorkerFileUploadCommand,
            {
                'path': path,
                'writer': FakeRemote(self.fakemaster),
                'maxsize': 100,
                'blocksize': 64,
                'keepstamp': False,
            },
        )

        yield self.run_command()

        self.assertUpdates([
            ('header', f'sending {self.datafile}\n'),
            'write 64',
            'write 36',
            'close',
            ('rc', 1),
            ('stderr', f"Maximum filesize reached, truncating file '{self.datafile}'"),
        ])

    @defer.inlineCallbacks
    def test_missing(self) -> InlineCallbacksType[None]:
        path = os.path.join(self.basedir, 'workdir', os.path.expanduser('data-nosuch'))
        self.make_command(
            transfer.WorkerFileUploadCommand,
            {
                'path': path,
                'writer': FakeRemote(self.fakemaster),
                'maxsize': 100,
                'blocksize': 64,
                'keepstamp': False,
            },
        )

        yield self.run_command()

        df = self.datafile + "-nosuch"
        self.assertUpdates([
            ('header', f'sending {df}\n'),
            'close',
            ('rc', 1),
            ('stderr', f"Cannot open file '{df}' for upload"),
        ])

    @defer.inlineCallbacks
    def test_out_of_space(self) -> InlineCallbacksType[None]:
        self.fakemaster.write_out_of_space_at = 70
        self.fakemaster.count_writes = True  # get actual byte counts

        path = os.path.join(self.basedir, 'workdir', os.path.expanduser('data'))
        self.make_command(
            transfer.WorkerFileUploadCommand,
            {
                'path': path,
                'writer': FakeRemote(self.fakemaster),
                'maxsize': 1000,
                'blocksize': 64,
                'keepstamp': False,
            },
        )

        with self.assertRaises(RuntimeError):
            yield self.run_command()

        self.assertUpdates([
            ('header', f'sending {self.datafile}\n'),
            'write 64',
            'close',
            ('rc', 1),
        ])

    @defer.inlineCallbacks
    def test_interrupted(self) -> InlineCallbacksType[None]:
        self.fakemaster.delay_write = True  # write very slowly

        path = os.path.join(self.basedir, 'workdir', os.path.expanduser('data'))
        self.make_command(
            transfer.WorkerFileUploadCommand,
            {
                'path': path,
                'writer': FakeRemote(self.fakemaster),
                'maxsize': 100,
                'blocksize': 2,
                'keepstamp': False,
            },
        )

        d = self.run_command()

        # wait a jiffy..
        interrupt_d: defer.Deferred[None] = defer.Deferred()
        cast("IReactorTime", reactor).callLater(0.01, interrupt_d.callback, None)

        # and then interrupt the step
        def do_interrupt(_: Any) -> defer.Deferred[None] | None:
            return self.cmd.interrupt()

        interrupt_d.addCallback(do_interrupt)

        yield defer.DeferredList([d, interrupt_d], consumeErrors=True)

        self.assertUpdates([
            ('header', f'sending {self.datafile}\n'),
            'write(s)',
            'close',
            ('rc', 1),
        ])

    @defer.inlineCallbacks
    def test_timestamp(self) -> InlineCallbacksType[None]:
        self.fakemaster.count_writes = True  # get actual byte counts
        timestamp = (os.path.getatime(self.datafile), os.path.getmtime(self.datafile))

        path = os.path.join(self.basedir, 'workdir', os.path.expanduser('data'))
        self.make_command(
            transfer.WorkerFileUploadCommand,
            {
                'path': path,
                'writer': FakeRemote(self.fakemaster),
                'maxsize': 1000,
                'blocksize': 64,
                'keepstamp': True,
            },
        )

        yield self.run_command()

        self.assertUpdates([
            ('header', f'sending {self.datafile}\n'),
            'write 64',
            'write 64',
            'write 52',
            'close',
            f'utime - {timestamp[0]}',
            ('rc', 0),
        ])


class TestWorkerDirectoryUpload(CommandTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.setUpCommand()

        self.fakemaster = FakeMasterMethods(self.add_update)

        # write a directory to upload
        self.datadir = os.path.join(self.basedir, 'workdir', 'data')
        if os.path.exists(self.datadir):
            shutil.rmtree(self.datadir)
        os.makedirs(self.datadir)
        with open(os.path.join(self.datadir, "aa"), mode="wb") as f:
            f.write(b"lots of a" * 100)
        with open(os.path.join(self.datadir, "bb"), mode="wb") as f:
            f.write(b"and a little b" * 17)

    def tearDown(self) -> None:
        if os.path.exists(self.datadir):
            shutil.rmtree(self.datadir)

    @defer.inlineCallbacks
    def test_simple(self, compress: str | None = None) -> InlineCallbacksType[None]:
        self.fakemaster.keep_data = True
        path = os.path.join(self.basedir, 'workdir', os.path.expanduser('data'))
        self.make_command(
            transfer.WorkerDirectoryUploadCommand,
            {
                'workdir': 'workdir',
                'path': path,
                'writer': FakeRemote(self.fakemaster),
                'maxsize': None,
                'blocksize': 512,
                'compress': compress,
            },
        )

        yield self.run_command()

        self.assertUpdates([
            ('header', f'sending {self.datadir}\n'),
            'write(s)',
            'unpack',  # note no 'close"
            ('rc', 0),
        ])

        f = io.BytesIO(self.fakemaster.data)
        a = tarfile.open(fileobj=f, name='check.tar', mode="r")
        exp_names = ['.', 'aa', 'bb']
        got_names = [n.rstrip('/') for n in a.getnames()]
        # py27 uses '' instead of '.'
        got_names = sorted([n or '.' for n in got_names])
        self.assertEqual(got_names, exp_names, "expected archive contents")
        a.close()
        f.close()

    # try it again with bz2 and gzip
    def test_simple_bz2(self) -> defer.Deferred[None]:
        return self.test_simple('bz2')

    def test_simple_gz(self) -> defer.Deferred[None]:
        return self.test_simple('gz')

    # except bz2 can't operate in stream mode on py24

    @defer.inlineCallbacks
    def test_out_of_space_unpack(self) -> InlineCallbacksType[None]:
        self.fakemaster.keep_data = True
        self.fakemaster.unpack_fail = True
        path = os.path.join(self.basedir, 'workdir', os.path.expanduser('data'))

        self.make_command(
            transfer.WorkerDirectoryUploadCommand,
            {
                'path': path,
                'workersrc': 'data',
                'writer': FakeRemote(self.fakemaster),
                'maxsize': None,
                'blocksize': 512,
                'compress': None,
            },
        )

        with self.assertRaises(RuntimeError):
            yield self.run_command()

        self.assertUpdates([
            ('header', f'sending {self.datadir}\n'),
            'write(s)',
            'unpack',
            ('rc', 1),
        ])


class TestWorkerDirectoryUploadNoDir(CommandTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.setUpCommand()
        self.fakemaster = FakeMasterMethods(self.add_update)

    @defer.inlineCallbacks
    def test_directory_not_available(self) -> InlineCallbacksType[None]:
        path = os.path.join(self.basedir, 'workdir', os.path.expanduser('data'))

        self.make_command(
            transfer.WorkerDirectoryUploadCommand,
            {
                'path': path,
                'workersrc': 'data',
                'writer': FakeRemote(self.fakemaster),
                'maxsize': None,
                'blocksize': 512,
                'compress': None,
            },
        )

        yield self.run_command()

        updates = self.get_updates()
        self.assertEqual(updates[0], ('rc', 1))
        self.assertEqual(updates[1][0], "stderr")

        error_msg = updates[1][1]
        pattern = re.compile("Cannot read directory (.*?) for upload: (.*?)")
        match = pattern.match(error_msg)
        self.assertNotEqual(error_msg, match)


class TestDownloadFile(CommandTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.setUpCommand()

        self.fakemaster = FakeMasterMethods(self.add_update)

        # the command will write to the basedir, so make sure it exists
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

    def tearDown(self) -> None:
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)

    @defer.inlineCallbacks
    def test_simple(self) -> InlineCallbacksType[None]:
        self.fakemaster.count_reads = True  # get actual byte counts
        self.fakemaster.data = test_data = b'1234' * 13
        assert len(self.fakemaster.data) == 52

        path = os.path.join(self.basedir, os.path.expanduser('data'))
        self.make_command(
            transfer.WorkerFileDownloadCommand,
            {
                'path': path,
                'reader': FakeRemote(self.fakemaster),
                'maxsize': None,
                'blocksize': 32,
                'mode': 0o777,
            },
        )

        yield self.run_command()

        self.assertUpdates(['read 32', 'read 32', 'read 32', 'close', ('rc', 0)])
        datafile = os.path.join(self.basedir, 'data')
        self.assertTrue(os.path.exists(datafile))
        with open(datafile, mode="rb") as f:
            datafileContent = f.read()
        self.assertEqual(datafileContent, test_data)
        if runtime.platformType != 'win32':
            self.assertEqual(os.stat(datafile).st_mode & 0o777, 0o777)

    @defer.inlineCallbacks
    def test_mkdir(self) -> InlineCallbacksType[None]:
        self.fakemaster.data = test_data = b'hi'

        path = os.path.join(
            self.basedir, 'workdir', os.path.expanduser(os.path.join('subdir', 'data'))
        )
        self.make_command(
            transfer.WorkerFileDownloadCommand,
            {
                'path': path,
                'reader': FakeRemote(self.fakemaster),
                'maxsize': None,
                'blocksize': 32,
                'mode': 0o777,
            },
        )

        yield self.run_command()

        self.assertUpdates(['read(s)', 'close', ('rc', 0)])
        datafile = os.path.join(self.basedir, 'workdir', 'subdir', 'data')
        self.assertTrue(os.path.exists(datafile))
        with open(datafile, mode="rb") as f:
            datafileContent = f.read()
        self.assertEqual(datafileContent, test_data)

    @defer.inlineCallbacks
    def test_failure(self) -> InlineCallbacksType[None]:
        self.fakemaster.data = b'hi'

        os.makedirs(os.path.join(self.basedir, 'dir'))
        path = os.path.join(self.basedir, os.path.expanduser('dir'))
        self.make_command(
            transfer.WorkerFileDownloadCommand,
            {
                'path': path,
                'reader': FakeRemote(self.fakemaster),
                'maxsize': None,
                'blocksize': 32,
                'mode': 0o777,
            },
        )

        yield self.run_command()

        self.assertUpdates([
            'close',
            ('rc', 1),
            (
                'stderr',
                "Cannot open file '{}' for download".format(os.path.join(self.basedir, 'dir')),
            ),
        ])

    @defer.inlineCallbacks
    def test_truncated(self) -> InlineCallbacksType[None]:
        self.fakemaster.data = test_data = b'tenchars--' * 10

        path = os.path.join(self.basedir, os.path.expanduser('data'))
        self.make_command(
            transfer.WorkerFileDownloadCommand,
            {
                'path': path,
                'reader': FakeRemote(self.fakemaster),
                'maxsize': 50,
                'blocksize': 32,
                'mode': 0o777,
            },
        )
        yield self.run_command()

        self.assertUpdates([
            'read(s)',
            'close',
            ('rc', 1),
            (
                'stderr',
                "Maximum filesize reached, truncating file '{}'".format(
                    os.path.join(self.basedir, 'data')
                ),
            ),
        ])
        datafile = os.path.join(self.basedir, 'data')
        self.assertTrue(os.path.exists(datafile))
        with open(datafile, mode="rb") as f:
            data = f.read()
        self.assertEqual(data, test_data[:50])

    @defer.inlineCallbacks
    def test_interrupted(self) -> InlineCallbacksType[None]:
        self.fakemaster.data = b'tenchars--' * 100  # 1k
        self.fakemaster.delay_read = True  # read very slowly

        path = os.path.join(self.basedir, os.path.expanduser('data'))
        self.make_command(
            transfer.WorkerFileDownloadCommand,
            {
                'path': path,
                'reader': FakeRemote(self.fakemaster),
                'maxsize': 100,
                'blocksize': 2,
                'mode': 0o777,
            },
        )

        d = self.run_command()

        # wait a jiffy..
        interrupt_d: defer.Deferred[None] = defer.Deferred()
        cast("IReactorTime", reactor).callLater(0.01, interrupt_d.callback, None)

        # and then interrupt the step
        def do_interrupt(_: Any) -> defer.Deferred[None] | None:
            return self.cmd.interrupt()

        interrupt_d.addCallback(do_interrupt)

        yield defer.DeferredList([d, interrupt_d], consumeErrors=True)

        self.assertUpdates(['read(s)', 'close', ('rc', 1)])
