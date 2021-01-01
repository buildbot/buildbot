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

import jinja2

from twisted.internet import defer

from buildbot import config
from buildbot import util
from buildbot.process.properties import Properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import statusToString
from buildbot.reporters import utils
from buildbot.warnings import warn_deprecated


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


class DeprecatedMessageFormatterBuildJson(MessageFormatterBase):

    template_type = 'json'

    def __init__(self, format_fn, **kwargs):
        super().__init__(**kwargs)
        self.format_fn = format_fn

    @defer.inlineCallbacks
    def format_message_for_build(self, mode, buildername, build, master, blamelist):
        msgdict = yield self.render_message_dict(master, {'build': build})
        return msgdict

    def render_message_body(self, context):
        return self.format_fn(context['build'])

    def render_message_subject(self, context):
        return None


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


class MessageFormatterBaseJinja(MessageFormatterBase):
    template_filename = 'default_mail.txt'

    compare_attrs = ['body_template', 'subject_template', 'template_type']

    def __init__(self, template_dir=None,
                 template_filename=None, template=None,
                 subject_filename=None, subject=None,
                 template_type=None, **kwargs):
        self.body_template = self.getTemplate(template_filename, template_dir, template)
        self.subject_template = None
        if subject_filename or subject:
            self.subject_template = self.getTemplate(subject_filename, template_dir, subject)

        if template_type is not None:
            self.template_type = template_type

        super().__init__(**kwargs)

    def getTemplate(self, filename, dirname, content):
        if content and (filename or dirname):
            config.error("Only one of template or template path can be given")

        if content:
            return jinja2.Template(content)

        if dirname is None:
            dirname = os.path.join(os.path.dirname(__file__), "templates")

        loader = jinja2.FileSystemLoader(dirname)
        env = jinja2.Environment(
            loader=loader, undefined=jinja2.StrictUndefined)

        if filename is None:
            filename = self.template_filename

        return env.get_template(filename)

    def buildAdditionalContext(self, master, ctx):
        pass

    def render_message_body(self, context):
        return self.body_template.render(context)

    def render_message_subject(self, context):
        if self.subject_template is None:
            return None
        return self.subject_template.render(context)


class MessageFormatter(MessageFormatterBaseJinja):
    template_filename = 'default_mail.txt'

    compare_attrs = ['wantProperties', 'wantSteps', 'wantLogs']

    def __init__(self, template_name=None, **kwargs):

        if template_name is not None:
            warn_deprecated('0.9.1', "template_name is deprecated, supply the template as text")
            kwargs['template_filename'] = template_name
        if 'template_filename' in kwargs:
            warn_deprecated('2.10.0',
                            "template_filename is deprecated, supply the template as text")
        if 'subject_filename' in kwargs:
            warn_deprecated('2.10.0',
                            "subject_filename is deprecated, supply the template as text")
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def format_message_for_build(self, mode, buildername, build, master, blamelist):
        ctx = create_context_for_build(mode, buildername, build, master, blamelist)
        msgdict = yield self.render_message_dict(master, ctx)
        return msgdict


class MessageFormatterMissingWorker(MessageFormatterBaseJinja):
    template_filename = 'missing_mail.txt'

    @defer.inlineCallbacks
    def formatMessageForMissingWorker(self, master, worker):
        ctx = create_context_for_worker(master, worker)
        msgdict = yield self.render_message_dict(master, ctx)
        return msgdict
