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

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from buildbot_worker.scripts.base import Options

workerTACTemplate = [
    """
import os

from buildbot_worker.bot import Worker
from twisted.application import service

basedir = %(basedir)r
rotateLength = %(log-size)d
maxRotatedFiles = %(log-count)s

# if this is a relocatable tac file, get the directory containing the TAC
if basedir == '.':
    import os.path
    basedir = os.path.abspath(os.path.dirname(__file__))

# note: this line is matched against to check that this is a worker
# directory; do not edit it.
application = service.Application('buildbot-worker')
""",
    """
from twisted.python.logfile import LogFile
from twisted.python.log import ILogObserver, FileLogObserver
logfile = LogFile.fromFullPath(
    os.path.join(basedir, "twistd.log"), rotateLength=rotateLength,
    maxRotatedFiles=maxRotatedFiles)
application.setComponent(ILogObserver, FileLogObserver(logfile).emit)
""",
    """
buildmaster_host = %(host)r
port = %(port)d
connection_string = None
""",
    """
buildmaster_host = None  # %(host)r
port = None  # %(port)d
connection_string = %(connection-string)r
""",
    """
workername = %(name)r
passwd = %(passwd)r
keepalive = %(keepalive)d
umask = %(umask)s
maxdelay = %(maxdelay)d
numcpus = %(numcpus)s
allow_shutdown = %(allow-shutdown)r
maxretries = %(maxretries)s
use_tls = %(use-tls)s
delete_leftover_dirs = %(delete-leftover-dirs)s
proxy_connection_string = %(proxy-connection-string)r
protocol = %(protocol)r

s = Worker(buildmaster_host, port, workername, passwd, basedir,
           keepalive, umask=umask, maxdelay=maxdelay,
           numcpus=numcpus, allow_shutdown=allow_shutdown,
           maxRetries=maxretries, protocol=protocol, useTls=use_tls,
           delete_leftover_dirs=delete_leftover_dirs,
           connection_string=connection_string,
           proxy_connection_string=proxy_connection_string)
s.setServiceParent(application)
""",
]


class CreateWorkerError(Exception):
    """
    Raised on errors while setting up worker directory.
    """


def _make_tac(config: Options) -> str:
    if config['relocatable']:
        config['basedir'] = '.'

    workerTAC = [workerTACTemplate[0]]

    if not config['no-logrotate']:
        workerTAC.append(workerTACTemplate[1])

    if not config['connection-string']:
        workerTAC.append(workerTACTemplate[2])
    else:
        workerTAC.append(workerTACTemplate[3])

    workerTAC.extend(workerTACTemplate[4:])

    return "".join(workerTAC) % config


def _makeBaseDir(basedir: str, quiet: bool) -> None:
    """
    Make worker base directory if needed.

    @param basedir: worker base directory relative path
    @param   quiet: if True, don't print info messages

    @raise CreateWorkerError: on error making base directory
    """
    if os.path.exists(basedir):
        if not quiet:
            print("updating existing installation")
        return

    if not quiet:
        print("mkdir", basedir)

    try:
        os.mkdir(basedir)
    except OSError as exception:
        raise CreateWorkerError(f"error creating directory {basedir}") from exception


def _makeBuildbotTac(basedir: str, tac_file_contents: str, quiet: bool) -> None:
    """
    Create buildbot.tac file. If buildbot.tac file already exists with
    different contents, create buildbot.tac.new instead.

    @param basedir: worker base directory relative path
    @param tac_file_contents: contents of buildbot.tac file to write
    @param quiet: if True, don't print info messages

    @raise CreateWorkerError: on error reading or writing tac file
    """
    tacfile = os.path.join(basedir, "buildbot.tac")

    if os.path.exists(tacfile):
        try:
            with open(tacfile) as f:
                oldcontents = f.read()
        except OSError as exception:
            raise CreateWorkerError(f"error reading {tacfile}") from exception

        if oldcontents == tac_file_contents:
            if not quiet:
                print("buildbot.tac already exists and is correct")
            return

        if not quiet:
            print("not touching existing buildbot.tac")
            print("creating buildbot.tac.new instead")

        tacfile = os.path.join(basedir, "buildbot.tac.new")

    try:
        with open(tacfile, "w") as f:
            f.write(tac_file_contents)
        os.chmod(tacfile, 0o600)
    except OSError as exception:
        raise CreateWorkerError(f"could not write {tacfile}") from exception


def _makeInfoFiles(basedir: str, quiet: bool) -> None:
    """
    Create info/* files inside basedir.

    @param basedir: worker base directory relative path
    @param   quiet: if True, don't print info messages

    @raise CreateWorkerError: on error making info directory or
                             writing info files
    """

    def createFile(path: str, file: str, contents: str) -> bool:
        filepath = os.path.join(path, file)

        if os.path.exists(filepath):
            return False

        if not quiet:
            print(
                "Creating {}, you need to edit it appropriately.".format(os.path.join("info", file))
            )

        try:
            open(filepath, "w").write(contents)
        except OSError as exception:
            raise CreateWorkerError(f"could not write {filepath}") from exception
        return True

    path = os.path.join(basedir, "info")
    if not os.path.exists(path):
        if not quiet:
            print("mkdir", path)
        try:
            os.mkdir(path)
        except OSError as exception:
            raise CreateWorkerError(f"error creating directory {path}") from exception

    # create 'info/admin' file
    created = createFile(path, "admin", "Your Name Here <admin@youraddress.invalid>\n")

    # create 'info/host' file
    created = createFile(path, "host", "Please put a description of this build host here\n")

    access_uri = os.path.join(path, "access_uri")

    if not os.path.exists(access_uri):
        if not quiet:
            print("Not creating {} - add it if you wish".format(os.path.join("info", "access_uri")))

    if created and not quiet:
        print(f"Please edit the files in {path} appropriately.")


def createWorker(config: Options) -> int:
    basedir = config['basedir']
    quiet = config['quiet']

    contents = _make_tac(config)

    try:
        _makeBaseDir(basedir, quiet)
        _makeBuildbotTac(basedir, contents, quiet)
        _makeInfoFiles(basedir, quiet)
    except CreateWorkerError as exception:
        print("{}\nfailed to configure worker in {}".format(exception, config['basedir']))
        return 1

    if not quiet:
        print(f"worker configured in {basedir}")

    return 0
