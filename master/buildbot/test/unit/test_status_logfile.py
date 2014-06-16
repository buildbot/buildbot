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

from __future__ import with_statement

import cPickle
import cStringIO
import mock
import os

from buildbot import config
from buildbot.status import logfile
from buildbot.test.util import dirs
from twisted.internet import defer
from twisted.trial import unittest


class TestLogFileProducer(unittest.TestCase):

    def make_static_logfile(self, contents):
        "make a fake logfile with the given contents"
        lf = mock.Mock()
        lf.getFile = lambda: cStringIO.StringIO(contents)
        lf.waitUntilFinished = lambda: defer.succeed(None)  # already finished
        lf.runEntries = []
        return lf

    def test_getChunks_static_helloworld(self):
        lf = self.make_static_logfile("13:0hello world!,")
        lfp = logfile.LogFileProducer(lf, mock.Mock())
        chunks = list(lfp.getChunks())
        self.assertEqual(chunks, [(0, 'hello world!')])

    def test_getChunks_static_multichannel(self):
        lf = self.make_static_logfile("2:0a,3:1xx,2:0c,")
        lfp = logfile.LogFileProducer(lf, mock.Mock())
        chunks = list(lfp.getChunks())
        self.assertEqual(chunks, [(0, 'a'), (1, 'xx'), (0, 'c')])

    # Remainder of LogFileProduer has a wacky interface that's not
    # well-defined, so it's not tested yet


class TestLogFile(unittest.TestCase, dirs.DirsMixin):

    def setUp(self):
        step = self.build_step_status = mock.Mock(name='build_step_status')
        self.basedir = step.build.builder.basedir = os.path.abspath('basedir')
        self.setUpDirs(self.basedir)
        self.logfile = logfile.LogFile(step, 'testlf', '123-stdio')
        self.master = self.logfile.master = mock.Mock()
        self.config = self.logfile.master.config = config.MasterConfig()

    def tearDown(self):
        if self.logfile.openfile:
            try:
                self.logfile.openfile.close()
            except:
                pass  # oh well, we tried
        self.tearDownDirs()

    def pickle_and_restore(self):
        pkl = cPickle.dumps(self.logfile)
        self.logfile = cPickle.loads(pkl)
        step = self.build_step_status
        self.logfile.step = step
        self.logfile.master = self.master
        step.build.builder.basedir = self.basedir

    def delete_logfile(self):
        if self.logfile.openfile:
            try:
                self.logfile.openfile.close()
            except:
                pass  # oh well, we tried
        os.unlink(os.path.join('basedir', '123-stdio'))

    # tests

    def test_getFilename(self):
        self.assertEqual(self.logfile.getFilename(),
                         os.path.abspath(os.path.join('basedir', '123-stdio')))

    def test_hasContents_yes(self):
        self.assertTrue(self.logfile.hasContents())

    def test_hasContents_no(self):
        self.delete_logfile()
        self.assertFalse(self.logfile.hasContents())

    def test_hasContents_gz(self):
        self.delete_logfile()
        with open(os.path.join(self.basedir, '123-stdio.gz'), "w") as f:
            f.write("hi")
        self.assertTrue(self.logfile.hasContents())

    def test_hasContents_gz_pickled(self):
        self.delete_logfile()
        with open(os.path.join(self.basedir, '123-stdio.gz'), "w") as f:
            f.write("hi")
        self.pickle_and_restore()
        self.assertTrue(self.logfile.hasContents())

    def test_hasContents_bz2(self):
        self.delete_logfile()
        with open(os.path.join(self.basedir, '123-stdio.bz2'), "w") as f:
            f.write("hi")
        self.assertTrue(self.logfile.hasContents())

    def test_getName(self):
        self.assertEqual(self.logfile.getName(), 'testlf')

    def test_getStep(self):
        self.assertEqual(self.logfile.getStep(), self.build_step_status)

    def test_isFinished_no(self):
        self.assertFalse(self.logfile.isFinished())

    def test_isFinished_yes(self):
        self.logfile.finish()
        self.assertTrue(self.logfile.isFinished())

    def test_waitUntilFinished(self):
        state = []
        d = self.logfile.waitUntilFinished()
        d.addCallback(lambda _: state.append('called'))
        self.assertEqual(state, [])  # not called yet
        self.logfile.finish()
        self.assertEqual(state, ['called'])

    def test_getFile(self):
        # test getFile at a number of points in the life-cycle
        self.logfile.addEntry(0, 'hello, world')
        self.logfile._merge()

        # while still open for writing
        fp = self.logfile.getFile()
        fp.seek(0, 0)
        self.assertEqual(fp.read(), '13:0hello, world,')

        self.logfile.finish()

        # fp is still open after finish()
        fp.seek(0, 0)
        self.assertEqual(fp.read(), '13:0hello, world,')

        # but a fresh getFile call works, too
        fp = self.logfile.getFile()
        fp.seek(0, 0)
        self.assertEqual(fp.read(), '13:0hello, world,')

        self.pickle_and_restore()

        # even after it is pickled
        fp = self.logfile.getFile()
        fp.seek(0, 0)
        self.assertEqual(fp.read(), '13:0hello, world,')

        # ..and compressed
        self.config.logCompressionMethod = 'bz2'
        d = self.logfile.compressLog()

        def check(_):
            self.assertTrue(
                os.path.exists(os.path.join(self.basedir, '123-stdio.bz2')))
            fp = self.logfile.getFile()
            fp.seek(0, 0)
            self.assertEqual(fp.read(), '13:0hello, world,')
        d.addCallback(check)
        return d

    def do_test_addEntry(self, entries, expected):
        for chan, txt in entries:
            self.logfile.addEntry(chan, txt)
        self.logfile.finish()
        fp = self.logfile.getFile()
        fp.seek(0, 0)
        self.assertEqual(fp.read(), expected)

    def test_addEntry_single(self):
        return self.do_test_addEntry([(0, 'hello, world')],
                                     '13:0hello, world,')

    def test_addEntry_run(self):
        # test that addEntry is calling merge() correctly
        return self.do_test_addEntry([(0, c) for c in 'hello, world'],
                                     '13:0hello, world,')

    def test_addEntry_multichan(self):
        return self.do_test_addEntry([(1, 'x'), (2, 'y'), (1, 'z')],
                                     '2:1x,2:2y,2:1z,')

    def test_addEntry_length(self):
        self.do_test_addEntry([(1, 'x'), (2, 'y')],
                              '2:1x,2:2y,')
        self.assertEqual(self.logfile.length, 2)

    def test_addEntry_unicode(self):
        return self.do_test_addEntry([(1, u'\N{SNOWMAN}')],
                                     '4:1\xe2\x98\x83,')  # utf-8 encoded

    def test_addEntry_logMaxSize(self):
        self.config.logMaxSize = 10  # not evenly divisible by chunk size
        return self.do_test_addEntry([(0, 'abcdef')] * 10,
                                     '11:0abcdefabcd,'
                                     '64:2\nOutput exceeded 10 bytes, remaining output has been '
                                     'truncated\n,')

    def test_addEntry_logMaxSize_ignores_header(self):
        self.config.logMaxSize = 10
        return self.do_test_addEntry([(logfile.HEADER, 'abcdef')] * 10,
                                     '61:2' + 'abcdef' * 10 + ',')

    def test_addEntry_logMaxSize_divisor(self):
        self.config.logMaxSize = 12  # evenly divisible by chunk size
        return self.do_test_addEntry([(0, 'abcdef')] * 10,
                                     '13:0abcdefabcdef,'
                                     '64:2\nOutput exceeded 12 bytes, remaining output has been '
                                     'truncated\n,')

    def test_addEntry_logMaxTailSize(self):
        self.config.logMaxSize = 10
        self.config.logMaxTailSize = 14
        return self.do_test_addEntry([(0, 'abcdef')] * 10,
                                     '11:0abcdefabcd,'
                                     '64:2\nOutput exceeded 10 bytes, remaining output has been '
                                     'truncated\n,'
                                     # NOTE: this gets too few bytes; this is OK for now, and
                                     # easier than subdividing chunks in the tail tracking
                                     '31:2\nFinal 12 bytes follow below:\n,'
                                     '13:0abcdefabcdef,')

    def test_addEntry_logMaxTailSize_divisor(self):
        self.config.logMaxSize = 10
        self.config.logMaxTailSize = 12
        return self.do_test_addEntry([(0, 'abcdef')] * 10,
                                     '11:0abcdefabcd,'
                                     '64:2\nOutput exceeded 10 bytes, remaining output has been '
                                     'truncated\n,'
                                     '31:2\nFinal 12 bytes follow below:\n,'
                                     '13:0abcdefabcdef,')

    # TODO: test that head and tail don't discriminate between stderr and stdout

    def test_addEntry_chunkSize(self):
        self.logfile.chunkSize = 11
        return self.do_test_addEntry([(0, 'abcdef')] * 10,
                                     # note that this doesn't re-chunk everything; just shrinks
                                     # chunks that will exceed the maximum size
                                     '12:0abcdefabcde,2:0f,' * 5)

    def test_addEntry_big_channel(self):
        # channels larger than one digit are not allowed
        self.assertRaises(AssertionError,
                          lambda: self.do_test_addEntry([(9999, 'x')], ''))

    def test_addEntry_finished(self):
        self.logfile.finish()
        self.assertRaises(AssertionError,
                          lambda: self.do_test_addEntry([(0, 'x')], ''))

    def test_addEntry_merge_exception(self):
        def fail():
            raise RuntimeError("FAIL")
        self.patch(self.logfile, '_merge', fail)
        self.assertRaises(RuntimeError,
                          lambda: self.do_test_addEntry([(0, 'x')], ''))

    def test_addEntry_watchers(self):
        watcher = mock.Mock(name='watcher')
        self.logfile.watchers.append(watcher)
        self.do_test_addEntry([(0, 'x')], '2:0x,')
        watcher.logChunk.assert_called_with(self.build_step_status.build,
                                            self.build_step_status, self.logfile, 0, 'x')

    def test_addEntry_watchers_logMaxSize(self):
        watcher = mock.Mock(name='watcher')
        self.logfile.watchers.append(watcher)
        self.config.logMaxSize = 10
        self.do_test_addEntry([(0, 'x')] * 15,
                              '11:0xxxxxxxxxx,'
                              '64:2\nOutput exceeded 10 bytes, remaining output has been '
                              'truncated\n,')
        logChunk_chunks = [tuple(args[0][3:])
                           for args in watcher.logChunk.call_args_list]
        self.assertEqual(logChunk_chunks, [(0, 'x')] * 15)

    def test_addStdout(self):
        addEntry = mock.Mock()
        self.patch(self.logfile, 'addEntry', addEntry)
        self.logfile.addStdout('oot')
        addEntry.assert_called_with(0, 'oot')

    def test_addStderr(self):
        addEntry = mock.Mock()
        self.patch(self.logfile, 'addEntry', addEntry)
        self.logfile.addStderr('eer')
        addEntry.assert_called_with(1, 'eer')

    def test_addHeader(self):
        addEntry = mock.Mock()
        self.patch(self.logfile, 'addEntry', addEntry)
        self.logfile.addHeader('hed')
        addEntry.assert_called_with(2, 'hed')

    def do_test_compressLog(self, ext, expect_comp=True):
        self.logfile.openfile.write('xyz' * 1000)
        self.logfile.finish()
        d = self.logfile.compressLog()

        def check(_):
            st = os.stat(self.logfile.getFilename() + ext)
            if expect_comp:
                self.assertTrue(0 < st.st_size < 3000)
            else:
                self.assertTrue(st.st_size == 3000)
        d.addCallback(check)
        return d

    def test_compressLog_gz(self):
        self.config.logCompressionMethod = 'gz'
        return self.do_test_compressLog('.gz')

    def test_compressLog_bz2(self):
        self.config.logCompressionMethod = 'bz2'
        return self.do_test_compressLog('.bz2')

    def test_compressLog_none(self):
        self.config.logCompressionMethod = None
        return self.do_test_compressLog('', expect_comp=False)


class TestHTMLLogFile(unittest.TestCase, dirs.DirsMixin):

    # The following script was used to pickle an 0.8.8 logfile. It was then
    # base64 encoded to be safely embedded in this test class.
    #
    # from buildbot.status import logfile
    # import pickle
    # lf = logfile.HTMLLogFile('error.html', '123-error_html', '<span>You lost the game</span>')
    # with open('123-error_html', 'w') as f:
    #     pickle.dump(lf, f)
    buildbot088pickle = '''
    KGlidWlsZGJvdC5zdGF0dXMubG9nZmlsZQpIVE1MTG9nRmlsZQpwMAooZHAyClMnaHRtbCcKcD
    MKUyc8c3Bhbj5Zb3UgbG9zdCB0aGUgZ2FtZTwvc3Bhbj4nCnA0CnNTJ25hbWUnCnA1ClMnZXJy
    b3IuaHRtbCcKcDYKc1MnZmlsZW5hbWUnCnA3ClMnMTIzLWVycm9yX2h0bWwnCnA4CnNiLg==
    '''

    def setUp(self):
        step = self.build_step_status = mock.Mock(name='build_step_status')
        self.basedir = step.build.builder.basedir = os.path.abspath('basedir')
        self.setUpDirs(self.basedir)
        self.logfile = logfile.HTMLLogFile(step, 'error.html', '123-error_html', '<span>You lost the game</span>')
        self.master = self.logfile.master = mock.Mock()
        self.config = self.logfile.master.config = config.MasterConfig()

    def tearDown(self):
        if self.logfile.openfile:
            try:
                self.logfile.openfile.close()
            except:
                pass  # oh well, we tried
        self.tearDownDirs()

    def pickle_and_restore(self):
        pkl = cPickle.dumps(self.logfile)
        self.logfile = cPickle.loads(pkl)
        step = self.build_step_status
        self.logfile.step = step
        self.logfile.master = self.master
        step.build.builder.basedir = self.basedir

    def test_unpickle(self):
        self.pickle_and_restore()

        d = self.logfile.finish()

        def check(_):
            fn = os.path.join('basedir', '123-error_html')
            self.assertTrue(os.path.exists(fn))
            fp = open(fn, 'r')
            self.assertEqual(fp.read(), '31:1<span>You lost the game</span>,')
            fp.close()

        d.addCallback(check)
        return d

    def test_unpickle_buildbot088pickle(self):
        import base64
        s = base64.b64decode(self.buildbot088pickle)
        self.logfile = cPickle.loads(s)
        step = self.build_step_status
        self.logfile.step = step
        self.logfile.master = self.master
        step.build.builder.basedir = self.basedir

        self.assertEqual(self.logfile.getName(), 'error.html')
        self.assertEqual(self.logfile.getText(), '<span>You lost the game</span>')

    def test_hasContents(self):
        self.assertTrue(self.logfile.hasContents())

    def test_getName(self):
        self.assertEqual(self.logfile.getName(), 'error.html')

    def test_getStep(self):
        self.assertEqual(self.logfile.getStep(), self.build_step_status)

    def test_isFinished(self):
        self.assertTrue(self.logfile.isFinished())

    def test_waitUntilFinished(self):
        d = self.logfile.waitUntilFinished()
        return d

    def test_getText(self):
        self.assertEqual(self.logfile.getText(), '<span>You lost the game</span>')

    def test_getTextWithHeaders(self):
        self.assertEqual(self.logfile.getTextWithHeaders(), '<span>You lost the game</span>')

    def test_getFile(self):
        fp = self.logfile.getFile()
        fp.seek(0, 0)
        self.assertEqual(fp.read(), '31:1<span>You lost the game</span>,')

        self.pickle_and_restore()

        fp = self.logfile.getFile()
        fp.seek(0, 0)
        self.assertEqual(fp.read(), '31:1<span>You lost the game</span>,')
