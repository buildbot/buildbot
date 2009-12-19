
import time, urllib
from twisted.python import log
from twisted.web import html
from twisted.web.util import Redirect
from twisted.web.error import NoResource

from buildbot.status.web.base import HtmlResource, abbreviate_age, \
        OneLineMixin, path_to_slave, path_to_build
from buildbot import version, util

# /buildslaves/$slavename
class OneBuildSlaveResource(HtmlResource, OneLineMixin):
    addSlash = False
    def __init__(self, slavename):
        HtmlResource.__init__(self)
        self.slavename = slavename

    def getTitle(self, req):
        return "Buildbot: %s" % html.escape(self.slavename)

    def getChild(self, path, req):
        s = self.getStatus(req)
        slave = s.getSlave(self.slavename)
        if path == "shutdown" and self.getControl(req):
            slave.setGraceful(True)
        return Redirect(path_to_slave(req, slave))

    def build_line(self, build, req):
        buildnum = build.getNumber()
        buildurl = path_to_build(req, build)
        data = '<a href="%(builderurl)s">%(builder_name)s</a>' % self.get_line_values(req, build)
        data += ' <a href="%s">#%d</a> ' % (buildurl, buildnum)

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

        builder_control = self.getControl(req)
        if builder_control is not None:
            stopURL = path_to_build(req, build) + '/stop'
            data += '''
<form action="%s" class="command stopbuild" style="display:inline" method="post">
  <input type="submit" value="Stop Build" />
</form>''' % stopURL
        return data

    def body(self, req):
        s = self.getStatus(req)
        slave = s.getSlave(self.slavename)
        my_builders = []
        for bname in s.getBuilderNames():
            b = s.getBuilder(bname)
            for bs in b.getSlaves():
                slavename = bs.getName()
                if bs.getName() == self.slavename:
                    my_builders.append(b)

        # Current builds
        current_builds = []
        for b in my_builders:
            for cb in b.getCurrentBuilds():
                if cb.getSlavename() == self.slavename:
                    current_builds.append(cb)

        data = []

        projectName = s.getProjectName()

        data.append("<a href=\"%s\">%s</a>\n" % (self.path_to_root(req), projectName))

        data.append("<h1>Build Slave: %s</h1>\n" % html.escape(self.slavename))

        access_uri = slave.getAccessURI()
        if access_uri:
            data.append("<a href=\"%s\">Click to Access Slave</a>" % html.escape(access_uri))

        shutdown_url = req.childLink("shutdown")

        if not slave.isConnected():
            data.append("<h2>NOT CONNECTED</h2>\n")
        elif self.getControl(req):
            if not slave.getGraceful():
                data.append('''<form method="POST" action="%s">
    <input type="submit" value="Gracefully Shutdown">
    </form>''' % shutdown_url)
            else:
                data.append("Gracefully shutting down...\n")

        if current_builds:
            data.append("<h2>Currently building:</h2>\n")
            data.append("<ul>\n")
            thisURL = "../../../" + path_to_slave(req, slave)
            for build in current_builds:
                data.append("<li>%s</li>\n" % self.build_line(build, req))
            data.append("</ul>\n")

        else:
            data.append("<h2>no current builds</h2>\n")

        # Recent builds
        data.append("<h2>Recent builds:</h2>\n")
        data.append("<ul>\n")
        n = 0
        try:
            max_builds = int(req.args.get('numbuilds')[0])
        except:
            max_builds = 10
        for build in s.generateFinishedBuilds(builders=[b.getName() for b in my_builders]):
            if build.getSlavename() == self.slavename:
                n += 1
                data.append("<li>%s</li>\n" % self.make_line(req, build, True))
                if n > max_builds:
                    break
        data.append("</ul>\n")

        data.append(self.footer(s, req))
        return "".join(data)

# /buildslaves
class BuildSlavesResource(HtmlResource):
    title = "BuildSlaves"
    addSlash = True

    def body(self, req):
        s = self.getStatus(req)
        data = ""
        data += "<h1>Build Slaves</h1>\n"

        used_by_builder = {}
        for bname in s.getBuilderNames():
            b = s.getBuilder(bname)
            for bs in b.getSlaves():
                slavename = bs.getName()
                if slavename not in used_by_builder:
                    used_by_builder[slavename] = []
                used_by_builder[slavename].append(bname)

        data += "<ol>\n"
        for name in util.naturalSort(s.getSlaveNames()):
            slave = s.getSlave(name)
            slave_status = s.botmaster.slaves[name].slave_status
            isBusy = len(slave_status.getRunningBuilds())
            data += " <li><a href=\"%s\">%s</a>:\n" % (req.childLink(urllib.quote(name,'')), name)
            data += " <ul>\n"
            version = slave.getVersion()
            data += "<li>Running Buildbot version: %s" % version
            builder_links = ['<a href="%s">%s</a>'
                             % (req.childLink("../builders/%s" % bname),bname)
                             for bname in used_by_builder.get(name, [])]
            if builder_links:
                data += ("  <li>Used by Builders: %s</li>\n" %
                         ", ".join(builder_links))
            else:
                data += "  <li>Not used by any Builders</li>\n"
            if slave.isConnected():
                data += "  <li>Slave is currently connected</li>\n"
                admin = slave.getAdmin()
                if admin:
                    # munge it to avoid feeding the spambot harvesters
                    admin = admin.replace("@", " -at- ")
                    data += "  <li>Admin: %s</li>\n" % admin
                last = slave.lastMessageReceived()
                if last:
                    lt = time.strftime("%Y-%b-%d %H:%M:%S",
                                       time.localtime(last))
                    age = abbreviate_age(time.time() - last)
                    data += "  <li>Last heard from: %s " % age
                    data += '<font size="-1">(%s)</font>' % lt
                    data += "</li>\n"
                    if isBusy:
                        data += "<li>Slave is currently building.</li>"
                    else:
                        data += "<li>Slave is idle.</li>"
            else:
                data += "  <li><b>Slave is NOT currently connected</b></li>\n"

            data += " </ul>\n"
            data += " </li>\n"
            data += "\n"

        data += "</ol>\n"

        return data

    def getChild(self, path, req):
        try:
            slave = self.getStatus(req).getSlave(path)
            return OneBuildSlaveResource(path)
        except KeyError:
            return NoResource("No such slave '%s'" % html.escape(path))
