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

from __future__ import absolute_import
from __future__ import print_function

import os

import jinja2

from twisted.internet import defer

from buildbot import config
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import statusToString
from buildbot.reporters import utils


class MessageFormatterBase(object):
    template_filename = 'default_mail.txt'
    template_type = 'plain'

    def __init__(self, template_dir=None,
                 template_filename=None, template=None,
                 subject_filename=None, subject=None,
                 template_type=None, ctx=None,
                 ):
        self.body_template = self.getTemplate(template_filename, template_dir, template)
        self.subject_template = None
        if subject_filename or subject:
            self.subject_template = self.getTemplate(subject_filename, template_dir, subject)

        if template_type is not None:
            self.template_type = template_type

        if ctx is None:
            ctx = {}

        self.ctx = ctx

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
        ctx.update(self.ctx)

    def renderMessage(self, ctx):
        body = self.body_template.render(ctx)
        msgdict = {'body': body, 'type': self.template_type}
        if self.subject_template is not None:
            msgdict['subject'] = self.subject_template.render(ctx)
        return msgdict


class MessageFormatter(MessageFormatterBase):
    template_filename = 'default_mail.txt'
    template_type = 'plain'

    def __init__(self, template_dir=None,
                 template_filename=None, template=None, template_name=None,
                 subject_filename=None, subject=None,
                 template_type=None, ctx=None,
                 wantProperties=True, wantSteps=False, wantLogs=False):

        if template_name is not None:
            config.warnDeprecated('0.9.1', "template_name is deprecated, use template_filename")
            template_filename = template_name
        MessageFormatterBase.__init__(self,
                                      template_dir=template_dir,
                                      template_filename=template_filename, template=template,
                                      subject_filename=subject_filename, subject=subject,
                                      template_type=template_type, ctx=ctx)
        self.wantProperties = wantProperties
        self.wantSteps = wantSteps
        self.wantLogs = wantLogs

    def getDetectedStatus(self, mode, results, previous_results):

        if results == FAILURE:
            if "change" in mode and previous_results is not None and previous_results != results:
                text = "new failure"
            elif "problem" in mode and previous_results and previous_results != FAILURE:
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
            text = "%s build" % (statusToString(results))

        return text

    def getProjects(self, source_stamps, master):
        projects = set()

        for ss in source_stamps:
            if ss['project']:
                projects.add(ss['project'])

        if not projects:
            projects = [master.config.title]

        return ', '.join(list(projects))

    def messageSourceStamps(self, source_stamps):
        text = ""

        for ss in source_stamps:
            source = ""

            if ss['branch']:
                source += "[branch %s] " % ss['branch']

            if ss['revision']:
                source += str(ss['revision'])
            else:
                source += "HEAD"

            if ss['patch'] is not None:
                source += " (plus patch)"

            discriminator = ""
            if ss['codebase']:
                discriminator = " '%s'" % ss['codebase']

            text += "Build Source Stamp%s: %s\n" % (discriminator, source)

        return text

    def messageSummary(self, build, results):
        t = build['state_string']
        if t:
            t = ": " + t
        else:
            t = ""

        if results == SUCCESS:
            text = "Build succeeded!"
        elif results == WARNINGS:
            text = "Build Had Warnings%s" % (t,)
        elif results == CANCELLED:
            text = "Build was cancelled"
        else:
            text = "BUILD FAILED%s" % (t,)

        return text

    @defer.inlineCallbacks
    def formatMessageForBuildResults(self, mode, buildername, buildset, build, master, previous_results, blamelist):
        """Generate a buildbot mail message and return a dictionary
           containing the message body, type and subject."""
        ss_list = buildset['sourcestamps']
        results = build['results']

        ctx = dict(results=build['results'],
                   mode=mode,
                   buildername=buildername,
                   workername=build['properties'].get(
                       'workername', ["<unknown>"])[0],
                   buildset=buildset,
                   build=build,
                   projects=self.getProjects(ss_list, master),
                   previous_results=previous_results,
                   status_detected=self.getDetectedStatus(
                       mode, results, previous_results),
                   build_url=utils.getURLForBuild(
                       master, build['builder']['builderid'], build['number']),
                   buildbot_url=master.config.buildbotURL,
                   blamelist=blamelist,
                   summary=self.messageSummary(build, results),
                   sourcestamps=self.messageSourceStamps(ss_list)
                   )
        yield self.buildAdditionalContext(master, ctx)
        msgdict = self.renderMessage(ctx)
        defer.returnValue(msgdict)


class MessageFormatterMissingWorker(MessageFormatterBase):
    template_filename = 'missing_mail.txt'

    @defer.inlineCallbacks
    def formatMessageForMissingWorker(self, master, worker):
        ctx = dict(buildbot_title=master.config.title,
                   buildbot_url=master.config.buildbotURL,
                   worker=worker)
        yield self.buildAdditionalContext(master, ctx)
        msgdict = self.renderMessage(ctx)
        defer.returnValue(msgdict)
