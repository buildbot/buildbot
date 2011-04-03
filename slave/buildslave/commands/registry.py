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
    "shell" : "buildslave.commands.shell.SlaveShellCommand",
    "uploadFile" : "buildslave.commands.transfer.SlaveFileUploadCommand",
    "uploadDirectory" : "buildslave.commands.transfer.SlaveDirectoryUploadCommand",
    "downloadFile" : "buildslave.commands.transfer.SlaveFileDownloadCommand",
    "svn" : "buildslave.commands.svn.SVN",
    "bk" : "buildslave.commands.bk.BK",
    "cvs" : "buildslave.commands.cvs.CVS",
    "darcs" : "buildslave.commands.darcs.Darcs",
    "git" : "buildslave.commands.git.Git",
    "repo" : "buildslave.commands.repo.Repo",
    "bzr" : "buildslave.commands.bzr.Bzr",
    "hg" : "buildslave.commands.hg.Mercurial",
    "p4" : "buildslave.commands.p4.P4",
    "p4sync" : "buildslave.commands.p4.P4Sync",
    "mtn" : "buildslave.commands.mtn.Monotone",
    "mkdir" : "buildslave.commands.fs.MakeDirectory",
    "rmdir" : "buildslave.commands.fs.RemoveDirectory",
    "cpdir" : "buildslave.commands.fs.CopyDirectory",
    "stat" : "buildslave.commands.fs.StatFile",
}

def getFactory(command):
    factory_name = commandRegistry[command]
    factory = reflect.namedObject(factory_name)
    return factory

def getAllCommandNames():
    return commandRegistry.keys()
