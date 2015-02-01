import os
import stat
import tempfile

from buildbot.process import remotetransfer
from mock import Mock
from twisted.trial import unittest


# Test buildbot.steps.remotetransfer.FileWriter class.
class TestFileWriter(unittest.TestCase):

    # test FileWriter.__init__() method.

    def testInit(self):
        #
        # patch functions called in constructor
        #

        # patch os.path.exists() to always return False
        mockedExists = Mock(return_value=False)
        self.patch(os.path, "exists", mockedExists)

        # capture calls to os.makedirs()
        mockedMakedirs = Mock()
        self.patch(os, 'makedirs', mockedMakedirs)

        # capture calls to tempfile.mkstemp()
        mockedMkstemp = Mock(return_value=(7, "tmpname"))
        self.patch(tempfile, "mkstemp", mockedMkstemp)

        # capture calls to os.fdopen()
        mockedFdopen = Mock()
        self.patch(os, "fdopen", mockedFdopen)

        #
        # call _FileWriter constructor
        #
        destfile = os.path.join("dir", "file")
        remotetransfer.FileWriter(destfile, 64, stat.S_IRUSR)

        #
        # validate captured calls
        #
        absdir = os.path.dirname(os.path.abspath(os.path.join("dir", "file")))
        mockedExists.assert_called_once_with(absdir)
        mockedMakedirs.assert_called_once_with(absdir)
        mockedMkstemp.assert_called_once_with(dir=absdir)
        mockedFdopen.assert_called_once_with(7, 'wb')
