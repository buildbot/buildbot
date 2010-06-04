import sys
import os
from shutil import copy, rmtree
from tempfile import mkdtemp
from os.path import isfile

from buildbot import master

class ConfigLoader(master.BuildMaster):
    def __init__(self, basedir=os.getcwd(), configFileName="master.cfg"):
        master.BuildMaster.__init__(self, basedir, configFileName)
        configFileName = os.path.join(basedir, configFileName)
        dir = os.getcwd()
        # Use a temporary directory since loadConfig() creates a bunch of
        # directories and compiles .py files
        tempdir = mkdtemp()
        try:
            copy(configFileName, tempdir)
            for entry in os.listdir("."):
                # Any code in a subdirectory will _not_ be copied! This is a bug
                if isfile(entry) and not entry.startswith("twistd.log"):
                    copy(entry, tempdir)
        except:
            raise

        try:
            os.chdir(tempdir)
            # Add the temp directory to the library path so local modules work
            sys.path.append(tempdir)
            configFile = open(configFileName, "r")
            self.loadConfig(configFile, check_synchronously_only=True)
        except:
            os.chdir(dir)
            configFile.close()
            rmtree(tempdir)
            raise
        os.chdir(dir)
        rmtree(tempdir)
