# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members


from buildbot.interfaces import BuildSlaveTooOldError
from buildbot.interfaces import IRenderable
from buildbot.process.buildstep import RemoteCommand
from buildbot.steps.source.base import Source
from email.utils import formatdate
from twisted.internet import defer
from twisted.python import log
from warnings import warn
from zope.interface import implements


class _ComputeRepositoryURL(object):
    implements(IRenderable)

    def __init__(self, step, repository):
        self.step = step
        self.repository = repository

    def getRenderingFor(self, props):
        '''
        Helper function that the repository URL based on the parameter the
        source step took and the Change 'repository' property
        '''

        build = props.getBuild()
        assert build is not None, "Build should be available *during* a build?"
        s = build.getSourceStamp(self.step.codebase)

        repository = self.repository

        if not repository:
            return str(s.repository)
        else:
            if callable(repository):
                d = props.render(repository(s.repository))
            elif isinstance(repository, dict):
                d = props.render(repository.get(s.repository))
            elif isinstance(repository, str) or isinstance(repository, unicode):
                try:
                    return str(repository % s.repository)
                except TypeError:
                    # that's the backward compatibility case
                    d = props.render(repository)
            else:
                d = props.render(repository)

        d.addCallback(str)
        return d


class SlaveSource(Source):

    def __init__(self, mode='update', retry=None, **kwargs):
        """
        @type  mode: string
        @param mode: the kind of VC operation that is desired:
           - 'update': specifies that the checkout/update should be
             performed directly into the workdir. Each build is performed
             in the same directory, allowing for incremental builds. This
             minimizes disk space, bandwidth, and CPU time. However, it
             may encounter problems if the build process does not handle
             dependencies properly (if you must sometimes do a 'clean
             build' to make sure everything gets compiled), or if source
             files are deleted but generated files can influence test
             behavior (e.g. python's .pyc files), or when source
             directories are deleted but generated files prevent CVS from
             removing them. When used with a patched checkout, from a
             previous buildbot try for instance, it will try to "revert"
             the changes first and will do a clobber if it is unable to
             get a clean checkout. The behavior is SCM-dependent.

           - 'copy': specifies that the source-controlled workspace
             should be maintained in a separate directory (called the
             'copydir'), using checkout or update as necessary. For each
             build, a new workdir is created with a copy of the source
             tree (rm -rf workdir; cp -R -P -p copydir workdir). This
             doubles the disk space required, but keeps the bandwidth low
             (update instead of a full checkout). A full 'clean' build
             is performed each time.  This avoids any generated-file
             build problems, but is still occasionally vulnerable to
             problems such as a CVS repository being manually rearranged
             (causing CVS errors on update) which are not an issue with
             a full checkout.

           - 'clobber': specifies that the working directory should be
             deleted each time, necessitating a full checkout for each
             build. This insures a clean build off a complete checkout,
             avoiding any of the problems described above, but is
             bandwidth intensive, as the whole source tree must be
             pulled down for each build.

           - 'export': is like 'clobber', except that e.g. the 'cvs
             export' command is used to create the working directory.
             This command removes all VC metadata files (the
             CVS/.svn/{arch} directories) from the tree, which is
             sometimes useful for creating source tarballs (to avoid
             including the metadata in the tar file). Not all VC systems
             support export.

        @type  retry: tuple of ints (delay, repeats) (or None)
        @param retry: if provided, VC update failures are re-attempted up
                      to REPEATS times, with DELAY seconds between each
                      attempt. Some users have slaves with poor connectivity
                      to their VC repository, and they say that up to 80% of
                      their build failures are due to transient network
                      failures that could be handled by simply retrying a
                      couple times.
        """
        Source.__init__(self, **kwargs)

        assert mode in ("update", "copy", "clobber", "export")
        if retry:
            delay, repeats = retry
            assert isinstance(repeats, int)
            assert repeats > 0
        self.args = {'mode': mode,
                     'retry': retry,
                     }

    def start(self):
        self.args['workdir'] = self.workdir
        self.args['logEnviron'] = self.logEnviron
        self.args['env'] = self.env
        self.args['timeout'] = self.timeout
        Source.start(self)

    def commandComplete(self, cmd):
        if "got_revision" not in cmd.updates:
            return
        got_revision = cmd.updates["got_revision"][-1]
        if got_revision is None:
            return

        self.updateSourceProperty('got_revision', str(got_revision))


class BK(SlaveSource):

    """I perform BitKeeper checkout/update operations."""

    name = 'bk'

    renderables = ['bkurl', 'baseURL']

    def __init__(self, bkurl=None, baseURL=None,
                 directory=None, extra_args=None, **kwargs):
        """
        @type  bkurl: string
        @param bkurl: the URL which points to the BitKeeper server.

        @type  baseURL: string
        @param baseURL: if branches are enabled, this is the base URL to
                        which a branch name will be appended. It should
                        probably end in a slash. Use exactly one of
                        C{bkurl} and C{baseURL}.
        """

        self.bkurl = _ComputeRepositoryURL(self, bkurl)
        self.baseURL = _ComputeRepositoryURL(self, baseURL)
        self.extra_args = extra_args

        Source.__init__(self, **kwargs)

        if bkurl and baseURL:
            raise ValueError("you must use exactly one of bkurl and baseURL")

    def computeSourceRevision(self, changes):
        return changes.revision

    def startVC(self, branch, revision, patch):

        warnings = []
        slavever = self.slaveVersion("bk")
        if not slavever:
            m = "slave does not have the 'bk' command"
            raise BuildSlaveTooOldError(m)

        if self.bkurl:
            assert not branch  # we need baseURL= to use branches
            self.args['bkurl'] = self.bkurl
        else:
            self.args['bkurl'] = self.baseURL + branch
        self.args['revision'] = revision
        self.args['patch'] = patch
        self.args['branch'] = branch
        if self.extra_args is not None:
            self.args['extra_args'] = self.extra_args

        revstuff = []
        revstuff.append("[branch]")
        if revision is not None:
            revstuff.append("r%s" % revision)
        if patch is not None:
            revstuff.append("[patch]")
        self.description.extend(revstuff)
        self.descriptionDone.extend(revstuff)

        cmd = RemoteCommand("bk", self.args)
        self.startCommand(cmd, warnings)


class CVS(SlaveSource):

    """I do CVS checkout/update operations.

    Note: if you are doing anonymous/pserver CVS operations, you will need
    to manually do a 'cvs login' on each buildslave before the slave has any
    hope of success. XXX: fix then, take a cvs password as an argument and
    figure out how to do a 'cvs login' on each build
    """

    name = "cvs"

    renderables = ["cvsroot"]

    # progressMetrics = ('output',)
    #
    # additional things to track: update gives one stderr line per directory
    # (starting with 'cvs server: Updating ') (and is fairly stable if files
    # is empty), export gives one line per directory (starting with 'cvs
    # export: Updating ') and another line per file (starting with U). Would
    # be nice to track these, requires grepping LogFile data for lines,
    # parsing each line. Might be handy to have a hook in LogFile that gets
    # called with each complete line.

    def __init__(self, cvsroot=None, cvsmodule="",
                 global_options=[], branch=None, checkoutDelay=None,
                 checkout_options=[], export_options=[], extra_options=[],
                 login=None,
                 **kwargs):
        """
        @type  cvsroot: string
        @param cvsroot: CVS Repository from which the source tree should
                        be obtained. '/home/warner/Repository' for local
                        or NFS-reachable repositories,
                        ':pserver:anon@foo.com:/cvs' for anonymous CVS,
                        'user@host.com:/cvs' for non-anonymous CVS or
                        CVS over ssh. Lots of possibilities, check the
                        CVS documentation for more.

        @type  cvsmodule: string
        @param cvsmodule: subdirectory of CVS repository that should be
                          retrieved

        @type  login: string or None
        @param login: if not None, a string which will be provided as a
                      password to the 'cvs login' command, used when a
                      :pserver: method is used to access the repository.
                      This login is only needed once, but must be run
                      each time (just before the CVS operation) because
                      there is no way for the buildslave to tell whether
                      it was previously performed or not.

        @type  branch: string
        @param branch: the default branch name, will be used in a '-r'
                       argument to specify which branch of the source tree
                       should be used for this checkout. Defaults to None,
                       which means to use 'HEAD'.

        @type  checkoutDelay: int or None
        @param checkoutDelay: if not None, the number of seconds to put
                              between the last known Change and the
                              timestamp given to the -D argument. This
                              defaults to exactly half of the parent
                              Build's .treeStableTimer, but it could be
                              set to something else if your CVS change
                              notification has particularly weird
                              latency characteristics.

        @type  global_options: list of strings
        @param global_options: these arguments are inserted in the cvs
                               command line, before the
                               'checkout'/'update' command word. See
                               'cvs --help-options' for a list of what
                               may be accepted here.  ['-r'] will make
                               the checked out files read only. ['-r',
                               '-R'] will also assume the repository is
                               read-only (I assume this means it won't
                               use locks to insure atomic access to the
                               ,v files).

        @type  checkout_options: list of strings
        @param checkout_options: these arguments are inserted in the cvs
                               command line, after 'checkout' but before
                               branch or revision specifiers.

        @type  export_options: list of strings
        @param export_options: these arguments are inserted in the cvs
                               command line, after 'export' but before
                               branch or revision specifiers.

        @type  extra_options: list of strings
        @param extra_options: these arguments are inserted in the cvs
                               command line, after 'checkout' or 'export' but before
                               branch or revision specifiers.
                               """

        self.checkoutDelay = checkoutDelay
        self.branch = branch
        self.cvsroot = _ComputeRepositoryURL(self, cvsroot)

        SlaveSource.__init__(self, **kwargs)

        self.args.update({'cvsmodule': cvsmodule,
                          'global_options': global_options,
                          'checkout_options': checkout_options,
                          'export_options': export_options,
                          'extra_options': extra_options,
                          'login': login,
                          })

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        lastChange = max([c.when for c in changes])
        if self.checkoutDelay is not None:
            when = lastChange + self.checkoutDelay
        else:
            lastSubmit = max([br.submittedAt for br in self.build.requests])
            when = (lastChange + lastSubmit) / 2
        return formatdate(when)

    def startVC(self, branch, revision, patch):
        if self.slaveVersionIsOlderThan("cvs", "1.39"):
            # the slave doesn't know to avoid re-using the same sourcedir
            # when the branch changes. We have no way of knowing which branch
            # the last build used, so if we're using a non-default branch and
            # either 'update' or 'copy' modes, it is safer to refuse to
            # build, and tell the user they need to upgrade the buildslave.
            if (branch != self.branch
                    and self.args['mode'] in ("update", "copy")):
                m = ("This buildslave (%s) does not know about multiple "
                     "branches, and using mode=%s would probably build the "
                     "wrong tree. "
                     "Refusing to build. Please upgrade the buildslave to "
                     "buildbot-0.7.0 or newer." % (self.build.slavename,
                                                   self.args['mode']))
                log.msg(m)
                raise BuildSlaveTooOldError(m)

        if self.slaveVersionIsOlderThan("cvs", "2.10"):
            if self.args['extra_options'] or self.args['export_options']:
                m = ("This buildslave (%s) does not support export_options "
                     "or extra_options arguments to the CVS step."
                     % (self.build.slavename))
                log.msg(m)
                raise BuildSlaveTooOldError(m)
            # the unwanted args are empty, and will probably be ignored by
            # the slave, but delete them just to be safe
            del self.args['export_options']
            del self.args['extra_options']

        if branch is None:
            branch = "HEAD"
        self.args['cvsroot'] = self.cvsroot
        self.args['branch'] = branch
        self.args['revision'] = revision
        self.args['patch'] = patch

        if self.args['branch'] == "HEAD" and self.args['revision']:
            # special case. 'cvs update -r HEAD -D today' gives no files
            # TODO: figure out why, see if it applies to -r BRANCH
            self.args['branch'] = None

        # deal with old slaves
        warnings = []
        slavever = self.slaveVersion("cvs", "old")

        if slavever == "old":
            # 0.5.0
            if self.args['mode'] == "export":
                self.args['export'] = 1
            elif self.args['mode'] == "clobber":
                self.args['clobber'] = 1
            elif self.args['mode'] == "copy":
                self.args['copydir'] = "source"
            self.args['tag'] = self.args['branch']
            assert not self.args['patch']  # 0.5.0 slave can't do patch

        cmd = RemoteCommand("cvs", self.args)
        self.startCommand(cmd, warnings)


class SVN(SlaveSource):

    """I perform Subversion checkout/update operations."""

    name = 'svn'
    branch_placeholder = '%%BRANCH%%'

    renderables = ['svnurl', 'baseURL']

    def __init__(self, svnurl=None, baseURL=None, defaultBranch=None,
                 directory=None, username=None, password=None,
                 extra_args=None, keep_on_purge=None, ignore_ignores=None,
                 always_purge=None, depth=None, **kwargs):
        """
        @type  svnurl: string
        @param svnurl: the URL which points to the Subversion server,
                       combining the access method (HTTP, ssh, local file),
                       the repository host/port, the repository path, the
                       sub-tree within the repository, and the branch to
                       check out. Use exactly one of C{svnurl} and C{baseURL}.

        @param baseURL: if branches are enabled, this is the base URL to
                        which a branch name will be appended. It should
                        probably end in a slash. Use exactly one of
                        C{svnurl} and C{baseURL}.

        @param defaultBranch: if branches are enabled, this is the branch
                              to use if the Build does not specify one
                              explicitly. It will simply be appended
                              to C{baseURL} and the result handed to
                              the SVN command.

        @type  username: string
        @param username: username to pass to svn's --username

        @type  password: string
        @param password: password to pass to svn's --password
        """

        if 'workdir' not in kwargs and directory is not None:
            # deal with old configs
            warn("Please use workdir=, not directory=", DeprecationWarning)
            kwargs['workdir'] = directory

        self.svnurl = svnurl and _ComputeRepositoryURL(self, svnurl)
        self.baseURL = _ComputeRepositoryURL(self, baseURL)
        self.branch = defaultBranch
        self.username = username
        self.password = password
        self.extra_args = extra_args
        self.keep_on_purge = keep_on_purge
        self.ignore_ignores = ignore_ignores
        self.always_purge = always_purge
        self.depth = depth

        SlaveSource.__init__(self, **kwargs)

        if svnurl and baseURL:
            raise ValueError("you must use either svnurl OR baseURL")

    def computeSourceRevision(self, changes):
        if not changes or None in [c.revision for c in changes]:
            return None
        lastChange = max([int(c.revision) for c in changes])
        return lastChange

    def checkCompatibility(self):
        ''' Handle compatibility between old slaves/svn clients '''

        slavever = self.slaveVersion("svn", "old")

        if not slavever:
            m = "slave does not have the 'svn' command"
            raise BuildSlaveTooOldError(m)

        if self.slaveVersionIsOlderThan("svn", "1.39"):
            # the slave doesn't know to avoid re-using the same sourcedir
            # when the branch changes. We have no way of knowing which branch
            # the last build used, so if we're using a non-default branch and
            # either 'update' or 'copy' modes, it is safer to refuse to
            # build, and tell the user they need to upgrade the buildslave.
            if (self.args['branch'] != self.branch
                    and self.args['mode'] in ("update", "copy")):
                m = ("This buildslave (%s) does not know about multiple "
                     "branches, and using mode=%s would probably build the "
                     "wrong tree. "
                     "Refusing to build. Please upgrade the buildslave to "
                     "buildbot-0.7.0 or newer." % (self.build.slavename,
                                                   self.args['mode']))
                raise BuildSlaveTooOldError(m)

        if (self.depth is not None) and self.slaveVersionIsOlderThan("svn", "2.9"):
            m = ("This buildslave (%s) does not support svn depth "
                 "arguments.  Refusing to build. "
                 "Please upgrade the buildslave." % (self.build.slavename))
            raise BuildSlaveTooOldError(m)

        if (self.username is not None or self.password is not None) \
                and self.slaveVersionIsOlderThan("svn", "2.8"):
            m = ("This buildslave (%s) does not support svn usernames "
                 "and passwords.  "
                 "Refusing to build. Please upgrade the buildslave to "
                 "buildbot-0.7.10 or newer." % (self.build.slavename,))
            raise BuildSlaveTooOldError(m)

    def getSvnUrl(self, branch):
        ''' Compute the svn url that will be passed to the svn remote command '''
        if self.svnurl:
            return self.svnurl
        else:
            if branch is None:
                m = ("The SVN source step belonging to builder '%s' does not know "
                     "which branch to work with. This means that the change source "
                     "did not specify a branch and that defaultBranch is None."
                     % self.build.builder.name)
                raise RuntimeError(m)

            computed = self.baseURL

            if self.branch_placeholder in self.baseURL:
                return computed.replace(self.branch_placeholder, branch)
            else:
                return computed + branch

    def startVC(self, branch, revision, patch):
        warnings = []

        self.checkCompatibility()

        self.args['svnurl'] = self.getSvnUrl(branch)
        self.args['revision'] = revision
        self.args['patch'] = patch
        self.args['always_purge'] = self.always_purge

        # Set up depth if specified
        if self.depth is not None:
            self.args['depth'] = self.depth

        if self.username is not None:
            self.args['username'] = self.username
        if self.password is not None:
            self.args['password'] = self.password

        if self.extra_args is not None:
            self.args['extra_args'] = self.extra_args

        revstuff = []
        # revstuff.append(self.args['svnurl'])
        if self.args['svnurl'].find('trunk') == -1:
            revstuff.append("[branch]")
        if revision is not None:
            revstuff.append("r%s" % revision)
        if patch is not None:
            revstuff.append("[patch]")
        self.description.extend(revstuff)
        self.descriptionDone.extend(revstuff)

        cmd = RemoteCommand("svn", self.args)
        self.startCommand(cmd, warnings)


class Darcs(SlaveSource):

    """Check out a source tree from a Darcs repository at 'repourl'.

    Darcs has no concept of file modes. This means the eXecute-bit will be
    cleared on all source files. As a result, you may need to invoke
    configuration scripts with something like:

    C{s(step.Configure, command=['/bin/sh', './configure'])}
    """

    name = "darcs"

    renderables = ['repourl', 'baseURL']

    def __init__(self, repourl=None, baseURL=None, defaultBranch=None,
                 **kwargs):
        """
        @type  repourl: string
        @param repourl: the URL which points at the Darcs repository. This
                        is used as the default branch. Using C{repourl} does
                        not enable builds of alternate branches: use
                        C{baseURL} to enable this. Use either C{repourl} or
                        C{baseURL}, not both.

        @param baseURL: if branches are enabled, this is the base URL to
                        which a branch name will be appended. It should
                        probably end in a slash. Use exactly one of
                        C{repourl} and C{baseURL}.

        @param defaultBranch: if branches are enabled, this is the branch
                              to use if the Build does not specify one
                              explicitly. It will simply be appended to
                              C{baseURL} and the result handed to the
                              'darcs pull' command.
        """
        self.repourl = _ComputeRepositoryURL(self, repourl)
        self.baseURL = _ComputeRepositoryURL(self, baseURL)
        self.branch = defaultBranch
        SlaveSource.__init__(self, **kwargs)
        assert self.args['mode'] != "export", \
            "Darcs does not have an 'export' mode"
        if repourl and baseURL:
            raise ValueError("you must provide exactly one of repourl and"
                             " baseURL")

    def startVC(self, branch, revision, patch):
        slavever = self.slaveVersion("darcs")
        if not slavever:
            m = "slave is too old, does not know about darcs"
            raise BuildSlaveTooOldError(m)

        if self.slaveVersionIsOlderThan("darcs", "1.39"):
            if revision:
                # TODO: revisit this once we implement computeSourceRevision
                m = "0.6.6 slaves can't handle args['revision']"
                raise BuildSlaveTooOldError(m)

            # the slave doesn't know to avoid re-using the same sourcedir
            # when the branch changes. We have no way of knowing which branch
            # the last build used, so if we're using a non-default branch and
            # either 'update' or 'copy' modes, it is safer to refuse to
            # build, and tell the user they need to upgrade the buildslave.
            if (branch != self.branch
                    and self.args['mode'] in ("update", "copy")):
                m = ("This buildslave (%s) does not know about multiple "
                     "branches, and using mode=%s would probably build the "
                     "wrong tree. "
                     "Refusing to build. Please upgrade the buildslave to "
                     "buildbot-0.7.0 or newer." % (self.build.slavename,
                                                   self.args['mode']))
                raise BuildSlaveTooOldError(m)

        if self.repourl:
            assert not branch  # we need baseURL= to use branches
            self.args['repourl'] = self.repourl
        else:
            self.args['repourl'] = self.baseURL + branch
        self.args['revision'] = revision
        self.args['patch'] = patch

        revstuff = []
        if branch is not None and branch != self.branch:
            revstuff.append("[branch]")
        self.description.extend(revstuff)
        self.descriptionDone.extend(revstuff)

        cmd = RemoteCommand("darcs", self.args)
        self.startCommand(cmd)


class Git(SlaveSource):

    """Check out a source tree from a git repository 'repourl'."""

    name = "git"

    renderables = ['repourl']

    def __init__(self, repourl=None,
                 branch="master",
                 submodules=False,
                 ignore_ignores=None,
                 reference=None,
                 shallow=False,
                 progress=False,
                 **kwargs):
        """
        @type  repourl: string
        @param repourl: the URL which points at the git repository

        @type  branch: string
        @param branch: The branch or tag to check out by default. If
                       a build specifies a different branch, it will
                       be used instead of this.

        @type  submodules: boolean
        @param submodules: Whether or not to update (and initialize)
                       git submodules.

        @type  reference: string
        @param reference: The path to a reference repository to obtain
                          objects from, if any.

        @type  shallow: boolean
        @param shallow: Use a shallow or clone, if possible

        @type  progress: boolean
        @param progress: Pass the --progress option when fetching. This
                         can solve long fetches getting killed due to
                         lack of output, but requires Git 1.7.2+.
        """
        SlaveSource.__init__(self, **kwargs)
        self.repourl = _ComputeRepositoryURL(self, repourl)
        self.branch = branch
        self.args.update({'submodules': submodules,
                          'ignore_ignores': ignore_ignores,
                          'reference': reference,
                          'shallow': shallow,
                          'progress': progress,
                          })

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        return changes[-1].revision

    def startVC(self, branch, revision, patch):
        self.args['branch'] = branch
        self.args['repourl'] = self.repourl
        self.args['revision'] = revision
        self.args['patch'] = patch

        # check if there is any patchset we should fetch from Gerrit
        if self.build.hasProperty("event.patchSet.ref"):
            # GerritChangeSource
            self.args['gerrit_branch'] = self.build.getProperty("event.patchSet.ref")
            self.updateSourceProperty("gerrit_branch",
                                      self.args['gerrit_branch'])
        else:
            try:
                # forced build
                change = self.build.getProperty("gerrit_change", '').split('/')
                if len(change) == 2:
                    self.args['gerrit_branch'] = "refs/changes/%2.2d/%d/%d" \
                                                 % (int(change[0]) % 100, int(change[0]), int(change[1]))
                    self.updateSourceProperty("gerrit_branch",
                                              self.args['gerrit_branch'])
            except:
                pass

        slavever = self.slaveVersion("git")
        if not slavever:
            raise BuildSlaveTooOldError("slave is too old, does not know "
                                        "about git")
        cmd = RemoteCommand("git", self.args)
        self.startCommand(cmd)


class Repo(SlaveSource):

    """Check out a source tree from a repo repository described by manifest."""

    name = "repo"

    renderables = ["manifest_url"]

    def __init__(self,
                 manifest_url=None,
                 manifest_branch="master",
                 manifest_file="default.xml",
                 tarball=None,
                 jobs=None,
                 **kwargs):
        """
        @type  manifest_url: string
        @param manifest_url: The URL which points at the repo manifests repository.

        @type  manifest_branch: string
        @param manifest_branch: The manifest branch to check out by default.

        @type  manifest_file: string
        @param manifest_file: The manifest to use for sync.

        """
        SlaveSource.__init__(self, **kwargs)
        self.manifest_url = _ComputeRepositoryURL(self, manifest_url)
        self.args.update({'manifest_branch': manifest_branch,
                          'manifest_file': manifest_file,
                          'tarball': tarball,
                          'manifest_override_url': None,
                          'jobs': jobs
                          })

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        return changes[-1].revision

    def parseDownloadProperty(self, s):
        """
         lets try to be nice in the format we want
         can support several instances of "repo download proj number/patch" (direct copy paste from gerrit web site)
         or several instances of "proj number/patch" (simpler version)
         This feature allows integrator to build with several pending interdependant changes.
         returns list of repo downloads sent to the buildslave
         """
        import re
        if s is None:
            return []
        re1 = re.compile("repo download ([^ ]+) ([0-9]+/[0-9]+)")
        re2 = re.compile("([^ ]+) ([0-9]+/[0-9]+)")
        re3 = re.compile("([^ ]+)/([0-9]+/[0-9]+)")
        ret = []
        for cur_re in [re1, re2, re3]:
            res = cur_re.search(s)
            while res:
                ret.append("%s %s" % (res.group(1), res.group(2)))
                s = s[:res.start(0)] + s[res.end(0):]
                res = cur_re.search(s)
        return ret

    def buildDownloadList(self):
        """taken the changesource and forcebuild property,
        build the repo download command to send to the slave
        making this a defereable allow config to tweak this
        in order to e.g. manage dependancies
        """
        downloads = self.build.getProperty("repo_downloads", [])

        # download patches based on GerritChangeSource events
        for change in self.build.allChanges():
            if ("event.type" in change.properties and
                    change.properties["event.type"] == "patchset-created"):
                downloads.append("%s %s/%s" % (change.properties["event.change.project"],
                                               change.properties["event.change.number"],
                                               change.properties["event.patchSet.number"]))

        # download patches based on web site forced build properties:
        # "repo_d", "repo_d0", .., "repo_d9"
        # "repo_download", "repo_download0", .., "repo_download9"
        for propName in ["repo_d"] + ["repo_d%d" % i for i in xrange(0, 10)] + \
                ["repo_download"] + ["repo_download%d" % i for i in xrange(0, 10)]:
            s = self.build.getProperty(propName)
            if s is not None:
                downloads.extend(self.parseDownloadProperty(s))

        if downloads:
            self.args["repo_downloads"] = downloads
            self.updateSourceProperty("repo_downloads", downloads)
        return defer.succeed(None)

    def startVC(self, branch, revision, patch):
        self.args['manifest_url'] = self.manifest_url

        # manifest override
        self.args['manifest_override_url'] = None
        try:
            self.args['manifest_override_url'] = self.build.getProperty("manifest_override_url")
        except KeyError:
            pass
        # only master has access to properties, so we must implement this here.
        d = self.buildDownloadList()
        d.addCallback(self.continueStartVC, branch, revision, patch)
        d.addErrback(self.failed)

    def continueStartVC(self, ignored, branch, revision, patch):
        slavever = self.slaveVersion("repo")
        if not slavever:
            raise BuildSlaveTooOldError("slave is too old, does not know "
                                        "about repo")
        cmd = RemoteCommand("repo", self.args)
        self.startCommand(cmd)

    def commandComplete(self, cmd):
        repo_downloaded = []
        if "repo_downloaded" in cmd.updates:
            repo_downloaded = cmd.updates["repo_downloaded"][-1]
            if repo_downloaded:
                self.updateSourceProperty("repo_downloaded",
                                          str(repo_downloaded))
            else:
                repo_downloaded = []
        orig_downloads = self.getProperty("repo_downloads") or []
        if len(orig_downloads) != len(repo_downloaded):
            self.step_status.setText(["repo download issues"])


class Bzr(SlaveSource):

    """Check out a source tree from a bzr (Bazaar) repository at 'repourl'.

    """

    name = "bzr"

    renderables = ['repourl', 'baseURL']

    def __init__(self, repourl=None, baseURL=None, defaultBranch=None,
                 forceSharedRepo=None,
                 **kwargs):
        """
        @type  repourl: string
        @param repourl: the URL which points at the bzr repository. This
                        is used as the default branch. Using C{repourl} does
                        not enable builds of alternate branches: use
                        C{baseURL} to enable this. Use either C{repourl} or
                        C{baseURL}, not both.

        @param baseURL: if branches are enabled, this is the base URL to
                        which a branch name will be appended. It should
                        probably end in a slash. Use exactly one of
                        C{repourl} and C{baseURL}.

        @param defaultBranch: if branches are enabled, this is the branch
                              to use if the Build does not specify one
                              explicitly. It will simply be appended to
                              C{baseURL} and the result handed to the
                              'bzr checkout pull' command.


        @param forceSharedRepo: Boolean, defaults to False. If set to True,
                                the working directory will be made into a
                                bzr shared repository if it is not already.
                                Shared repository greatly reduces the amount
                                of history data that needs to be downloaded
                                if not using update/copy mode, or if using
                                update/copy mode with multiple branches.
        """
        self.repourl = _ComputeRepositoryURL(self, repourl)
        self.baseURL = _ComputeRepositoryURL(self, baseURL)
        self.branch = defaultBranch
        SlaveSource.__init__(self, **kwargs)
        self.args.update({'forceSharedRepo': forceSharedRepo})
        if repourl and baseURL:
            raise ValueError("you must provide exactly one of repourl and"
                             " baseURL")

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        lastChange = max([int(c.revision) for c in changes])
        return lastChange

    def startVC(self, branch, revision, patch):
        slavever = self.slaveVersion("bzr")
        if not slavever:
            m = "slave is too old, does not know about bzr"
            raise BuildSlaveTooOldError(m)

        if self.repourl:
            assert not branch  # we need baseURL= to use branches
            self.args['repourl'] = self.repourl
        else:
            self.args['repourl'] = self.baseURL + branch
        self.args['revision'] = revision
        self.args['patch'] = patch

        revstuff = []
        if branch is not None and branch != self.branch:
            revstuff.append("[" + branch + "]")
        if revision is not None:
            revstuff.append("r%s" % revision)
        self.description.extend(revstuff)
        self.descriptionDone.extend(revstuff)

        cmd = RemoteCommand("bzr", self.args)
        self.startCommand(cmd)


class Mercurial(SlaveSource):

    """Check out a source tree from a mercurial repository 'repourl'."""

    name = "hg"

    renderables = ['repourl', 'baseURL']

    def __init__(self, repourl=None, baseURL=None, defaultBranch=None,
                 branchType='dirname', clobberOnBranchChange=True, **kwargs):
        """
        @type  repourl: string
        @param repourl: the URL which points at the Mercurial repository.
                        This uses the 'default' branch unless defaultBranch is
                        specified below and the C{branchType} is set to
                        'inrepo'.  It is an error to specify a branch without
                        setting the C{branchType} to 'inrepo'.

        @param baseURL: if 'dirname' branches are enabled, this is the base URL
                        to which a branch name will be appended. It should
                        probably end in a slash.  Use exactly one of C{repourl}
                        and C{baseURL}.

        @param defaultBranch: if branches are enabled, this is the branch
                              to use if the Build does not specify one
                              explicitly.
                              For 'dirname' branches, It will simply be
                              appended to C{baseURL} and the result handed to
                              the 'hg update' command.
                              For 'inrepo' branches, this specifies the named
                              revision to which the tree will update after a
                              clone.

        @param branchType: either 'dirname' or 'inrepo' depending on whether
                           the branch name should be appended to the C{baseURL}
                           or the branch is a mercurial named branch and can be
                           found within the C{repourl}

        @param clobberOnBranchChange: boolean, defaults to True. If set and
                                      using inrepos branches, clobber the tree
                                      at each branch change. Otherwise, just
                                      update to the branch.
        """
        self.repourl = _ComputeRepositoryURL(self, repourl)
        self.baseURL = _ComputeRepositoryURL(self, baseURL)
        self.branch = defaultBranch
        self.branchType = branchType
        self.clobberOnBranchChange = clobberOnBranchChange
        SlaveSource.__init__(self, **kwargs)
        if repourl and baseURL:
            raise ValueError("you must provide exactly one of repourl and"
                             " baseURL")

    def startVC(self, branch, revision, patch):
        slavever = self.slaveVersion("hg")
        if not slavever:
            raise BuildSlaveTooOldError("slave is too old, does not know "
                                        "about hg")

        if self.repourl:
            # we need baseURL= to use dirname branches
            assert self.branchType == 'inrepo' or not branch
            self.args['repourl'] = self.repourl
            if branch:
                self.args['branch'] = branch
        else:
            self.args['repourl'] = self.baseURL + (branch or '')
        self.args['revision'] = revision
        self.args['patch'] = patch
        self.args['clobberOnBranchChange'] = self.clobberOnBranchChange
        self.args['branchType'] = self.branchType

        revstuff = []
        if branch is not None and branch != self.branch:
            revstuff.append("[branch]")
        self.description.extend(revstuff)
        self.descriptionDone.extend(revstuff)

        cmd = RemoteCommand("hg", self.args)
        self.startCommand(cmd)

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        # without knowing the revision ancestry graph, we can't sort the
        # changes at all. So for now, assume they were given to us in sorted
        # order, and just pay attention to the last one. See ticket #103 for
        # more details.
        if len(changes) > 1:
            log.msg("Mercurial.computeSourceRevision: warning: "
                    "there are %d changes here, assuming the last one is "
                    "the most recent" % len(changes))
        return changes[-1].revision


class P4(SlaveSource):

    """ P4 is a class for accessing perforce revision control"""
    name = "p4"

    renderables = ['p4base']

    def __init__(self, p4base=None, defaultBranch=None, p4port=None, p4user=None,
                 p4passwd=None, p4extra_views=[], p4line_end='local',
                 p4client='buildbot_%(slave)s_%(builder)s', **kwargs):
        """
        @type  p4base: string
        @param p4base: A view into a perforce depot, typically
                       "//depot/proj/"

        @type  defaultBranch: string
        @param defaultBranch: Identify a branch to build by default. Perforce
                              is a view based branching system. So, the branch
                              is normally the name after the base. For example,
                              branch=1.0 is view=//depot/proj/1.0/...
                              branch=1.1 is view=//depot/proj/1.1/...

        @type  p4port: string
        @param p4port: Specify the perforce server to connection in the format
                       <host>:<port>. Example "perforce.example.com:1666"

        @type  p4user: string
        @param p4user: The perforce user to run the command as.

        @type  p4passwd: string
        @param p4passwd: The password for the perforce user.

        @type  p4extra_views: list of tuples
        @param p4extra_views: Extra views to be added to
                              the client that is being used.

        @type  p4line_end: string
        @param p4line_end: value of the LineEnd client specification property

        @type  p4client: string
        @param p4client: The perforce client to use for this buildslave.
        """

        self.p4base = _ComputeRepositoryURL(self, p4base)
        self.branch = defaultBranch
        SlaveSource.__init__(self, **kwargs)
        self.args['p4port'] = p4port
        self.args['p4user'] = p4user
        self.args['p4passwd'] = p4passwd
        self.args['p4extra_views'] = p4extra_views
        self.args['p4line_end'] = p4line_end
        self.p4client = p4client

    def setBuild(self, build):
        SlaveSource.setBuild(self, build)
        self.args['p4client'] = self.p4client % {
            'slave': build.slavename,
            'builder': build.builder.name,
        }

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        lastChange = max([int(c.revision) for c in changes])
        return lastChange

    def startVC(self, branch, revision, patch):
        slavever = self.slaveVersion("p4")
        assert slavever, "slave is too old, does not know about p4"
        args = dict(self.args)
        args['p4base'] = self.p4base
        args['branch'] = branch or self.branch
        args['revision'] = revision
        args['patch'] = patch
        cmd = RemoteCommand("p4", args)
        self.startCommand(cmd)


class Monotone(SlaveSource):

    """Check out a source tree from a monotone repository 'repourl'."""

    name = "mtn"

    renderables = ['repourl']

    def __init__(self, repourl=None, branch=None, progress=False, **kwargs):
        """
        @type  repourl: string
        @param repourl: the URI which points at the monotone repository.

        @type  branch: string
        @param branch: The branch or tag to check out by default. If
                       a build specifies a different branch, it will
                       be used instead of this.

        @type  progress: boolean
        @param progress: Pass the --ticker=dot option when pulling. This
                         can solve long fetches getting killed due to
                         lack of output.
        """
        SlaveSource.__init__(self, **kwargs)
        self.repourl = _ComputeRepositoryURL(self, repourl)
        if (not repourl):
            raise ValueError("you must provide a repository uri in 'repourl'")
        if (not branch):
            raise ValueError("you must provide a default branch in 'branch'")
        self.args.update({'branch': branch,
                          'progress': progress,
                          })

    def startVC(self, branch, revision, patch):
        slavever = self.slaveVersion("mtn")
        if not slavever:
            raise BuildSlaveTooOldError("slave is too old, does not know "
                                        "about mtn")

        self.args['repourl'] = self.repourl
        if branch:
            self.args['branch'] = branch
        self.args['revision'] = revision
        self.args['patch'] = patch

        cmd = RemoteCommand("mtn", self.args)
        self.startCommand(cmd)

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        # without knowing the revision ancestry graph, we can't sort the
        # changes at all. So for now, assume they were given to us in sorted
        # order, and just pay attention to the last one. See ticket #103 for
        # more details.
        if len(changes) > 1:
            log.msg("Monotone.computeSourceRevision: warning: "
                    "there are %d changes here, assuming the last one is "
                    "the most recent" % len(changes))
        return changes[-1].revision
