from datetime import datetime

from trac.util.datefmt import utc


class Builder(object):

    def __init__(self, name, builds, slaves):
        self.name = name
        self.current = builds[0]
        self.recent = builds
        self.slaves = slaves


class Build(object):

    def __init__(self, build_results):
        for attr in ('builder_name', 'reason', 'slavename', 'results',
                     'text', 'start', 'end', 'steps', 'branch', 'revision', 'number'):
            setattr(self, attr, build_results.get(attr, 'UNDEFINED'))
        try:
            self.start = datetime.fromtimestamp(self.start, utc)
            self.end = datetime.fromtimestamp(self.end, utc)
        except Exception:
            pass

    def __str__(self):
        return 'Slave <%s>' % (self.slave)
