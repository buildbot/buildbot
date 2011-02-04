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


from twisted.spread import pb
from twisted.cred import credentials
from twisted.internet import reactor

class Sender:
    def __init__(self, master, auth=('change','changepw')):
        self.username, self.password = auth
        self.host, self.port = master.split(":")
        self.port = int(self.port)
        self.num_changes = 0

    def send(self, branch, revision, comments, files, who=None, category=None,
             when=None, properties={}, repository='', project='', revlink=''):
        change = {'project': project, 'repository': repository, 'who': who,
                  'files': files, 'comments': comments, 'branch': branch,
                  'revision': revision, 'category': category, 'when': when,
                  'properties': properties, 'revlink': revlink}
        self.num_changes += 1

        f = pb.PBClientFactory()
        d = f.login(credentials.UsernamePassword(self.username, self.password))
        reactor.connectTCP(self.host, self.port, f)
        d.addCallback(self.addChange, change)
        return d

    def addChange(self, remote, change):
        d = remote.callRemote('addChange', change)
        d.addCallback(lambda res: remote.broker.transport.loseConnection())
        return d

    def printSuccess(self, res):
        print self.getSuccessString(res)

    def getSuccessString(self, res):
        if self.num_changes > 1:
            return "%d changes sent successfully" % self.num_changes
        elif self.num_changes == 1:
            return "change sent successfully"
        else:
            return "no changes to send"

    def printFailure(self, why):
        print self.getFailureString(why)

    def getFailureString(self, why):
        return "change(s) NOT sent, something went wrong: " + str(why)

    def stop(self, res):
        reactor.stop()
        return res

    def run(self):
        reactor.run()
