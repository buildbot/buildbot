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

from __future__ import annotations

import datetime
import os
import re
import sys
import traceback
import warnings
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import ClassVar
from typing import Generator
from typing import Sequence
from typing import cast

from twisted.internet import defer
from twisted.python import log
from twisted.python.compat import execfile
from zope.interface import implementer

from buildbot import interfaces
from buildbot import locks
from buildbot import util
from buildbot.config.builder import BuilderConfig
from buildbot.config.errors import ConfigErrors
from buildbot.config.errors import capture_config_errors
from buildbot.config.errors import error
from buildbot.db.compression import ZStdCompressor
from buildbot.interfaces import IProperties
from buildbot.interfaces import IRenderable
from buildbot.process.codebase import Codebase
from buildbot.process.project import Project
from buildbot.revlinks import default_revlink_matcher
from buildbot.util import ComparableMixin
from buildbot.util import identifiers as util_identifiers
from buildbot.util import service as util_service
from buildbot.warnings import ConfigWarning
from buildbot.www import auth
from buildbot.www import avatar
from buildbot.www.authz import authz

DEFAULT_DB_URL = 'sqlite:///state.sqlite'

_in_unit_tests = False


def set_is_in_unit_tests(in_tests: bool) -> None:
    global _in_unit_tests
    _in_unit_tests = in_tests


def get_is_in_unit_tests() -> bool:
    return _in_unit_tests


def _default_log_compression_method() -> str:
    if ZStdCompressor.available:
        return ZStdCompressor.name
    return 'gz'


def loadConfigDict(basedir: str, configFileName: str) -> tuple[str, dict[str, Any]]:
    if not os.path.isdir(basedir):
        raise ConfigErrors([f"basedir '{basedir}' does not exist"])
    filename = os.path.join(basedir, configFileName)
    if not os.path.exists(filename):
        raise ConfigErrors([f"configuration file '{filename}' does not exist"])

    try:
        with open(filename, encoding='utf-8'):
            pass
    except OSError as e:
        raise ConfigErrors([f"unable to open configuration file {filename!r}: {e}"]) from e

    log.msg(f"Loading configuration from {filename!r}")

    # execute the config file
    localDict = {
        'basedir': os.path.expanduser(basedir),
        '__file__': os.path.abspath(filename),
    }

    old_sys_path = sys.path[:]
    sys.path.append(basedir)
    try:
        try:
            execfile(filename, localDict)
        except ConfigErrors:
            raise
        except SyntaxError:
            error(
                f"encountered a SyntaxError while parsing config file:\n{traceback.format_exc()} ",
                always_raise=True,
            )
        except Exception as e:
            log.err(e, 'error while parsing config file:')
            error(
                f"error while parsing config file: {sys.exc_info()[1]} (traceback in logfile)",
                always_raise=True,
            )
    finally:
        sys.path[:] = old_sys_path

    if 'BuildmasterConfig' not in localDict:
        error(
            f"Configuration file {filename!r} does not define 'BuildmasterConfig'",
            always_raise=True,
        )

    return filename, cast(dict[str, Any], localDict['BuildmasterConfig'])


@implementer(interfaces.IConfigLoader)
class FileLoader(ComparableMixin):
    compare_attrs: ClassVar[Sequence[str]] = ['basedir', 'configFileName']

    def __init__(self, basedir: str, configFileName: str) -> None:
        self.basedir = basedir
        self.configFileName = configFileName

    def loadConfig(self) -> MasterConfig:
        # from here on out we can batch errors together for the user's
        # convenience
        with capture_config_errors(raise_on_error=True):
            filename, config_dict = loadConfigDict(self.basedir, self.configFileName)
            config = MasterConfig.loadFromDict(config_dict, filename)

        return config


@implementer(IRenderable)
@dataclass
class DBConfig:
    db_url: str | interfaces.IRenderable = DEFAULT_DB_URL
    engine_kwargs: dict[str, Any] = field(default_factory=lambda: {})

    @defer.inlineCallbacks
    def getRenderingFor(self, iprops: IProperties) -> Generator[Any, Any, DBConfig]:
        if interfaces.IRenderable.providedBy(self.db_url):
            db_url = yield iprops.render(self.db_url)
        else:
            db_url = self.db_url
        engine_kwargs = yield iprops.render(self.engine_kwargs)

        return DBConfig(db_url, engine_kwargs)


class MasterConfig(util.ComparableMixin):
    db: DBConfig
    protocols: dict[str, Any]
    schedulers: dict[str, Any]
    secretsProviders: list[Any]
    builders: list[Any]
    workers: list[Any]
    change_sources: list[Any]
    machines: list[Any]
    projects: list[Any]
    codebases: list[Any]
    status: list[Any]
    user_managers: list[Any]
    www: dict[str, Any]
    services: dict[str, Any]
    buildbotNetUsageData: str | None
    metrics: dict[str, Any] | None

    def __init__(self) -> None:
        # local import to avoid circular imports
        from buildbot.process import properties

        # default values for all attributes
        # global
        self.title = 'Buildbot'
        self.titleURL = 'http://buildbot.net/'
        self.buildbotURL = 'http://localhost:8080/'
        self.changeHorizon = None
        self.logCompressionLimit = 4 * 1024
        self.logCompressionMethod = _default_log_compression_method()
        self.logEncoding = 'utf-8'
        self.logMaxSize = None
        self.logMaxTailSize = None
        self.properties = properties.Properties()
        self.collapseRequests = None
        self.codebaseGenerator = None
        self.prioritizeBuilders = None
        self.select_next_worker = None
        self.multiMaster = False
        self.manhole = None
        self.protocols = {}
        self.buildbotNetUsageData = "basic"

        self.validation = {
            "branch": re.compile(r'^[\w.+/~-]*$'),
            "revision": re.compile(r'^[ \w\.\-/]*$'),
            "property_name": re.compile(r'^[\w\.\-/~:]*$'),
            "property_value": re.compile(r'^[\w\.\-/~:]*$'),
        }
        self.db = DBConfig()
        self.mq = {"type": 'simple'}
        self.metrics = None
        self.caches = {"Builds": 15, "Changes": 10}
        self.schedulers = {}
        self.secretsProviders = []
        self.builders = []
        self.workers = []
        self.change_sources = []
        self.machines = []
        self.projects = []
        self.codebases = []
        self.status = []
        self.user_managers = []
        self.revlink = default_revlink_matcher
        self.www = {
            "port": None,
            "plugins": {},
            "auth": auth.NoAuth(),
            "authz": authz.Authz(),
            "avatar_methods": avatar.AvatarGravatar(),
            "logfileName": 'http.log',
        }
        self.services = {}

    _known_config_keys = set([
        "buildbotNetUsageData",
        "buildbotURL",
        "buildCacheSize",
        "builders",
        "caches",
        "change_source",
        "codebaseGenerator",
        "codebases",
        "configurators",
        "changeCacheSize",
        "changeHorizon",
        'db',
        "db_url",
        "logCompressionLimit",
        "logCompressionMethod",
        "logEncoding",
        "logMaxSize",
        "logMaxTailSize",
        "manhole",
        "machines",
        "collapseRequests",
        "metrics",
        "mq",
        "multiMaster",
        "prioritizeBuilders",
        "projects",
        "properties",
        "protocols",
        "revlink",
        "schedulers",
        "secretsProviders",
        "select_next_worker",
        "services",
        "title",
        "titleURL",
        "user_managers",
        "validation",
        "www",
        "workers",
    ])
    compare_attrs: ClassVar[Sequence[str]] = list(_known_config_keys)

    def preChangeGenerator(self, **kwargs: Any) -> dict[str, Any]:
        return {
            'author': kwargs.get('author', None),
            'files': kwargs.get('files', None),
            'comments': kwargs.get('comments', None),
            'revision': kwargs.get('revision', None),
            'when_timestamp': kwargs.get('when_timestamp', None),
            'branch': kwargs.get('branch', None),
            'category': kwargs.get('category', None),
            'revlink': kwargs.get('revlink', ''),
            'properties': kwargs.get('properties', {}),
            'repository': kwargs.get('repository', ''),
            'project': kwargs.get('project', ''),
            'codebase': kwargs.get('codebase', None),
        }

    @classmethod
    def loadFromDict(cls, config_dict: dict[str, Any], filename: str) -> MasterConfig:
        # warning, all of this is loaded from a thread

        with capture_config_errors(raise_on_error=True):
            # check for unknown keys
            unknown_keys = set(config_dict.keys()) - cls._known_config_keys
            if unknown_keys:
                if len(unknown_keys) == 1:
                    error(f'Unknown BuildmasterConfig key {unknown_keys.pop()}')
                else:
                    error(f"Unknown BuildmasterConfig keys {', '.join(sorted(unknown_keys))}")

            # instantiate a new config object, which will apply defaults
            # automatically
            config = cls()

            # and defer the rest to sub-functions, for code clarity
            config.run_configurators(filename, config_dict)
            config.load_global(filename, config_dict)
            config.load_validation(filename, config_dict)
            config.load_dbconfig(filename, config_dict)
            config.load_mq(filename, config_dict)
            config.load_metrics(filename, config_dict)
            config.load_secrets(filename, config_dict)
            config.load_caches(filename, config_dict)
            config.load_schedulers(filename, config_dict)
            config.load_projects(filename, config_dict)
            config.load_codebases(filename, config_dict)
            config.load_builders(filename, config_dict)
            config.load_workers(filename, config_dict)
            config.load_change_sources(filename, config_dict)
            config.load_machines(filename, config_dict)
            config.load_user_managers(filename, config_dict)
            config.load_www(filename, config_dict)
            config.load_services(filename, config_dict)

            # run some sanity checks
            config.check_single_master()
            config.check_schedulers()
            config.check_locks()
            config.check_projects()
            config.check_builders()
            config.check_ports()
            config.check_machines()

        return config

    def run_configurators(self, filename: str, config_dict: dict[str, Any]) -> None:
        for configurator in config_dict.get('configurators', []):
            interfaces.IConfigurator(configurator).configure(config_dict)

    def load_global(self, filename: str, config_dict: dict[str, Any]) -> None:
        def copy_param(
            name: str,
            check_type: type | tuple[type, ...] | None = None,
            check_type_name: str | None = None,
            can_be_callable: bool = False,
        ) -> None:
            if name in config_dict:
                v = config_dict[name]
            else:
                return
            if (
                v is not None
                and check_type
                and not (isinstance(v, check_type) or (can_be_callable and callable(v)))
            ):
                error(f"c['{name}'] must be {check_type_name}")
            else:
                setattr(self, name, v)

        def copy_int_param(name: str) -> None:
            copy_param(name, check_type=int, check_type_name='an int')

        def copy_str_param(name: str) -> None:
            copy_param(name, check_type=(str,), check_type_name='a string')

        def copy_str_url_param_with_trailing_slash(name: str) -> None:
            copy_str_param(name)
            url = getattr(self, name, None)
            if url is not None and not url.endswith('/'):
                setattr(self, name, url + '/')

        copy_str_param('title')

        max_title_len = 18
        if len(self.title) > max_title_len:
            # Warn if the title length limiting logic in www/base/src/app/app.route.js
            # would hide the title.
            warnings.warn(
                'WARNING: Title is too long to be displayed. ' + '"Buildbot" will be used instead.',
                category=ConfigWarning,
                stacklevel=1,
            )

        copy_str_url_param_with_trailing_slash('titleURL')
        copy_str_url_param_with_trailing_slash('buildbotURL')

        def copy_str_or_callable_param(name: str) -> None:
            copy_param(
                name,
                check_type=(str,),
                check_type_name='a string or callable',
                can_be_callable=True,
            )

        if "buildbotNetUsageData" not in config_dict:
            if get_is_in_unit_tests():
                self.buildbotNetUsageData = None
            else:
                warnings.warn(
                    '`buildbotNetUsageData` is not configured and defaults to basic.\n'
                    'This parameter helps the buildbot development team to understand'
                    ' the installation base.\n'
                    'No personal information is collected.\n'
                    'Only installation software version info and plugin usage is sent.\n'
                    'You can `opt-out` by setting this variable to None.\n'
                    'Or `opt-in` for more information by setting it to "full".\n',
                    category=ConfigWarning,
                    stacklevel=1,
                )
        copy_str_or_callable_param('buildbotNetUsageData')

        copy_int_param('changeHorizon')
        copy_int_param('logCompressionLimit')

        self.logCompressionMethod = config_dict.get(
            'logCompressionMethod',
            _default_log_compression_method(),
        )
        if self.logCompressionMethod not in ('raw', 'bz2', 'gz', 'lz4', 'zstd', 'br'):
            error("c['logCompressionMethod'] must be 'raw', 'bz2', 'gz', 'lz4', 'br' or 'zstd'")

        if self.logCompressionMethod == "lz4":
            try:
                import lz4  # pylint: disable=import-outside-toplevel

                _ = lz4
            except ImportError:
                error(
                    "To set c['logCompressionMethod'] to 'lz4' "
                    "you must install the lz4 library ('pip install lz4')"
                )
        elif self.logCompressionMethod == "zstd":
            try:
                import zstandard  # pylint: disable=import-outside-toplevel

                _ = zstandard
            except ImportError:
                error(
                    "To set c['logCompressionMethod'] to 'zstd' "
                    "you must install the zstandard Buildbot extra ('pip install buildbot[zstd]')"
                )
        elif self.logCompressionMethod == "br":
            try:
                import brotli  # pylint: disable=import-outside-toplevel

                _ = brotli
            except ImportError:
                error(
                    "To set c['logCompressionMethod'] to 'br' "
                    "you must install the brotli Buildbot extra ('pip install buildbot[brotli]')"
                )

        copy_int_param('logMaxSize')
        copy_int_param('logMaxTailSize')
        copy_param('logEncoding')

        properties = config_dict.get('properties', {})
        if not isinstance(properties, dict):
            error("c['properties'] must be a dictionary")
        else:
            self.properties.update(properties, filename)

        collapseRequests = config_dict.get('collapseRequests')
        if collapseRequests not in (None, True, False) and not callable(collapseRequests):
            error("collapseRequests must be a callable, True, or False")
        else:
            self.collapseRequests = collapseRequests

        codebaseGenerator = config_dict.get('codebaseGenerator')
        if codebaseGenerator is not None and not callable(codebaseGenerator):
            error("codebaseGenerator must be a callable accepting a dict and returning a str")
        else:
            self.codebaseGenerator = codebaseGenerator

        prioritizeBuilders = config_dict.get('prioritizeBuilders')
        if prioritizeBuilders is not None and not callable(prioritizeBuilders):
            error("prioritizeBuilders must be a callable")
        else:
            self.prioritizeBuilders = prioritizeBuilders

        select_next_worker = config_dict.get("select_next_worker")
        if select_next_worker is not None and not callable(select_next_worker):
            error("select_next_worker must be a callable")
        else:
            self.select_next_worker = select_next_worker

        protocols = config_dict.get('protocols', {})
        if isinstance(protocols, dict):
            for proto, options in protocols.items():
                if not isinstance(proto, str):
                    error("c['protocols'] keys must be strings")
                if not isinstance(options, dict):
                    error(f"c['protocols']['{proto}'] must be a dict")
                    return
                if proto == "wamp":
                    self.check_wamp_proto(options)
        else:
            error("c['protocols'] must be dict")
            return
        self.protocols = protocols

        if 'multiMaster' in config_dict:
            self.multiMaster = config_dict["multiMaster"]

        if 'debugPassword' in config_dict:
            log.msg(
                "the 'debugPassword' parameter is unused and "
                "can be removed from the configuration file"
            )

        if 'manhole' in config_dict:
            # we don't check that this is a manhole instance, since that
            # requires importing buildbot.manhole for every user, and currently
            # that will fail if cryptography isn't installed
            self.manhole = config_dict['manhole']

        if 'revlink' in config_dict:
            revlink = config_dict['revlink']
            if not callable(revlink):
                error("revlink must be a callable")
            else:
                self.revlink = revlink

    def load_validation(self, filename: str, config_dict: dict[str, Any]) -> None:
        validation = config_dict.get("validation", {})
        if not isinstance(validation, dict):
            error("c['validation'] must be a dictionary")
        else:
            unknown_keys = set(validation.keys()) - set(self.validation.keys())
            if unknown_keys:
                error(f"unrecognized validation key(s): {', '.join(unknown_keys)}")
            else:
                self.validation.update(validation)

    @staticmethod
    def get_dbconfig_from_config(config_dict: dict[str, Any], throwErrors: bool = True) -> DBConfig:
        dbconfig = DBConfig()

        if 'db' in config_dict:
            if set(config_dict['db'].keys()) - set(['db_url', 'engine_kwargs']) and throwErrors:
                error("unrecognized keys in c['db']")
            dbconfig = DBConfig(
                db_url=config_dict['db'].get('db_url', DEFAULT_DB_URL),
                engine_kwargs=config_dict['db'].get('engine_kwargs', {}),
            )
        elif 'db_url' in config_dict:
            dbconfig = DBConfig(config_dict['db_url'])

        return dbconfig

    def load_dbconfig(self, filename: str, config_dict: dict[str, Any]) -> None:
        self.db = self.get_dbconfig_from_config(config_dict)

    def load_mq(self, filename: str, config_dict: dict[str, Any]) -> None:
        from buildbot.mq import connector  # avoid circular imports

        if 'mq' in config_dict:
            self.mq.update(config_dict['mq'])

        classes = connector.MQConnector.classes
        typ = self.mq.get('type', 'simple')
        if typ not in classes:
            error(f"mq type '{typ}' is not known")
            return

        known_keys = classes[typ]['keys']
        unk = set(self.mq.keys()) - set(known_keys) - set(['type'])
        if unk:
            error(f"unrecognized keys in c['mq']: {', '.join(unk)}")

    def load_metrics(self, filename: str, config_dict: dict[str, Any]) -> None:
        # we don't try to validate metrics keys
        if 'metrics' in config_dict:
            metrics = config_dict["metrics"]
            if not isinstance(metrics, dict):
                error("c['metrics'] must be a dictionary")
            else:
                self.metrics = metrics

    def load_secrets(self, filename: str, config_dict: dict[str, Any]) -> None:
        if 'secretsProviders' in config_dict:
            secretsProviders = config_dict["secretsProviders"]
            if not isinstance(secretsProviders, list):
                error("c['secretsProviders'] must be a list")
            else:
                self.secretsProviders = secretsProviders

    def load_caches(self, filename: str, config_dict: dict[str, Any]) -> None:
        explicit = False
        if 'caches' in config_dict:
            explicit = True
            caches = config_dict['caches']
            if not isinstance(caches, dict):
                error("c['caches'] must be a dictionary")
            else:
                for name, value in caches.items():
                    if not isinstance(value, int):
                        error(f"value for cache size '{name}' must be an integer")
                        return
                    if value < 1:
                        error(f"'{name}' cache size must be at least 1, got '{value}'")
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

    def load_schedulers(self, filename: str, config_dict: dict[str, Any]) -> None:
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
                error(f"scheduler name '{s.name}' used multiple times")
            seen_names.add(s.name)

        self.schedulers = dict((s.name, s) for s in schedulers)

    def load_projects(self, filename: str, config_dict: dict[str, Any]) -> None:
        if 'projects' not in config_dict:
            return
        projects = config_dict['projects']

        if not isinstance(projects, (list, tuple)):
            error("c['projects'] must be a list")
            return

        def mapper(p: Any) -> Any:
            if isinstance(p, Project):
                return p
            error(f"{p!r} is not a project config (in c['projects']")
            return None

        self.projects = [mapper(p) for p in projects]

    def load_codebases(self, filename: str, config_dict: dict[str, Any]) -> None:
        if 'codebases' not in config_dict:
            return

        codebases = config_dict['codebases']

        if not isinstance(codebases, (list, tuple)):
            error("c['codebases'] must be a list")
            return

        project_names = [p.name for p in self.projects]

        def mapper(c: Any) -> Any:
            if not isinstance(c, Codebase):
                error(f"{c!r} is not a codebase config (in c['codebases']")
                return None

            if c.project not in project_names:
                error(f"{c!r} includes unknown project name {c.project} (in c['codebases']")
                return None

            return c

        self.codebases = [mapper(p) for p in codebases]

    def load_builders(self, filename: str, config_dict: dict[str, Any]) -> None:
        if 'builders' not in config_dict:
            return
        builders = config_dict['builders']

        if not isinstance(builders, (list, tuple)):
            error("c['builders'] must be a list")
            return

        # convert all builder configs to BuilderConfig instances
        def mapper(b: Any) -> Any:
            if isinstance(b, BuilderConfig):
                return b
            elif isinstance(b, dict):
                return BuilderConfig(**b)
            else:
                error(f"{b!r} is not a builder config (in c['builders']")
            return None

        builders = [mapper(b) for b in builders]

        for builder in builders:
            if builder and os.path.isabs(builder.builddir):
                warnings.warn(
                    (
                        f"Absolute path '{builder.builddir}' for builder may cause mayhem. "
                        "Perhaps you meant to specify workerbuilddir instead."
                    ),
                    category=ConfigWarning,
                    stacklevel=1,
                )

        self.builders = builders

    @staticmethod
    def _check_workers(workers: list[Any], conf_key: str) -> bool:
        if not isinstance(workers, (list, tuple)):
            error(f"{conf_key} must be a list")
            return False

        for worker in workers:
            if not interfaces.IWorker.providedBy(worker):
                msg = f"{conf_key} must be a list of Worker instances but there is {worker!r}"
                error(msg)
                return False

            def validate(workername: str) -> Generator[str, None, None]:
                if workername in ("debug", "change", "status"):
                    yield f"worker name {workername!r} is reserved"
                if not util_identifiers.ident_re.match(workername):
                    yield f"worker name {workername!r} is not an identifier"
                if not workername:
                    yield f"worker name {workername!r} cannot be an empty string"
                max_workername = 50
                if len(workername) > max_workername:
                    yield f"worker name {workername!r} is longer than {max_workername} characters"

            errors = list(validate(worker.workername))
            for msg in errors:
                error(msg)

            if errors:
                return False

        return True

    def load_workers(self, filename: str, config_dict: dict[str, Any]) -> None:
        workers = config_dict.get('workers')
        if workers is None:
            return

        if not self._check_workers(workers, "c['workers']"):
            return

        self.workers = workers[:]

    def load_change_sources(self, filename: str, config_dict: dict[str, Any]) -> None:
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

        self.change_sources = list(change_sources)

    def load_machines(self, filename: str, config_dict: dict[str, Any]) -> None:
        if 'machines' not in config_dict:
            return

        machines = config_dict['machines']
        msg = "c['machines'] must be a list of machines"
        if not isinstance(machines, (list, tuple)):
            error(msg)
            return

        for m in machines:
            if not interfaces.IMachine.providedBy(m):
                error(msg)
                return

        self.machines = list(machines)

    def load_user_managers(self, filename: str, config_dict: dict[str, Any]) -> None:
        if 'user_managers' not in config_dict:
            return
        user_managers = config_dict['user_managers']

        msg = "c['user_managers'] must be a list of user managers"
        if not isinstance(user_managers, (list, tuple)):
            error(msg)
            return

        self.user_managers = list(user_managers)

    def load_www(self, filename: str, config_dict: dict[str, Any]) -> None:
        if 'www' not in config_dict:
            return
        www_cfg = config_dict['www']
        allowed = {
            'allowed_origins',
            'auth',
            'authz',
            'avatar_methods',
            'change_hook_auth',
            'change_hook_dialects',
            'cookie_expiration_time',
            'custom_templates_dir',
            'debug',
            'default_page',
            'json_cache_seconds',
            'jsonp',
            'logRotateLength',
            'logfileName',
            'maxRotatedFiles',
            'plugins',
            'port',
            'rest_minimum_version',
            'ui_default_config',
            'versions',
            'ws_ping_interval',
            'project_widgets',
            'graphql',
            'theme',
        }
        unknown = set(list(www_cfg)) - allowed

        if unknown:
            error(f"unknown www configuration parameter(s) {', '.join(unknown)}")

        versions = www_cfg.get('versions')

        if versions is not None:
            cleaned_versions = []
            if not isinstance(versions, list):
                error('Invalid www configuration value of versions')
            else:
                for v in versions:
                    if not isinstance(v, tuple) or len(v) < 2:
                        error('Invalid www configuration value of versions')
                        break
                    cleaned_versions.append(v)
            www_cfg['versions'] = cleaned_versions

        cookie_expiration_time = www_cfg.get('cookie_expiration_time')
        if cookie_expiration_time is not None:
            if not isinstance(cookie_expiration_time, datetime.timedelta):
                error(
                    'Invalid www["cookie_expiration_time"] configuration should '
                    'be a datetime.timedelta'
                )

        self.www.update(www_cfg)

    def load_services(self, filename: str, config_dict: dict[str, Any]) -> None:
        if 'services' not in config_dict:
            return
        self.services = {}
        for _service in config_dict['services']:
            if not isinstance(_service, util_service.BuildbotService):
                error(
                    f"{type(_service)} object should be an instance of "
                    "buildbot.util.service.BuildbotService"
                )

                continue

            assert _service.name is not None

            if _service.name in self.services:
                error(f'Duplicate service name {_service.name!r}')
                continue

            self.services[_service.name] = _service

    def check_single_master(self) -> None:
        # check additional problems that are only valid in a single-master
        # installation
        if self.multiMaster:
            return

        if not self.workers:
            error("no workers are configured")

        if not self.builders:
            error("no builders are configured")

        # check that all builders are implemented on this master
        unscheduled_buildernames = {b.name for b in self.builders}
        for s in self.schedulers.values():
            builderNames = s.listBuilderNames()
            if interfaces.IRenderable.providedBy(builderNames):
                unscheduled_buildernames.clear()
            else:
                for n in builderNames:
                    if interfaces.IRenderable.providedBy(n):
                        unscheduled_buildernames.clear()
                    elif n in unscheduled_buildernames:
                        unscheduled_buildernames.remove(n)
        if unscheduled_buildernames:
            names_str = ', '.join(unscheduled_buildernames)
            error(f"builder(s) {names_str} have no schedulers to drive them")

    def check_schedulers(self) -> None:
        # don't perform this check in multiMaster mode
        if self.multiMaster:
            return

        all_buildernames = {b.name for b in self.builders}

        for s in self.schedulers.values():
            builderNames = s.listBuilderNames()
            if interfaces.IRenderable.providedBy(builderNames):
                continue
            for n in builderNames:
                if interfaces.IRenderable.providedBy(n):
                    continue
                if n not in all_buildernames:
                    error(f"Unknown builder '{n}' in scheduler '{s.name}'")

    def check_locks(self) -> None:
        # assert that all locks used by the Builds and their Steps are
        # uniquely named.
        lock_dict: dict[str, Any] = {}

        def check_lock(lock: Any) -> None:
            if isinstance(lock, locks.LockAccess):
                lock = lock.lockid
            if lock.name in lock_dict:
                if lock_dict[lock.name] is not lock:
                    msg = f"Two locks share the same name, '{lock.name}'"
                    error(msg)
            else:
                lock_dict[lock.name] = lock

        for b in self.builders:
            if b.locks and not IRenderable.providedBy(b.locks):
                for lock in b.locks:
                    check_lock(lock)

    def check_projects(self) -> None:
        seen_names = set()
        for p in self.projects:
            if p.name in seen_names:
                error(f"duplicate project name '{p.name}'")
            seen_names.add(p.name)

    def check_builders(self) -> None:
        # look both for duplicate builder names, and for builders pointing
        # to unknown workers
        workernames = {w.workername for w in self.workers}
        project_names = {p.name for p in self.projects}

        seen_names = set()
        seen_builddirs = set()

        for b in self.builders:
            unknowns = set(b.workernames) - workernames
            if unknowns:
                error(
                    f"builder '{b.name}' uses unknown workers "
                    f"{', '.join(repr(u) for u in unknowns)}"
                )
            if b.name in seen_names:
                error(f"duplicate builder name '{b.name}'")
            seen_names.add(b.name)

            if b.builddir in seen_builddirs:
                error(f"duplicate builder builddir '{b.builddir}'")
            seen_builddirs.add(b.builddir)

            if b.project is not None:
                if b.project not in project_names:
                    error(f"builder '{b.name}' uses unknown project name '{b.project}'")

    def check_ports(self) -> None:
        ports: set[str | int] = set()
        if self.protocols:
            for proto, options in self.protocols.items():
                if proto == 'null':
                    port: str | int = -1
                else:
                    port = options.get("port")
                if port is None:
                    continue
                if isinstance(port, int):
                    # Conversion needed to compare listenTCP and strports ports
                    port = f"tcp:{port}"
                if port != -1 and port in ports:
                    error("Some of ports in c['protocols'] duplicated")
                ports.add(port)

        if ports:
            return
        if self.workers:
            error("workers are configured, but c['protocols'] not")

    def check_machines(self) -> None:
        seen_names = set()

        for mm in self.machines:
            if mm.name in seen_names:
                error(f"duplicate machine name '{mm.name}'")
            seen_names.add(mm.name)

        for w in self.workers:
            if w.machine_name is not None and w.machine_name not in seen_names:
                error(f"worker '{w.name}' uses unknown machine '{w.machine_name}'")

    def check_wamp_proto(self, options: dict[str, Any]) -> None:
        # This method is referenced but not implemented
        # Adding a stub to satisfy the type checker
        pass
