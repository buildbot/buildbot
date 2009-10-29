
import time, urllib
from twisted.python import log
from twisted.web import html
from twisted.web.util import Redirect

from buildbot.status.web.base import HtmlResource, abbreviate_age, OneLineMixin, path_to_slave
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
        my_builders = []
        for bname in s.getBuilderNames():
            b = s.getBuilder(bname)
            for bs in b.getSlaves():
                if bs.getName() == self.slavename:
                    my_builders.append(b)

        # Current builds
        current_builds = []
        for b in my_builders:
            for cb in b.getCurrentBuilds():
                if cb.getSlavename() == self.slavename:
                    current_builds.append(self.get_line_values(req, cb))
        
        try:
            max_builds = int(req.args.get('builds')[0])
        except:
            max_builds = 10
           
        recent_builds = []    
            
        n = 0
        for rb in s.generateFinishedBuilds(builders=[b.getName() for b in my_builders]):
            if rb.getSlavename() == self.slavename:
                n += 1
                recent_builds.append(self.get_line_values(req, rb))
                if n > max_builds:
                    break

        template = self.templates.get_template("buildslave.html");
        data = template.render(slave = self, 
                               current = current_builds, 
                               recent = recent_builds, 
                               shutdown_url = req.childLink("shutdown"))
        data += self.footer(req)
        return data

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

        template = self.templates.get_template("buildslaves.html");
        data = template.render(slaves=slaves)
        data += self.footer(req)
        return data

    def getChild(self, path, req):
        return OneBuildSlaveResource(path)
