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

import re
import xml.dom.minidom
import xml.parsers.expat
import os


from twisted.python import log
from twisted.internet import defer

from buildbot.process import buildstep
from buildbot.steps.source import Source
from zope.interface import implements
from buildbot.interfaces import BuildSlaveTooOldError, IRenderable
from buildbot.process.properties import WithProperties


"""
Notes:
    see  for getting p4 command to output
    marshalled python dictionaries as output for commands
    """
    


class P4(Source):
    """Perform Perforce checkout/update operations."""

    name = 'p4'

    renderables = [ 'p4base', 'p4client','p4viewspec', 'p4branch' ]
    possible_modes = ('incremental', 'full')
    
    def __init__(self, mode='incremental',
                 method=None,p4base=None, p4branch=None,
                 p4port=None, p4user=None,
                 p4passwd=None, p4extra_views=[], p4line_end='local',
                 p4viewspec=None,
                 p4client='buildbot_%(slave)s_%(builder)s',p4bin='p4',
                  **kwargs):
        """
        @type  p4base: string
        @param p4base: A view into a perforce depot, typically
                       "//depot/proj/"
                       
        @type  p4branch: string
        @param p4branch: A single string, which is appended to the p4base as follows
                        "<p4base><p4branch>/..." 
                        to form the first line in the viewspec

        @type  p4extra_views: list of tuples
        @param p4extra_views: Extra views to be added to the client that is being used.

        @type  p4viewspec: list of tuples
        @param p4viewspec: This will override any p4branch, p4base, and/or p4extra_views
                           specified.  The viewspec will be an array of tuples as follows
                           [('//depot/main/','')]  yields a viewspec with just
                           //depot/main/... //<p4client>/...

        @type  p4port: string
        @param p4port: Specify the perforce server to connection in the format
                       <host>:<port>. Example "perforce.example.com:1666"

        @type  p4user: string
        @param p4user: The perforce user to run the command as.

        @type  p4passwd: string
        @param p4passwd: The password for the perforce user.

        @type  p4line_end: string
        @param p4line_end: value of the LineEnd client specification property

        @type  p4client: string
        @param p4client: The perforce client to use for this buildslave.
        """

        self.method = method
        self.mode   = mode
        self.p4branch = defaultBranch
        self.p4bin  = p4bin
        self.p4base = p4base
        self.p4port = p4port
        self.p4user = p4user
        self.p4passwd = p4passwd
        self.p4extra_views = p4extra_views
        self.p4viewspec = p4viewspec
        self.p4line_end = p4line_end
        self.p4client = p4client
        log.msg("P4 client:%s",self.p4client)
                
        Source.__init__(self, **kwargs)
        
        self.addFactoryArguments(mode = mode,
                                 method = method,
                                 p4bin = p4bin,
                                 p4base=p4base,
                                 defaultBranch=defaultBranch,
                                 p4port=p4port,
                                 p4user=p4user,
                                 p4passwd=p4passwd,
                                 p4extra_views=p4extra_views,
                                 p4viewspec=p4viewspec,
                                 p4line_end=p4line_end,
                                 p4client=p4client,
                                 )
        self.p4client = p4client
        
        errors = []
        if self.mode not in self.possible_modes:
            errors.append("mode %s is not one of %s" % (self.mode, self.possible_modes))

        if not p4viewspec and p4base is None:
            errors.append("you must provide p4base")

        if errors:
            raise ValueError(errors)

    def startVC(self, branch, revision, patch):
        log.msg('in startVC')
        self.revision = revision
        self.method = self._getMethod()
        self.stdio_log = self.addLog("stdio")

        d = self.checkP4()
        def checkInstall(p4Installed):
            if not p4Installed:
                raise BuildSlaveTooOldError("p4 is not installed on slave")
            return 0
        d.addCallback(checkInstall)

        if self.mode == 'full':
            d.addCallback(self.full)
        elif self.mode == 'incremental':
            d.addCallback(self.incremental)

        d.addCallback(self.parseGotRevision)
        d.addCallback(self.finish)
        d.addErrback(self.failed)
        return d

    

    @defer.inlineCallbacks
    def full(self, _):
        
        # First we need to create the client
        yield self._createClientSpec()
        
        # Then we need to sync the client
        if self.revision:
            yield self._dovccmd(['sync','@%d'%int(self.revision)], collectStdout=True)
        else:
            yield self._dovccmd(['sync'], collectStdout=True)


#
#        updatable = yield self._sourcedirIsUpdatable()
#        if not updatable:
#            # blow away the old (un-updatable) directory
#            yield self._rmdir(self.workdir)
#
#            # then do a checkout
#            checkout_cmd = ['checkout', self.repourl, '.']
#            if self.revision:
#                checkout_cmd.extend(["--revision", str(self.revision)])
#            yield self._dovccmd(checkout_cmd)


    @defer.inlineCallbacks
    def incremental(self, _):
        updatable = yield self._sourcedirIsUpdatable()

        if not updatable:
            # blow away the old (un-updatable) directory
            # TODO: Figure out if this makes sense for perforce..
            # yield self._rmdir(self.workdir)
            
            # First we need to create the client
            yield self._createClientSpec()


            # First we need to create the client
            yield self._createClientSpec()

            # and plan to do a checkout
            command = ['sync',]
        else:
            # otherwise, do an update
            command = ['sync',]

        if self.revision:
            command.extend(['@%s'%self.revision])

        yield self._dovccmd(command)



    def finish(self, res):
        d = defer.succeed(res)
        def _gotResults(results):
            self.setStatus(self.cmd, results)
            return results
        d.addCallback(_gotResults)
        d.addCallbacks(self.finished, self.checkDisconnect)
        return d

    @defer.inlineCallbacks
    def _rmdir(self, dir):
        cmd = buildstep.RemoteCommand('rmdir',
                {'dir': dir, 'logEnviron': self.logEnviron })
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)
        if cmd.rc != 0:
            raise buildstep.BuildStepFailed()

    def _buildVCCommand(self,doCommand):
        assert doCommand, "No command specified"

        command = [self.p4bin,]

        if self.p4port:
            command.extend(['-p', self.p4port])
        if self.p4user:
            command.extend(['-u', self.p4user])
        if self.p4passwd:
            # Need to find out if there's a way to obfuscate this
            command.extend(['-P', self.p4passwd]) 
        if self.p4client:
            command.extend(['-c', self.p4client])
            
        command.extend(doCommand)
        
        command = [c.encode('utf-8') for c in command]
        return command


    def _dovccmd(self, command, collectStdout=False,initialStdin=None):
        command = self._buildVCCommand(command)
#        if self.extra_args:
#            command.extend(self.extra_args)

        log.msg("p4:_DOVCCMD:workdir->%s"%self.workdir)
        cmd = buildstep.RemoteShellCommand(self.workdir, command,
                                           env=self.env,
                                           logEnviron=self.logEnviron,
                                           collectStdout=collectStdout,
                                           initialStdin=initialStdin,)
        cmd.useLog(self.stdio_log, False)
        log.msg("Starting p4 command : p4 %s" % (" ".join(command), ))
        log.msg("Starting p4 command : p4 %s" % command)

        d = self.runCommand(cmd)
        def evaluateCommand(cmd):
            if cmd.rc != 0:
                log.msg("Source step failed while running command %s" % cmd)
                raise buildstep.BuildStepFailed()
            if collectStdout:
                return cmd.stdout
            else:
                return cmd.rc
        d.addCallback(lambda _: evaluateCommand(cmd))
        return d

    def _getMethod(self):
        if self.method is not None and self.mode != 'incremental':
            return self.method
        elif self.mode == 'incremental':
            return None
        elif self.method is None and self.mode == 'full':
            return 'fresh'

    @defer.inlineCallbacks
    def _sourcedirIsUpdatable(self):
        # first, perform a stat to ensure that this is really an p4 directory
        cmd = buildstep.RemoteCommand('stat', {'file': self.workdir + '/.p4',
                                               'logEnviron': self.logEnviron,})
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        if cmd.rc != 0:
            defer.returnValue(False)
            return

        # then run 'p4 info' to check that the URL matches our repourl
        stdout = yield self._dovccmd(['info'], collectStdout=True)

        # extract the URL, handling whitespace carefully so that \r\n works
        # is a line terminator
        mo = re.search('^URL:\s*(.*?)\s*$', stdout, re.M)
        defer.returnValue(mo and mo.group(1) == self.repourl)
        return
    
       
    @defer.inlineCallbacks
    def _createClientSpec(self):
        workdir=self.getProperty('workdir')
        
        log.msg("P4:_createClientSpec:WORKDIR:%s"%workdir)
        log.msg("P4:_createClientSpecSELF.workdir:%s"%self.workdir)
        
        prop_dict=self.getProperties().asDict()
        prop_dict['p4client'] = self.p4client
        
        client_spec = ''
        client_spec += "Client: %s\n\n" % self.p4client
        client_spec += "Owner: %s\n\n" % self.p4user
        client_spec += "Description:\n\tCreated by %s\n\n" % self.p4user
        
        client_spec += "Root:\t%s\n\n" % os.path.join(workdir,self.workdir) # self.workdir
        client_spec += "Options:\tallwrite rmdir\n\n"
        if self.p4line_end:
            client_spec += "LineEnd:\t%s\n\n" % self.p4line_end
        else:
            client_spec += "LineEnd:\tlocal\n\n"

        # Setup a view
        client_spec += "View:\n"
        
        
        if self.p4viewspec:
            # If the user specifies a viewspec via an array of tuples then
            # Ignore any specified p4base,p4branch, and/or p4extra_views
            for k,v in self.p4viewspec:
                log.msg('P4:_createClientSpec:key:%s value:%s'%(k,v))
                client_spec += '\t%s... //%s/%s...\n'%(k,self.p4client,v)
        else:  
            client_spec += "\t%s" % (self.p4base)

            if self.p4branch:
                client_spec += "%s/" % (self.p4branch)
                client_spec += "... //%s/...\n" % (self.p4client)
                
            if self.p4extra_views:
                for k, v in self.p4extra_views:
                    client_spec += "\t%s/... //%s/%s/...\n" % (k, self.p4client, v)
                    
        client_spec = client_spec.encode('utf-8') # resolve unicode issues
        log.msg(client_spec)
        
        stdout = yield self._dovccmd(['client','-i'], collectStdout=True, initialStdin=client_spec)
        mo = re.search('Client (\S+) (.+)$',stdout,re.M)
        defer.returnValue(mo and (mo.group(2) == 'saved.' or mo.group(2) == 'not changed.'))


#    @defer.inlineCallbacks
    def parseGotRevision(self, _):
        command = self._buildVCCommand(['changes','-m1','#have'])
        
        cmd = buildstep.RemoteShellCommand(self.workdir, command,
                                           env=self.env,
                                           logEnviron=self.logEnviron,
                                           collectStdout=True)
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def _setrev(_):
            stdout = cmd.stdout.strip()
            # Example output from p4 changes -m1 #have
            #     Change 212798 on 2012/04/13 by bdeegan@bdeegan-unix-bldng2 'change to pickup buildspecs fro'
            revision = stdout.split()[1]
            try:
                int(revision)
            except ValueError:
                msg =("p4.parseGotRevision unable to parse output "
                      "of 'p4 changes -m1 \"#have\"': '%s'" % stdout)
                log.msg(msg)
                raise buildstep.BuildStepFailed()

            log.msg("Got p4 revision %s" % (revision, ))
            self.setProperty('got_revision', revision, 'Source')
            return 0
        d.addCallback(lambda _: _setrev(cmd.rc))
        return d

    def purge(self, ignore_ignores):
        """Delete everything that shown up on status."""
        command = ['sync', '#none']
        if ignore_ignores:
            command.append('--no-ignore')
        d = self._dovccmd(command, collectStdout=True)
        
        # add deferred to rm tree
        
        # then add defer to sync to revision
        return d


    def checkP4(self):
        cmd = buildstep.RemoteShellCommand(self.workdir, ['p4', '-V'],
                                           env=self.env,
                                           logEnviron=self.logEnviron)
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def evaluate(cmd):
            if cmd.rc != 0:
                return False
            return True
        d.addCallback(lambda _: evaluate(cmd))
        return d

    def computeSourceRevision(self, changes):
        if not changes or None in [c.revision for c in changes]:
            return None
        lastChange = max([int(c.revision) for c in changes])
        return lastChange
    
