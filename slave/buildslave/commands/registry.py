from twisted.python import reflect

commandRegistry = {
    # command name : fully qualified factory name (callable)
    "shell" : "buildslave.commands.shell.SlaveShellCommand",
    "uploadFile" : "buildslave.commands.transfer.SlaveFileUploadCommand",
    "uploadDirectory" : "buildslave.commands.transfer.SlaveDirectoryUploadCommand",
    "downloadFile" : "buildslave.commands.transfer.SlaveFileDownloadCommand",
    "svn" : "buildslave.commands.svn.SVN",
    "bk" : "buildslave.commands.bk.BK",
    "cvs" : "buildslave.commands.vcs.CVS",
    "svn" : "buildslave.commands.vcs.SVN",
    "darcs" : "buildslave.commands.vcs.Darcs",
    "monotone" : "buildslave.commands.vcs.Monotone",
    "git" : "buildslave.commands.vcs.Git",
    "arch" : "buildslave.commands.vcs.Arch",
    "bazaar" : "buildslave.commands.vcs.Bazaar",
    "bzr" : "buildslave.commands.vcs.Bzr",
    "hg" : "buildslave.commands.vcs.Mercurial",
    "p4" : "buildslave.commands.vcs.P4",
    "p4sync" : "buildslave.commands.vcs.P4Sync",
}

def getFactory(command):
    factory_name = commandRegistry[command]
    factory = reflect.namedObject(factory_name)
    return factory

def getAllCommandNames():
    return commandRegistry.keys()
