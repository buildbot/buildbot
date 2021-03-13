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


import jinja2

from twisted.internet import defer

from buildbot import util
from buildbot.process.properties import Properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import statusToString
from buildbot.reporters import utils


def get_detected_status_text(mode, results, previous_results):
    if results == FAILURE:
        if ('change' in mode or 'problem' in mode) and previous_results is not None \
                and previous_results != FAILURE:
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
        text = "{} build".format(statusToString(results))

    return text


def get_message_summary_text(build, results):
    t = build['state_string']
    if t:
        t = ": " + t
    else:
        t = ""

    if results == SUCCESS:
        text = "Build succeeded!"
    elif results == WARNINGS:
        text = "Build Had Warnings{}".format(t)
    elif results == CANCELLED:
        text = "Build was cancelled"
    else:
        text = "BUILD FAILED{}".format(t)

    return text


def get_message_source_stamp_text(source_stamps):
    text = ""

    for ss in source_stamps:
        source = ""

        if ss['branch']:
            source += "[branch {}] ".format(ss['branch'])

        if ss['revision']:
            source += str(ss['revision'])
        else:
            source += "HEAD"

        if ss['patch'] is not None:
            source += " (plus patch)"

        discriminator = ""
        if ss['codebase']:
            discriminator = " '{}'".format(ss['codebase'])

        text += "Build Source Stamp{}: {}\n".format(discriminator, source)

    return text


def get_projects_text(source_stamps, master):
    projects = set()

    for ss in source_stamps:
        if ss['project']:
            projects.add(ss['project'])

    if not projects:
        projects = [master.config.title]

    return ', '.join(list(projects))


def create_context_for_build(mode, buildername, build, master, blamelist):
    buildset = build['buildset']
    ss_list = buildset['sourcestamps']
    results = build['results']

    if 'prev_build' in build and build['prev_build'] is not None:
        previous_results = build['prev_build']['results']
    else:
        previous_results = None

    return {
        'results': build['results'],
        'mode': mode,
        'buildername': buildername,
        'workername': build['properties'].get('workername', ["<unknown>"])[0],
        'buildset': buildset,
        'build': build,
        'projects': get_projects_text(ss_list, master),
        'previous_results': previous_results,
        'status_detected': get_detected_status_text(mode, results, previous_results),
        'build_url': utils.getURLForBuild(master, build['builder']['builderid'], build['number']),
        'buildbot_url': master.config.buildbotURL,
        'blamelist': blamelist,
        'summary': get_message_summary_text(build, results),
        'sourcestamps': get_message_source_stamp_text(ss_list)
    }


def create_context_for_worker(master, worker):
    return {
        'buildbot_title': master.config.title,
        'buildbot_url': master.config.buildbotURL,
        'worker': worker,
    }


class MessageFormatterBase(util.ComparableMixin):

    template_type = 'plain'

    def __init__(self, ctx=None, wantProperties=True, wantSteps=False, wantLogs=False):
        if ctx is None:
            ctx = {}
        self.context = ctx
        self.wantProperties = wantProperties
        self.wantSteps = wantSteps
        self.wantLogs = wantLogs

    def buildAdditionalContext(self, master, ctx):
        pass

    @defer.inlineCallbacks
    def render_message_dict(self, master, context):
        """Generate a buildbot reporter message and return a dictionary
           containing the message body, type and subject."""

        ''' This is an informal description of what message dictionaries are expected to be
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

                - 'json': Must be a non-encoded jsonnable value. The root element must be either
                  of dictionary, list or string. This must not change during all invocations of
                  a particular instance of the formatter.

            In case of a report being created for multiple builds (e.g. in the case of a buildset),
            the values returned by message formatter are concatenated. If this is not possible
            (e.g. if the body is a dictionary), any subsequent messages are ignored.
        '''
        yield self.buildAdditionalContext(master, context)
        context.update(self.context)

        return {
            'body': (yield self.render_message_body(context)),
            'type': self.template_type,
            'subject': (yield self.render_message_subject(context))
        }

    def render_message_body(self, context):
        return None

    def render_message_subject(self, context):
        return None


class MessageFormatterEmpty(MessageFormatterBase):
    def format_message_for_build(self, mode, buildername, build, master, blamelist):
        return {
            'body': None,
            'type': 'plain',
            'subject': None
        }


class MessageFormatterFunction(MessageFormatterBase):

    def __init__(self, function, template_type, **kwargs):
        super().__init__(**kwargs)
        self.template_type = template_type
        self._function = function

    @defer.inlineCallbacks
    def format_message_for_build(self, mode, buildername, build, master, blamelist):
        msgdict = yield self.render_message_dict(master, {'build': build})
        return msgdict

    def render_message_body(self, context):
        return self._function(context)

    def render_message_subject(self, context):
        return None


class MessageFormatterRenderable(MessageFormatterBase):

    template_type = 'plain'

    def __init__(self, template, subject=None):
        super().__init__()
        self.template = template
        self.subject = subject

    @defer.inlineCallbacks
    def format_message_for_build(self, mode, buildername, build, master, blamelist):
        msgdict = yield self.render_message_dict(master, {'build': build, 'master': master})
        return msgdict

    @defer.inlineCallbacks
    def render_message_body(self, context):
        props = Properties.fromDict(context['build']['properties'])
        props.master = context['master']

        body = yield props.render(self.template)
        return body

    @defer.inlineCallbacks
    def render_message_subject(self, context):
        props = Properties.fromDict(context['build']['properties'])
        props.master = context['master']

        body = yield props.render(self.subject)
        return body


default_body_template = '''\
The Buildbot has detected a {{ status_detected }} on builder {{ buildername }} while building {{ projects }}.
Full details are available at:
    {{ build_url }}

Buildbot URL: {{ buildbot_url }}

Worker for this Build: {{ workername }}

Build Reason: {{ build['properties'].get('reason', ["<unknown>"])[0] }}
Blamelist: {{ ", ".join(blamelist) }}

{{ summary }}

Sincerely,
 -The Buildbot
'''  # noqa pylint: disable=line-too-long


class MessageFormatterBaseJinja(MessageFormatterBase):
    compare_attrs = ['body_template', 'subject_template', 'template_type']
    subject_template = None
    template_type = 'plain'

    def __init__(self, template=None, subject=None, template_type=None, **kwargs):
        if template is None:
            template = default_body_template

        self.body_template = jinja2.Template(template)

        if subject is not None:
            self.subject_template = jinja2.Template(subject)

        if template_type is not None:
            self.template_type = template_type

        super().__init__(**kwargs)

    def buildAdditionalContext(self, master, ctx):
        pass

    def render_message_body(self, context):
        return self.body_template.render(context)

    def render_message_subject(self, context):
        if self.subject_template is None:
            return None
        return self.subject_template.render(context)


class MessageFormatter(MessageFormatterBaseJinja):
    @defer.inlineCallbacks
    def format_message_for_build(self, mode, buildername, build, master, blamelist):
        ctx = create_context_for_build(mode, buildername, build, master, blamelist)
        msgdict = yield self.render_message_dict(master, ctx)
        return msgdict


default_missing_template = '''\
The Buildbot working for '{{buildbot_title}}' has noticed that the worker named {{worker.name}} went away.

It last disconnected at {{worker.last_connection}}.

{% if 'admin' in worker['workerinfo'] %}
The admin on record (as reported by WORKER:info/admin) was {{worker.workerinfo.admin}}.
{% endif %}

Sincerely,
 -The Buildbot
'''  # noqa pylint: disable=line-too-long


class MessageFormatterMissingWorker(MessageFormatterBaseJinja):
    template_filename = 'missing_mail.txt'

    def __init__(self, template=None, **kwargs):
        if template is None:
            template = default_missing_template
        super().__init__(template=template, **kwargs)

    @defer.inlineCallbacks
    def formatMessageForMissingWorker(self, master, worker):
        ctx = create_context_for_worker(master, worker)
        msgdict = yield self.render_message_dict(master, ctx)
        return msgdict
