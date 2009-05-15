
import time, urllib
from twisted.python import log
from twisted.web import html
from twisted.web.util import Redirect

from buildbot.status.web.base import HtmlResource, abbreviate_age, OneLineMixin, path_to_slave, env
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
        if path == "shutdown":
            s = self.getStatus(req)
            slave = s.getSlave(self.slavename)
            slave.setGraceful(True)
        return Redirect(path_to_slave(req, slave))

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

        data.append("<h1>Build Slave: %s</h1>\n" % self.slavename)

        shutdown_url = req.childLink("shutdown")

        if not slave.isConnected():
            data.append("<h2>NOT CONNECTED</h2>\n")
        elif not slave.getGraceful():
            data.append('''<form method="POST" action="%s">
<input type="submit" value="Gracefully Shutdown">
</form>''' % shutdown_url)
        else:
            data.append("Gracefully shutting down...\n")

        if current_builds:
            data.append("<h2>Currently building:</h2>\n")
            data.append("<ul>\n")
            for build in current_builds:
                data.append("<li>%s</li>\n" % self.make_line(req, build, True))
            data.append("</ul>\n")

        else:
            data.append("<h2>no current builds</h2>\n")

        # Recent builds
        data.append("<h2>Recent builds:</h2>\n")
        data.append("<ul>\n")
        n = 0
        try:
            max_builds = int(req.args.get('builds')[0])
        except:
            max_builds = 10
        for build in s.generateFinishedBuilds(builders=[b.getName() for b in my_builders]):
            if build.getSlavename() == self.slavename:
                n += 1
                data.append("<li>%s</li>\n" % self.make_line(req, build, True))
                if n > max_builds:
                    break
        data.append("</ul>\n")

        projectURL = s.getProjectURL()
        projectName = s.getProjectName()
        data.append('<hr /><div class="footer">\n')

        welcomeurl = self.path_to_root(req) + "index.html"
        data.append("[<a href=\"%s\">welcome</a>]\n" % welcomeurl)
        data.append("<br />\n")

        data.append('<a href="http://buildbot.sourceforge.net/">Buildbot</a>')
        data.append("-%s " % version)
        if projectName:
            data.append("working for the ")
            if projectURL:
                data.append("<a href=\"%s\">%s</a> project." % (projectURL,
                                                            projectName))
            else:
                data.append("%s project." % projectName)
        data.append("<br />\n")
        data.append("Page built: " +
                 time.strftime("%a %d %b %Y %H:%M:%S",
                               time.localtime(util.now()))
                 + "\n")
        data.append("</div>\n")

        return "".join(data) + self.footer(req)

# /buildslaves
class BuildSlavesResource(HtmlResource):
    title = "BuildSlaves"
    addSlash = True

    def body(self, req):
        s = self.getStatus(req)

        used_by_builder = {}
        for bname in s.getBuilderNames():
            b = s.getBuilder(bname)
            for bs in b.getSlaves():
                slavename = bs.getName()
                if slavename not in used_by_builder:
                    used_by_builder[slavename] = []
                used_by_builder[slavename].append(bname)

        slaves = []
        for name in util.naturalSort(s.getSlaveNames()):
            info = {}
            slaves.append(info)
            slave = s.getSlave(name)
            slave_status = s.botmaster.slaves[name].slave_status
            info['running_builds'] = len(slave_status.getRunningBuilds())
            info['link'] = req.childLink(urllib.quote(name,''))
            info['name'] = name
            info['builders'] = [{'link': req.childLink("../builders/%s" % bname), 'name': bname}
                                for bname in used_by_builder.get(name, [])]
            info['connected'] = slave.isConnected()
            
            if slave.isConnected():
                info['admin'] = slave.getAdmin()
                last = slave.lastMessageReceived()
                if last:
                    info['last_heard_from_age'] = abbreviate_age(time.time() - last)
                    info['last_heard_from_time'] = time.strftime("%Y-%b-%d %H:%M:%S",
                                                                time.localtime(last))

        template = env.get_template("buildslaves.html");
        template.autoescape = True
        data = template.render(slaves=slaves)
        data += self.footer(req)
        return data

    def getChild(self, path, req):
        return OneBuildSlaveResource(path)
