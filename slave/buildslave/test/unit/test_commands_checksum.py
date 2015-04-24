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

import mock
from twisted.trial import unittest
from twisted.internet import defer
from buildslave.commands import checksum
from buildslave.test.util.command import CommandTestMixin


class _ReadMock:
    def __init__(self, chunks):
        self._chunks = iter(chunks + [None])

    __call__ = lambda self, size: self._chunks.next()

def _setup_open_mock(open_mock, read_chunks):
        mock_file = mock.MagicMock()
        mock_file.read.side_effect = _ReadMock(read_chunks)
        open_mock.return_value.__enter__.return_value = mock_file


class TestCalcCheckSumsFunc(unittest.TestCase):
    #
    # test checksums._calc_checksum() function
    #
    ROOTDIR = "rootdir"

    FILE_NAME = "a-file"
    FILE_CHUNKS = ["chunk1", "chunk2"]

    MD5_SUM = {FILE_NAME: "097c42989a9e5d9dcced7b35ec4b0486"}
    SHA1_SUM = {FILE_NAME: "308b22e31bd944179c376b6a5482e623f75ee747"}

    IO_ERROR_MSG = "test-io-error"

    @mock.patch("__builtin__.open")
    def test_md5(self, open_mock):
        _setup_open_mock(open_mock, self.FILE_CHUNKS)

        sums = checksum._calc_checksum(self.ROOTDIR, [self.FILE_NAME], "md5")
        self.assertEquals(sums, self.MD5_SUM)

    @mock.patch("__builtin__.open")
    def test_sha1(self, open_mock):
        _setup_open_mock(open_mock, self.FILE_CHUNKS)

        sums = checksum._calc_checksum(self.ROOTDIR, [self.FILE_NAME], "sha1")
        self.assertEquals(sums, self.SHA1_SUM)

    def test_unsupported_algo_err(self):
        # test the case when unsupported hash algorithm is specified

        self.assertRaisesRegexp(checksum._CheckSumException,
                                "unsupported hash type mangokiwi",
                                checksum._calc_checksum,
                                self.ROOTDIR, [self.FILE_NAME], "mangokiwi")

    @mock.patch("__builtin__.open")
    def test_io_err(self, open_mock):
        open_mock.side_effect = IOError(self.IO_ERROR_MSG)

        self.assertRaisesRegexp(checksum._CheckSumException,
                                self.IO_ERROR_MSG,
                                checksum._calc_checksum,
                                self.ROOTDIR, [self.FILE_NAME], "md5")


class TestCalcCheckSums(CommandTestMixin, unittest.TestCase):
    #
    # test CheckSums command
    #
    WORKDIR = "wkrdir"
    ERROR_MESSAGE = "calsum-err-msg"

    def setUp(self):
        self._calc_checksum = mock.Mock()
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    @defer.inlineCallbacks
    def test_ok(self):
        self.patch(checksum, "_calc_checksum", self._calc_checksum)

        self.make_command(checksum.CheckSums,
                          dict(workdir=self.WORKDIR,
                               files=["f1", "f2"]))

        yield self.run_command()

        self.assertUpdates([{"sums": self._calc_checksum.return_value},
                            {"rc": 0}])

    @defer.inlineCallbacks
    def test_error(self):
        self._calc_checksum.side_effect = \
            checksum._CheckSumException(self.ERROR_MESSAGE)

        self.patch(checksum, "_calc_checksum", self._calc_checksum)

        self.make_command(checksum.CheckSums,
                          dict(workdir=self.WORKDIR,
                               files=["f1", "f2"]))

        yield self.run_command()

        self.assertUpdates([
            {"header": "error calculating checksum: %s" % self.ERROR_MESSAGE},
            {"rc": 1}])
