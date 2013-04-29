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

import os


slaveTACTemplate = ["""
import os

from twisted.application import service
from buildslave.bot import BuildSlave

basedir = r'%(basedir)s'
rotateLength = %(log-size)s
maxRotatedFiles = %(log-count)s

# if this is a relocatable tac file, get the directory containing the TAC
if basedir == '.':
    import os.path
    basedir = os.path.abspath(os.path.dirname(__file__))

# note: this line is matched against to check that this is a buildslave
# directory; do not edit it.
application = service.Application('buildslave')
""",
"""
try:
  from twisted.python.logfile import LogFile
  from twisted.python.log import ILogObserver, FileLogObserver
  logfile = LogFile.fromFullPath(os.path.join(basedir, "twistd.log"), rotateLength=rotateLength,
                                 maxRotatedFiles=maxRotatedFiles)
  application.setComponent(ILogObserver, FileLogObserver(logfile).emit)
except ImportError:
  # probably not yet twisted 8.2.0 and beyond, can't set log yet
  pass
""",
"""
buildmaster_host = '%(host)s'
port = %(port)d
slavename = '%(name)s'
passwd = '%(passwd)s'
keepalive = %(keepalive)d
usepty = %(usepty)d
umask = %(umask)s
maxdelay = %(maxdelay)d

s = BuildSlave(buildmaster_host, port, slavename, passwd, basedir,
               keepalive, usepty, umask=umask, maxdelay=maxdelay,
               allow_shutdown=%(allow-shutdown)s)
s.setServiceParent(application)

"""]


def _makeBaseDir(basedir, quiet):
    """
    Create buildslave base directory if needed.

    @param basedir: buildslave base directory relative path
    @param   quiet: if True, don't print info messages
    """
    if os.path.exists(basedir):
        if not quiet:
            print "updating existing installation"
        return

    if not quiet:
        print "mkdir", basedir

    os.mkdir(basedir)


def _makeBuildbotTac(basedir, tac_file_contents, quiet):
    """
    Create buildbot.tac file. If buildbot.tac file already exists with
    different contents, create buildbot.tac.new instead.

    @param basedir: buildslave base directory relative path
    @param tac_file_contents: contents of buildbot.tac file to write
    @param quiet: if True, don't print info messages
    """
    tacfile = os.path.join(basedir, "buildbot.tac")

    if os.path.exists(tacfile):
        oldcontents = open(tacfile, "rt").read()

        if oldcontents == tac_file_contents:
            if not quiet:
                print "buildbot.tac already exists and is correct"
            return

        if not quiet:
            print "not touching existing buildbot.tac"
            print "creating buildbot.tac.new instead"

        tacfile = os.path.join(basedir, "buildbot.tac.new")

    f = open(tacfile, "wt")
    f.write(tac_file_contents)
    f.close()
    os.chmod(tacfile, 0600)


def _makeInfoFiles(basedir, quiet):
    """
    Create info/* files inside basedir.

    @param basedir: buildslave base directory relative path
    @param   quiet: if True, don't print info messages
    """
    def createFile(path, file, contents):
        filepath = os.path.join(path, file)

        if os.path.exists(filepath):
            return False

        if not quiet:
            print "Creating info/%s, you need to edit it appropriately." % file

        open(filepath, "wt").write(contents)

        return True

    path = os.path.join(basedir, "info")
    if not os.path.exists(path):
        if not quiet:
            print "mkdir", path
        os.mkdir(path)

    # create 'info/admin' file
    created = createFile(path, "admin",
                         "Your Name Here <admin@youraddress.invalid>\n")

    # create 'info/host' file
    created = createFile(path, "host",
                         "Please put a description of this build host here\n")

    access_uri = os.path.join(path, "access_uri")

    if not os.path.exists(access_uri):
        if not quiet:
            print "Not creating info/access_uri - add it if you wish"

    if created and not quiet:
        print "Please edit the files in %s appropriately." % path


def createSlave(config):
    basedir = config['basedir']
    quiet = config['quiet']

    if config['relocatable']:
        config['basedir'] = '.'

    asd = config['allow-shutdown']
    if asd:
        config['allow-shutdown'] = "'%s'" % asd

    if config['no-logrotate']:
        slaveTAC = "".join([slaveTACTemplate[0]] + slaveTACTemplate[2:])
    else:
        slaveTAC = "".join(slaveTACTemplate)
    contents = slaveTAC % config

    _makeBaseDir(basedir, quiet)
    _makeBuildbotTac(basedir, contents, quiet)
    _makeInfoFiles(basedir, quiet)

    if not quiet:
        print "buildslave configured in %s" % basedir

    return 0
