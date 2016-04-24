import os

import jinja2

from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import statusToString
from buildbot.reporters import utils


class MessageFormatter(object):
    template_name = 'default_mail.txt'
    template_type = 'plain'
    wantProperties = True
    wantSteps = False

    def __init__(self, template_name=None, template_dir=None, template_type=None):

        if template_dir is None:
            template_dir = os.path.join(os.path.dirname(__file__), "templates")

        loader = jinja2.FileSystemLoader(template_dir)
        self.env = jinja2.Environment(
            loader=loader, undefined=jinja2.StrictUndefined)

        if template_name is not None:
            self.template_name = template_name
        if template_type is not None:
            self.template_type = template_type

    def getDetectedStatus(self, mode, results, previous_results):

        if results == FAILURE:
            if "change" in mode and previous_results is not None and previous_results != results or \
                    "problem" in mode and previous_results and previous_results != FAILURE:
                text = "new failure"
            else:
                text = "failed build"
        elif results == WARNINGS:
            text = "The Buildbot has detected a problem in the build"
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

    def __call__(self, mode, buildername, buildset, build, master, previous_results, blamelist):
        """Generate a buildbot mail message and return a tuple of message text
            and type."""
        ss_list = buildset['sourcestamps']
        results = build['results']

        tpl = self.env.get_template(self.template_name)
        cxt = dict(results=build['results'],
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
        contents = tpl.render(cxt)
        return {'body': contents, 'type': 'plain'}
