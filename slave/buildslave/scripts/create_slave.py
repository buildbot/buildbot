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
import re


class Maker:
    def __init__(self, config):
        self.config = config
        self.basedir = config['basedir']
        self.force = config.get('force', False)
        self.quiet = config['quiet']

    def mkdir(self):
        if os.path.exists(self.basedir):
            if not self.quiet:
                print "updating existing installation"
            return
        if not self.quiet:
            print "mkdir", self.basedir
        os.mkdir(self.basedir)

    def mkinfo(self):
        path = os.path.join(self.basedir, "info")
        if not os.path.exists(path):
            if not self.quiet:
                print "mkdir", path
            os.mkdir(path)
        created = False
        admin = os.path.join(path, "admin")
        if not os.path.exists(admin):
            if not self.quiet:
                print "Creating info/admin, you need to edit it appropriately"
            f = open(admin, "wt")
            f.write("Your Name Here <admin@youraddress.invalid>\n")
            f.close()
            created = True
        host = os.path.join(path, "host")
        if not os.path.exists(host):
            if not self.quiet:
                print "Creating info/host, you need to edit it appropriately"
            f = open(host, "wt")
            f.write("Please put a description of this build host here\n")
            f.close()
            created = True
        access_uri = os.path.join(path, "access_uri")
        if not os.path.exists(access_uri):
            if not self.quiet:
                print "Not creating info/access_uri - add it if you wish"
        if created and not self.quiet:
            print "Please edit the files in %s appropriately." % path

    def chdir(self):
        if not self.quiet:
            print "chdir", self.basedir
        os.chdir(self.basedir)

    def makeTAC(self, contents, secret=False):
        tacfile = "buildbot.tac"
        if os.path.exists(tacfile):
            oldcontents = open(tacfile, "rt").read()
            if oldcontents == contents:
                if not self.quiet:
                    print "buildbot.tac already exists and is correct"
                return
            if not self.quiet:
                print "not touching existing buildbot.tac"
                print "creating buildbot.tac.new instead"
            tacfile = "buildbot.tac.new"
        f = open(tacfile, "wt")
        f.write(contents)
        f.close()
        if secret:
            os.chmod(tacfile, 0600)

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


def createSlave(config):
    m = Maker(config)
    m.mkdir()
    m.chdir()
    if config['relocatable']:
        config['basedir'] = '.'
    try:
        master = config['master']
        port = None
        host, port = re.search(r'^([^:]+)(?:[:](\d+))?', master).groups()
        if port == None:
            port = '9989'
        config['host'] = host
        config['port'] = int(port)
    except:
        print "unparseable master location '%s'" % master
        print " expecting something more like localhost:8007 or localhost"
        return 1

    asd = config['allow-shutdown']
    if asd:
        config['allow-shutdown'] = "'%s'" % asd

    if config['no-logrotate']:
        slaveTAC = "".join([slaveTACTemplate[0]] + slaveTACTemplate[2:])
    else:
        slaveTAC = "".join(slaveTACTemplate)
    contents = slaveTAC % config

    m.makeTAC(contents, secret=True)
    m.mkinfo()

    if not m.quiet:
        print "buildslave configured in %s" % m.basedir

    return 0
