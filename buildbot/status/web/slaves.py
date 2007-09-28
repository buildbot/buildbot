
import time
from buildbot.status.web.base import HtmlResource, abbreviate_age

# /buildslaves/$slavename
class OneBuildSlaveResource(HtmlResource):
    pass  # TODO

# /buildslaves/
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
        for name in s.getSlaveNames():
            slave = s.getSlave(name)
            data += " <li>%s:\n" % name
            data += " <ul>\n"
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
                    lt = time.strftime("%Y-%M-%d %H:%M:%S",
                                       time.localtime(last))
                    age = abbreviate_age(time.time() - last)
                    data += "  <li>Last heard from: %s " % age
                    data += '<font size="-1">(%s)</font>' % lt
                    data += "</li>\n"
            else:
                data += "  <li>Slave is NOT currently connected</li>\n"

            data += " </ul>\n"
            data += " </li>\n"
            data += "\n"

        data += "</ol>\n"

        return data
