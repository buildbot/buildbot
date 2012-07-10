from twisted.internet import defer

class StateMixin(object):
    ## state management

    _objectid = None

    @defer.inlineCallbacks
    def getState(self, *args, **kwargs):
        # get the objectid, if not known
        if self._objectid is None:
            self._objectid = yield self.master.db.state.getObjectId(self.name,
                                                    self.__class__.__name__)

        rv = yield self.master.db.state.getState(self._objectid, *args,
                                                                    **kwargs)
        defer.returnValue(rv)

    @defer.inlineCallbacks
    def setState(self, key, value):
        # get the objectid, if not known
        if self._objectid is None:
            self._objectid = yield self.master.db.state.getObjectId(self.name,
                                                self.__class__.__name__)

        yield self.master.db.state.setState(self._objectid, key, value)
