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
import os
import re
import sys
import traceback
import warnings
from types import MethodType

from future.utils import iteritems
from future.utils import itervalues
from twisted.python import failure
from twisted.python import log
from zope.interface import implementer

from buildbot import interfaces
from buildbot import locks
from buildbot import util
from buildbot.revlinks import default_revlink_matcher
from buildbot.util import config as util_config
from buildbot.util import identifiers as util_identifiers
from buildbot.util import service as util_service
from buildbot.util import ComparableMixin
from buildbot.util import safeTranslate
from buildbot.worker_transition import WorkerAPICompatMixin
from buildbot.worker_transition import reportDeprecatedWorkerNameUsage
from buildbot.www import auth
from buildbot.www import avatar
from buildbot.www.authz import authz


class ConfigErrors(Exception):

    def __init__(self, errors=[]):
        self.errors = errors[:]

    def __str__(self):
        return "\n".join(self.errors)

    def addError(self, msg):
        self.errors.append(msg)

    def merge(self, errors):
        self.errors.extend(errors.errors)

    def __nonzero__(self):
        return len(self.errors)

_errors = None

DEFAULT_DB_URL = 'sqlite:///state.sqlite'


def error(error, always_raise=False):
    if _errors is not None and not always_raise:
        _errors.addError(error)
    else:
        raise ConfigErrors([error])


def warnDeprecated(version, msg):
    # for now just log the deprecation
    log.msg("NOTE: [%s and later] %s" % (version, msg))


def loadConfigDict(basedir, configFileName):
    if not os.path.isdir(basedir):
        raise ConfigErrors([
            "basedir '%s' does not exist" % (basedir,),
        ])
    filename = os.path.join(basedir, configFileName)
    if not os.path.exists(filename):
        raise ConfigErrors([
            "configuration file '%s' does not exist" % (filename,),
        ])

    try:
        f = open(filename, "r")
    except IOError as e:
        raise ConfigErrors([
            "unable to open configuration file %r: %s" % (filename, e),
        ])

    log.msg("Loading configuration from %r" % (filename,))

    # execute the config file
    localDict = {
        'basedir': os.path.expanduser(basedir),
        '__file__': os.path.abspath(filename),
    }

    old_sys_path = sys.path[:]
    sys.path.append(basedir)
    try:
        try:
            exec(f, localDict)
        except ConfigErrors:
            raise
        except SyntaxError:
            error("encountered a SyntaxError while parsing config file:\n%s " %
                  (traceback.format_exc(),),
                  always_raise=True,
                  )
        except Exception:
            log.err(failure.Failure(), 'error while parsing config file:')
            error("error while parsing config file: %s (traceback in logfile)" %
                  (sys.exc_info()[1],),
                  always_raise=True,
                  )
    finally:
        f.close()
        sys.path[:] = old_sys_path

    if 'BuildmasterConfig' not in localDict:
        error("Configuration file %r does not define 'BuildmasterConfig'"
              % (filename,),
              always_raise=True,
              )

    return filename, localDict['BuildmasterConfig']


@implementer(interfaces.IConfigLoader)
class FileLoader(ComparableMixin, object):
    compare_attrs = ['basedir', 'configFileName']

    def __init__(self, basedir, configFileName):
        self.basedir = basedir
        self.configFileName = configFileName

    def loadConfig(self):
        # from here on out we can batch errors together for the user's
        # convenience
        global _errors
        _errors = errors = ConfigErrors()

        try:
            filename, config_dict = loadConfigDict(
                self.basedir, self.configFileName)
            config = MasterConfig.loadFromDict(config_dict, filename)
        except ConfigErrors as e:
            errors.merge(e)
        finally:
            _errors = None

        if errors:
            raise errors

        return config


class MasterConfig(util.ComparableMixin, WorkerAPICompatMixin):

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
        self.logCompressionLimit = 4 * 1024
        self.logCompressionMethod = 'gz'
        self.logEncoding = 'utf-8'
        self.logMaxSize = None
        self.logMaxTailSize = None
        self.properties = properties.Properties()
        self.collapseRequests = None
        self.codebaseGenerator = None
        self.prioritizeBuilders = None
        self.multiMaster = False
        self.manhole = None
        self.protocols = {}

        self.validation = dict(
            branch=re.compile(r'^[\w.+/~-]*$'),
            revision=re.compile(r'^[ \w\.\-/]*$'),
            property_name=re.compile(r'^[\w\.\-/~:]*$'),
            property_value=re.compile(r'^[\w\.\-/~:]*$'),
        )
        self.db = dict(
            db_url=DEFAULT_DB_URL,
        )
        self.mq = dict(
            type='simple',
        )
        self.metrics = None
        self.caches = dict(
            Builds=15,
            Changes=10,
        )
        self.schedulers = {}
        self.builders = []
        self.workers = []
        self._registerOldWorkerAttr("workers")
        self.change_sources = []
        self.status = []
        self.user_managers = []
        self.revlink = default_revlink_matcher
        self.www = dict(
            port=None,
            plugins=dict(),
            auth=auth.NoAuth(),
            authz=authz.Authz(),
            avatar_methods=avatar.AvatarGravatar(),
            logfileName='http.log',
        )
        self.services = {}

    _known_config_keys = set([
        "buildbotURL", "buildCacheSize", "builders", "buildHorizon", "caches",
        "change_source", "codebaseGenerator", "changeCacheSize", "changeHorizon",
        'db', "db_poll_interval", "db_url", "eventHorizon",
        "logCompressionLimit", "logCompressionMethod", "logEncoding",
        "logHorizon", "logMaxSize", "logMaxTailSize", "manhole",
        "collapseRequests", "metrics", "mq", "multiMaster", "prioritizeBuilders",
        "projectName", "projectURL", "properties", "protocols", "revlink",
        "schedulers", "services", "status", "title", "titleURL",
        "user_managers", "validation", "www", "workers",

        # deprecated, c['protocols']['pb']['port'] should be used
        "slavePortnum",
        "slaves",  # deprecated, "worker" should be used
    ])
    compare_attrs = list(_known_config_keys)

    def preChangeGenerator(self, **kwargs):
        return {
            'author': kwargs.get('author', None),
            'files': kwargs.get('files', None),
            'comments': kwargs.get('comments', None),
            'revision': kwargs.get('revision', None),
            'when_timestamp': kwargs.get('when_timestamp', None),
            'branch': kwargs.get('branch', None),
            'category': kwargs.get('category', None),
            'revlink': kwargs.get('revlink', u''),
            'properties': kwargs.get('properties', {}),
            'repository': kwargs.get('repository', u''),
            'project': kwargs.get('project', u''),
            'codebase': kwargs.get('codebase', None)
        }

    @classmethod
    def loadFromDict(cls, config_dict, filename):
        global _errors
        _errors = errors = ConfigErrors()

        # check for unknown keys
        unknown_keys = set(config_dict.keys()) - cls._known_config_keys
        if unknown_keys:
            if len(unknown_keys) == 1:
                error('Unknown BuildmasterConfig key %s' %
                      (unknown_keys.pop()))
            else:
                error('Unknown BuildmasterConfig keys %s' %
                      (', '.join(sorted(unknown_keys))))

        # instantiate a new config object, which will apply defaults
        # automatically
        config = cls()

        # and defer the rest to sub-functions, for code clarity
        try:
            config.load_global(filename, config_dict)
            config.load_validation(filename, config_dict)
            config.load_db(filename, config_dict)
            config.load_mq(filename, config_dict)
            config.load_metrics(filename, config_dict)
            config.load_caches(filename, config_dict)
            config.load_schedulers(filename, config_dict)
            config.load_builders(filename, config_dict)
            config.load_workers(filename, config_dict)
            config.load_change_sources(filename, config_dict)
            config.load_status(filename, config_dict)
            config.load_user_managers(filename, config_dict)
            config.load_www(filename, config_dict)
            config.load_services(filename, config_dict)

            # run some sanity checks
            config.check_single_master()
            config.check_schedulers()
            config.check_locks()
            config.check_builders()
            config.check_status()
            config.check_horizons()
            config.check_ports()
        finally:
            _errors = None

        if errors:
            raise errors

        return config

    def load_global(self, filename, config_dict):
        def copy_param(name, alt_key=None,
                       check_type=None, check_type_name=None):
            if name in config_dict:
                v = config_dict[name]
            elif alt_key and alt_key in config_dict:
                v = config_dict[alt_key]
            else:
                return
            if v is not None and check_type and not isinstance(v, check_type):
                error("c['%s'] must be %s" %
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

        self.logCompressionMethod = config_dict.get(
            'logCompressionMethod', 'gz')
        if self.logCompressionMethod not in ('raw', 'bz2', 'gz', 'lz4'):
            error(
                "c['logCompressionMethod'] must be 'raw', 'bz2', 'gz' or 'lz4'")

        if self.logCompressionMethod == "lz4":
            try:

                import lz4
                [lz4]
            except ImportError:
                error(
                    "To set c['logCompressionMethod'] to 'lz4' you must install the lz4 library ('pip install lz4')")

        copy_int_param('logMaxSize')
        copy_int_param('logMaxTailSize')
        copy_param('logEncoding')

        properties = config_dict.get('properties', {})
        if not isinstance(properties, dict):
            error("c['properties'] must be a dictionary")
        else:
            self.properties.update(properties, filename)

        collapseRequests = config_dict.get('collapseRequests')
        if (collapseRequests not in (None, True, False)
                and not callable(collapseRequests)):
            error("collapseRequests must be a callable, True, or False")
        else:
            self.collapseRequests = collapseRequests

        codebaseGenerator = config_dict.get('codebaseGenerator')
        if (codebaseGenerator is not None and
                not callable(codebaseGenerator)):
            error(
                "codebaseGenerator must be a callable accepting a dict and returning a str")
        else:
            self.codebaseGenerator = codebaseGenerator

        prioritizeBuilders = config_dict.get('prioritizeBuilders')
        if prioritizeBuilders is not None and not callable(prioritizeBuilders):
            error("prioritizeBuilders must be a callable")
        else:
            self.prioritizeBuilders = prioritizeBuilders

        protocols = config_dict.get('protocols', {})
        if isinstance(protocols, dict):
            for proto, options in iteritems(protocols):
                if not isinstance(proto, str):
                    error("c['protocols'] keys must be strings")
                if not isinstance(options, dict):
                    error("c['protocols']['%s'] must be a dict" % proto)
                    return
                if (proto == "pb" and options.get("port") and
                        'slavePortnum' in config_dict):
                    error("Both c['slavePortnum'] and c['protocols']['pb']['port']"
                          " defined, recommended to remove slavePortnum and leave"
                          " only c['protocols']['pb']['port']")
                if proto == "wamp":
                    self.check_wamp_proto(options)
        else:
            error("c['protocols'] must be dict")
            return
        self.protocols = protocols

        # saved for backward compatability
        if 'slavePortnum' in config_dict:
            reportDeprecatedWorkerNameUsage(
                "c['slavePortnum'] key is deprecated, use "
                "c['protocols']['pb']['port'] instead",
                filename=filename)
            port = config_dict.get('slavePortnum')
            if isinstance(port, int):
                port = "tcp:%d" % port
            pb_options = self.protocols.get('pb', {})
            pb_options['port'] = port
            self.protocols['pb'] = pb_options

        if 'multiMaster' in config_dict:
            self.multiMaster = config_dict["multiMaster"]

        if 'debugPassword' in config_dict:
            log.msg(
                "the 'debugPassword' parameter is unused and can be removed from the configuration flie")

        if 'manhole' in config_dict:
            # we don't check that this is a manhole instance, since that
            # requires importing buildbot.manhole for every user, and currently
            # that will fail if pycrypto isn't installed
            self.manhole = config_dict['manhole']

        if 'revlink' in config_dict:
            revlink = config_dict['revlink']
            if not callable(revlink):
                error("revlink must be a callable")
            else:
                self.revlink = revlink

    def load_validation(self, filename, config_dict):
        validation = config_dict.get("validation", {})
        if not isinstance(validation, dict):
            error("c['validation'] must be a dictionary")
        else:
            unknown_keys = (
                set(validation.keys()) - set(self.validation.keys()))
            if unknown_keys:
                error("unrecognized validation key(s): %s" %
                      (", ".join(unknown_keys)))
            else:
                self.validation.update(validation)

    @staticmethod
    def getDbUrlFromConfig(config_dict, throwErrors=True):

        if 'db' in config_dict:
            db = config_dict['db']
            if set(db.keys()) - set(['db_url', 'db_poll_interval']) and throwErrors:
                error("unrecognized keys in c['db']")
            config_dict = db

        if 'db_poll_interval' in config_dict and throwErrors:
            warnDeprecated(
                "0.8.7", "db_poll_interval is deprecated and will be ignored")

        # we don't attempt to parse db URLs here - the engine strategy will do
        # so.
        if 'db_url' in config_dict:
            return config_dict['db_url']

        return DEFAULT_DB_URL

    def load_db(self, filename, config_dict):
        self.db = dict(db_url=self.getDbUrlFromConfig(config_dict))

    def load_mq(self, filename, config_dict):
        from buildbot.mq import connector  # avoid circular imports
        if 'mq' in config_dict:
            self.mq.update(config_dict['mq'])

        classes = connector.MQConnector.classes
        typ = self.mq.get('type', 'simple')
        if typ not in classes:
            error("mq type '%s' is not known" % (typ,))
            return

        known_keys = classes[typ]['keys']
        unk = set(self.mq.keys()) - known_keys - set(['type'])
        if unk:
            error("unrecognized keys in c['mq']: %s"
                  % (', '.join(unk),))

    def load_metrics(self, filename, config_dict):
        # we don't try to validate metrics keys
        if 'metrics' in config_dict:
            metrics = config_dict["metrics"]
            if not isinstance(metrics, dict):
                error("c['metrics'] must be a dictionary")
            else:
                self.metrics = metrics

    def load_caches(self, filename, config_dict):
        explicit = False
        if 'caches' in config_dict:
            explicit = True
            caches = config_dict['caches']
            if not isinstance(caches, dict):
                error("c['caches'] must be a dictionary")
            else:
                for (name, value) in iteritems(caches):
                    if not isinstance(value, int):
                        error("value for cache size '%s' must be an integer"
                              % name)
                    if value < 1:
                        error("'%s' cache size must be at least 1, got '%s'"
                              % (name, value))
                self.caches.update(caches)

        if 'buildCacheSize' in config_dict:
            if explicit:
                msg = "cannot specify c['caches'] and c['buildCacheSize']"
                error(msg)
            self.caches['Builds'] = config_dict['buildCacheSize']
        if 'changeCacheSize' in config_dict:
            if explicit:
                msg = "cannot specify c['caches'] and c['changeCacheSize']"
                error(msg)
            self.caches['Changes'] = config_dict['changeCacheSize']

    def load_schedulers(self, filename, config_dict):
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
            msg = "c['schedulers'] must be a list of Scheduler instances"
            error(msg)

        # convert from list to dict, first looking for duplicates
        seen_names = set()
        for s in schedulers:
            if s.name in seen_names:
                error("scheduler name '%s' used multiple times" %
                      s.name)
            seen_names.add(s.name)

        self.schedulers = dict((s.name, s) for s in schedulers)

    def load_builders(self, filename, config_dict):
        if 'builders' not in config_dict:
            return
        builders = config_dict['builders']

        if not isinstance(builders, (list, tuple)):
            error("c['builders'] must be a list")
            return

        # convert all builder configs to BuilderConfig instances
        def mapper(b):
            if isinstance(b, BuilderConfig):
                return b
            elif isinstance(b, dict):
                return BuilderConfig(**b)
            else:
                error("%r is not a builder config (in c['builders']" % (b,))
        builders = [mapper(b) for b in builders]

        for builder in builders:
            if builder and os.path.isabs(builder.builddir):
                warnings.warn("Absolute path '%s' for builder may cause "
                              "mayhem.  Perhaps you meant to specify workerbuilddir "
                              "instead.")

        self.builders = builders

    @staticmethod
    def _check_workers(workers, conf_key):
        if not isinstance(workers, (list, tuple)):
            error("{0} must be a list".format(conf_key))
            return False

        for worker in workers:
            if not interfaces.IWorker.providedBy(worker):
                msg = "{0} must be a list of Worker instances".format(conf_key)
                error(msg)
                return False

            def validate(workername):
                if workername in ("debug", "change", "status"):
                    yield "worker name %r is reserved" % workername
                if not util_identifiers.ident_re.match(workername):
                    yield "worker name %r is not an identifier" % workername
                if not workername:
                    yield "worker name %r cannot be an empty string" % workername
                if len(workername) > 50:
                    yield "worker name %r is longer than %d characters" % (workername, 50)

            errors = list(validate(worker.workername))
            for msg in errors:
                error(msg)

            if errors:
                return False

        return True

    def load_workers(self, filename, config_dict):
        config_valid = True

        deprecated_workers = config_dict.get('slaves')
        if deprecated_workers is not None:
            reportDeprecatedWorkerNameUsage(
                "c['slaves'] key is deprecated, use c['workers'] instead",
                filename=filename)
            if not self._check_workers(deprecated_workers, "c['slaves']"):
                config_valid = False

        workers = config_dict.get('workers')
        if workers is not None:
            if not self._check_workers(workers, "c['workers']"):
                config_valid = False

        if deprecated_workers is not None and workers is not None:
            error("Use of c['workers'] and c['slaves'] at the same time is "
                  "not supported. Use only c['workers'] instead")
            return

        if not config_valid:
            return

        elif deprecated_workers is not None or workers is not None:
            self.workers = []
            if deprecated_workers is not None:
                self.workers.extend(deprecated_workers)
            if workers is not None:
                self.workers.extend(workers)

        else:
            pass

    def load_change_sources(self, filename, config_dict):
        change_source = config_dict.get('change_source', [])
        if isinstance(change_source, (list, tuple)):
            change_sources = change_source
        else:
            change_sources = [change_source]

        for s in change_sources:
            if not interfaces.IChangeSource.providedBy(s):
                msg = "c['change_source'] must be a list of change sources"
                error(msg)
                return

        self.change_sources = change_sources

    def load_status(self, filename, config_dict):
        if 'status' not in config_dict:
            return
        status = config_dict.get('status', [])

        msg = "c['status'] must be a list of status receivers"
        if not isinstance(status, (list, tuple)):
            error(msg)
            return

        msg = lambda s: "c['status'] contains an object that is not a status receiver (type %r)" % type(
            s)
        for s in status:
            if not interfaces.IStatusReceiver.providedBy(s):
                error(msg(s))
                return

        self.status = status

    def load_user_managers(self, filename, config_dict):
        if 'user_managers' not in config_dict:
            return
        user_managers = config_dict['user_managers']

        msg = "c['user_managers'] must be a list of user managers"
        if not isinstance(user_managers, (list, tuple)):
            error(msg)
            return

        self.user_managers = user_managers

    def load_www(self, filename, config_dict):
        if 'www' not in config_dict:
            return
        www_cfg = config_dict['www']
        allowed = set(['port', 'debug', 'json_cache_seconds',
                       'rest_minimum_version', 'allowed_origins', 'jsonp',
                       'plugins', 'auth', 'authz', 'avatar_methods', 'logfileName',
                       'logRotateLength', 'maxRotatedFiles', 'versions',
                       'change_hook_dialects', 'change_hook_auth',
                       'custom_templates_dir'])
        unknown = set(list(www_cfg)) - allowed

        if unknown:
            error("unknown www configuration parameter(s) %s" %
                  (', '.join(unknown),))

        versions = www_cfg.get('versions')

        if versions is not None:
            cleaned_versions = []
            if not isinstance(versions, list):
                error('Invalid www configuration value of versions')
            else:
                for i, v in enumerate(versions):
                    if not isinstance(v, tuple) or len(v) < 2:
                        error('Invalid www configuration value of versions')
                        break
                    cleaned_versions.append(v)
            www_cfg['versions'] = cleaned_versions

        self.www.update(www_cfg)

    def load_services(self, filename, config_dict):
        if 'services' not in config_dict:
            return
        self.services = {}
        for _service in config_dict['services']:
            if not isinstance(_service, util_service.BuildbotService):
                error("%s object should be an instance of "
                      "buildbot.util.service.BuildbotService" % type(_service))

                continue

            self.services[_service.name] = _service

    def check_single_master(self):
        # check additional problems that are only valid in a single-master
        # installation
        if self.multiMaster:
            return

        if not self.workers:
            error("no workers are configured")

        if not self.builders:
            error("no builders are configured")

        # check that all builders are implemented on this master
        unscheduled_buildernames = set([b.name for b in self.builders])
        for s in itervalues(self.schedulers):
            for n in s.listBuilderNames():
                if n in unscheduled_buildernames:
                    unscheduled_buildernames.remove(n)
        if unscheduled_buildernames:
            error("builder(s) %s have no schedulers to drive them"
                  % (', '.join(unscheduled_buildernames),))

    def check_schedulers(self):
        # don't perform this check in multiMaster mode
        if self.multiMaster:
            return

        all_buildernames = set([b.name for b in self.builders])

        for s in itervalues(self.schedulers):
            for n in s.listBuilderNames():
                if n not in all_buildernames:
                    error("Unknown builder '%s' in scheduler '%s'"
                          % (n, s.name))

    def check_locks(self):
        # assert that all locks used by the Builds and their Steps are
        # uniquely named.
        lock_dict = {}

        def check_lock(l):
            if isinstance(l, locks.LockAccess):
                l = l.lockid
            if l.name in lock_dict:
                if lock_dict[l.name] is not l:
                    msg = "Two locks share the same name, '%s'" % l.name
                    error(msg)
            else:
                lock_dict[l.name] = l

        for b in self.builders:
            if b.locks:
                for l in b.locks:
                    check_lock(l)

    def check_builders(self):
        # look both for duplicate builder names, and for builders pointing
        # to unknown workers
        workernames = set([w.workername for w in self.workers])
        seen_names = set()
        seen_builddirs = set()

        for b in self.builders:
            unknowns = set(b.workernames) - workernames
            if unknowns:
                error("builder '%s' uses unknown workers %s" %
                      (b.name, ", ".join(repr(u) for u in unknowns)))
            if b.name in seen_names:
                error("duplicate builder name '%s'" % b.name)
            seen_names.add(b.name)

            if b.builddir in seen_builddirs:
                error("duplicate builder builddir '%s'" % b.builddir)
            seen_builddirs.add(b.builddir)

    def check_status(self):
        # allow status receivers to check themselves against the rest of the
        # receivers
        for s in self.status:
            s.checkConfig(self.status)

    def check_horizons(self):
        if self.logHorizon is not None and self.buildHorizon is not None:
            if self.logHorizon > self.buildHorizon:
                error("logHorizon must be less than or equal to buildHorizon")

    def check_ports(self):
        ports = set()
        if self.protocols:
            for proto, options in iteritems(self.protocols):
                if proto == 'null':
                    port = -1
                else:
                    port = options.get("port")
                if not port:
                    continue
                if isinstance(port, int):
                    # Conversion needed to compare listenTCP and strports ports
                    port = "tcp:%d" % port
                if port != -1 and port in ports:
                    error("Some of ports in c['protocols'] duplicated")
                ports.add(port)

        if ports:
            return
        if self.workers:
            error("workers are configured, but c['protocols'] not")


class BuilderConfig(util_config.ConfiguredMixin, WorkerAPICompatMixin):

    def __init__(self, name=None, workername=None, workernames=None,
                 builddir=None, workerbuilddir=None, factory=None,
                 tags=None, category=None,
                 nextWorker=None, nextBuild=None, locks=None, env=None,
                 properties=None, collapseRequests=None, description=None,
                 canStartBuild=None,

                 slavename=None,  # deprecated, use `workername` instead
                 slavenames=None,  # deprecated, use `workernames` instead
                 # deprecated, use `workerbuilddir` instead
                 slavebuilddir=None,
                 nextSlave=None,  # deprecated, use `nextWorker` instead
                 ):

        # Deprecated API support.
        if slavename is not None:
            reportDeprecatedWorkerNameUsage(
                "'slavename' keyword argument is deprecated, "
                "use 'workername' instead")
            assert workername is None
            workername = slavename
        if slavenames is not None:
            reportDeprecatedWorkerNameUsage(
                "'slavenames' keyword argument is deprecated, "
                "use 'workernames' instead")
            assert workernames is None
            workernames = slavenames
        if slavebuilddir is not None:
            reportDeprecatedWorkerNameUsage(
                "'slavebuilddir' keyword argument is deprecated, "
                "use 'workerbuilddir' instead")
            assert workerbuilddir is None
            workerbuilddir = slavebuilddir
        if nextSlave is not None:
            reportDeprecatedWorkerNameUsage(
                "'nextSlave' keyword argument is deprecated, "
                "use 'nextWorker' instead")
            assert nextWorker is None
            nextWorker = nextSlave

        # name is required, and can't start with '_'
        if not name or type(name) not in (str, unicode):
            error("builder's name is required")
            name = '<unknown>'
        elif name[0] == '_':
            error(
                "builder names must not start with an underscore: '%s'" % name)
        try:
            self.name = util.ascii2unicode(name)
        except UnicodeDecodeError:
            error("builder names must be unicode or ASCII")

        # factory is required
        if factory is None:
            error("builder '%s' has no factory" % name)
        from buildbot.process.factory import BuildFactory
        if factory is not None and not isinstance(factory, BuildFactory):
            error("builder '%s's factory is not a BuildFactory instance" %
                  name)
        self.factory = factory

        # workernames can be a single worker name or a list, and should also
        # include workername, if given
        if isinstance(workernames, str):
            workernames = [workernames]
        if workernames:
            if not isinstance(workernames, list):
                error("builder '%s': workernames must be a list or a string" %
                      (name,))
        else:
            workernames = []

        if workername:
            if not isinstance(workername, str):
                error("builder '%s': workername must be a string" % (name,))
            workernames = workernames + [workername]
        if not workernames:
            error("builder '%s': at least one workername is required" %
                  (name,))

        self.workernames = workernames
        self._registerOldWorkerAttr("workernames")

        # builddir defaults to name
        if builddir is None:
            builddir = safeTranslate(name)
        self.builddir = builddir

        # workerbuilddir defaults to builddir
        if workerbuilddir is None:
            workerbuilddir = builddir
        self.workerbuilddir = workerbuilddir
        self._registerOldWorkerAttr("workerbuilddir")

        # remainder are optional

        if category and tags:
            error("builder '%s': builder categories are deprecated and "
                  "replaced by tags; you should only specify tags" % (name,))
        if category:
            warnDeprecated("0.9", "builder '%s': builder categories are "
                                  "deprecated and should be replaced with "
                                  "'tags=[cat]'" % (name,))
            if not isinstance(category, str):
                error("builder '%s': category must be a string" % (name,))
            tags = [category]
        if tags:
            if not isinstance(tags, list):
                error("builder '%s': tags must be a list" % (name,))
            bad_tags = any((tag for tag in tags if not isinstance(tag, str)))
            if bad_tags:
                error(
                    "builder '%s': tags list contains something that is not a string" % (name,))
        else:
            tags = []

        self.tags = tags

        self.nextWorker = nextWorker
        self._registerOldWorkerAttr("nextWorker")
        if nextWorker and not callable(nextWorker):
            error('nextWorker must be a callable')
            # Keeping support of the previous nextWorker API
        if nextWorker and (nextWorker.func_code.co_argcount == 2 or
                           (isinstance(nextWorker, MethodType) and
                            nextWorker.func_code.co_argcount == 3)):
            warnDeprecated(
                "0.9", "nextWorker now takes a 3rd argument (build request)")
            self.nextWorker = lambda x, y, z: nextWorker(
                x, y)  # pragma: no cover
        self.nextBuild = nextBuild
        if nextBuild and not callable(nextBuild):
            error('nextBuild must be a callable')
        self.canStartBuild = canStartBuild
        if canStartBuild and not callable(canStartBuild):
            error('canStartBuild must be a callable')

        self.locks = locks or []
        self.env = env or {}
        if not isinstance(self.env, dict):
            error("builder's env must be a dictionary")
        self.properties = properties or {}
        self.collapseRequests = collapseRequests

        self.description = description

    def getConfigDict(self):
        # note: this method will disappear eventually - put your smarts in the
        # constructor!
        rv = {
            'name': self.name,
            'workernames': self.workernames,
            'factory': self.factory,
            'builddir': self.builddir,
            'workerbuilddir': self.workerbuilddir,
        }
        if self.tags:
            rv['tags'] = self.tags
        if self.nextWorker:
            rv['nextWorker'] = self.nextWorker
        if self.nextBuild:
            rv['nextBuild'] = self.nextBuild
        if self.locks:
            rv['locks'] = self.locks
        if self.env:
            rv['env'] = self.env
        if self.properties:
            rv['properties'] = self.properties
        if self.collapseRequests is not None:
            rv['collapseRequests'] = self.collapseRequests
        if self.description:
            rv['description'] = self.description
        return rv
