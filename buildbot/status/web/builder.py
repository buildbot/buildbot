
from zope.interface import implements
from twisted.web.error import NoResource
from twisted.web import html, static
from twisted.web.util import Redirect

import re, time, urllib
from twisted.python import components, log
from buildbot import util, interfaces
from buildbot.status import builder
from buildbot.status.web.base import HtmlResource, Box, IBox, \
     build_get_class, make_row, ICurrentBox, ITopBox
from buildbot.process.base import BuildRequest
from buildbot.status.web.build import StatusResourceBuild

from buildbot.sourcestamp import SourceStamp

# $builder
class StatusResourceBuilder(HtmlResource):

    def __init__(self, status, builder, control):
        HtmlResource.__init__(self)
        self.status = status
        self.title = builder.getName() + " Builder"
        self.builder = builder
        self.control = control

    def body(self, request):
        b = self.builder
        slaves = b.getSlaves()
        connected_slaves = [s for s in slaves if s.isConnected()]

        buildbotURL = self.status.getBuildbotURL()
        projectName = self.status.getProjectName()
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

        if self.control is not None and connected_slaves:
            forceURL = urllib.quote(request.childLink("force"))
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
        elif self.control is not None:
            data += """
            <p>All buildslaves appear to be offline, so it's not possible
            to force this build to execute at this time.</p>
            """

        if self.control is not None:
            pingURL = urllib.quote(request.childLink("ping"))
            data += """
            <form action="%s" class='command pingbuilder'>
            <p>To ping the buildslave(s), push the 'Ping' button</p>

            <input type="submit" value="Ping Builder" />
            </form>
            """ % pingURL

        return data

    def force(self, request):
        name = request.args.get("username", ["<unknown>"])[0]
        reason = request.args.get("comments", ["<no reason specified>"])[0]
        branch = request.args.get("branch", [""])[0]
        revision = request.args.get("revision", [""])[0]

        r = "The web-page 'force build' button was pressed by '%s': %s\n" \
            % (name, reason)
        log.msg("web forcebuild of builder '%s', branch='%s', revision='%s'"
                % (self.builder.name, branch, revision))

        if not self.control:
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
            self.control.requestBuildSoon(req)
        except interfaces.NoSlaveError:
            # TODO: tell the web user that their request could not be
            # honored
            pass
        return Redirect("..")

    def ping(self, request):
        log.msg("web ping of builder '%s'" % self.builder.name)
        self.control.ping() # TODO: there ought to be an ISlaveControl
        return Redirect("..")

    def getChild(self, path, request):
        if path == "force":
            return self.force(request)
        if path == "ping":
            return self.ping(request)
        if not path in ("events", "builds"):
            return NoResource("Bad URL '%s'" % path)
        num = request.postpath.pop(0)
        request.prepath.append(num)
        num = int(num)
        if path == "events":
            # TODO: is this dead code? .statusbag doesn't exist,right?
            log.msg("getChild['path']: %s" % request.uri)
            return NoResource("events are unavailable until code gets fixed")
            filename = request.postpath.pop(0)
            request.prepath.append(filename)
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
            build = self.builder.getBuild(num)
            if build:
                control = None
                if self.control:
                    control = self.control.getBuild(num)
                return StatusResourceBuild(self.status, build,
                                           self.control, control)
            else:
                return NoResource("No such build '%d'" % num)
        return NoResource("really weird URL %s" % path)


class CurrentBox(components.Adapter):
    # this provides the "current activity" box, just above the builder name
    implements(ICurrentBox)

    def formatETA(self, eta):
        if eta is None:
            return []
        if eta < 0:
            return ["Soon"]
        abstime = time.strftime("%H:%M:%S", time.localtime(util.now()+eta))
        return ["ETA in", "%d secs" % eta, "at %s" % abstime]

    def getBox(self, status):
        # getState() returns offline, idle, or building
        state, builds = self.original.getState()

        # look for upcoming builds. We say the state is "waiting" if the
        # builder is otherwise idle and there is a scheduler which tells us a
        # build will be performed some time in the near future. TODO: this
        # functionality used to be in BuilderStatus.. maybe this code should
        # be merged back into it.
        upcoming = []
        builderName = self.original.getName()
        for s in status.getSchedulers():
            if builderName in s.listBuilderNames():
                upcoming.extend(s.getPendingBuildTimes())
        if state == "idle" and upcoming:
            state = "waiting"

        if state == "building":
            color = "yellow"
            text = ["building"]
            if builds:
                for b in builds:
                    eta = b.getETA()
                    if eta:
                        text.extend(self.formatETA(eta))
        elif state == "offline":
            color = "red"
            text = ["offline"]
        elif state == "idle":
            color = "white"
            text = ["idle"]
        elif state == "waiting":
            color = "yellow"
            text = ["waiting"]
        else:
            # just in case I add a state and forget to update this
            color = "white"
            text = [state]

        # TODO: for now, this pending/upcoming stuff is in the "current
        # activity" box, but really it should go into a "next activity" row
        # instead. The only times it should show up in "current activity" is
        # when the builder is otherwise idle.

        # are any builds pending? (waiting for a slave to be free)
        pbs = self.original.getPendingBuilds()
        if pbs:
            text.append("%d pending" % len(pbs))
        for t in upcoming:
            text.extend(["next at", 
                         time.strftime("%H:%M:%S", time.localtime(t)),
                         "[%d secs]" % (t - util.now()),
                         ])
            # TODO: the upcoming-builds box looks like:
            #  ['waiting', 'next at', '22:14:15', '[86 secs]']
            # while the currently-building box is reversed:
            #  ['building', 'ETA in', '2 secs', 'at 22:12:50']
            # consider swapping one of these to make them look the same. also
            # consider leaving them reversed to make them look different.
        return Box(text, color=color, class_="Activity " + state)

components.registerAdapter(CurrentBox, builder.BuilderStatus, ICurrentBox)


class BuildTopBox(components.Adapter):
    # this provides a per-builder box at the very top of the display,
    # showing the results of the most recent build
    implements(IBox)

    def getBox(self):
        assert interfaces.IBuilderStatus(self.original)
        b = self.original.getLastFinishedBuild()
        if not b:
            return Box(["none"], "white", class_="LastBuild")
        name = b.getBuilder().getName()
        number = b.getNumber()
        url = "%s/builds/%d" % (name, number)
        text = b.getText()
        # TODO: add logs?
        # TODO: add link to the per-build page at 'url'
        c = b.getColor()
        class_ = build_get_class(b)
        return Box(text, c, class_="LastBuild %s" % class_)
components.registerAdapter(BuildTopBox, builder.BuilderStatus, ITopBox)
