# Import this module and call the monkeypatch() method to add a bunch of useful
# Twisted monkeypatches that help to catch stupid errors.

def monkeypatch_startService():
    from twisted.application.service import Service
    old_startService = Service.startService
    old_stopService = Service.stopService
    def startService(self):
        assert not self.running
        return old_startService(self)
    def stopService(self):
        assert self.running
        return old_stopService(self)
    Service.startService = startService
    Service.stopService = stopService

def monkeypatch():
    monkeypatch_startService()
