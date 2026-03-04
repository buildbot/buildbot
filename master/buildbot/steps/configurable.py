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

import re
import traceback
import warnings
from typing import TYPE_CHECKING
from typing import Any

import yaml
from evalidate import Expr
from evalidate import base_eval_model
from twisted.internet import defer

from buildbot.db.model import Model
from buildbot.plugins import util
from buildbot.plugins.db import get_plugins
from buildbot.process import buildstep
from buildbot.process.properties import Properties
from buildbot.process.properties import renderer
from buildbot.process.results import SUCCESS
from buildbot.steps.shell import ShellCommand
from buildbot.steps.trigger import Trigger
from buildbot.steps.worker import CompositeStepMixin

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class BuildbotCiYmlInvalid(Exception):
    pass


_env_string_key_re = re.compile(r'^\s*(\w+)=')
_env_string_value_re = re.compile(r'''(?:"((?:\\.|[^"])*?)"|'([^']*?)'|(\S*))''')


def parse_env_string(env_str: str, parent_env: dict[str, str] | None = None) -> dict[str, str]:
    env_str = env_str.strip()
    orig_env_str = env_str

    props: dict[str, str] = {}
    if parent_env:
        props.update(parent_env)
    if not env_str:
        return props

    while env_str:
        m = _env_string_key_re.match(env_str)
        if m is None:
            raise ValueError(f'Could not parse \'{orig_env_str}\': splitting \'{env_str}\' failed')
        k = m.group(1)

        env_str = env_str[m.end() :]

        m = _env_string_value_re.match(env_str)
        if m is None:
            raise ValueError(f'Could not parse \'{orig_env_str}\': splitting \'{env_str}\' failed')

        env_str = env_str[m.end() :]

        v = m.group(1) or m.group(2) or m.group(3) or ''
        props[k] = v

    return props


def interpolate_constructor(loader: yaml.Loader, node: yaml.Node) -> Any:
    value = loader.construct_scalar(node)
    return util.Interpolate(value)


class BuildbotCiLoader(yaml.SafeLoader):
    constructors_loaded = False

    @classmethod
    def ensure_constructors_loaded(cls) -> None:
        if cls.constructors_loaded:
            return
        cls.load_constructors()

    @classmethod
    def load_constructors(cls) -> None:
        cls.add_constructor('!Interpolate', interpolate_constructor)
        cls.add_constructor('!i', interpolate_constructor)

        steps = get_plugins('steps', None, load_now=True)
        for step_name in steps.names:
            # Accessing a step from the plugin DB may raise warrings (e.g. deprecation).
            # We don't want them logged until the step is actually used.
            with warnings.catch_warnings(record=True) as all_warnings:
                warnings.simplefilter("always")
                step_class = steps.get(step_name)
                step_warnings = list(all_warnings)
            cls.register_step_class(step_name, step_class, step_warnings)

    @classmethod
    def register_step_class(cls, name: str, step_class: Any, step_warnings: list[Any]) -> None:
        def step_constructor(loader: yaml.Loader, node: yaml.Node) -> Any:
            try:
                kwargs: dict[str, Any] = {}
                if isinstance(node, yaml.ScalarNode):
                    args = [loader.construct_scalar(node)]
                elif isinstance(node, yaml.SequenceNode):
                    args = loader.construct_sequence(node)
                elif isinstance(node, yaml.MappingNode):
                    args = []
                    kwargs = loader.construct_mapping(node)
                else:
                    raise Exception('Unsupported node type')
            except Exception as e:
                raise Exception(f"Could not parse steps arguments: {e}") from e

            # Re-raise all warnings that occurred when accessing step class. We only want them to be
            # logged if the configuration actually uses the step class.
            for w in step_warnings:
                warnings.warn_explicit(w.message, w.category, w.filename, w.lineno)

            return step_class(*args, **kwargs)

        cls.add_constructor('!' + name, step_constructor)


class BuildbotCiYml:
    SCRIPTS = (
        "before_install",
        "install",
        "after_install",
        "before_script",
        "script",
        "after_script",
    )

    steps_loaded = False

    def __init__(self) -> None:
        self.config_dict = None
        self.label_mapping: dict[str, Any] = {}
        self.global_env: dict[str, str] = {}
        self.script_commands: dict[str, list[Any]] = {}
        for script in self.SCRIPTS:
            self.script_commands[script] = []
        self.matrix: list[Any] = []

    @classmethod
    def load_from_str(cls, config_input: str) -> BuildbotCiYml:
        BuildbotCiLoader.ensure_constructors_loaded()

        try:
            config_dict = yaml.load(config_input, Loader=BuildbotCiLoader)
        except Exception as e:
            raise BuildbotCiYmlInvalid(f"Invalid YAML data\n{e}") from e

        return cls.load_from_dict(config_dict)

    @classmethod
    def load_from_dict(cls, config: Any) -> BuildbotCiYml:
        yml = cls()
        yml.load_from_dict_internal(config)
        return yml

    def load_from_dict_internal(self, config: Any) -> None:
        self.config = config
        self.label_mapping = self.config.get('label_mapping', {})
        self.global_env = BuildbotCiYml.load_global_env(config)
        self.script_commands = BuildbotCiYml.load_scripts(config)
        self.matrix = BuildbotCiYml.load_matrix(config, self.global_env)

    @classmethod
    def load_global_env(cls, config: Any) -> dict[str, str]:
        env = config.get("env", None)

        if env is None:
            return {}

        if isinstance(env, list):
            return {}

        if isinstance(env, dict):
            env = env.get('global')
            if isinstance(env, str):
                return parse_env_string(env)
            if isinstance(env, list):
                global_env: dict[str, str] = {}
                for e in env:
                    global_env.update(parse_env_string(e))
                return global_env
            raise BuildbotCiYmlInvalid("'env.global' configuration parameter is invalid")

        raise BuildbotCiYmlInvalid("'env' parameter is invalid")

    @classmethod
    def load_scripts(cls, config: Any) -> dict[str, list[Any]]:
        script_commands: dict[str, list[Any]] = {}
        for script in cls.SCRIPTS:
            commands = config.get(script, [])
            if isinstance(commands, str):
                commands = [commands]
            if not isinstance(commands, list):
                raise BuildbotCiYmlInvalid(f"'{script}' parameter is invalid")
            script_commands[script] = commands
        return script_commands

    @staticmethod
    def adjust_matrix_config(c: dict[str, Any], global_env: dict[str, str]) -> dict[str, Any]:
        c = c.copy()
        c['env'] = parse_env_string(c.get('env', ''), global_env)
        return c

    @classmethod
    def load_matrix(cls, config: Any, global_env: dict[str, str]) -> list[Any]:
        return [
            cls.adjust_matrix_config(matrix_config, global_env)
            for matrix_config in config.get('matrix', {}).get('include') or []
        ]


class BuildbotTestCiReadConfigMixin:
    config_filenames = ['.bbtravis.yml', '.buildbot-ci.yml']
    config: BuildbotCiYml | None = None
    descriptionDone: str | list[str] | None

    @defer.inlineCallbacks
    def get_config_yml_from_worker(self) -> InlineCallbacksType[tuple[str | None, Any]]:
        exceptions: list[Any] = []
        for filename in self.config_filenames:
            try:
                config_yml = yield self.getFileContentFromWorker(filename, abandonOnFailure=True)  # type: ignore[attr-defined]
                return filename, config_yml
            except buildstep.BuildStepFailed as e:
                exceptions.append(e)

        return None, exceptions

    @defer.inlineCallbacks
    def get_ci_config(self) -> InlineCallbacksType[BuildbotCiYml]:
        filename, result = yield self.get_config_yml_from_worker()
        if not filename:
            exceptions = result
            msg = ' '.join(str(exceptions))

            self.descriptionDone = "failed to read configuration"
            self.addCompleteLog(  # type: ignore[attr-defined]
                'error',
                f'Failed to read configuration from files {self.config_filenames}: got {msg}',
            )
            raise buildstep.BuildStepFailed("failed to read configuration")

        config_yml = result

        self.addCompleteLog(filename, config_yml)  # type: ignore[attr-defined]

        try:
            config = BuildbotCiYml.load_from_str(config_yml)
        except BuildbotCiYmlInvalid as e:
            self.descriptionDone = f'bad configuration file {filename}'
            self.addCompleteLog('error', f'Bad configuration file:\n{e}')  # type: ignore[attr-defined]
            raise buildstep.BuildStepFailed(f'bad configuration file {filename}') from e

        return config


class BuildbotTestCiTrigger(BuildbotTestCiReadConfigMixin, CompositeStepMixin, Trigger):
    def __init__(self, scheduler: str, **kwargs: Any) -> None:
        super().__init__(
            name='buildbot-test-ci trigger',
            waitForFinish=True,
            schedulerNames=[scheduler],
            haltOnFailure=True,
            flunkOnFailure=True,
            sourceStamps=[],
            alwaysUseLatest=False,
            updateSourceStamp=False,
            **kwargs,
        )

    @defer.inlineCallbacks
    def run(self) -> InlineCallbacksType[int]:
        self.config = yield self.get_ci_config()

        rv = yield super().run()
        return rv

    def _replace_label(self, v: str) -> str:
        return str(self.config.label_mapping.get(v, v))  # type: ignore[union-attr]

    def build_scheduler_for_env(
        self, scheduler_name: str, env: dict[str, Any]
    ) -> tuple[str, Properties]:
        new_build_props = Properties()
        new_build_props.setProperty(
            "BUILDBOT_PULL_REQUEST", self.getProperty("BUILDBOT_PULL_REQUEST"), "inherit"
        )
        for k, v in env.items():
            if k == "env":
                # v is dictionary
                new_build_props.update(v, "BuildbotTestCiTrigger")
            else:
                new_build_props.setProperty(k, v, "BuildbotTestCiTrigger")

        tags_from_props = sorted(
            f'{self._replace_label(k)}:{self._replace_label(v)}'
            for k, (v, _) in new_build_props.asDict().items()
            if k not in self.config.global_env.keys() and k != 'BUILDBOT_PULL_REQUEST'  # type: ignore[union-attr]
        )

        tags = [t for t in self.build.builder.config.tags if t not in ('try', 'spawner')]  # type: ignore[union-attr]

        new_build_props.setProperty(
            "virtual_builder_name", " ".join(tags + tags_from_props), "BuildbotTestCiTrigger"
        )
        new_build_props.setProperty(
            "virtual_builder_tags", tags + tags_from_props, "BuildbotTestCiTrigger"
        )
        new_build_props.setProperty(
            "matrix_label", "/".join(tags_from_props), "BuildbotTestCiTrigger"
        )

        return (scheduler_name, new_build_props)

    def createTriggerProperties(self, props: Any) -> Any:
        return props

    def getSchedulersAndProperties(self) -> list[Any]:
        scheduler_name = self.schedulerNames[0]
        return [self.build_scheduler_for_env(scheduler_name, env) for env in self.config.matrix]  # type: ignore[union-attr]


eval_model = base_eval_model.clone()
eval_model.nodes.append('Mul')
eval_model.nodes.append('Slice')
eval_model.nodes.append('Tuple')


def evaluate_condition(condition: str, local_dict: dict[str, Any]) -> bool:
    expr = Expr(condition, eval_model)
    return bool(expr.eval(local_dict))


class BuildbotCiSetupSteps(BuildbotTestCiReadConfigMixin, CompositeStepMixin, buildstep.BuildStep):
    name = "setup-steps"
    haltOnFailure = True
    flunkOnFailure = True
    MAX_NAME_LENGTH = 47
    disable = False

    def _add_step(self, command: Any) -> None:
        name = None
        condition = None
        step = None
        original_command = command
        if isinstance(command, dict):
            name = command.get("title")
            condition = command.get("condition")
            step = command.get("step")
            command = command.get("cmd")

        if isinstance(command, buildstep.BuildStep):
            step = command

        if condition is not None:
            try:
                local_dict = {k: v for k, (v, s) in self.build.getProperties().properties.items()}  # type: ignore[union-attr]
                if not evaluate_condition(condition, local_dict):
                    return
            except Exception:
                self.descriptionDone = "Problem parsing condition"
                self.addCompleteLog("condition error", traceback.format_exc())
                return

        if step is None:
            if command is None:
                self.addCompleteLog(
                    "BuildbotCiSetupSteps error",
                    f"Neither step nor cmd is defined: {original_command}",
                )
                return
            if name is None:
                name = self._name_from_command(command)

            @renderer
            def render_env(props: Properties) -> dict[str, str]:
                return {str(k): str(v[0]) for k, v in props.properties.items()}

            step = ShellCommand(
                name=name,
                description=command,
                command=command,
                doStepIf=not self.disable,
                env=render_env,
            )
        self.build.addStepsAfterLastStep([step])  # type: ignore[union-attr, list-item]

    def _name_from_command(self, name: str) -> str:
        name = name.lstrip("#").lstrip(" ").split("\n")[0]
        max_length = Model.steps.c.name.type.length  # type: ignore[attr-defined]
        if len(name) > max_length:
            name = name[: max_length - 3] + "..."
        return name

    @defer.inlineCallbacks
    def run(self) -> InlineCallbacksType[int]:
        config = yield self.get_ci_config()
        for k in BuildbotCiYml.SCRIPTS:
            for command in config.script_commands[k]:
                self._add_step(command=command)

        return SUCCESS
