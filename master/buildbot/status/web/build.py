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


from twisted.internet import defer
from twisted.internet import reactor
from twisted.web import html
from twisted.web.util import DeferredResource
from twisted.web.util import Redirect

import time
import urllib

from buildbot import interfaces
from buildbot import util
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.schedulers.forcesched import TextParameter
from buildbot.status.web.base import ActionResource
from buildbot.status.web.base import HtmlResource
from buildbot.status.web.base import css_classes
from buildbot.status.web.base import getAndCheckProperties
from buildbot.status.web.base import getRequestCharset
from buildbot.status.web.base import path_to_authzfail
from buildbot.status.web.base import path_to_build
from buildbot.status.web.base import path_to_builder
from buildbot.status.web.base import path_to_slave
from buildbot.status.web.step import StepsResource
from buildbot.status.web.tests import TestsResource
from twisted.python import log


def _get_comments_from_request(req):
    comments = req.args.get("comments", ["<no reason specified>"])[0]
    return comments.decode(getRequestCharset(req))


class ForceBuildActionResource(ActionResource):

    rebuildString = "The web-page 'rebuild' button was pressed by '%(rebuild_owner)s': %(rebuild_comments)s"

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
            builder_name = self.builder.getName()
            log.msg("web rebuild of build %s:%s" % (builder_name, b.getNumber()))
            name = authz.getUsernameFull(req)
            comments = _get_comments_from_request(req)

            reason = self.rebuildString % {
                'build_number': b.getNumber(),
                'owner': b.getInterestedUsers(),
                'rebuild_owner': name,
                'rebuild_comments': comments
            }

            useSourcestamp = req.args.get("useSourcestamp", None)
            if useSourcestamp and useSourcestamp == ['updated']:
                absolute = False
            else:
                absolute = True

            msg = ""
            extraProperties = getAndCheckProperties(req)
            if not bc or not b.isFinished() or extraProperties is None:
                msg = "could not rebuild: "
                if not b.isFinished():
                    msg += "build still not finished "
                if not bc:
                    msg += "could not get builder control"
            else:
                tup = yield bc.rebuildBuild(b,
                                            reason=reason,
                                            extraProperties=extraProperties,
                                            absolute=absolute)
                # rebuildBuild returns None on error (?!)
                if not tup:
                    msg = "rebuilding a build failed " + str(tup)
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
        log.msg("web stopBuild of build %s:%s" %
                (b.getBuilder().getName(), b.getNumber()))
        name = authz.getUsernameFull(req)
        comments = _get_comments_from_request(req)
        # html-quote both the username and comments, just to be safe
        reason = ("The web-page 'stop build' button was pressed by "
                  "'%s': %s\n" % (html.escape(name), html.escape(comments)))

        c = interfaces.IControl(self.getBuildmaster(req))
        bldrc = c.getBuilder(self.build_status.getBuilder().getName())
        if bldrc:
            bldc = bldrc.getBuild(self.build_status.getNumber())
            if bldc:
                bldc.stopBuild(reason)

        defer.returnValue(path_to_builder(req, self.build_status.getBuilder()))

# /builders/$builder/builds/$buildnum


class StatusResourceBuild(HtmlResource):
    addSlash = True

    def __init__(self, build_status):
        HtmlResource.__init__(self)
        self.build_status = build_status

    def getPageTitle(self, request):
        return ("Buildbot: %s Build #%d" %
                (self.build_status.getBuilder().getName(),
                 self.build_status.getNumber()))

    def content(self, req, cxt):
        b = self.build_status
        status = self.getStatus(req)
        req.setHeader('Cache-Control', 'no-cache')

        cxt['b'] = b
        cxt['path_to_builder'] = path_to_builder(req, b.getBuilder())

        if not b.isFinished():
            step = b.getCurrentStep()
            if not step:
                cxt['current_step'] = "[waiting for Lock]"
            else:
                if step.isWaitingForLocks():
                    cxt['current_step'] = "%s [waiting for Lock]" % step.getName()
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
            cxt['slave_url'] = path_to_slave(req, status.getSlave(b.getSlavename()))
        except KeyError:
            pass

        cxt['steps'] = []

        for s in b.getSteps():
            step = {'name': s.getName()}

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

            step['link'] = req.childLink("steps/%s" %
                                         urllib.quote(s.getName(), safe=''))
            step['text'] = " ".join([str(txt) for txt in s.getText()])
            step['urls'] = map(lambda x: dict(url=x[1], logname=x[0]), s.getURLs().items())

            step['logs'] = []
            for l in s.getLogs():
                logname = l.getName()
                step['logs'].append({'link': req.childLink("steps/%s/logs/%s" %
                                                           (urllib.quote(s.getName(), safe=''),
                                                            urllib.quote(logname, safe=''))),
                                     'name': logname})

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
            p = {'name': name, 'value': cxt_value, 'source': source}
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

        cxt['responsible_users'] = list(b.getResponsibleUsers())

        (start, end) = b.getTimes()
        cxt['start'] = time.ctime(start)
        if end:
            cxt['end'] = time.ctime(end)
            cxt['elapsed'] = util.formatInterval(end - start)
        else:
            now = util.now()
            cxt['elapsed'] = util.formatInterval(now - start)

        has_changes = False
        for ss in sourcestamps:
            has_changes = has_changes or ss.changes
        cxt['has_changes'] = has_changes
        cxt['build_url'] = path_to_build(req, b)
        cxt['authz'] = self.getAuthz(req)

        template = req.site.buildbot_service.templates.get_template("build.html")
        return template.render(**cxt)

    def stop(self, req, auth_ok=False):
        # check if this is allowed
        if not auth_ok:
            return StopBuildActionResource(self.build_status)

        b = self.build_status
        log.msg("web stopBuild of build %s:%s" %
                (b.getBuilder().getName(), b.getNumber()))

        name = self.getAuthz(req).getUsernameFull(req)
        comments = _get_comments_from_request(req)
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

    def rebuild(self, req):
        return ForceBuildActionResource(self.build_status,
                                        self.build_status.getBuilder())

    def getChild(self, path, req):
        if path == "stop":
            return self.stop(req)
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
