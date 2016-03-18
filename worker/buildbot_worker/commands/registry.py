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

from twisted.python import reflect

commandRegistry = {
    # command name : fully qualified factory name (callable)
    "shell": "buildbot_worker.commands.shell.WorkerShellCommand",
    "uploadFile": "buildbot_worker.commands.transfer.WorkerFileUploadCommand",
    "uploadDirectory": "buildbot_worker.commands.transfer.WorkerDirectoryUploadCommand",
    "downloadFile": "buildbot_worker.commands.transfer.WorkerFileDownloadCommand",
    "repo": "buildbot_worker.commands.repo.Repo",
    "mkdir": "buildbot_worker.commands.fs.MakeDirectory",
    "rmdir": "buildbot_worker.commands.fs.RemoveDirectory",
    "cpdir": "buildbot_worker.commands.fs.CopyDirectory",
    "stat": "buildbot_worker.commands.fs.StatFile",
    "glob": "buildbot_worker.commands.fs.GlobPath",
    "listdir": "buildbot_worker.commands.fs.ListDir",

    # Commands that are no longer supported
    "svn": "buildbot_worker.commands.removed.Svn",
    "bk": "buildbot_worker.commands.removed.Bk",
    "cvs": "buildbot_worker.commands.removed.Cvs",
    "darcs": "buildbot_worker.commands.removed.Darcs",
    "git": "buildbot_worker.commands.removed.Git",
    "bzr": "buildbot_worker.commands.removed.Bzr",
    "hg": "buildbot_worker.commands.removed.Hg",
    "p4": "buildbot_worker.commands.removed.P4",
    "mtn": "buildbot_worker.commands.removed.Mtn",
}


def getFactory(command):
    factory_name = commandRegistry[command]
    factory = reflect.namedObject(factory_name)
    return factory


def getAllCommandNames():
    return list(commandRegistry)
