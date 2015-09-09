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
    "shell": "buildworker.commands.shell.WorkerShellCommand",
    "uploadFile": "buildworker.commands.transfer.WorkerFileUploadCommand",
    "uploadDirectory": "buildworker.commands.transfer.WorkerDirectoryUploadCommand",
    "downloadFile": "buildworker.commands.transfer.WorkerFileDownloadCommand",
    "repo": "buildworker.commands.repo.Repo",
    "mkdir": "buildworker.commands.fs.MakeDirectory",
    "rmdir": "buildworker.commands.fs.RemoveDirectory",
    "cpdir": "buildworker.commands.fs.CopyDirectory",
    "stat": "buildworker.commands.fs.StatFile",
    "glob": "buildworker.commands.fs.GlobPath",
    "listdir": "buildworker.commands.fs.ListDir",

    # Commands that are no longer supported
    "svn": "buildworker.commands.removed.Svn",
    "bk": "buildworker.commands.removed.Bk",
    "cvs": "buildworker.commands.removed.Cvs",
    "darcs": "buildworker.commands.removed.Darcs",
    "git": "buildworker.commands.removed.Git",
    "bzr": "buildworker.commands.removed.Bzr",
    "hg": "buildworker.commands.removed.Hg",
    "p4": "buildworker.commands.removed.P4",
    "mtn": "buildworker.commands.removed.Mtn",
}


def getFactory(command):
    factory_name = commandRegistry[command]
    factory = reflect.namedObject(factory_name)
    return factory


def getAllCommandNames():
    return list(commandRegistry)
