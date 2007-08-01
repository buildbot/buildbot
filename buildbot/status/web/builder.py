
from twisted.web.error import NoResource
from twisted.web import html, static
from twisted.web.util import Redirect

import re, urllib
from twisted.python import log
from buildbot import interfaces
from buildbot.status.web.base import HtmlResource, make_row
from buildbot.process.base import BuildRequest
from buildbot.sourcestamp import SourceStamp

from buildbot.status.web.build import BuildsResource

# $builder
class StatusResourceBuilder(HtmlResource):
    addSlash = True

    def __init__(self, builder_status, builder_control):
        HtmlResource.__init__(self)
        self.builder_status = builder_status
        self.builder_control = builder_control

    def body(self, req):
        b = self.builder_status
        control = self.builder_control
        status = self.getStatus(req)

        slaves = b.getSlaves()
        connected_slaves = [s for s in slaves if s.isConnected()]

        buildbotURL = status.getBuildbotURL()
        projectName = status.getProjectName()
        data = "<a href=\"%s\">%s</a>\n" % (buildbotURL, projectName)
        data += make_row("Builder:", html.escape(b.getName()))
        b1 = b.getBuild(-1)
        if b1 is not None:
            data += make_row("Current/last build:", str(b1.getNumber()))
        data += "\n<br />BUILDSLAVES<br />\n"
        data += "<ol>\n"
        for slave in slaves:
            data += "<li><b>%s</b>: " % html.escape(slave.getName())
            if slave.isConnected():
                data += "CONNECTED\n"
                if slave.getAdmin():
                    data += make_row("Admin:", html.escape(slave.getAdmin()))
                if slave.getHost():
                    data += "<span class='label'>Host info:</span>\n"
                    data += html.PRE(slave.getHost())
            else:
                data += ("NOT CONNECTED\n")
            data += "</li>\n"
        data += "</ol>\n"

        if control is not None and connected_slaves:
            forceURL = urllib.quote(req.childLink("force"))
            data += (
                """
                <form action='%(forceURL)s' class='command forcebuild'>
                <p>To force a build, fill out the following fields and
                push the 'Force Build' button</p>"""
                + make_row("Your name:",
                           "<input type='text' name='username' />")
                + make_row("Reason for build:",
                           "<input type='text' name='comments' />")
                + make_row("Branch to build:",
                           "<input type='text' name='branch' />")
                + make_row("Revision to build:",
                           "<input type='text' name='revision' />")
                + """
                <input type='submit' value='Force Build' />
                </form>
                """) % {"forceURL": forceURL}
        elif control is not None:
            data += """
            <p>All buildslaves appear to be offline, so it's not possible
            to force this build to execute at this time.</p>
            """

        if control is not None:
            pingURL = urllib.quote(req.childLink("ping"))
            data += """
            <form action="%s" class='command pingbuilder'>
            <p>To ping the buildslave(s), push the 'Ping' button</p>

            <input type="submit" value="Ping Builder" />
            </form>
            """ % pingURL

        return data

    def force(self, req):
        name = req.args.get("username", ["<unknown>"])[0]
        reason = req.args.get("comments", ["<no reason specified>"])[0]
        branch = req.args.get("branch", [""])[0]
        revision = req.args.get("revision", [""])[0]

        r = "The web-page 'force build' button was pressed by '%s': %s\n" \
            % (name, reason)
        log.msg("web forcebuild of builder '%s', branch='%s', revision='%s'"
                % (self.builder.name, branch, revision))

        if not self.builder_control:
            # TODO: tell the web user that their request was denied
            log.msg("but builder control is disabled")
            return Redirect("..")

        # keep weird stuff out of the branch and revision strings. TODO:
        # centralize this somewhere.
        if not re.match(r'^[\w\.\-\/]*$', branch):
            log.msg("bad branch '%s'" % branch)
            return Redirect("..")
        if not re.match(r'^[\w\.\-\/]*$', revision):
            log.msg("bad revision '%s'" % revision)
            return Redirect("..")
        if branch == "":
            branch = None
        if revision == "":
            revision = None

        # TODO: if we can authenticate that a particular User pushed the
        # button, use their name instead of None, so they'll be informed of
        # the results.
        s = SourceStamp(branch=branch, revision=revision)
        req = BuildRequest(r, s, self.builder.getName())
        try:
            self.builder_control.requestBuildSoon(req)
        except interfaces.NoSlaveError:
            # TODO: tell the web user that their request could not be
            # honored
            pass
        return Redirect("..")

    def ping(self, req):
        log.msg("web ping of builder '%s'" % self.builder.name)
        self.builder_control.ping() # TODO: there ought to be an ISlaveControl
        return Redirect("..")

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
            e = self.builder.statusbag.getEventNumbered(num)
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
        if path == "builds":
            return BuildsResource(self.builder_status, self.builder_control)

        return HtmlResource.getChild(self, path, req)


class BuildersResource(HtmlResource):
    addSlash = True

    def getChild(self, path, req):
        s = self.getStatus(req)
        if path in s.getBuilderNames():
            builder_status = s.getBuilder(path)
            builder_control = None
            c = self.getControl(req)
            if c:
                builder_control = c.getBuilder(path)
            return StatusResourceBuilder(builder_status, builder_control)

        return HtmlResource.getChild(self, path, req)

