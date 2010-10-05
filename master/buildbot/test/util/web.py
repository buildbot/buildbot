from mock import Mock

class MockRequest(Mock):
    def __init__(self, args={}):
        self.args = args
        self.site = Mock()
        self.site.buildbot_service = Mock()
        self.site.buildbot_service.master = Mock()
        self.site.buildbot_service.master.change_svc = Mock()
        Mock.__init__(self)
