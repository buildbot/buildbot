
from zope.interface import implements
from twisted.application import service

from buildbot.interfaces import IStatusReceiver
from buildbot import util, pbutil

class StatusReceiver:
    implements(IStatusReceiver)

    def requestSubmitted(self, request):
        pass

    def requestCancelled(self, builder, request):
        pass

    def buildsetSubmitted(self, buildset):
        pass

    def builderAdded(self, builderName, builder):
        pass

    def builderChangedState(self, builderName, state):
        pass

    def buildStarted(self, builderName, build):
        pass

    def buildETAUpdate(self, build, ETA):
        pass

    def changeAdded(self, change):
        pass

    def stepStarted(self, build, step):
        pass

    def stepTextChanged(self, build, step, text):
        pass

    def stepText2Changed(self, build, step, text2):
        pass

    def stepETAUpdate(self, build, step, ETA, expectations):
        pass

    def logStarted(self, build, step, log):
        pass

    def logChunk(self, build, step, log, channel, text):
        pass

    def logFinished(self, build, step, log):
        pass

    def stepFinished(self, build, step, results):
        pass

    def buildFinished(self, builderName, build, results):
        pass

    def builderRemoved(self, builderName):
        pass

    def slaveConnected(self, slaveName):
        pass

    def slaveDisconnected(self, slaveName):
        pass

class StatusReceiverMultiService(StatusReceiver, service.MultiService,
                                 util.ComparableMixin):
    implements(IStatusReceiver)

    def __init__(self):
        service.MultiService.__init__(self)


class StatusReceiverPerspective(StatusReceiver, pbutil.NewCredPerspective):
    implements(IStatusReceiver)

