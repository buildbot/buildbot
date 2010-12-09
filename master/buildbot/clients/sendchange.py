
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
        if self.num_changes > 1:
            print "%d changes sent successfully" % self.num_changes
        elif self.num_changes == 1:
            print "change sent successfully"
        else:
            print "no changes to send"

    def printFailure(self, why):
        print "change(s) NOT sent, something went wrong:"
        print why

    def stop(self, res):
        reactor.stop()
        return res

    def run(self):
        reactor.run()
