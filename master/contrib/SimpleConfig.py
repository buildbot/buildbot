# Example of simple declarative configuration for buildbot
# This is a starting point; adjust to taste.
# Copyright 2013 Dan Kegel for Oblong Industries
# GPL
#
# To use, you'll need to create four files:
# 1) a ~/myconfig.json file containing your buildbot-related secrets, e.g.
#   {
#      "webuser" : "fred",
#      "webpass" : "fredspassword",
#      "slavepass" : "buildbotslavepassword"
#   }
#
# 2) a master.cfg file that reads the declarative configuration, e.g.
#   import SimpleConfig
#   BuildmasterConfig = SimpleConfig.SimpleConfig(
#       name="exampleProj", homepage="http://wiki.example.com/exampleProj")
#
# 3) a master.json file containing the declarative
# configuration as described below, e.g.  for a project that needs to be
# built on two different operating systems, you might have
#   {
#       "slaves" : [
#           { "os":"osx107",  "name":"slave1.example.com" },
#           { "os":"win7",    "name":"slave2.example.com" }
#       ],
#       "projects" : [
#           {
#               "name" : "frobozz",
#               "repourl" : "git.example.com:/git/frobozz.git",
#               "builders" : [
#                   { "os":"osx107",  "branch":"master"  },
#                   { "os":"osx107",  "branch":"rel-3.8" },
#                   { "os":"win7",    "branch":"master"  }
#               ]
#           }
#       ]
#   }
#
# 4) an executable script named 'buildshim' at the top of the project
# which holds all knowledge of how to run the project's build system.
# For Makefile-driven projects, buildshim might be
# !/bin/sh
#   case $1 in
#   compile) make -j4;;
#   esac
# For debian package projects, buildshim might be
# !/bin/sh
#   case $1 in
#   install_deps) sudo mk-build-deps -i;;
#   package) debuild;;
#   esac
# (This seemed more likely to work in the real world than trying to
# encode how to build projects into the declarative configuration file.
# If you don't want to store buildshim in the project's directory,
# it's easy to adjust the python code to find it somewhere else.)
#
# Fancy features:
#
# 1) Parameterized builds
# You can pass an extra argument to the buildshim by appending
#    , "suffix":"nameofvariant" "params":"...."
# to a builder line.  (The suffix is appended to the builder name.)
#
# 2) Building a particular tag
# You can ask for a particular tag by appending
#    , "tag":"thetagname"
# to a builder line.  This isn't generally very useful,
# but sometimes it can get you out of a jam.
#
# 3) Chained builds
# You can chain builds between different slave types by listing
# the slave types separated by > in the "os" field, e.g.
#    { "os":"osx107>win7", "branch":"master" }
# will run the job on a slave marked 'osx107', then on one marked 'win'.
# But you have to copy any intermediate results between the slaves
# yourself in the buildshim, using e.g. scp.
# We use this e.g. for stuff that has to be built on Mac but
# signed on Windows, or built on one set of slaves and tested
# on another.  The buildshim has to figure out which link in
# the chain it is itself, by e.g. looking at what operating
# system it's running on.
#
# A variant of this script has been deployed in our shop for
# about six months, and has proven quite useful.

import json
import os
import random
import socket

from buildbot.buildslave import BuildSlave
from buildbot.changes import filter
from buildbot.changes.gitpoller import GitPoller
from buildbot.config import BuilderConfig
from buildbot.process.factory import BuildFactory
from buildbot.reporter.mail import MailNotifier
from buildbot.schedulers import triggerable
from buildbot.schedulers.basic import SingleBranchScheduler
from buildbot.schedulers.forcesched import FixedParameter
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.status import html
from buildbot.status.web import auth
from buildbot.status.web import authz
from buildbot.steps import trigger
from buildbot.steps.shell import ShellCommand
from buildbot.steps.source.git import Git
from twisted.python import log


class SimpleConfig(dict):

    """A buildbot master with a web status page and a 'force build' button,
    which reads public configuration from 'master.json'
    and secrets from a different json file (default ~/myconfig.json).

    Example json file master.json:
    {
        "slaves" : [
            { "os":"osx107",  "name":"peanuts-north"        },
            { "os":"ubu1004", "name":"peanuts-west-ubu1004" },
            { "os":"ubu1204", "name":"peanuts-west-ubu1204" },
            { "os":"win7",    "name":"peanuts-south"        }
        ],
        "projects" : [
            {
                "name" : "christmas",
                "repourl" : "git.example.com:/ob/git/peanuts/christmas.git",
                "builders" : [
                    { "os":"osx107",  "branch":"master"  },
                    { "os":"osx107",  "branch":"rel-3.8" },
                    { "os":"ubu1004", "branch":"master"  },
                    { "os":"win7",    "branch":"master"  }
                ]
            },
            {
                "name" : "thanksgiving",
                "repourl" : "git.cbs.com:/ob/git/peanuts/thanksgiving.git",
                "builders" : [
                    { "os":"osx107>win7", "branch":"master" }
                ]
            },
        ]
    }
    Legend:
    "slaves":
       "os" is an arbitary tag used below to specify where builders should run.
       "name" is the name of the buildslave instance (my scripts name them using
           the name of the project plus the hostname of the slave).
           In this example, peanuts is the project, west is
           a machine running ubuntu 10.04 and ubuntu 12.04 slaves in
           LXC containers, and north and south are plain old mac and
           windows machines.
    "projects":
       "name" is an arbitary tag used as a prefix in the names of the enclosed schedulers and builders.
       "repourl" is where the source code comes from.
       "builders":
          "branch" is which branch of the source code to build.
          "os" means "build this on any buildslave from the list above
          which has a matching os tag".
          If a '>'-separated list of os tags is given, the build is run
          on each one sequentially, e.g. so you can build on one machine
          and then sign or test on another.

    """

    def __init__(self,
                 name,
                 homepage,
                 secretsfile="~/myconfig.json",
                 *args, **kwargs):
        dict.__init__(self, *args, **kwargs)

        # Find the directory containing this .py file
        thisfile = __file__
        thisfile = thisfile.replace(".pyc", ".py")
        try:
            thisfile = os.readlink(thisfile)
        except OSError:
            pass
        dir = os.path.join(os.path.dirname(thisfile))

        masterjson = json.load(open(os.path.join(dir, "master.json")))

        # Lots of unrelated stuff is grouped here simply because buildbot needs it all.
        # See e.g. https://github.com/buildbot/buildbot/blob/master/master/buildbot/scripts/sample.cfg
        # for a simple hard-coded linear example of what buildbot needs set.
        # FIXME: find a more readable way to organize this

        # Since we need to process tags, disable merging for the moment
        # Later we can make this smarter and disable merging just changes
        # which are at tags, or enable merging just on builders that are
        # way too slow and don't mind missing a tag
        self['collapseRequests'] = False

        # PORT NUMBERS
        # It's hard to keep port numbers straight for multiple projects,
        # so let's assign each project a slot number,
        # and use 8010 + slotnum for the http port,
        # 9010 + slotnum for the slave port, etc.
        # FIXME: get slot from masterjson
        slot = 0
        self.__http_port = 8010 + slot
        self['slavePortnum'] = 9010 + slot

        # SECRETS
        # Avoid checking secrets into git by keeping them in a json file.
        try:
            s = json.load(open(os.path.expanduser(secretsfile)))
            self.__auth = auth.BasicAuth([(s["webuser"].encode('ascii', 'ignore'), s["webpass"].encode('ascii', 'ignore'))])
            # For the moment, all slaves have same password
            self.slavepass = s["slavepass"].encode('ascii', 'ignore')
        except Exception:
            exit("%s must be a json file containing webuser, webpass, and slavepass; ascii only, no commas in quotes" % secretsfile)

        # STATUS TARGETS
        self['status'] = []
        authz_cfg = authz.Authz(
            # change any of these to True to enable; see the manual for more
            # options
            auth=self.__auth,
            gracefulShutdown=False,
            forceBuild='auth',
            forceAllBuilds=True,
            pingBuilder=True,
            stopBuild=True,
            stopAllBuilds=True,
            cancelPendingBuild=True,
        )
        # Need order_console_by_time for git or hg or any vcs that doesn't have numbered changesets
        self['status'].append(
            html.WebStatus(http_port=self.__http_port, authz=authz_cfg, order_console_by_time=True))

        self['status'].append(
            MailNotifier(fromaddr="buildbot@example.com",
                         mode=('problem'),
                         sendToInterestedUsers=True,
                         extraRecipients=['buildteam@example.com']))

        # DB URL
        self['db'] = {
            # This specifies what database buildbot uses to store its state.
            # This default is ok for all but the largest installations.
            'db_url': "sqlite:///state.sqlite",
        }

        # PROJECT IDENTITY
        # the 'title' string will appear at the top of this buildbot
        # installation's html.WebStatus home page (linked to the
        # 'titleURL') and is embedded in the title of the waterfall HTML page.

        # FIXME: get name and homepage from masterjson
        self['title'] = name
        self['titleURL'] = homepage

        # the 'buildbotURL' string should point to the location where the buildbot's
        # internal web server (usually the html.WebStatus page) is visible. This
        # typically uses the port number set in the Waterfall 'status' entry, but
        # with an externally-visible host name which the buildbot cannot figure out
        # without some help.

        self['buildbotURL'] = "http://" + socket.gethostname() + ":%d/" % self.__http_port

        # SLAVES
        self._os2slaves = {}
        self['slaves'] = []
        slaveconfigs = masterjson["slaves"]
        for slaveconfig in slaveconfigs:
            sname = slaveconfig["name"].encode('ascii', 'ignore')
            sos = slaveconfig["os"].encode('ascii', 'ignore')
            # Restrict to a single build at a time because our buildshims
            # typically assume they have total control of machine, and use sudo apt-get, etc. with abandon.
            s = BuildSlave(sname, self.slavepass, max_builds=1)
            self['slaves'].append(s)
            if sos not in self._os2slaves:
                self._os2slaves[sos] = []
            self._os2slaves[sos].append(sname)

        # These will be built up over the course of one or more calls to addSimpleProject
        self['change_source'] = []
        self['builders'] = []
        self['schedulers'] = []

        # Righty-o, wire 'em all up
        for project in masterjson["projects"]:
            self.addSimpleProject(project["name"].encode('ascii', 'ignore'), project["category"].encode('ascii', 'ignore'), project["repourl"].encode('ascii', 'ignore'), project["builders"])

    def addSimpleBuilder(self, name, buildername, category, repourl, builderconfig, sos, sbranch, bparams):
        """Private.
        Add a single builder on the given OS type for the given repo and branch.

        """

        factory = BuildFactory()
        factory.addStep(Git(repourl=repourl, mode='full', submodules=True, method='copy', branch=sbranch, getDescription={'tags': True}))
        if "tag" in builderconfig and not(builderconfig["tag"] is None):
            stag = builderconfig["tag"].encode('ascii', 'ignore')
            factory.addStep(ShellCommand(
                command=['git', 'checkout', stag],
                workdir="build",
                description="checkout tag"))
        # Delegate all knowlege of how to build to a script called buildshim in the project
        # directory.  Call this script in nine standardize steps.  It should ignore steps that it doesn't need.
        # Pass the step name as the first arg, and if params was given in the json for this builder, pass that as the
        # second arg.
        for step in ["patch", "install_deps", "configure", "compile", "check", "package", "upload", "compile_extra", "uninstall_deps"]:
            factory.addStep(ShellCommand(command=["./buildshim", step, bparams], description=step, haltOnFailure=True))

        self['builders'].append(
            BuilderConfig(name=buildername,
                          slavenames=self._os2slaves[sos],
                          factory=factory,
                          category=category))

        return factory

    def addSimpleProject(self, name, category, repourl, builderconfigs):
        """Private.
        Add a project which builds when the source changes or when Force is clicked.

        """

        # FACTORIES
        # FIXME: get list of steps from buildshim here
        # factory = BuildFactory()
        # check out the source
        # This fails with git-1.8 and up unless you specify the branch, so do this down lower where we now the branch
        # factory.addStep(Git(repourl=repourl, mode='full', method='copy'))
        # for step in ["patch", "install_deps", "configure", "compile", "check", "package", "upload", "uninstall_deps"]:
        #    factory.addStep(ShellCommand(command=["../../srclink/" + name + "/buildshim", step], description=step))

        # BUILDERS AND SCHEDULERS
        # For each builder in config file, see what OS they want to
        # run on, and assign them to suitable slaves.
        # Also create a force scheduler that knows about all the builders.
        branchnames = []
        buildernames = []
        for builderconfig in builderconfigs:
            bparams = ''
            if "params" in builderconfig:
                bparams = builderconfig["params"].encode('ascii', 'ignore')
            bsuffix = ''
            if "suffix" in builderconfig:
                bsuffix = builderconfig["suffix"].encode('ascii', 'ignore')
            sbranch = builderconfig["branch"].encode('ascii', 'ignore')
            if sbranch not in branchnames:
                branchnames.append(sbranch)
            sosses = builderconfig["os"].encode('ascii', 'ignore').split('>')
            sosses.reverse()

            # The first OS in the list triggers when there's a source change
            sos = sosses.pop()
            buildername = name + '-' + sos + '-' + sbranch + bsuffix

            factory = self.addSimpleBuilder(name, buildername, category, repourl, builderconfig, sos, sbranch, bparams)
            self['schedulers'].append(
                SingleBranchScheduler(
                    name=buildername,
                    change_filter=filter.ChangeFilter(branch=sbranch, repository=repourl),
                    treeStableTimer=1 * 60,  # Set this just high enough so you don't swamp the slaves, or to None if you don't want changes batched
                    builderNames=[buildername]))
            buildernames.append(buildername)

            # The rest of the OSes in the list, if any, are triggered when the previous OS in the list finishes
            while len(sosses) > 0:
                prev_factory = factory
                sos = sosses.pop()
                buildername = name + '-' + sos + '-' + sbranch + bsuffix
                factory = self.addSimpleBuilder(name, buildername, category, repourl, builderconfig, sos, sbranch, bparams)
                self['schedulers'].append(
                    triggerable.Triggerable(
                        name=buildername,
                        builderNames=[buildername]))
                prev_factory.addStep(trigger.Trigger(schedulerNames=[buildername], waitForFinish=False))

        self['schedulers'].append(
            ForceScheduler(
                name=name + "-force",
                builderNames=buildernames,
                branch=FixedParameter(name="branch", default=""),
                revision=FixedParameter(name="revision", default=""),
                repository=FixedParameter(name="repository", default=""),
                project=FixedParameter(name="project", default=""),
                properties=[],
            ))

        # CHANGESOURCES
        # It's a git git git git git world
        already = False
        for cs in self['change_source']:
            if cs.repourl == repourl:
                log.msg("There's already a changesource for %s.  Hope it has the branch you wanted." % cs.repourl)
                already = True
        if not already:
            self['change_source'].append(
                # Fuzz the interval to avoid slamming the git server and hitting the MaxStartups or MaxSessions limits
                # If you hit them, twistd.log will have lots of "ssh_exchange_identification: Connection closed by remote host" errors
                # See http://trac.buildbot.net/ticket/2480
                GitPoller(repourl, branches=branchnames, workdir='gitpoller-workdir-' + name, pollinterval=60 + random.uniform(-10, 10)))
