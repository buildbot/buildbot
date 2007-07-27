
from buildbot.util import ComparableMixin

class BuildSlave(ComparableMixin):
    compare_attrs = ["name", "password"]

    def __init__(self, name, password):
        self.name = name
        self.password = password

