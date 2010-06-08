import pprint

class FakeSlaveBuilder:
    """
    Simulates a SlaveBuilder, but just records the updates from sendUpdate
    in its updates attribute.  Call show() to get a pretty-printed string
    showing the updates.  Set debug to True to show updates as they happen.
    """
    debug = False
    def __init__(self, usePTY=False, basedir="."):
        self.updates = []
        self.basedir = basedir
        self.usePTY = usePTY

    def sendUpdate(self, data):
        if self.debug:
            print "FakeSlaveBuilder.sendUpdate", data
        self.updates.append(data)

    def show(self):
        return pprint.pformat(self.updates)

