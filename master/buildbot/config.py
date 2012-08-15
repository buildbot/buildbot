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

from __future__ import with_statement

import os
import re
import sys
import warnings
from buildbot.util import safeTranslate
from buildbot import interfaces
from buildbot import locks
from buildbot.revlinks import default_revlink_matcher
from twisted.python import log, failure
from twisted.internet import defer
from twisted.application import service

class ConfigErrors(Exception):

    def __init__(self, errors=[]):
        self.errors = errors[:]

    def __str__(self):
        return "\n".join(self.errors)

    def addError(self, msg):
        self.errors.append(msg)

    def __nonzero__(self):
        return len(self.errors)

_errors = None
def error(error):
    if _errors is not None:
        _errors.addError(error)
    else:
        raise ConfigErrors([error])

class MasterConfig(object):

    def __init__(self):
        # local import to avoid circular imports
        from buildbot.process import properties
        # default values for all attributes

        # global
        self.title = 'Buildbot'
        self.titleURL = 'http://buildbot.net'
        self.buildbotURL = 'http://localhost:8080/'
        self.changeHorizon = None
        self.eventHorizon = 50
        self.logHorizon = None
        self.buildHorizon = None
        self.logCompressionLimit = 4*1024
        self.logCompressionMethod = 'bz2'
        self.logMaxTailSize = None
        self.logMaxSize = None
        self.properties = properties.Properties()
        self.mergeRequests = None
        self.codebaseGenerator = None
        self.prioritizeBuilders = None
        self.slavePortnum = None
        self.multiMaster = False
        self.debugPassword = None
        self.manhole = None

        self.validation = dict(
            branch=re.compile(r'^[\w.+/~-]*$'),
            revision=re.compile(r'^[ \w\.\-\/]*$'),
            property_name=re.compile(r'^[\w\.\-\/\~:]*$'),
            property_value=re.compile(r'^[\w\.\-\/\~:]*$'),
        )
        self.db = dict(
            db_url='sqlite:///state.sqlite',
            db_poll_interval=None,
        )
        self.metrics = None
        self.caches = dict(
            Builds=15,
            Changes=10,
        )
        self.schedulers = {}
        self.builders = []
        self.slaves = []
        self.change_sources = []
        self.status = []
        self.user_managers = []
        self.revlink = default_revlink_matcher

    _known_config_keys = set([
        "buildbotURL", "buildCacheSize", "builders", "buildHorizon", "caches",
        "change_source", "codebaseGenerator", "changeCacheSize", "changeHorizon",
        'db', "db_poll_interval", "db_url", "debugPassword", "eventHorizon",
        "logCompressionLimit", "logCompressionMethod", "logHorizon",
        "logMaxSize", "logMaxTailSize", "manhole", "mergeRequests", "metrics",
        "multiMaster", "prioritizeBuilders", "projectName", "projectURL",
        "properties", "revlink", "schedulers", "slavePortnum", "slaves",
        "status", "title", "titleURL", "user_managers", "validation"
    ])

    @classmethod
    def loadConfig(cls, basedir, filename):
        if not os.path.isdir(basedir):
            raise ConfigErrors([
                "basedir '%s' does not exist" % (basedir,),
            ])
        filename = os.path.join(basedir, filename)
        if not os.path.exists(filename):
            raise ConfigErrors([
                "configuration file '%s' does not exist" % (filename,),
            ])

        try:
            f = open(filename, "r")
        except IOError, e:
            raise ConfigErrors([
                "unable to open configuration file %r: %s" % (filename, e),
            ])

        log.msg("Loading configuration from %r" % (filename,))

        # execute the config file
        localDict = {
            'basedir': os.path.expanduser(basedir),
            '__file__': os.path.abspath(filename),
        }

        # from here on out we can batch errors together for the user's
        # convenience
        global _errors
        _errors = errors = ConfigErrors()

        old_sys_path = sys.path[:]
        sys.path.append(basedir)
        try:
            try:
                exec f in localDict
            except ConfigErrors, e:
                for error in e.errors:
                    errors.addError(error)
                raise errors
            except:
                log.err(failure.Failure(), 'error while parsing config file:')
                errors.addError(
                    "error while parsing config file: %s (traceback in logfile)" %
                        (sys.exc_info()[1],),
                )
                raise errors
        finally:
            f.close()
            sys.path[:] = old_sys_path
            _errors = None

        if 'BuildmasterConfig' not in localDict:
            errors.addError(
                "Configuration file %r does not define 'BuildmasterConfig'"
                    % (filename,),
            )
            raise errors

        config_dict = localDict['BuildmasterConfig']

        # check for unknown keys
        unknown_keys = set(config_dict.keys()) - cls._known_config_keys
        if unknown_keys:
            if len(unknown_keys) == 1:
                errors.addError('Unknown BuildmasterConfig key %s' %
                        (unknown_keys.pop()))
            else:
                errors.addError('Unknown BuildmasterConfig keys %s' %
                        (', '.join(sorted(unknown_keys))))

        # instantiate a new config object, which will apply defaults
        # automatically
        config = cls()

        # and defer the rest to sub-functions, for code clarity
        config.load_global(filename, config_dict, errors)
        config.load_validation(filename, config_dict, errors)
        config.load_db(filename, config_dict, errors)
        config.load_metrics(filename, config_dict, errors)
        config.load_caches(filename, config_dict, errors)
        config.load_schedulers(filename, config_dict, errors)
        config.load_builders(filename, config_dict, errors)
        config.load_slaves(filename, config_dict, errors)
        config.load_change_sources(filename, config_dict, errors)
        config.load_status(filename, config_dict, errors)
        config.load_user_managers(filename, config_dict, errors)

        # run some sanity checks
        config.check_single_master(errors)
        config.check_schedulers(errors)
        config.check_locks(errors)
        config.check_builders(errors)
        config.check_status(errors)
        config.check_horizons(errors)
        config.check_slavePortnum(errors)

        if errors:
            raise errors

        return config

    def load_global(self, filename, config_dict, errors):
        def copy_param(name, alt_key=None,
                       check_type=None, check_type_name=None):
            if name in config_dict:
                v = config_dict[name]
            elif alt_key and alt_key in config_dict:
                v = config_dict[alt_key]
            else:
                return
            if v is not None and check_type and not isinstance(v, check_type):
                errors.addError("c['%s'] must be %s" %
                                (name, check_type_name))
            else:
                setattr(self, name, v)

        def copy_int_param(name, alt_key=None):
            copy_param(name, alt_key=alt_key,
                    check_type=int, check_type_name='an int')

        def copy_str_param(name, alt_key=None):
            copy_param(name, alt_key=alt_key,
                    check_type=basestring, check_type_name='a string')

        copy_str_param('title', alt_key='projectName')
        copy_str_param('titleURL', alt_key='projectURL')
        copy_str_param('buildbotURL')

        copy_int_param('changeHorizon')
        copy_int_param('eventHorizon')
        copy_int_param('logHorizon')
        copy_int_param('buildHorizon')

        copy_int_param('logCompressionLimit')

        if 'logCompressionMethod' in config_dict:
            logCompressionMethod = config_dict.get('logCompressionMethod')
            if logCompressionMethod not in ('bz2', 'gz'):
                errors.addError(
                        "c['logCompressionMethod'] must be 'bz2' or 'gz'")
            self.logCompressionMethod = logCompressionMethod

        copy_int_param('logMaxSize')
        copy_int_param('logMaxTailSize')

        properties = config_dict.get('properties', {})
        if not isinstance(properties, dict):
            errors.addError("c['properties'] must be a dictionary")
        else:
            self.properties.update(properties, filename)

        mergeRequests = config_dict.get('mergeRequests')
        if (mergeRequests not in (None, True, False)
            and not callable(mergeRequests)):
            errors.addError("mergeRequests must be a callable, True, or False")
        else:
            self.mergeRequests = mergeRequests

        codebaseGenerator = config_dict.get('codebaseGenerator')
        if (codebaseGenerator is not None and
            not callable(codebaseGenerator)):
            errors.addError("codebaseGenerator must be a callable accepting a dict and returning a str")
        else:
            self.codebaseGenerator = codebaseGenerator
            
        prioritizeBuilders = config_dict.get('prioritizeBuilders')
        if prioritizeBuilders is not None and not callable(prioritizeBuilders):
            errors.addError("prioritizeBuilders must be a callable")
        else:
            self.prioritizeBuilders = prioritizeBuilders

        if 'slavePortnum' in config_dict:
            slavePortnum = config_dict.get('slavePortnum')
            if isinstance(slavePortnum, int):
                slavePortnum = "tcp:%d" % slavePortnum
            self.slavePortnum = slavePortnum

        if 'multiMaster' in config_dict:
            self.multiMaster = config_dict["multiMaster"]

        copy_str_param('debugPassword')

        if 'manhole' in config_dict:
            # we don't check that this is a manhole instance, since that
            # requires importing buildbot.manhole for every user, and currently
            # that will fail if pycrypto isn't installed
            self.manhole = config_dict['manhole']

        if 'revlink' in config_dict:
            revlink = config_dict['revlink']
            if not callable(revlink):
                errors.addError("revlink must be a callable")
            else:
                self.revlink = revlink

    def load_validation(self, filename, config_dict, errors):
        validation = config_dict.get("validation", {})
        if not isinstance(validation, dict):
            errors.addError("c['validation'] must be a dictionary")
        else:
            unknown_keys = (
                set(validation.keys()) - set(self.validation.keys()))
            if unknown_keys:
                errors.addError("unrecognized validation key(s): %s" %
                                    (", ".join(unknown_keys)))
            else:
                self.validation.update(validation)


    def load_db(self, filename, config_dict, errors):
        if 'db' in config_dict:
            db = config_dict['db']
            if set(db.keys()) > set(['db_url', 'db_poll_interval']):
                errors.addError("unrecognized keys in c['db']")
            self.db.update(db)
        if 'db_url' in config_dict:
            self.db['db_url'] = config_dict['db_url']
        if 'db_poll_interval' in config_dict:
            self.db['db_poll_interval'] = config_dict["db_poll_interval"]

        # we don't attempt to parse db URLs here - the engine strategy will do so

        # check the db_poll_interval
        db_poll_interval = self.db['db_poll_interval']
        if db_poll_interval is not None and \
                    not isinstance(db_poll_interval, int):
            errors.addError("c['db_poll_interval'] must be an int")
        else:
            self.db['db_poll_interval'] = db_poll_interval


    def load_metrics(self, filename, config_dict, errors):
        # we don't try to validate metrics keys
        if 'metrics' in config_dict:
            metrics = config_dict["metrics"]
            if not isinstance(metrics, dict):
                errors.addError("c['metrics'] must be a dictionary")
            else:
                self.metrics = metrics


    def load_caches(self, filename, config_dict, errors):
        explicit = False
        if 'caches' in config_dict:
            explicit = True
            caches = config_dict['caches']
            if not isinstance(caches, dict):
                errors.addError("c['caches'] must be a dictionary")
            else:
                valPairs = caches.items()
                for (x, y) in valPairs:
                  if (not isinstance(y, int)):
                     errors.addError(
                     "value for cache size '%s' must be an integer" % x)
                self.caches.update(caches)

        if 'buildCacheSize' in config_dict:
            if explicit:
                msg = "cannot specify c['caches'] and c['buildCacheSize']"
                errors.addError(msg)
            self.caches['Builds'] = config_dict['buildCacheSize']
        if 'changeCacheSize' in config_dict:
            if explicit:
                msg = "cannot specify c['caches'] and c['changeCacheSize']"
                errors.addError(msg)
            self.caches['Changes'] = config_dict['changeCacheSize']


    def load_schedulers(self, filename, config_dict, errors):
        if 'schedulers' not in config_dict:
            return
        schedulers = config_dict['schedulers']

        ok = True
        if not isinstance(schedulers, (list, tuple)):
            ok = False
        else:
            for s in schedulers:
                if not interfaces.IScheduler.providedBy(s):
                    ok = False
        if not ok:
            msg="c['schedulers'] must be a list of Scheduler instances"
            errors.addError(msg)

        # convert from list to dict, first looking for duplicates
        seen_names = set()
        for s in schedulers:
            if s.name in seen_names:
                errors.addError("scheduler name '%s' used multiple times" %
                                s.name)
            seen_names.add(s.name)

        self.schedulers = dict((s.name, s) for s in schedulers)


    def load_builders(self, filename, config_dict, errors):
        if 'builders' not in config_dict:
            return
        builders = config_dict['builders']

        if not isinstance(builders, (list, tuple)):
            errors.addError("c['builders'] must be a list")
            return

        # convert all builder configs to BuilderConfig instances
        def mapper(b):
            if isinstance(b, BuilderConfig):
                return b
            elif isinstance(b, dict):
                return BuilderConfig(**b)
            else:
                raise RuntimeError() # signal for the try/except below
        try:
            builders = [ mapper(b) for b in builders ]
        except RuntimeError:
            errors.addError("c['builders'] must be a list of builder configs")
            return

        for builder in builders:
            if os.path.isabs(builder.builddir):
                warnings.warn("Absolute path '%s' for builder may cause "
                        "mayhem.  Perhaps you meant to specify slavebuilddir "
                        "instead.")

        self.builders = builders


    def load_slaves(self, filename, config_dict, errors):
        if 'slaves' not in config_dict:
            return
        slaves = config_dict['slaves']

        if not isinstance(slaves, (list, tuple)):
            errors.addError("c['slaves'] must be a list")
            return

        for sl in slaves:
            if not interfaces.IBuildSlave.providedBy(sl):
                msg = "c['slaves'] must be a list of BuildSlave instances"
                errors.addError(msg)
                return

            if sl.slavename in ("debug", "change", "status"):
                msg = "slave name '%s' is reserved" % sl.slavename
                errors.addError(msg)

        self.slaves = config_dict['slaves']


    def load_change_sources(self, filename, config_dict, errors):
        change_source = config_dict.get('change_source', [])
        if isinstance(change_source, (list, tuple)):
            change_sources = change_source
        else:
            change_sources = [change_source]

        for s in change_sources:
            if not interfaces.IChangeSource.providedBy(s):
                msg = "c['change_source'] must be a list of change sources"
                errors.addError(msg)
                return

        self.change_sources = change_sources

    def load_status(self, filename, config_dict, errors):
        if 'status' not in config_dict:
            return
        status = config_dict.get('status', [])

        msg = "c['status'] must be a list of status receivers"
        if not isinstance(status, (list, tuple)):
            errors.addError(msg)
            return

        for s in status:
            if not interfaces.IStatusReceiver.providedBy(s):
                errors.addError(msg)
                return

        self.status = status


    def load_user_managers(self, filename, config_dict, errors):
        if 'user_managers' not in config_dict:
            return
        user_managers = config_dict['user_managers']

        msg = "c['user_managers'] must be a list of user managers"
        if not isinstance(user_managers, (list, tuple)):
            errors.addError(msg)
            return

        self.user_managers = user_managers


    def check_single_master(self, errors):
        # check additional problems that are only valid in a single-master
        # installation
        if self.multiMaster:
            return

        if not self.slaves:
            errors.addError("no slaves are configured")

        if not self.builders:
            errors.addError("no builders are configured")

        # check that all builders are implemented on this master
        unscheduled_buildernames = set([ b.name for b in self.builders ])
        for s in self.schedulers.itervalues():
            for n in s.listBuilderNames():
                if n in unscheduled_buildernames:
                    unscheduled_buildernames.remove(n)
        if unscheduled_buildernames:
            errors.addError("builder(s) %s have no schedulers to drive them"
                            % (', '.join(unscheduled_buildernames),))


    def check_schedulers(self, errors):
        all_buildernames = set([ b.name for b in self.builders ])

        for s in self.schedulers.itervalues():
            for n in s.listBuilderNames():
                if n not in all_buildernames:
                    errors.addError("Unknown builder '%s' in scheduler '%s'"
                                    % (n, s.name))


    def check_locks(self, errors):
        # assert that all locks used by the Builds and their Steps are
        # uniquely named.
        lock_dict = {}
        def check_lock(l):
            if isinstance(l, locks.LockAccess):
                l = l.lockid
            if lock_dict.has_key(l.name):
                if lock_dict[l.name] is not l:
                    msg = "Two locks share the same name, '%s'" % l.name
                    errors.addError(msg)
            else:
                lock_dict[l.name] = l

        for b in self.builders:
            if b.locks:
                for l in b.locks:
                    check_lock(l)

    def check_builders(self, errors):
        # look both for duplicate builder names, and for builders pointing
        # to unknown slaves
        slavenames = set([ s.slavename for s in self.slaves ])
        seen_names = set()
        seen_builddirs = set()

        for b in self.builders:
            unknowns = set(b.slavenames) - slavenames
            if unknowns:
                errors.addError("builder '%s' uses unknown slaves %s" %
                            (b.name, ", ".join(`u` for u in unknowns)))
            if b.name in seen_names:
                errors.addError("duplicate builder name '%s'" % b.name)
            seen_names.add(b.name)

            if b.builddir in seen_builddirs:
                errors.addError("duplicate builder builddir '%s'" % b.builddir)
            seen_builddirs.add(b.builddir)


    def check_status(self, errors):
        # allow status receivers to check themselves against the rest of the
        # receivers
        for s in self.status:
            s.checkConfig(self.status, errors)


    def check_horizons(self, errors):
        if self.logHorizon is not None and self.buildHorizon is not None:
            if self.logHorizon > self.buildHorizon:
                errors.addError(
                    "logHorizon must be less than or equal to buildHorizon")

    def check_slavePortnum(self, errors):
        if self.slavePortnum:
            return

        if self.slaves:
            errors.addError(
                    "slaves are configured, but no slavePortnum is set")
        if self.debugPassword:
            errors.addError(
                    "debug client is configured, but no slavePortnum is set")


class BuilderConfig:

    def __init__(self, name=None, slavename=None, slavenames=None,
            builddir=None, slavebuilddir=None, factory=None, category=None,
            nextSlave=None, nextBuild=None, locks=None, env=None,
            properties=None, mergeRequests=None):

        errors = ConfigErrors([])

        # name is required, and can't start with '_'
        if not name or type(name) not in (str, unicode):
            errors.addError("builder's name is required")
            name = '<unknown>'
        elif name[0] == '_':
            errors.addError(
                "builder names must not start with an underscore: '%s'" % name)
        self.name = name

        # factory is required
        if factory is None:
            errors.addError("builder '%s' has no factory" % name)
        from buildbot.process.factory import BuildFactory
        if factory is not None and not isinstance(factory, BuildFactory):
            errors.addError(
                "builder '%s's factory is not a BuildFactory instance" % name)
        self.factory = factory

        # slavenames can be a single slave name or a list, and should also
        # include slavename, if given
        if type(slavenames) is str:
            slavenames = [ slavenames ]
        if slavenames:
            if not isinstance(slavenames, list):
                errors.addError(
                    "builder '%s': slavenames must be a list or a string" %
                        (name,))
        else:
            slavenames = []

        if slavename:
            if type(slavename) != str:
                errors.addError(
                    "builder '%s': slavename must be a string" % (name,))
            slavenames = slavenames + [ slavename ]
        if not slavenames:
            errors.addError(
                "builder '%s': at least one slavename is required" % (name,))

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
        if category is not None and not isinstance(category, str):
            errors.addError(
                "builder '%s': category must be a string" % (name,))

        self.category = category or ''
        self.nextSlave = nextSlave
        if nextSlave and not callable(nextSlave):
            errors.addError('nextSlave must be a callable')
        self.nextBuild = nextBuild
        if nextBuild and not callable(nextBuild):
            errors.addError('nextBuild must be a callable')
        self.locks = locks or []
        self.env = env or {}
        if not isinstance(self.env, dict):
            errors.addError("builder's env must be a dictionary")
        self.properties = properties or {}
        self.mergeRequests = mergeRequests

        if errors:
            raise errors


    def getConfigDict(self):
        # note: this method will disappear eventually - put your smarts in the
        # constructor!
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
        if self.properties:
            rv['properties'] = self.properties
        if self.mergeRequests:
            rv['mergeRequests'] = self.mergeRequests
        return rv


class ReconfigurableServiceMixin:

    reconfig_priority = 128

    @defer.inlineCallbacks
    def reconfigService(self, new_config):
        if not service.IServiceCollection.providedBy(self):
            return

        # get a list of child services to reconfigure
        reconfigurable_services = [ svc
                for svc in self
                if isinstance(svc, ReconfigurableServiceMixin) ]

        # sort by priority
        reconfigurable_services.sort(key=lambda svc : -svc.reconfig_priority)

        for svc in reconfigurable_services:
            yield svc.reconfigService(new_config)
