import sys
import os
from shutil import copy, rmtree
from tempfile import mkdtemp
from os.path import isfile
import traceback

from buildbot import master

class ConfigLoader(master.BuildMaster):
    def __init__(self, configFileName="master.cfg"):
        master.BuildMaster.__init__(self, ".", configFileName)
        dir = os.getcwd()
        # Use a temporary directory since loadConfig() creates a bunch of
        # directories and compiles .py files
        tempdir = mkdtemp()
        try:
            copy(configFileName, tempdir)
            for entry in os.listdir("."):
                # Any code in a subdirectory will _not_ be copied! This is a bug
                if isfile(entry):
                    copy(entry, tempdir)
        except:
            raise

        try:
            os.chdir(tempdir)
            # Add the temp directory to the library path so local modules work
            sys.path.append(tempdir)
            configFile = open(configFileName, "r")
            self.loadConfig(configFile)
        except:
            os.chdir(dir)
            rmtree(tempdir)
            raise
        os.chdir(dir)
        rmtree(tempdir)

if __name__ == '__main__':
    try:
        if len(sys.argv) > 1:
            c = ConfigLoader(sys.argv[1])
        else:
            c = ConfigLoader()
    except IOError:
        print >> sys.stderr, "Could not open config file"
        sys.exit(2)
    except:
        print >> sys.stderr, "Error in config file:"
        t, v, tb = sys.exc_info()
        print >> sys.stderr, traceback.print_exception(t, v, tb)
        sys.exit(1)
