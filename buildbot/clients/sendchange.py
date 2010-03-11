
from twisted.spread import pb
from twisted.cred import credentials
from twisted.internet import reactor

class Sender:
    def __init__(self, master, user=None):
        self.user = user
        self.host, self.port = master.split(":")
        self.port = int(self.port)
        self.num_changes = 0

    def send(self, branch, revision, comments, files, user=None, category=None,
             when=None, properties={}, repository = '', project = ''):
        if user is None:
            user = self.user
        change = {'project': project, 'repository': repository, 'who': user,
                  'files': files, 'comments': comments, 'branch': branch,
                  'revision': revision, 'category': category, 'when': when,
                  'properties': properties}
        self.num_changes += 1

        f = pb.PBClientFactory()
        d = f.login(credentials.UsernamePassword("change", "changepw"))
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
