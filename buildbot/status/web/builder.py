
from twisted.web.error import NoResource
from twisted.web import html, static
from twisted.web.util import Redirect

import re, urllib, time
from twisted.python import log
from buildbot import interfaces
from buildbot.status.web.base import HtmlResource, make_row, \
     make_force_build_form, OneLineMixin, path_to_build, path_to_slave, \
     path_to_builder, path_to_change, getAndCheckProperties
from buildbot.process.base import BuildRequest
from buildbot.process.properties import Properties
from buildbot.sourcestamp import SourceStamp

from buildbot.status.web.build import BuildsResource, StatusResourceBuild
from buildbot import util

# /builders/$builder
class StatusResourceBuilder(HtmlResource, OneLineMixin):
    addSlash = True

    def __init__(self, builder_status, builder_control):
        HtmlResource.__init__(self)
        self.builder_status = builder_status
        self.builder_control = builder_control

    def getTitle(self, request):
        return "Buildbot: %s" % html.escape(self.builder_status.getName())

    def build_line(self, build, req):
        buildnum = build.getNumber()
        buildurl = path_to_build(req, build)
        data = '<a href="%s">#%d</a> ' % (buildurl, buildnum)

        when = build.getETA()
        if when is not None:
            when_time = time.strftime("%H:%M:%S",
                                      time.localtime(time.time() + when))
            data += "ETA %ds (%s) " % (when, when_time)
        step = build.getCurrentStep()
        if step:
            data += "[%s]" % step.getName()
        else:
            data += "[waiting for Lock]"
            # TODO: is this necessarily the case?

        if self.builder_control is not None:
            stopURL = path_to_build(req, build) + '/stop'
            data += '''
<form method="post" action="%s" class="command stopbuild" style="display:inline">
  <input type="submit" value="Stop Build" />
</form>''' % stopURL
        return data

    def request_line(self, build_request, req):
        when = time.strftime("%b %d %H:%M:%S", time.localtime(build_request.getSubmitTime()))
        delay = util.formatInterval(util.now() - build_request.getSubmitTime())
        changes = build_request.source.changes
        if changes:
            change_strings = []
            for c in changes:
                change_strings.append("<a href=\"%s\">%s</a>" % (path_to_change(req, c), c.who))
            if len(change_strings) == 1:
                reason = "change by %s" % change_strings[0]
            else:
                reason = "changes by %s" % ", ".join(change_strings)
        elif build_request.source.revision:
            reason = build_request.source.revision
        else:
            reason = "no changes specified"

        if self.builder_control is not None:
            cancelURL = path_to_builder(req, self.builder_status) + '/cancelbuild'
            cancelButton = '''
<form action="%s" class="command cancelbuild" style="display:inline" method="post">
  <input type="hidden" name="id" value="%s" />
  <input type="submit" value="Cancel Build" />
</form>''' % (cancelURL, id(build_request))
        else:
            cancelButton = ""
        return "<font size=\"-1\">(%s, waiting %s)</font>%s%s" % (when, delay, cancelButton, reason)

    def body(self, req):
        b = self.builder_status
        control = self.builder_control
        status = self.getStatus(req)

        slaves = b.getSlaves()
        connected_slaves = [s for s in slaves if s.isConnected()]

        projectName = status.getProjectName()

        data = '<a href="%s">%s</a>\n' % (self.path_to_root(req), projectName)

        data += "<h1>Builder: %s</h1>\n" % html.escape(b.getName())

        # the first section shows builds which are currently running, if any.

        current = b.getCurrentBuilds()
        if current:
            data += "<h2>Currently Building:</h2>\n"
            data += "<ul>\n"
            for build in current:
                data += " <li>" + self.build_line(build, req) + "</li>\n"
            data += "</ul>\n"
        else:
            data += "<h2>no current builds</h2>\n"

        pending = b.getPendingBuilds()
        if pending:
            data += "<h2>Pending Builds:</h2>\n"
            data += "<ul>\n"
            for request in pending:
                data += " <li>" + self.request_line(request, req) + "</li>\n"
            data += "</ul>\n"

            cancelURL = path_to_builder(req, self.builder_status) + '/cancelbuild'
            if self.builder_control is not None:
                data += '''
<form action="%s" class="command cancelbuild" style="display:inline" method="post">
  <input type="hidden" name="id" value="all" />
  <input type="submit" value="Cancel All" />
</form>''' % cancelURL
        else:
            data += "<h2>no pending builds</h2>\n"

        # Then a section with the last 5 builds, with the most recent build
        # distinguished from the rest.

        data += "<h2>Recent Builds:</h2>\n"
        data += "(<a href=\"%s\">view in waterfall</a>)\n" % (self.path_to_root(req)+"waterfall?show="+html.escape(b.getName()))
        data += "<ul>\n"
        numbuilds = int(req.args.get('numbuilds', ['5'])[0])
        for i,build in enumerate(b.generateFinishedBuilds(num_builds=int(numbuilds))):
            data += " <li>" + self.make_line(req, build, False) + "</li>\n"
            if i == 0:
                data += "<br />\n" # separator
                # TODO: or empty list?
        data += "</ul>\n"


        data += "<h2>Buildslaves:</h2>\n"
        data += "<ol>\n"
        for slave in slaves:
            slaveurl = path_to_slave(req, slave)
            data += "<li><b><a href=\"%s\">%s</a></b>: " % (html.escape(slaveurl), html.escape(slave.getName()))
            if slave.isConnected():
                data += "CONNECTED\n"
                if slave.getAdmin():
                    data += make_row("Admin:", html.escape(slave.getAdmin()))
                if slave.getHost():
                    data += "<span class='label'>Host info:</span>\n"
                    data += html.PRE(html.escape(slave.getHost()))
            else:
                data += ("NOT CONNECTED\n")
            data += "</li>\n"
        data += "</ol>\n"

        if control is not None and connected_slaves:
            forceURL = path_to_builder(req, b) + '/force'
            data += make_force_build_form(forceURL, self.isUsingUserPasswd(req))
        elif control is not None:
            data += """
            <p>All buildslaves appear to be offline, so it's not possible
            to force this build to execute at this time.</p>
            """

        if control is not None:
            pingURL = path_to_builder(req, b) + '/ping'
            data += """
            <form method="post" action="%s" class='command pingbuilder'>
            <p>To ping the buildslave(s), push the 'Ping' button</p>

            <input type="submit" value="Ping Builder" />
            </form>
            """ % pingURL

        data += self.footer(status, req)

        return data

    def force(self, req):
        """

        Custom properties can be passed from the web form.  To do
        this, subclass this class, overriding the force() method.  You
        can then determine the properties (usually from form values,
        by inspecting req.args), then pass them to this superclass
        force method.
        
        """
        name = req.args.get("username", ["<unknown>"])[0]
        reason = req.args.get("comments", ["<no reason specified>"])[0]
        branch = req.args.get("branch", [""])[0]
        revision = req.args.get("revision", [""])[0]

        r = "The web-page 'force build' button was pressed by '%s': %s\n" \
            % (html.escape(name), html.escape(reason))
        log.msg("web forcebuild of builder '%s', branch='%s', revision='%s'"
                " by user '%s'" % (self.builder_status.getName(), branch,
                                   revision, name))

        if not self.builder_control:
            # TODO: tell the web user that their request was denied
            log.msg("but builder control is disabled")
            return Redirect("..")

        if self.isUsingUserPasswd(req):
            if not self.authUser(req):
                return Redirect("../../authfail")

        # keep weird stuff out of the branch revision, and property strings.
        # TODO: centralize this somewhere.
        if not re.match(r'^[\w\.\-\/]*$', branch):
            log.msg("bad branch '%s'" % branch)
            return Redirect("..")
        if not re.match(r'^[\w\.\-\/]*$', revision):
            log.msg("bad revision '%s'" % revision)
            return Redirect("..")
        properties = getAndCheckProperties(req)
        if properties is None:
            return Redirect("..")
        if not branch:
            branch = None
        if not revision:
            revision = None

        # TODO: if we can authenticate that a particular User pushed the
        # button, use their name instead of None, so they'll be informed of
        # the results.
        # TODO2: we can authenticate that a particular User pushed the button
        # now, so someone can write this support. but it requires a
        # buildbot.changes.changes.Change instance which is tedious at this
        # stage to compute
        s = SourceStamp(branch=branch, revision=revision)
        req = BuildRequest(r, s, builderName=self.builder_status.getName(),
                           properties=properties)
        try:
            self.builder_control.requestBuildSoon(req)
        except interfaces.NoSlaveError:
            # TODO: tell the web user that their request could not be
            # honored
            pass
        # send the user back to the builder page
        return Redirect(".")

    def ping(self, req):
        log.msg("web ping of builder '%s'" % self.builder_status.getName())
        self.builder_control.ping() # TODO: there ought to be an ISlaveControl
        # send the user back to the builder page
        return Redirect(".")

    def cancel(self, req):
        try:
            request_id = req.args.get("id", [None])[0]
            if request_id == "all":
                cancel_all = True
            else:
                cancel_all = False
                request_id = int(request_id)
        except:
            request_id = None
        if request_id:
            for build_req in self.builder_control.getPendingBuilds():
                if cancel_all or id(build_req.original_request.status) == request_id:
                    log.msg("Cancelling %s" % build_req)
                    build_req.cancel()
                    if not cancel_all:
                        break
        return Redirect(".")

    def getChild(self, path, req):
        if path == "force":
            return self.force(req)
        if path == "ping":
            return self.ping(req)
        if path == "events":
            num = req.postpath.pop(0)
            req.prepath.append(num)
            num = int(num)
            # TODO: is this dead code? .statusbag doesn't exist,right?
            log.msg("getChild['path']: %s" % req.uri)
            return NoResource("events are unavailable until code gets fixed")
            filename = req.postpath.pop(0)
            req.prepath.append(filename)
            e = self.builder_status.getEventNumbered(num)
            if not e:
                return NoResource("No such event '%d'" % num)
            file = e.files.get(filename, None)
            if file == None:
                return NoResource("No such file '%s'" % filename)
            if type(file) == type(""):
                if file[:6] in ("<HTML>", "<html>"):
                    return static.Data(file, "text/html")
                return static.Data(file, "text/plain")
            return file
        if path == "cancelbuild":
            return self.cancel(req)
        if path == "builds":
            return BuildsResource(self.builder_status, self.builder_control)

        return HtmlResource.getChild(self, path, req)


# /builders/_all
class StatusResourceAllBuilders(HtmlResource, OneLineMixin):

    def __init__(self, status, control):
        HtmlResource.__init__(self)
        self.status = status
        self.control = control

    def getChild(self, path, req):
        if path == "force":
            return self.force(req)
        if path == "stop":
            return self.stop(req)

        return HtmlResource.getChild(self, path, req)

    def force(self, req):
        for bname in self.status.getBuilderNames():
            builder_status = self.status.getBuilder(bname)
            builder_control = None
            c = self.getControl(req)
            if c:
                builder_control = c.getBuilder(bname)
            build = StatusResourceBuilder(builder_status, builder_control)
            build.force(req)
        # back to the welcome page
        return Redirect("../..")

    def stop(self, req):
        for bname in self.status.getBuilderNames():
            builder_status = self.status.getBuilder(bname)
            builder_control = None
            c = self.getControl(req)
            if c:
                builder_control = c.getBuilder(bname)
            (state, current_builds) = builder_status.getState()
            if state != "building":
                continue
            for b in current_builds:
                build_status = builder_status.getBuild(b.number)
                if not build_status:
                    continue
                if builder_control:
                    build_control = builder_control.getBuild(b.number)
                else:
                    build_control = None
                build = StatusResourceBuild(build_status, build_control,
                                            builder_control)
                build.stop(req)
        # go back to the welcome page
        return Redirect("../..")


# /builders
class BuildersResource(HtmlResource):
    title = "Builders"
    addSlash = True

    def body(self, req):
        s = self.getStatus(req)
        data = ""
        data += "<h1>Builders</h1>\n"

        # TODO: this is really basic. It should be expanded to include a
        # brief one-line summary of the builder (perhaps with whatever the
        # builder is currently doing)
        data += "<ol>\n"
        for bname in s.getBuilderNames():
            data += (' <li><a href="%s">%s</a></li>\n' %
                     (req.childLink(urllib.quote(bname, safe='')),
                      bname))
        data += "</ol>\n"

        data += self.footer(s, req)

        return data

    def getChild(self, path, req):
        s = self.getStatus(req)
        if path in s.getBuilderNames():
            builder_status = s.getBuilder(path)
            builder_control = None
            c = self.getControl(req)
            if c:
                builder_control = c.getBuilder(path)
            return StatusResourceBuilder(builder_status, builder_control)
        if path == "_all":
            return StatusResourceAllBuilders(self.getStatus(req),
                                             self.getControl(req))

        return HtmlResource.getChild(self, path, req)

