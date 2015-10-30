from buildbot.reporters.authz import Authz


class IrcAuthz(Authz):

    def __init__(self, allowOnlyOps=True):
        self.channelUsers = {}
        self.allowOnlyOps = allowOnlyOps

    def addUserstoChannel(self, nicklist, channel):
        if '%s-tmp' % channel not in self.channelUsers:
            self.channelUsers['%s-tmp' % channel] = []
        n = self.channelUsers['%s-tmp' % channel]
        n += nicklist

    def finalizeAddUsersToChannel(self, channel):
        if '%s-tmp' % channel not in self.channelUsers:
            return

        self.channelUsers[channel] = self.channelUsers['%s-tmp' % channel]
        del self.channelUsers['%s-tmp' % channel]

    def assertAllowPM(self):
        if self.allowOnlyOps:
            return False
        else:
            return True

    def assertUserAllowed(self, user, channel):
        if self.allowOnlyOps:
            return '@%s' % user not in self.channelUsers[channel]
        else:
            return True
