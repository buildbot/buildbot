from buildbot.reporters.authz import Authz


class IrcAuthz(Authz):

    def __init__(self, allowOnlyOps=True):
        self.channelUsers = {}
        self.tmpChannelUsers = {}
        self.allowOnlyOps = allowOnlyOps

    def addUserstoChannel(self, nicklist, channel):
        self.tmpChannelUsers.setdefault(channel, default=[])
        n = self.tmpChannelUsers[channel]
        n += nicklist

    def finalizeAddUsersToChannel(self, channel):
        self.tmpChannelUsers.setdefault(channel, default=[])

        self.channelUsers[channel] = self.tmpChannelUsers[channel]
        del self.tmpChannelUsers[channel]

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
