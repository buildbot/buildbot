from buildbot.util import now, safeTranslate


class BuilderConfig:
    """

    Used in config files to specify a builder - this can be subclassed by users
    to add extra config args, set defaults, or whatever.  It is converted to a
    dictionary for consumption by the buildmaster at config time.

    """

    def __init__(self,
                name=None,
                slavename=None,
                slavenames=None,
                builddir=None,
                slavebuilddir=None,
                factory=None,
                category=None,
                nextSlave=None,
                nextBuild=None,
                locks=None,
                env=None):

        # name is required, and can't start with '_'
        if not name or type(name) is not str:
            raise ValueError("builder's name is required")
        if name[0] == '_':
            raise ValueError("builder names must not start with an "
                             "underscore: " + name)
        self.name = name

        # factory is required
        if factory is None:
            raise ValueError("builder's factory is required")
        self.factory = factory

        # slavenames can be a single slave name or a list, and should also
        # include slavename, if given
        if type(slavenames) is str:
            slavenames = [ slavenames ]
        if slavenames:
            if type(slavenames) is not list:
                raise TypeError("slavenames must be a list or a string")
        else:
            slavenames = []
        if slavename:
            if type(slavename) != str:
                raise TypeError("slavename must be a string")
            slavenames = slavenames + [ slavename ]
        if not slavenames:
            raise ValueError("at least one slavename is required")
        self.slavenames = slavenames

        # builddir defaults to name
        if builddir is None:
            builddir = safeTranslate(name)
        self.builddir = builddir

        # slavebuilddir defaults to builddir
        if slavebuilddir is None:
            slavebuilddir = builddir
        self.slavebuilddir = slavebuilddir

        # remainder are optional
        self.category = category
        self.nextSlave = nextSlave
        self.nextBuild = nextBuild
        self.locks = locks
        self.env = env

    def getConfigDict(self):
        rv = {
            'name': self.name,
            'slavenames': self.slavenames,
            'factory': self.factory,
            'builddir': self.builddir,
            'slavebuilddir': self.slavebuilddir,
        }
        if self.category:
            rv['category'] = self.category
        if self.nextSlave:
            rv['nextSlave'] = self.nextSlave
        if self.nextBuild:
            rv['nextBuild'] = self.nextBuild
        if self.locks:
            rv['locks'] = self.locks
        if self.env:
            rv['env'] = self.env
        return rv
