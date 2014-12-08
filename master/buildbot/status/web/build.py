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
import json

from twisted.web import html
from twisted.internet import defer, reactor
from twisted.web.util import Redirect, DeferredResource

import urllib, time
from twisted.python import log
from buildbot.status.web.base import HtmlResource, \
     css_classes, path_to_build, path_to_builder, path_to_slave, \
    path_to_codebases, path_to_builders, path_to_step, getCodebasesArg, \
     getAndCheckProperties, ActionResource, path_to_authzfail, \
     getRequestCharset, path_to_json_build
from buildbot.schedulers.forcesched import ForceScheduler, TextParameter
from buildbot.status.web.status_json import BuildJsonResource
from buildbot.status.web.step import StepsResource
from buildbot.status.web.tests import TestsResource
from buildbot import util, interfaces

class ForceBuildActionResource(ActionResource):

    def __init__(self, build_status, builder):
        self.build_status = build_status
        self.builder = builder
        self.action = "forceBuild"

    @defer.inlineCallbacks
    def performAction(self, req):
        url = None
        authz = self.getAuthz(req)
        res = yield authz.actionAllowed(self.action, req, self.builder)

        if not res:
            url = path_to_authzfail(req)
        else:
            # get a control object
            c = interfaces.IControl(self.getBuildmaster(req))
            bc = c.getBuilder(self.builder.getName())

            b = self.build_status
            builder_name = urllib.quote(self.builder.getName(), safe='')
            builder_name_link = urllib.quote(self.builder.getName(), safe='')
            log.msg("web rebuild of build %s:%s" % (builder_name, b.getNumber()))
            name =authz.getUsernameFull(req)
            comments = req.args.get("comments", ["<no reason specified>"])[0]
            comments.decode(getRequestCharset(req))
            reason = ("The web-page 'rebuild' button was pressed by "
                      "'%s':\n" % (comments))
            msg = ""
            extraProperties = getAndCheckProperties(req)
            if not bc or not b.isFinished() or extraProperties is None:
                msg = "could not rebuild: "
                if b.isFinished():
                    msg += "build still not finished "
                if bc:
                    msg += "could not get builder control"
            else:
                tup = yield bc.rebuildBuild(b, reason, extraProperties)
                # rebuildBuild returns None on error (?!)
                if not tup:
                    msg = "rebuilding a build failed "+ str(tup)
            # we're at
            # http://localhost:8080/builders/NAME/builds/5/rebuild?[args]
            # Where should we send them?
            #
            # Ideally it would be to the per-build page that they just started,
            # but we don't know the build number for it yet (besides, it might
            # have to wait for a current build to finish). The next-most
            # preferred place is somewhere that the user can see tangible
            # evidence of their build starting (or to see the reason that it
            # didn't start). This should be the Builder page.

            url = path_to_builder(req, self.builder), msg
        defer.returnValue(url)


class StopBuildActionResource(ActionResource):

    def __init__(self, build_status):
        self.build_status = build_status
        self.action = "stopBuild"

    @defer.inlineCallbacks
    def performAction(self, req):
        authz = self.getAuthz(req)
        res = yield authz.actionAllowed(self.action, req, self.build_status)

        if not res:
            defer.returnValue(path_to_authzfail(req))
            return

        b = self.build_status
        log.msg("web stopBuild of build %s:%s" % \
                    (b.getBuilder().getName(), b.getNumber()))
        name = authz.getUsernameFull(req)
        comments = req.args.get("comments", ["<no reason specified>"])[0]
        comments.decode(getRequestCharset(req))
        # html-quote both the username and comments, just to be safe
        reason = ("The web-page 'Stop Build' button was pressed by "
                  "'%s': %s\n" % (html.escape(name), html.escape(comments)))

        c = interfaces.IControl(self.getBuildmaster(req))
        bldrc = c.getBuilder(self.build_status.getBuilder().getName())
        if bldrc:
            bldc = bldrc.getBuild(self.build_status.getNumber())
            if bldc:
                bldc.stopBuild(reason)

        defer.returnValue(path_to_builder(req, self.build_status.getBuilder()))

class StopBuildChainActionResource(ActionResource):

    def __init__(self, build_status):
        self.build_status = build_status
        self.action = "stopAllBuilds"

    def stopCurrentBuild(self, master, buildername, number, reason):
        builderc = master.getBuilder(buildername)
        if builderc:
            buildc = builderc.getBuild(number)
            if buildc:
                buildc.stopBuild(reason)
        return buildc

    @defer.inlineCallbacks
    def cancelCurrentBuild(self, master, brids, buildername):
        builderc = master.getBuilder(buildername)
        brcontrols = yield builderc.getPendingBuildRequestControls(brids=brids)
        for build_req in brcontrols:
            if build_req:
                build_req.cancel()

        defer.returnValue(len(brcontrols) > 0)

    @defer.inlineCallbacks
    def stopEntireBuildChain(self, master, build, buildername, reason, brid=None, retry=0):

        if build:

            if retry > 3:
                log.msg("Giving up after 3 times retry, stop build chain: buildername: %s, build # %d" %
                            (buildername, build.build_status.number))
                return

            buildchain = yield build.getBuildChain(brid)
            if len(buildchain) < 1:
                return

            if brid is not None:
                yield build.setStopBuildChain(brid)

            for br in buildchain:
                if br['number']:
                    buildc = self.stopCurrentBuild(master, br['buildername'], br['number'], reason)
                    log.msg("Stopping build chain: buildername: %s, build # %d, brid: %d" %
                            (br['buildername'], br['number'], br['brid']))
                    # stop dependencies subtree
                    yield self.stopEntireBuildChain(master, buildc, br['buildername'], reason, br['brid'])
                else:
                    # the build was still on the queue
                    canceledrequests = yield self.cancelCurrentBuild(master, [br['brid']], br['buildername'])

                    if not canceledrequests:
                        # the build was removed from queue, we will need to update the build chain list
                        log.msg("Could not cancel build chain: buildername: %s, brid: %d" %
                            (br['buildername'], br['brid']))

                    log.msg("Canceling build chain: buildername: %s, brid: %d" %
                            (br['buildername'], br['brid']))

            # the build chain should be empty by now, will retry any builds that changed state
            buildchain = yield build.getBuildChain(brid)
            if len(buildchain) > 0:
                retry += 1
                log.msg("Retry #%d stop build chain: buildername: %s, build # %d" %
                            (retry, buildername, build.build_status.number))
                yield self.stopEntireBuildChain(master, build, buildername, reason, brid, retry)


    @defer.inlineCallbacks
    def performAction(self, req):
        authz = self.getAuthz(req)
        res = yield authz.actionAllowed(self.action, req, self.build_status)

        if not res:
            defer.returnValue(path_to_authzfail(req))
            return

        b = self.build_status
        log.msg("web stopEntireBuildChain of build %s:%s" % \
                    (b.getBuilder().getName(), b.getNumber()))
        name = authz.getUsernameFull(req)

        reason = ("The web-page 'Stop Entire Build Chain' button was pressed by '%s'\n"
                  % html.escape(name))

        master = interfaces.IControl(self.getBuildmaster(req))
        buildername = self.build_status.getBuilder().getName()
        number = self.build_status.getNumber()

        builderc = master.getBuilder(buildername)
        if builderc:
            build = builderc.getBuild(number)

        if build:
            markedrequests = yield build.setStopBuildChain()

            if markedrequests:
                yield self.stopEntireBuildChain(master, build, buildername, reason)

            build.stopBuild(reason)

        defer.returnValue(path_to_builder(req, self.build_status.getBuilder()))

# /builders/$builder/builds/$buildnum
class StatusResourceBuild(HtmlResource):
    addSlash = True

    def __init__(self, build_status):
        HtmlResource.__init__(self)
        self.build_status = build_status

    def getPageTitle(self, request):
        return ("Katana - %s Build #%d" %
                (self.build_status.getBuilder().getFriendlyName(),
                 self.build_status.getNumber()))

    @defer.inlineCallbacks
    def content(self, req, cxt):
        b = self.build_status
        status = self.getStatus(req)
        req.setHeader('Cache-Control', 'no-cache')

        builder = self.build_status.getBuilder()
        cxt['builder'] = builder
        cxt['builder_name'] = builder.getFriendlyName()
        cxt['build_number'] = b.getNumber()
        cxt['builder_name_link'] = urllib.quote(self.build_status.getBuilder().getName(), safe='')
        cxt['b'] = b
        project = cxt['selectedproject'] = builder.getProject()
        cxt['path_to_builder'] = path_to_builder(req, b.getBuilder())
        cxt['path_to_builders'] = path_to_builders(req, project)
        cxt['path_to_codebases'] = path_to_codebases(req, project)
        cxt['build_url'] = path_to_build(req, b, False)
        codebases_arg = cxt['codebases_arg'] = getCodebasesArg(request=req)

        if not b.isFinished():
            cxt['stop_build_chain'] = False
            step = b.getCurrentStep()
            if not step:
                cxt['current_step'] = "[waiting for build slave]"
            else:
                if step.isWaitingForLocks():
                    cxt['current_step'] = "%s [waiting for build slave]" % step.getName()
                else:
                    cxt['current_step'] = step.getName()
            when = b.getETA()
            if when is not None:
                cxt['when'] = util.formatInterval(when)
                cxt['when_time'] = time.strftime("%H:%M:%S",
                                                time.localtime(time.time() + when))

        else:
            cxt['result_css'] = css_classes[b.getResults()]
            if b.getTestResults():
                cxt['tests_link'] = req.childLink("tests")

        ssList = b.getSourceStamps()
        sourcestamps = cxt['sourcestamps'] = ssList

        all_got_revisions = b.getAllGotRevisions()
        cxt['got_revisions'] = all_got_revisions

        try:
            slave_obj = status.getSlave(b.getSlavename())

            if slave_obj is not None:
                cxt['slave_friendly_name'] = slave_obj.getFriendlyName()
                cxt['slave_url'] = path_to_slave(req, slave_obj)
            else:
                cxt['slave_friendly_name'] = b.getSlavename()
                cxt['slave_url'] = ""

        except KeyError:
            pass

        cxt['steps'] = []

        for s in b.getSteps():
            step = {'name': s.getName() }

            if s.isFinished():
                if s.isHidden():
                    continue

                step['css_class'] = css_classes[s.getResults()[0]]
                (start, end) = s.getTimes()
                step['time_to_run'] = util.formatInterval(end - start)
            elif s.isStarted():
                if s.isWaitingForLocks():
                    step['css_class'] = "waiting"
                    step['time_to_run'] = "waiting for locks"
                else:
                    step['css_class'] = "running"
                    step['time_to_run'] = "running"
            else:
                step['css_class'] = "not_started"
                step['time_to_run'] = ""

            cxt['steps'].append(step)

            step['link'] = path_to_step(req, s)
            step['text'] = " ".join(s.getText())
            urls = []
            getUrls = s.getURLs().items()
            for k,v in s.getURLs().items():
                if isinstance(v, dict):
                    if 'results' in v.keys():
                        url_dict = dict(logname=k, url=v['url'] + codebases_arg, results=css_classes[v['results']])
                    else:
                        url_dict = dict(logname=k, url=v['url'] + codebases_arg)
                else:
                    url_dict = dict(logname=k, url=v + codebases_arg)
                urls.append(url_dict)

            step['urls'] = urls

            step['logs']= []
            for l in s.getLogs():
                logname = l.getName()
                step['logs'].append({ 'link': req.childLink("steps/%s/logs/%s%s" %
                                           (urllib.quote(s.getName(), safe=''),
                                            urllib.quote(logname, safe=''), codebases_arg)),
                                      'name': logname })

        scheduler = b.getProperty("scheduler", None)
        parameters = {}
        master = self.getBuildmaster(req)
        for sch in master.allSchedulers():
            if isinstance(sch, ForceScheduler) and scheduler == sch.name:
                for p in sch.all_fields:
                    parameters[p.name] = p

        ps = cxt['properties'] = []
        for name, value, source in b.getProperties().asList():
            if not isinstance(value, dict):
                cxt_value = unicode(value)
            else:
                cxt_value = value
            p = { 'name': name, 'value': cxt_value, 'source': source}
            if len(cxt_value) > 500:
                p['short_value'] = cxt_value[:500]
            if name in parameters:
                param = parameters[name]
                if isinstance(param, TextParameter):
                    p['text'] = param.value_to_text(value)
                    p['cols'] = param.cols
                    p['rows'] = param.rows
                p['label'] = param.label
            ps.append(p)


        (start, end, raw_end_time) = b.getTimes(include_raw_build_time=True)
        cxt['start'] = time.ctime(start)
        if end:
            cxt['end'] = time.ctime(end)
            cxt['elapsed'] = util.formatInterval(end - start)
            cxt['raw_elapsed'] = util.formatInterval(raw_end_time - start)
        else:
            now = util.now()
            cxt['elapsed'] = util.formatInterval(now - start)
            
        exactly = True
        has_changes = False
        for ss in sourcestamps:
            exactly = exactly and (ss.revision is not None)
            has_changes = has_changes or ss.changes
        cxt['exactly'] = (exactly) or b.getChanges()
        cxt['has_changes'] = has_changes
        cxt['authz'] = self.getAuthz(req)

        filters = {
            "number": b.getNumber()
        }

        build_json = BuildJsonResource(status, b)
        build_dict = yield build_json.asDict(req)
        cxt['instant_json']['build'] = {"url": path_to_json_build(status, req, builder.name, b.getNumber()),
                                        "data": json.dumps(build_dict, separators=(',', ':')),
                                        "waitForPush": status.master.config.autobahn_push,
                                        "pushFilters": {
                                            "buildStarted": filters,
                                            "buildFinished": filters,
                                            "stepStarted": filters,
                                            "stepFinished": filters,
                                        }}

        template = req.site.buildbot_service.templates.get_template("build.html")
        defer.returnValue(template.render(**cxt))

    def stop(self, req, auth_ok=False):
        # check if this is allowed
        if not auth_ok:
            return StopBuildActionResource(self.build_status)

        b = self.build_status
        log.msg("web stopBuild of build %s:%s" % \
                (b.getBuilder().getName(), b.getNumber()))

        name = self.getAuthz(req).getUsernameFull(req)
        comments = req.args.get("comments", ["<no reason specified>"])[0]
        comments.decode(getRequestCharset(req))
        # html-quote both the username and comments, just to be safe
        reason = ("The web-page 'stop build' button was pressed by "
                  "'%s': %s\n" % (html.escape(name), html.escape(comments)))

        c = interfaces.IControl(self.getBuildmaster(req))
        bldrc = c.getBuilder(self.build_status.getBuilder().getName())
        if bldrc:
            bldc = bldrc.getBuild(self.build_status.getNumber())
            if bldc:
                bldc.stopBuild(reason)

        # we're at http://localhost:8080/svn-hello/builds/5/stop?[args] and
        # we want to go to: http://localhost:8080/svn-hello
        r = Redirect(path_to_builder(req, self.build_status.getBuilder()))
        d = defer.Deferred()
        reactor.callLater(1, d.callback, r)
        return DeferredResource(d)

    def stopchain(self, req):
        return StopBuildChainActionResource(self.build_status)

    def rebuild(self, req):
        return ForceBuildActionResource(self.build_status,
                                        self.build_status.getBuilder())

    def getChild(self, path, req):
        if path == "stop":
            return self.stop(req)
        if path == "stopchain":
            return self.stopchain(req)
        if path == "rebuild":
            return self.rebuild(req)
        if path == "steps":
            return StepsResource(self.build_status)
        if path == "tests":
            return TestsResource(self.build_status)

        return HtmlResource.getChild(self, path, req)

# /builders/$builder/builds
class BuildsResource(HtmlResource):
    addSlash = True

    def __init__(self, builder_status):
        HtmlResource.__init__(self)
        self.builder_status = builder_status

    def content(self, req, cxt):
        return "subpages shows data for each build"

    def getChild(self, path, req):
        try:
            num = int(path)
        except ValueError:
            num = None
        if num is not None:
            build_status = self.builder_status.getBuild(num)
            if build_status:
                return StatusResourceBuild(build_status)

        return HtmlResource.getChild(self, path, req)

