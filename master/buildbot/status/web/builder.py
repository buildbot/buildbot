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
from buildbot.status.web.status_json import ProjectJsonResource, SingleProjectJsonResource, FilterOut

from twisted.web import html
import urllib, time
from twisted.python import log
from twisted.internet import defer
from buildbot import interfaces
from buildbot.status.web.base import HtmlResource, BuildLineMixin, \
    path_to_build, path_to_buildqueue, path_to_codebases, path_to_slave, path_to_builder, path_to_builders, path_to_change, \
    path_to_root, ICurrentBox, build_get_class, getCodebasesArg, \
    map_branches, path_to_authzfail, ActionResource, \
    getRequestCharset, path_to_json_builders
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.schedulers.forcesched import InheritBuildParameter, NestedParameter
from buildbot.schedulers.forcesched import ValidationError
from buildbot.status.web.build import BuildsResource, StatusResourceBuild
from buildbot import util
import collections

class ForceAllBuildsActionResource(ActionResource):

    def __init__(self, status, selectedOrAll):
        self.status = status
        self.selectedOrAll = selectedOrAll
        self.action = "forceAllBuilds"

    @defer.inlineCallbacks
    def performAction(self, req):
        authz = self.getAuthz(req)
        res = yield authz.actionAllowed('forceAllBuilds', req)

        if not res:
            defer.returnValue(path_to_authzfail(req))
            return

        builders = None
        if self.selectedOrAll == 'all':
            builders = self.status.getBuilderNames()
        elif self.selectedOrAll == 'selected':
            builders = [b for b in req.args.get("selected", []) if b]

        for bname in builders:
            builder_status = self.status.getBuilder(bname)
            ar = ForceBuildActionResource(builder_status)
            d = ar.performAction(req)
            d.addErrback(log.err, "(ignored) while trying to force build")
        # back to the welcome page
        defer.returnValue(path_to_root(req))

class StopAllBuildsActionResource(ActionResource):

    def __init__(self, status, selectedOrAll):
        self.status = status
        self.selectedOrAll = selectedOrAll
        self.action = "stopAllBuilds"

    @defer.inlineCallbacks
    def performAction(self, req):
        authz = self.getAuthz(req)
        res = yield authz.actionAllowed('stopAllBuilds', req)
        if not res:
            defer.returnValue(path_to_authzfail(req))
            return

        builders = None
        if self.selectedOrAll == 'all':
            builders = self.status.getBuilderNames()
        elif self.selectedOrAll == 'selected':
            builders = [b for b in req.args.get("selected", []) if b]

        for bname in builders:
            builder_status = self.status.getBuilder(bname)
            (state, current_builds) = builder_status.getState()
            if state != "building":
                continue
            for b in current_builds:
                build_status = builder_status.getBuild(b.number)
                if not build_status:
                    continue
                build = StatusResourceBuild(build_status)
                build.stop(req, auth_ok=True)

        # go back to the welcome page
        defer.returnValue(path_to_root(req))

class PingBuilderActionResource(ActionResource):

    def __init__(self, builder_status):
        self.builder_status = builder_status
        self.action = "pingBuilder"

    @defer.inlineCallbacks
    def performAction(self, req):
        log.msg("web ping of builder '%s'" % self.builder_status.getName())
        res = yield self.getAuthz(req).actionAllowed('pingBuilder', req,
                                                    self.builder_status)
        if not res:
            log.msg("..but not authorized")
            defer.returnValue(path_to_authzfail(req))
            return

        c = interfaces.IControl(self.getBuildmaster(req))
        bc = c.getBuilder(self.builder_status.getName())
        bc.ping()
        # send the user back to the builder page
        defer.returnValue(path_to_builder(req, self.builder_status))

class ForceBuildActionResource(ActionResource):

    def __init__(self, builder_status):
        self.builder_status = builder_status
        self.action = "forceBuild"

    @defer.inlineCallbacks
    def performAction(self, req):
        # check if this is allowed
        res = yield self.getAuthz(req).actionAllowed(self.action, req,
                                             self.builder_status)
        if not res:
            log.msg("..but not authorized")
            defer.returnValue(path_to_authzfail(req))
            return

        master = self.getBuildmaster(req)
        owner = self.getAuthz(req).getUsernameFull(req)
        schedulername = req.args.get("forcescheduler", ["<unknown>"])[0]
        if schedulername == "<unknown>":
            defer.returnValue((path_to_builder(req, self.builder_status),
                               "forcescheduler arg not found"))
            return

        args = req.args.copy()

        # decode all of the args
        encoding = getRequestCharset(req)
        for name, argl in args.iteritems():
            args[name] = [ urllib.unquote(arg).decode(encoding) for arg in argl ]

        # damn html's ungeneric checkbox implementation...
        for cb in args.get("checkbox", []):
            args[cb] = True

        builder_name = self.builder_status.getName()

        for sch in master.allSchedulers():
            if schedulername == sch.name:
                try:
                    yield sch.force(owner, builder_name, **args)
                    msg = ""
                except ValidationError, e:
                    msg = html.escape(e.message.encode('ascii','ignore'))
                break

        # send the user back to the builder page
        returnpage = args.get("returnpage", None)
        if returnpage is None:
            defer.returnValue((path_to_builder(req, self.builder_status), msg))
        elif "builders" in returnpage:
            defer.returnValue((path_to_builders(req, self.builder_status.getProject()), msg))
        elif "builders_json" in returnpage:
            defer.returnValue((path_to_json_builders(req, self.builder_status.getProject()), msg))

def buildForceContextForField(req, default_props, sch, field, master, buildername):
    pname = "%s.%s"%(sch.name, field.fullName)
    
    default = field.default
    if isinstance(field, InheritBuildParameter):
        # yes, I know, its bad to overwrite the parameter attribute,
        # but I dont have any other simple way of doing this atm.
        field.choices = field.compatible_builds(master.status, buildername)
        if field.choices:
            default = field.choices[0]
            
    default = req.args.get(pname, [default])[0]
    if "bool" in field.type:
        default_props[pname] = "checked" if default else ""
    else:
        # filter out unicode chars, and html stuff
        if isinstance(default, unicode):
            default = html.escape(default.encode('utf-8','ignore'))
        default_props[pname] = default
        
    if isinstance(field, NestedParameter):
        for subfield in field.fields:
            buildForceContextForField(req, default_props, sch, subfield, master, buildername)

def buildForceContext(cxt, req, master, buildername=None):
    force_schedulers = {}
    default_props = collections.defaultdict(str)
    for sch in master.allSchedulers():
        if isinstance(sch, ForceScheduler) and (buildername is None or(buildername in sch.builderNames)):
            force_schedulers[sch.name] = sch
            for field in sch.all_fields:
                buildForceContextForField(req, default_props, sch, field, master, buildername)
                
    cxt['force_schedulers'] = force_schedulers
    cxt['default_props'] = default_props


def builder_info(build, req, codebases_arg={}):
    b = {}

    b['num'] = build.getNumber()
    b['link'] = path_to_build(req, build)

    when = build.getETA()
    if when is not None:
        b['when'] = util.formatInterval(when)
        b['when_time'] = time.strftime("%H:%M:%S",
                                       time.localtime(time.time() + when))

    step = build.getCurrentStep()
    # TODO: is this necessarily the case?
    if not step:
        b['current_step'] = "[waiting for build slave]"
    else:
        if step.isWaitingForLocks():
            b['current_step'] = "%s [waiting for build slave]" % step.getName()
        else:
            b['current_step'] = step.getName()

    b['stop_url'] = path_to_build(req, build, False) + '/stop' + codebases_arg

    return b

# /builders/$builder
class StatusResourceBuilder(HtmlResource, BuildLineMixin):
    addSlash = True

    def __init__(self, builder_status):
        HtmlResource.__init__(self)
        self.builder_status = builder_status

    def getPageTitle(self, request):
        return "Katana - %s" % self.builder_status.getFriendlyName()

    @defer.inlineCallbacks
    def content(self, req, cxt):
        b = self.builder_status
        project = cxt['selectedproject'] =  b.getProject()
        cxt['name'] = b.getName()
        cxt['friendly_name'] = b.getFriendlyName()

        req.setHeader('Cache-Control', 'no-cache')
        slaves = b.getSlaves()
        connected_slaves = [s for s in slaves if s.isConnected()]

        codebases = {}
        codebases_arg = getCodebasesArg(request=req, codebases=codebases)
        codebases_in_args = len(codebases_arg) > 0
        cxt['current'] = [builder_info(x, req, codebases_arg) for x in b.getCurrentBuilds(codebases=codebases)]

        cxt['pending'] = []
        statuses = yield b.getPendingBuildRequestStatuses()
        for pb in statuses:
            changes = []

            source = yield pb.getSourceStamp()

            if len(codebases) > 0:
                found = yield foundCodebasesInPendingBuild(pb, codebases)
                if not found:
                    continue

            submitTime = yield pb.getSubmitTime()
            bsid = yield pb.getBsid()

            properties = yield \
                    pb.master.db.buildsets.getBuildsetProperties(bsid)

            ## this should use sources instead
            if source.changes:
                for c in source.changes:
                    changes.append({ 'url' : path_to_change(req, c),
                                     'who' : c.who,
                                     'revision' : c.revision,
                                     'repo' : c.repository })

            cxt['pending'].append({
                'when': time.strftime("%b %d %H:%M:%S",
                                      time.localtime(submitTime)),
                'delay': util.formatInterval(util.now() - submitTime),
                'id': pb.brid,
                'changes' : changes,
                'num_changes' : len(changes),
                'properties' : properties,
                })

        numbuilds = int(req.args.get('numbuilds', ['15'])[0])
        recent = cxt['recent'] = []

        for build in b.generateFinishedBuilds(codebases=codebases, num_builds=int(numbuilds)):
            recent.append(self.get_line_values(req, build, False))

        sl = cxt['slaves'] = []
        connected_slaves = 0
        for slave in slaves:
            s = {}
            sl.append(s)
            s['link'] = path_to_slave(req, slave)
            s['name'] = slave.getName()
            c = s['connected'] = slave.isConnected()
            if c:
                s['admin'] = unicode(slave.getAdmin() or '', 'utf-8')
                connected_slaves += 1
        cxt['connected_slaves'] = connected_slaves

        cxt['authz'] = self.getAuthz(req)
        cxt['builder_url'] = path_to_builder(req, b, codebases=False)
        cxt['codebases_arg'] = codebases_arg
        cxt['path_to_codebases'] = path_to_codebases(req, project)
        cxt['path_to_builders'] = path_to_builders(req, project)
        cxt['builder_name'] = b.getName()

        cxt['rt_update'] = req.args

        buildForceContext(cxt, req, self.getBuildmaster(req), b.getName())
        template = req.site.buildbot_service.templates.get_template("builder.html")
        defer.returnValue(template.render(**cxt))

    def ping(self, req):
        return PingBuilderActionResource(self.builder_status)

    def getChild(self, path, req):
        if path == "force":
            return ForceBuildActionResource(self.builder_status)
        if path == "ping":
            return self.ping(req)
        if path == "cancelbuild":
            return CancelChangeResource(self.builder_status)
        if path == "stopchange":
            return StopChangeResource(self.builder_status)
        if path == "builds":
            return BuildsResource(self.builder_status)

        return HtmlResource.getChild(self, path, req)

class CancelChangeResource(ActionResource):

    def __init__(self, builder_status):
        ActionResource.__init__(self)
        self.builder_status = builder_status

    @defer.inlineCallbacks
    def performAction(self, req):
        try:
            request_id = req.args.get("id", [None])[0]
            if request_id == "all":
                cancel_all = True
            else:
                cancel_all = False
                request_id = int(request_id)
        except:
            request_id = None

        authz = self.getAuthz(req)
        if request_id:
            c = interfaces.IControl(self.getBuildmaster(req))
            builder_control = c.getBuilder(self.builder_status.getName())

            brcontrols = yield builder_control.getPendingBuildRequestControls()

            for build_req in brcontrols:
                if cancel_all or (build_req.brid == request_id):
                    log.msg("Cancelling %s" % build_req)
                    res = yield authz.actionAllowed('cancelPendingBuild', req,
                                                                build_req)
                    if res:
                        build_req.cancel()
                    else:
                        defer.returnValue(path_to_authzfail(req))
                        return
                    if not cancel_all:
                        break
        args = req.args.copy()

        returnpage = args.get("returnpage", None)

        if returnpage is None:
            defer.returnValue((path_to_builder(req, self.builder_status)))
        elif "builders" in returnpage:
            defer.returnValue((path_to_builders(req, self.builder_status.getProject())))
        elif "buildqueue" in returnpage:
            defer.returnValue(path_to_buildqueue(req))

class StopChangeMixin(object):

    @defer.inlineCallbacks
    def stopChangeForBuilder(self, req, builder_status, auth_ok=False):
        try:
            request_change = req.args.get("change", [None])[0]
            request_change = int(request_change)
        except:
            request_change = None

        authz = self.getAuthz(req)
        if request_change:
            c = interfaces.IControl(self.getBuildmaster(req))
            builder_control = c.getBuilder(builder_status.getName())

            brcontrols = yield builder_control.getPendingBuildRequestControls()
            build_controls = dict((x.brid, x) for x in brcontrols)

            build_req_statuses = yield \
                    builder_status.getPendingBuildRequestStatuses()

            for build_req in build_req_statuses:
                ss = yield build_req.getSourceStamp()

                if not ss.changes:
                    continue

                for change in ss.changes:
                    if change.number == request_change:
                        control = build_controls[build_req.brid]
                        log.msg("Cancelling %s" % control)
                        res = yield authz.actionAllowed('stopChange', req, control)
                        if (auth_ok or res):
                            control.cancel()
                        else:
                            defer.returnValue(False)
                            return

        defer.returnValue(True)


class StopChangeResource(StopChangeMixin, ActionResource):

    def __init__(self, builder_status):
        ActionResource.__init__(self)
        self.builder_status = builder_status

    @defer.inlineCallbacks
    def performAction(self, req):
        """Cancel all pending builds that include a given numbered change."""
        success = yield self.stopChangeForBuilder(req, self.builder_status)

        if not success:
            defer.returnValue(path_to_authzfail(req))
        else:
            defer.returnValue(path_to_builder(req, self.builder_status))


class StopChangeAllResource(StopChangeMixin, ActionResource):

    def __init__(self, status):
        ActionResource.__init__(self)
        self.status = status

    @defer.inlineCallbacks
    def performAction(self, req):
        """Cancel all pending builds that include a given numbered change."""
        authz = self.getAuthz(req)
        res = yield authz.actionAllowed('stopChange', req)
        if not res:
            defer.returnValue(path_to_authzfail(req))
            return

        for bname in self.status.getBuilderNames():
            builder_status = self.status.getBuilder(bname)
            res = yield self.stopChangeForBuilder(req, builder_status, auth_ok=True)
            if not res:
                defer.returnValue(path_to_authzfail(req))
                return

        defer.returnValue(path_to_root(req))


# /builders/_all
class StatusResourceAllBuilders(HtmlResource, BuildLineMixin):

    def __init__(self, status):
        HtmlResource.__init__(self)
        self.status = status

    def getChild(self, path, req):
        if path == "forceall":
            return self.forceall(req)
        if path == "stopall":
            return self.stopall(req)
        if path == "stopchangeall":
            return StopChangeAllResource(self.status)

        return HtmlResource.getChild(self, path, req)

    def forceall(self, req):
        return ForceAllBuildsActionResource(self.status, 'all')

    def stopall(self, req):
        return StopAllBuildsActionResource(self.status, 'all')

# /builders/_selected
class StatusResourceSelectedBuilders(HtmlResource, BuildLineMixin):

    def __init__(self, status):
        HtmlResource.__init__(self)
        self.status = status

    def getChild(self, path, req):
        if path == "forceselected":
            return self.forceselected(req)
        if path == "stopselected":
            return self.stopselected(req)

        return HtmlResource.getChild(self, path, req)

    def forceselected(self, req):
        return ForceAllBuildsActionResource(self.status, 'selected')

    def stopselected(self, req):
        return StopAllBuildsActionResource(self.status, 'selected')

@defer.inlineCallbacks
def foundCodebasesInPendingBuild(pendingbuild, codebases):
    sources = yield pendingbuild.getSourceStamps()
    foundcodebases = []
    for key, ss in sources.iteritems():
        if key in codebases.keys() and ss.branch in codebases[key]:
            foundcodebases.append(ss)
    found = len(foundcodebases) == len(sources)
    defer.returnValue(found)


# /builders
class BuildersResource(HtmlResource):
    pageTitle = "Katana - Builders"
    addSlash = True

    def __init__(self, project):
        HtmlResource.__init__(self)
        self.project = project

    @defer.inlineCallbacks
    def content(self, req, cxt):
        status = self.getStatus(req)

        cxt['path_to_codebases'] = path_to_codebases(req, self.project.name)
        cxt['selectedproject'] = self.project.name
        cxt['authz'] = self.getAuthz(req)

        project_json = SingleProjectJsonResource(status, self.project)
        project_dict = yield project_json.asDict(req)
        project_dict = FilterOut(project_dict)
        cxt['instant_json'] = json.dumps(project_dict)

        template = req.site.buildbot_service.templates.get_template("builders.html")
        defer.returnValue(template.render(**cxt))

    def getChild(self, path, req):
        s = self.getStatus(req)
        if path in s.getBuilderNames():
            builder_status = s.getBuilder(path)
            return StatusResourceBuilder(builder_status)
        if path == "_all":
            return StatusResourceAllBuilders(self.getStatus(req))
        if path == "_selected":
            return StatusResourceSelectedBuilders(self.getStatus(req))

        return HtmlResource.getChild(self, path, req)

