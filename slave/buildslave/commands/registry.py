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
    "bzr" : "buildslave.commands.bzr.Bzr",
    "hg" : "buildslave.commands.hg.Mercurial",
    "p4" : "buildslave.commands.p4.P4",
    "p4sync" : "buildslave.commands.p4.P4Sync",
    "mkdir" : "buildslave.commands.fs.MakeDirectory",
    "rmdir" : "buildslave.commands.fs.RemoveDirectory",
    "cpdir" : "buildslave.commands.fs.CopyDirectory",
}

def getFactory(command):
    factory_name = commandRegistry[command]
    factory = reflect.namedObject(factory_name)
    return factory

def getAllCommandNames():
    return commandRegistry.keys()
