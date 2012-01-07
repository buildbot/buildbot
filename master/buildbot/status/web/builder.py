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


from twisted.web import html
import urllib, time
from twisted.python import log
from twisted.internet import defer
from buildbot import interfaces
from buildbot.status.web.base import HtmlResource, BuildLineMixin, \
    path_to_build, path_to_slave, path_to_builder, path_to_change, \
    path_to_root, ICurrentBox, build_get_class, \
    map_branches, path_to_authzfail, ActionResource
from buildbot.schedulers.forcesched import ForceScheduler, InheritBuildParameter
from buildbot.status.web.build import BuildsResource, StatusResourceBuild
from buildbot import util

class ForceAllBuildsActionResource(ActionResource):

    def __init__(self, status, selectedOrAll):
        self.status = status
        self.selectedOrAll = selectedOrAll
        self.action = "forceAllBuilds"

    @defer.deferredGenerator
    def performAction(self, req):
        authz = self.getAuthz(req)
        d = authz.actionAllowed('forceAllBuilds', req)
        wfd = defer.waitForDeferred(d)
        yield wfd
        res = wfd.getResult()

        if not res:
            yield path_to_authzfail(req)
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
        yield path_to_root(req)

class StopAllBuildsActionResource(ActionResource):

    def __init__(self, status, selectedOrAll):
        self.status = status
        self.selectedOrAll = selectedOrAll
        self.action = "stopAllBuilds"

    @defer.deferredGenerator
    def performAction(self, req):
        authz = self.getAuthz(req)
        d = authz.actionAllowed('stopAllBuilds', req)
        wfd = defer.waitForDeferred(d)
        yield wfd
        res = wfd.getResult()
        if not res:
            yield path_to_authzfail(req)
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
        yield path_to_root(req)

class PingBuilderActionResource(ActionResource):

    def __init__(self, builder_status):
        self.builder_status = builder_status
        self.action = "pingBuilder"

    @defer.deferredGenerator
    def performAction(self, req):
        log.msg("web ping of builder '%s'" % self.builder_status.getName())
        d = self.getAuthz(req).actionAllowed('pingBuilder', req, self.builder_status)
        wfd = defer.waitForDeferred(d)
        yield wfd
        res = wfd.getResult()
        if not res:
            log.msg("..but not authorized")
            yield path_to_authzfail(req)
            return

        c = interfaces.IControl(self.getBuildmaster(req))
        bc = c.getBuilder(self.builder_status.getName())
        bc.ping()
        # send the user back to the builder page
        yield path_to_builder(req, self.builder_status)

class ForceBuildActionResource(ActionResource):

    def __init__(self, builder_status):
        self.builder_status = builder_status
        self.action = "forceBuild"

    @defer.deferredGenerator
    def performAction(self, req):
        # check if this is allowed
        d = self.getAuthz(req).actionAllowed(self.action, req,
                                             self.builder_status)
        wfd = defer.waitForDeferred(d)
        yield wfd
        res = wfd.getResult()
        if not res:
            log.msg("..but not authorized")
            yield path_to_authzfail(req)
            return

        master = self.getBuildmaster(req)
        owner = self.getAuthz(req).getUsernameFull(req)
        schedulername = req.args.get("forcescheduler", ["<unknown>"])[0]
        if schedulername == "<unknown>":
            yield path_to_builder(req, self.builder_status), "forcescheduler arg not found"
            return
        for sch in master.allSchedulers():
            if schedulername == sch.name:
                try:
                    d = sch.forceWithWebRequest(owner,self.builder_status.getName(),req)
                    msg = ""
                except Exception, e:
                    msg = html.escape(e.message.encode('ascii','ignore'))
                break
        wfd = defer.waitForDeferred(d)
        yield wfd
        res = wfd.getResult()
        # send the user back to the builder page
        yield path_to_builder(req, self.builder_status), msg

def buildForceContext(cxt, req, master, buildername=None):
    force_schedulers = {}
    default_props = {}
    for sch in master.allSchedulers():
        if isinstance(sch, ForceScheduler) and (buildername is None or(buildername in sch.builderNames)):
            force_schedulers[sch.name] = sch
            for p in sch.all_fields:
                pname = "%s.%s"%(sch.name, p.name)
                default = p.default
                if isinstance(p, InheritBuildParameter):
                    # yes, I know, its bad to overwrite the parameter attribute,
                    # but I dont have any other simple way of doing this atm.
                    p.choices = p.compatible_builds(master.status, buildername)
                    if p.choices:
                        default = p.choices[0]
                default = req.args.get(pname, [default])[0]
                if p.type=="bool":
                    default_props[pname] = default and "checked" or ""
                else:
                    # filter out unicode chars, and html stuff
                    if type(default)==unicode:
                        default = html.escape(default.encode('ascii','ignore'))
                    default_props[pname] = default
    cxt['force_schedulers'] = force_schedulers
    cxt['default_props'] = default_props

# /builders/$builder
class StatusResourceBuilder(HtmlResource, BuildLineMixin):
    addSlash = True

    def __init__(self, builder_status):
        HtmlResource.__init__(self)
        self.builder_status = builder_status

    def getPageTitle(self, request):
        return "Buildbot: %s" % self.builder_status.getName()

    def builder(self, build, req):
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
            b['current_step'] = "[waiting for Lock]"
        else:
            if step.isWaitingForLocks():
                b['current_step'] = "%s [waiting for Lock]" % step.getName()
            else:
                b['current_step'] = step.getName()

        b['stop_url'] = path_to_build(req, build) + '/stop'

        return b

    @defer.deferredGenerator
    def content(self, req, cxt):
        b = self.builder_status

        cxt['name'] = b.getName()
        req.setHeader('Cache-Control', 'no-cache')
        slaves = b.getSlaves()
        connected_slaves = [s for s in slaves if s.isConnected()]

        cxt['current'] = [self.builder(x, req) for x in b.getCurrentBuilds()]

        cxt['pending'] = []
        wfd = defer.waitForDeferred(
            b.getPendingBuildRequestStatuses())
        yield wfd
        statuses = wfd.getResult()
        for pb in statuses:
            changes = []

            wfd = defer.waitForDeferred(
                    pb.getSourceStamp())
            yield wfd
            source = wfd.getResult()

            wfd = defer.waitForDeferred(
                    pb.getSubmitTime())
            yield wfd
            submitTime = wfd.getResult()

            wfd = defer.waitForDeferred(
                pb.master.db.buildsets.getBuildsetProperties(pb._buildrequest.bsid))
            yield wfd
            properties = wfd.getResult()

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

        numbuilds = int(req.args.get('numbuilds', ['5'])[0])
        recent = cxt['recent'] = []
        for build in b.generateFinishedBuilds(num_builds=int(numbuilds)):
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
        cxt['builder_url'] = path_to_builder(req, b)
        buildForceContext(cxt, req, self.getBuildmaster(req), b.getName())
        template = req.site.buildbot_service.templates.get_template("builder.html")
        yield template.render(**cxt)

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

    @defer.deferredGenerator
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

            wfd = defer.waitForDeferred(
                    builder_control.getPendingBuildRequestControls())
            yield wfd
            brcontrols = wfd.getResult()

            for build_req in brcontrols:
                if cancel_all or (build_req.brid == request_id):
                    log.msg("Cancelling %s" % build_req)
                    d = authz.actionAllowed('cancelPendingBuild',
                                            req, build_req)
                    wfd = defer.waitForDeferred(d)
                    yield wfd
                    res = wfd.getResult()
                    if res:
                        build_req.cancel()
                    else:
                        yield path_to_authzfail(req)
                        return
                    if not cancel_all:
                        break

        yield path_to_builder(req, self.builder_status)

class StopChangeMixin(object):

    @defer.deferredGenerator
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

            wfd = defer.waitForDeferred(
                    builder_control.getPendingBuildRequestControls())
            yield wfd
            brcontrols = wfd.getResult()

            build_controls = dict((x.brid, x) for x in brcontrols)

            wfd = defer.waitForDeferred(
                    builder_status.getPendingBuildRequestStatuses())
            yield wfd
            build_req_statuses = wfd.getResult()

            for build_req in build_req_statuses:
                wfd = defer.waitForDeferred(
                        build_req.getSourceStamp())
                yield wfd
                ss = wfd.getResult()

                if not ss.changes:
                    continue

                for change in ss.changes:
                    if change.number == request_change:
                        control = build_controls[build_req.brid]
                        log.msg("Cancelling %s" % control)
                        d = authz.actionAllowed('stopChange', req, control)
                        wfd = defer.waitForDeferred(d)
                        yield wfd
                        res = wfd.getResult()
                        if (auth_ok or res):
                            control.cancel()
                        else:
                            yield False
                            return

        yield True


class StopChangeResource(StopChangeMixin, ActionResource):

    def __init__(self, builder_status):
        ActionResource.__init__(self)
        self.builder_status = builder_status

    @defer.deferredGenerator
    def performAction(self, req):
        """Cancel all pending builds that include a given numbered change."""
        wfd = defer.waitForDeferred(
            self.stopChangeForBuilder(req, self.builder_status))
        yield wfd
        success = wfd.getResult()

        if not success:
            yield path_to_authzfail(req)
        else:
            yield path_to_builder(req, self.builder_status)


class StopChangeAllResource(StopChangeMixin, ActionResource):

    def __init__(self, status):
        ActionResource.__init__(self)
        self.status = status

    @defer.deferredGenerator
    def performAction(self, req):
        """Cancel all pending builds that include a given numbered change."""
        authz = self.getAuthz(req)
        wfd = defer.waitForDeferred(authz.actionAllowed('stopChange', req))
        yield wfd
        res = wfd.getResult()
        if not res:
            yield path_to_authzfail(req)
            return

        for bname in self.status.getBuilderNames():
            builder_status = self.status.getBuilder(bname)
            wfd = defer.waitForDeferred(
                self.stopChangeForBuilder(req, builder_status, auth_ok=True))
            yield wfd
            if not wfd.getResult():
                yield path_to_authzfail(req)
                return

        yield path_to_root(req)


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

# /builders
class BuildersResource(HtmlResource):
    pageTitle = "Builders"
    addSlash = True

    @defer.deferredGenerator
    def content(self, req, cxt):
        status = self.getStatus(req)

        builders = req.args.get("builder", status.getBuilderNames())
        branches = [b for b in req.args.get("branch", []) if b]

        # get counts of pending builds for each builder
        brstatus_ds = []
        brcounts = {}
        def keep_count(statuses, builderName):
            brcounts[builderName] = len(statuses)
        for builderName in builders:
            builder_status = status.getBuilder(builderName)
            d = builder_status.getPendingBuildRequestStatuses()
            d.addCallback(keep_count, builderName)
            brstatus_ds.append(d)
        wfd = defer.waitForDeferred(
            defer.gatherResults(brstatus_ds))
        yield wfd
        wfd.getResult()

        cxt['branches'] = branches
        bs = cxt['builders'] = []

        building = 0
        online = 0
        base_builders_url = path_to_root(req) + "builders/"
        for bn in builders:
            bld = { 'link': base_builders_url + urllib.quote(bn, safe=''),
                    'name': bn }
            bs.append(bld)

            builder = status.getBuilder(bn)
            builds = list(builder.generateFinishedBuilds(map_branches(branches),
                                                         num_builds=1))
            if builds:
                b = builds[0]
                bld['build_url'] = (bld['link'] + "/builds/%d" % b.getNumber())
                label = b.getProperty("got_revision")
                if not label or len(str(label)) > 20:
                    label = "#%d" % b.getNumber()

                bld['build_label'] = label
                bld['build_text'] = " ".join(b.getText())
                bld['build_css_class'] = build_get_class(b)

            current_box = ICurrentBox(builder).getBox(status, brcounts)
            bld['current_box'] = current_box.td()

            builder_status = builder.getState()[0]
            if builder_status == "building":
                building += 1
                online += 1
            elif builder_status != "offline":
                online += 1

        cxt['authz'] = self.getAuthz(req)
        cxt['num_building'] = building
        cxt['num_online'] = online
        buildForceContext(cxt, req, self.getBuildmaster(req))
        template = req.site.buildbot_service.templates.get_template("builders.html")
        yield template.render(**cxt)

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

