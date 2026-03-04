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

from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar

import jinja2
from twisted.internet import defer

from buildbot import config
from buildbot import util
from buildbot.process.properties import Properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import Results
from buildbot.process.results import statusToString
from buildbot.reporters import utils

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Sequence

    from buildbot.util.twisted import InlineCallbacksType


def get_detected_status_text(mode: Any, results: int, previous_results: int | None) -> str:
    if results == FAILURE:
        if (
            ('change' in mode or 'problem' in mode)
            and previous_results is not None
            and previous_results != FAILURE
        ):
            text = "new failure"
        else:
            text = "failed build"
    elif results == WARNINGS:
        text = "problem in the build"
    elif results == SUCCESS:
        if "change" in mode and previous_results is not None and previous_results != results:
            text = "restored build"
        else:
            text = "passing build"
    elif results == EXCEPTION:
        text = "build exception"
    else:
        text = f"{statusToString(results)} build"

    return text


def get_message_summary_text(build: Any, results: int) -> str:
    t = build['state_string']
    if t:
        t = ": " + t
    else:
        t = ""

    if results == SUCCESS:
        text = "Build succeeded!"
    elif results == WARNINGS:
        text = f"Build Had Warnings{t}"
    elif results == CANCELLED:
        text = "Build was cancelled"
    else:
        text = f"BUILD FAILED{t}"

    return text


def get_message_source_stamp_text(source_stamps: Any) -> str:
    text = ""

    for ss in source_stamps:
        source = ""

        if ss['branch']:
            source += f"[branch {ss['branch']}] "

        if ss['revision']:
            source += str(ss['revision'])
        else:
            source += "HEAD"

        if ss['patch'] is not None:
            source += " (plus patch)"

        discriminator = ""
        if ss['codebase']:
            discriminator = f" '{ss['codebase']}'"

        text += f"Build Source Stamp{discriminator}: {source}\n"

    return text


def get_projects_text(source_stamps: Any, master: Any) -> str:
    projects: set[str] | list[Any] = set()

    for ss in source_stamps:
        if ss['project']:
            projects.add(ss['project'])  # type: ignore[union-attr]

    if not projects:
        projects = [master.config.title]

    return ', '.join(list(projects))


def create_context_for_build(
    mode: Any, build: Any, is_buildset: bool, master: Any, blamelist: Any
) -> dict[str, Any]:
    buildset = build['buildset']
    ss_list = buildset['sourcestamps']
    results = build['results']

    if 'prev_build' in build and build['prev_build'] is not None:
        previous_results = build['prev_build']['results']
    else:
        previous_results = None

    return {
        'results': build['results'],
        'result_names': Results,
        'mode': mode,
        'buildername': build['builder']['name'],
        'workername': build['properties'].get('workername', ["<unknown>"])[0],
        'buildset': buildset,
        'build': build,
        'is_buildset': is_buildset,
        'projects': get_projects_text(ss_list, master),
        'previous_results': previous_results,
        'status_detected': get_detected_status_text(mode, results, previous_results),
        'build_url': utils.getURLForBuild(master, build['builder']['builderid'], build['number']),
        'buildbot_title': master.config.title,
        'buildbot_url': master.config.buildbotURL,
        'blamelist': blamelist,
        'summary': get_message_summary_text(build, results),
        'sourcestamps': get_message_source_stamp_text(ss_list),
    }


def create_context_for_buildset(
    mode: Any, buildset: Any, builds: Any, master: Any, blamelist: Any
) -> dict[str, Any]:
    ss_list = buildset['sourcestamps']
    results = buildset["results"]

    return {
        "results": results,
        "result_names": Results,
        "mode": mode,
        "buildset": buildset,
        "builds": builds,
        "is_buildset": True,
        "projects": get_projects_text(ss_list, master),
        "status_detected": get_detected_status_text(mode, results, None),
        "buildbot_title": master.config.title,
        "buildbot_url": master.config.buildbotURL,
        "blamelist": blamelist,
        "sourcestamps": get_message_source_stamp_text(ss_list),
    }


def create_context_for_worker(master: Any, worker: Any) -> dict[str, Any]:
    return {
        'buildbot_title': master.config.title,
        'buildbot_url': master.config.buildbotURL,
        'worker': worker,
    }


class MessageFormatterBase(util.ComparableMixin):
    template_type = 'plain'

    def __init__(
        self,
        ctx: dict[str, Any] | None = None,
        want_properties: bool = True,
        want_steps: bool = False,
        want_logs: bool = False,
        want_logs_content: bool = False,
    ) -> None:
        if ctx is None:
            ctx = {}
        self.context = ctx
        self.want_properties = want_properties
        self.want_steps = want_steps
        self.want_logs = want_logs
        self.want_logs_content = want_logs_content

    def buildAdditionalContext(self, master: Any, ctx: dict[str, Any]) -> None:
        pass

    @defer.inlineCallbacks
    def render_message_dict(
        self, master: Any, context: dict[str, Any]
    ) -> InlineCallbacksType[dict[str, Any]]:
        """Generate a buildbot reporter message and return a dictionary
        containing the message body, type and subject.

        This is an informal description of what message dictionaries are expected to be
        produced. It is an internal API and expected to change even within bugfix releases, if
        needed.

        The message dictionary contains the 'body', 'type' and 'subject' keys:

          - 'subject' is a string that defines a subject of the message. It's not necessarily
            used on all reporters. It may be None.

          - 'type' must be 'plain', 'html' or 'json'.

          - 'body' is the content of the message. It may be None. The type of the data depends
            on the value of the 'type' parameter:

            - 'plain': Must be a string

            - 'html': Must be a string

            - 'json': Must be a non-encoded jsonable value. The root element must be either
              of dictionary, list or string. This must not change during all invocations of
              a particular instance of the formatter.

          - "extra_info" is an optional dictionary of dictionaries of extra information.

        In case of a report being created for multiple builds (e.g. in the case of a buildset),
        the values returned by message formatter are concatenated. If this is not possible
        (e.g. if the body is a dictionary), any subsequent messages are ignored.
        """
        yield self.buildAdditionalContext(master, context)  # type: ignore[func-returns-value]
        context.update(self.context)

        body, subject, extra_info = yield defer.gatherResults(
            [
                defer.maybeDeferred(self.render_message_body, context),
                defer.maybeDeferred(self.render_message_subject, context),
                defer.maybeDeferred(self.render_message_extra_info, context),
            ],
            consumeErrors=True,
        )

        return {
            "body": body,
            'type': self.template_type,
            "subject": subject,
            "extra_info": extra_info,
        }

    def render_message_body(self, context: dict[str, Any]) -> Any:
        return None

    def render_message_subject(self, context: dict[str, Any]) -> Any:
        return None

    def render_message_extra_info(self, context: dict[str, Any]) -> Any:
        return None

    def format_message_for_build(self, master: Any, build: Any, **kwargs: Any) -> Any:
        # Known kwargs keys: mode, users, is_buildset
        raise NotImplementedError

    def format_message_for_buildset(
        self, master: Any, buildset: Any, builds: Any, **kwargs: Any
    ) -> Any:
        # Known kwargs keys: mode, users, is_buildset
        raise NotImplementedError


class MessageFormatterEmpty(MessageFormatterBase):
    def format_message_for_build(self, master: Any, build: Any, **kwargs: Any) -> dict[str, Any]:
        return {'body': None, 'type': 'plain', 'subject': None, "extra_info": None}

    def format_message_for_buildset(
        self, master: Any, buildset: Any, builds: Any, **kwargs: Any
    ) -> dict[str, Any]:
        return {"body": None, "type": "plain", "subject": None}


class MessageFormatterFunctionRaw(MessageFormatterBase):
    def __init__(self, function: Callable[..., Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._function = function

    @defer.inlineCallbacks
    def format_message_for_build(  # type: ignore[override]
        self,
        master: Any,
        build: Any,
        is_buildset: bool = False,
        users: Any = None,
        mode: Any = None,
    ) -> InlineCallbacksType[dict[str, Any]]:
        ctx = create_context_for_build(mode, build, is_buildset, master, users)
        msgdict = yield self._function(master, ctx)
        return {
            "body": msgdict.get("body", None),
            "type": msgdict.get("type", "plain"),
            "subject": msgdict.get("subject", None),
            "extra_info": msgdict.get("extra_info", None),
        }

    @defer.inlineCallbacks
    def format_message_for_buildset(
        self,
        master: Any,
        buildset: Any,
        builds: Any,
        users: Any = None,
        mode: Any = None,
        **kwargs: Any,
    ) -> InlineCallbacksType[dict[str, Any]]:
        ctx = create_context_for_buildset(mode, buildset, builds, master, users)
        msgdict = yield self._function(master, ctx)
        return {
            "body": msgdict.get("body", None),
            "type": msgdict.get("type", "plain"),
            "subject": msgdict.get("subject", None),
            "extra_info": msgdict.get("extra_info", None),
        }


class MessageFormatterFunction(MessageFormatterBase):
    def __init__(self, function: Callable[..., Any], template_type: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.template_type = template_type
        self._function = function

    @defer.inlineCallbacks
    def format_message_for_build(
        self, master: Any, build: Any, **kwargs: Any
    ) -> InlineCallbacksType[dict[str, Any]]:
        msgdict = yield self.render_message_dict(master, {'build': build})
        return msgdict

    @defer.inlineCallbacks
    def format_message_for_buildset(
        self, master: Any, buildset: Any, builds: Any, **kwargs: Any
    ) -> InlineCallbacksType[dict[str, Any]]:
        msgdict = yield self.render_message_dict(master, {"buildset": buildset, "builds": builds})
        return msgdict

    def render_message_body(self, context: dict[str, Any]) -> Any:
        return self._function(context)

    def render_message_subject(self, context: dict[str, Any]) -> None:
        return None


class MessageFormatterRenderable(MessageFormatterBase):
    template_type = 'plain'

    def __init__(self, template: Any, subject: Any = None) -> None:
        super().__init__()
        self.template = template
        self.subject = subject

    @defer.inlineCallbacks
    def format_message_for_build(
        self, master: Any, build: Any, **kwargs: Any
    ) -> InlineCallbacksType[dict[str, Any]]:
        msgdict = yield self.render_message_dict(master, {'build': build, 'master': master})
        return msgdict

    def format_message_for_buildset(
        self, master: Any, buildset: Any, builds: Any, **kwargs: Any
    ) -> Any:
        raise NotImplementedError

    @defer.inlineCallbacks
    def render_message_body(self, context: dict[str, Any]) -> InlineCallbacksType[Any]:
        props = Properties.fromDict(context['build']['properties'])
        props.master = context['master']

        body = yield props.render(self.template)
        return body

    @defer.inlineCallbacks
    def render_message_subject(self, context: dict[str, Any]) -> InlineCallbacksType[Any]:
        if self.subject is None:
            return None

        props = Properties.fromDict(context['build']['properties'])
        props.master = context['master']

        body = yield props.render(self.subject)
        return body


default_body_template_plain = """\
A {{ status_detected }} has been detected on builder {{ buildername }} while building {{ projects }}.

Full details are available at:
    {{ build_url }}

Build state: {{ build['state_string'] }}
Revision: {{ build['properties'].get('got_revision', ['(unknown)'])[0] }}
Worker: {{ workername }}
Build Reason: {{ build['properties'].get('reason', ["(unknown)"])[0] }}
Blamelist: {{ ", ".join(blamelist) }}

Steps:
{% if build['steps'] %}{% for step in build['steps'] %}
- {{ step['number'] }}: {{ step['name'] }} ( {{ result_names[step['results']] }} )
{% if step['logs'] %}    Logs:{% for log in step['logs'] %}
        - {{ log.name }}: {{ log.url }}{% endfor %}
{% endif %}{% endfor %}
{% else %}
- (no steps)
{% endif %}
"""


default_body_template_html = """\
<p>A {{ status_detected }} has been detected on builder
<a href="{{ build_url }}">{{ buildername }}</a>
while building {{ projects }}.</p>
<p>Information:</p>
<ul>
    <li>Build state: {{ build['state_string'] }}</li>
    <li>Revision: {{ build['properties'].get('got_revision', ['(unknown)'])[0] }}</li>
    <li>Worker: {{ workername }}</li>
    <li>Build Reason: {{ build['properties'].get('reason', ["(unknown)"])[0] }}</li>
    <li>Blamelist: {{ ", ".join(blamelist) }}</li>
</ul>
<p>Steps:</p>
<ul>
{% if build['steps'] %}{% for step in build['steps'] %}
    <li style="{{ results_style[step['results']] }}">
    {{ step['number'] }}: {{ step['name'] }} ( {{ result_names[step['results']] }} )
    {% if step['logs'] %}({% for log in step['logs'] %}
        <a href="{{ log.url }}">&lt;{{ log.name }}&gt;</a>{% endfor %}
    )
    {% endif %}</li>
{% endfor %}{% else %}
    <li>No steps</li>
{% endif %}
</ul>
"""

default_subject_template = """\
{{ '☠' if result_names[results] == 'failure' else '☺' if result_names[results] == 'success' else '☝' }} \
Buildbot ({{ buildbot_title }}): {{ build['properties'].get('project', ['whole buildset'])[0] if is_buildset else buildername }} \
- \
{{ build['state_string'] }} \
{{ '(%s)' % (build['properties']['branch'][0] if (build['properties']['branch'] and build['properties']['branch'][0]) else build['properties'].get('got_revision', ['(unknown revision)'])[0]) }}"""


class MessageFormatterBaseJinja(MessageFormatterBase):
    compare_attrs: ClassVar[Sequence[str]] = ['body_template', 'subject_template', 'template_type']
    subject_template: jinja2.Template | None = None
    template_type = 'plain'
    uses_default_body_template = False

    def __init__(
        self,
        template: str | None = None,
        subject: str | None = None,
        template_type: str | None = None,
        extra_info_cb: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if template_type is not None:
            self.template_type = template_type

        if template is None:
            self.uses_default_body_template = True
            if self.template_type == 'plain':
                template = default_body_template_plain
            elif self.template_type == 'html':
                template = default_body_template_html
            else:
                config.error(
                    f'{self.__class__.__name__}: template type {self.template_type} '
                    'is not known to pick default template'
                )

            kwargs['want_steps'] = True
            kwargs['want_logs'] = True

        if subject is None:
            subject = default_subject_template

        self.body_template = jinja2.Template(template)  # type: ignore[arg-type]
        self.subject_template = jinja2.Template(subject)
        self.extra_info_cb = extra_info_cb

        super().__init__(**kwargs)

    def buildAdditionalContext(self, master: Any, ctx: dict[str, Any]) -> None:
        if self.uses_default_body_template:
            ctx['results_style'] = {
                SUCCESS: '',
                EXCEPTION: 'color: #f0f; font-weight: bold;',
                FAILURE: 'color: #f00; font-weight: bold;',
                RETRY: 'color: #4af;',
                SKIPPED: 'color: #4af;',
                WARNINGS: 'color: #f80;',
                CANCELLED: 'color: #4af;',
            }

    def render_message_body(self, context: dict[str, Any]) -> str:
        return self.body_template.render(context)

    def render_message_subject(self, context: dict[str, Any]) -> str:
        return self.subject_template.render(context)  # type: ignore[union-attr]

    def render_message_extra_info(self, context: dict[str, Any]) -> Any:
        if self.extra_info_cb is None:
            return None
        return self.extra_info_cb(context)


class MessageFormatter(MessageFormatterBaseJinja):
    @defer.inlineCallbacks
    def format_message_for_build(  # type: ignore[override]
        self,
        master: Any,
        build: Any,
        is_buildset: bool = False,
        users: Any = None,
        mode: Any = None,
    ) -> InlineCallbacksType[dict[str, Any]]:
        ctx = create_context_for_build(mode, build, is_buildset, master, users)
        msgdict = yield self.render_message_dict(master, ctx)
        return msgdict

    @defer.inlineCallbacks
    def format_message_for_buildset(  # type: ignore[override]
        self, master: Any, buildset: Any, builds: Any, users: Any = None, mode: Any = None
    ) -> InlineCallbacksType[dict[str, Any]]:
        ctx = create_context_for_buildset(mode, buildset, builds, master, users)
        msgdict = yield self.render_message_dict(master, ctx)
        return msgdict


default_missing_template_plain = """\
The Buildbot worker named {{worker.name}} went away.

It last disconnected at {{worker.last_connection}}.

{% if 'admin' in worker['workerinfo'] %}
The admin on record (as reported by WORKER:info/admin) was {{worker.workerinfo.admin}}.
{% endif %}
"""

default_missing_template_html = """\
<p>The Buildbot worker named {{worker.name}} went away.</p>
<p>It last disconnected at {{worker.last_connection}}.</p>

{% if 'admin' in worker['workerinfo'] %}
<p>The admin on record (as reported by WORKER:info/admin) was {{worker.workerinfo.admin}}.</p>
{% endif %}
"""


default_missing_worker_subject_template = (
    'Buildbot {{ buildbot_title }} worker {{ worker.name }} missing'
)


class MessageFormatterMissingWorker(MessageFormatterBaseJinja):
    def __init__(
        self,
        template: str | None = None,
        subject: str | None = None,
        template_type: str | None = None,
        **kwargs: Any,
    ) -> None:
        if template_type is None:
            template_type = 'plain'

        if template is None:
            if template_type == 'plain':
                template = default_missing_template_plain
            elif template_type == 'html':
                template = default_missing_template_html
            else:
                config.error(
                    f'{self.__class__.__name__}: template type {self.template_type} '
                    'is not known to pick default template'
                )

        if subject is None:
            subject = default_missing_worker_subject_template
        super().__init__(template=template, subject=subject, template_type=template_type, **kwargs)

    @defer.inlineCallbacks
    def formatMessageForMissingWorker(
        self, master: Any, worker: Any
    ) -> InlineCallbacksType[dict[str, Any]]:
        ctx = create_context_for_worker(master, worker)
        msgdict = yield self.render_message_dict(master, ctx)
        return msgdict
