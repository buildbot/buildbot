
from twisted.web import html
from twisted.web.util import Redirect, DeferredResource
from twisted.internet import defer, reactor

import urllib, time
from twisted.python import log
from buildbot.status.web.base import HtmlResource, make_row, make_stop_form, \
     make_extra_property_row, css_classes, path_to_builder, path_to_slave, \
     make_name_user_passwd_form, getAndCheckProperties


from buildbot.status.web.tests import TestsResource
from buildbot.status.web.step import StepsResource
from buildbot import version, util

# /builders/$builder/builds/$buildnum
class StatusResourceBuild(HtmlResource):
    addSlash = True

    def __init__(self, build_status, build_control, builder_control):
        HtmlResource.__init__(self)
        self.build_status = build_status
        self.build_control = build_control
        self.builder_control = builder_control

    def getTitle(self, request):
        return ("Buildbot: %s Build #%d" %
                (html.escape(self.build_status.getBuilder().getName()),
                 self.build_status.getNumber()))

    def body(self, req):
        b = self.build_status
        status = self.getStatus(req)
        projectName = status.getProjectName()
        projectURL = status.getProjectURL()
        data = ('<div class="title"><a href="%s">%s</a></div>\n'
                % (self.path_to_root(req), projectName))
        builder_name = b.getBuilder().getName()
        data += ("<h1><a href=\"%s\">Builder %s</a>: Build #%d</h1>\n"
                 % (path_to_builder(req, b.getBuilder()),
                    builder_name, b.getNumber()))

        if not b.isFinished():
            data += "<h2>Build In Progress</h2>"
            when = b.getETA()
            if when is not None:
                when_time = time.strftime("%H:%M:%S",
                                          time.localtime(time.time() + when))
                data += "<div>ETA %ds (%s)</div>\n" % (when, when_time)

            if self.build_control is not None:
                stopURL = urllib.quote(req.childLink("stop"))
                data += make_stop_form(stopURL, self.isUsingUserPasswd(req))

        if b.isFinished():
            # Results map loosely to css_classes
            results = b.getResults()
            data += "<h2>Results:</h2>\n"
            text = " ".join(b.getText())
            data += '<span class="%s">%s</span>\n' % (css_classes[results],
                                                      text)
            if b.getTestResults():
                url = req.childLink("tests")
                data += "<h3><a href=\"%s\">test results</a></h3>\n" % url

        ss = b.getSourceStamp()
        data += "<h2>SourceStamp:</h2>\n"
        data += " <ul>\n"
        if ss.branch:
            data += "  <li>Branch: %s</li>\n" % html.escape(ss.branch)
        if ss.revision:
            data += "  <li>Revision: %s</li>\n" % html.escape(str(ss.revision))
        if ss.patch:
            data += "  <li>Patch: YES</li>\n" # TODO: provide link to .diff
        if ss.changes:
            data += "  <li>Changes: see below</li>\n"
        if (ss.branch is None and ss.revision is None and ss.patch is None
            and not ss.changes):
            data += "  <li>build of most recent revision</li>\n"
        got_revision = None
        try:
            got_revision = b.getProperty("got_revision")
        except KeyError:
            pass
        if got_revision:
            got_revision = str(got_revision)
            if len(got_revision) > 40:
                got_revision = "[revision string too long]"
            data += "  <li>Got Revision: %s</li>\n" % got_revision
        data += " </ul>\n"

        # TODO: turn this into a table, or some other sort of definition-list
        # that doesn't take up quite so much vertical space
        try:
            slaveurl = path_to_slave(req, status.getSlave(b.getSlavename()))
            data += "<h2>Buildslave:</h2>\n <a href=\"%s\">%s</a>\n" % (html.escape(slaveurl), html.escape(b.getSlavename()))
        except KeyError:
            data += "<h2>Buildslave:</h2>\n %s\n" % html.escape(b.getSlavename())
        data += "<h2>Reason:</h2>\n%s\n" % html.escape(b.getReason())

        data += "<h2>Steps and Logfiles:</h2>\n"
        # TODO:
#        urls = self.original.getURLs()
#        ex_url_class = "BuildStep external"
#        for name, target in urls.items():
#            text.append('[<a href="%s" class="%s">%s</a>]' %
#                        (target, ex_url_class, html.escape(name)))
        data += "<ol>\n"
        for s in b.getSteps():
            name = s.getName()
            time_to_run = 0
            (start, end) = s.getTimes()
            if start and end:
              time_to_run = end - start
            if s.isFinished():
                css_class = css_classes[s.getResults()[0]]
            elif s.isStarted():
                css_class = "running"
            else:
                css_class = ""
            data += (' <li><span class="%s"><a href=\"%s\">%s</a> [%s] [%d seconds]</span>\n'
                     % (css_class, 
                        req.childLink("steps/%s" % urllib.quote(name)),
                        name,
                        " ".join(s.getText()),
                        time_to_run))
            data += "  <ol>\n"
            if s.getLogs():
                for logfile in s.getLogs():
                    logname = logfile.getName()
                    logurl = req.childLink("steps/%s/logs/%s" %
                                           (urllib.quote(name),
                                            urllib.quote(logname)))
                    data += ("   <li><a href=\"%s\">%s</a></li>\n" %
                             (logurl, logfile.getName()))
            if s.getURLs():
                for url in s.getURLs().items():
                    logname = url[0]
                    logurl = url[1]
                    data += ('   <li><a href="%s">%s</a></li>\n' %
                             (logurl, html.escape(logname)))
            data += "</ol>\n"
            data += " </li>\n"

        data += "</ol>\n"

        data += "<h2>Build Properties:</h2>\n"
        data += "<table><tr><th valign=\"left\">Name</th><th valign=\"left\">Value</th><th valign=\"left\">Source</th></tr>\n"
        for name, value, source in b.getProperties().asList():
            value = str(value)
            if len(value) > 500:
                value = value[:500] + " .. [property value too long]"
            data += "<tr>"
            data += "<td>%s</td>" % html.escape(name)
            data += "<td>%s</td>" % html.escape(value)
            data += "<td>%s</td>" % html.escape(source)
            data += "</tr>\n"
        data += "</table>"

        data += "<h2>Blamelist:</h2>\n"
        if list(b.getResponsibleUsers()):
            data += " <ol>\n"
            for who in b.getResponsibleUsers():
                data += "  <li>%s</li>\n" % html.escape(who)
            data += " </ol>\n"
        else:
            data += "<div>no responsible users</div>\n"


        (start, end) = b.getTimes()
        data += "<h2>Timing</h2>\n"
        data += "<table>\n"
        data += "<tr><td>Start</td><td>%s</td></tr>\n" % time.ctime(start)
        if end:
            data += "<tr><td>End</td><td>%s</td></tr>\n" % time.ctime(end)
            data += "<tr><td>Elapsed</td><td>%s</td></tr>\n" % util.formatInterval(end - start)
        else:
            now = util.now()
            data += "<tr><td>Elapsed</td><td>%s</td></tr>\n" % util.formatInterval(now - start)
        data += "</table>\n"

        if ss.changes:
            data += "<h2>All Changes</h2>\n"
            data += "<ol>\n"
            for c in ss.changes:
                data += "<li>" + c.asHTML() + "</li>\n"
            data += "</ol>\n"
            #data += html.PRE(b.changesText()) # TODO

        if b.isFinished() and self.builder_control is not None:
            data += "<h3>Resubmit Build:</h3>\n"
            # can we rebuild it exactly?
            exactly = (ss.revision is not None) or b.getChanges()
            if exactly:
                data += ("<p>This tree was built from a specific set of \n"
                         "source files, and can be rebuilt exactly</p>\n")
            else:
                data += ("<p>This tree was built from the most recent "
                         "revision")
                if ss.branch:
                    data += " (along some branch)"
                data += (" and thus it might not be possible to rebuild it \n"
                         "exactly. Any changes that have been committed \n"
                         "after this build was started <b>will</b> be \n"
                         "included in a rebuild.</p>\n")
            rebuildURL = urllib.quote(req.childLink("rebuild"))
            data += ('<form method="post" action="%s" class="command rebuild">\n'
                     % rebuildURL)
            data += make_name_user_passwd_form(self.isUsingUserPasswd(req))
            data += make_extra_property_row(1)
            data += make_extra_property_row(2)
            data += make_extra_property_row(3)
            data += make_row("Reason for re-running build:",
                             "<input type='text' name='comments' />")
            data += '<input type="submit" value="Rebuild" />\n'
            data += '</form>\n'

        data += self.footer(status, req)

        return data

    def stop(self, req):
        if self.isUsingUserPasswd(req):
            if not self.authUser(req):
                return Redirect("../../../authfailed")
        b = self.build_status
        c = self.build_control
        log.msg("web stopBuild of build %s:%s" % \
                (b.getBuilder().getName(), b.getNumber()))
        name = req.args.get("username", ["<unknown>"])[0]
        comments = req.args.get("comments", ["<no reason specified>"])[0]
        # html-quote both the username and comments, just to be safe
        reason = ("The web-page 'stop build' button was pressed by "
                  "'%s': %s\n" % (html.escape(name), html.escape(comments)))
        if c:
            c.stopBuild(reason)
        # we're at http://localhost:8080/svn-hello/builds/5/stop?[args] and
        # we want to go to: http://localhost:8080/svn-hello
        r = Redirect("../..")
        d = defer.Deferred()
        reactor.callLater(1, d.callback, r)
        return DeferredResource(d)

    def rebuild(self, req):
        if self.isUsingUserPasswd(req):
            if not self.authUser(req):
                return Redirect("../../../authfailed")
        b = self.build_status
        bc = self.builder_control
        builder_name = b.getBuilder().getName()
        log.msg("web rebuild of build %s:%s" % (builder_name, b.getNumber()))
        name = req.args.get("username", ["<unknown>"])[0]
        comments = req.args.get("comments", ["<no reason specified>"])[0]
        reason = ("The web-page 'rebuild' button was pressed by "
                  "'%s': %s\n" % (html.escape(name), html.escape(comments)))
        extraProperties = getAndCheckProperties(req)
        if not bc or not b.isFinished() or extraProperties is None:
            log.msg("could not rebuild: bc=%s, isFinished=%s"
                    % (bc, b.isFinished()))
            # TODO: indicate an error
        else:
            bc.resubmitBuild(b, reason, extraProperties)
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
        r = Redirect("../..") # the Builder's page
        d = defer.Deferred()
        reactor.callLater(1, d.callback, r)
        return DeferredResource(d)

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

    def __init__(self, builder_status, builder_control):
        HtmlResource.__init__(self)
        self.builder_status = builder_status
        self.builder_control = builder_control

    def getChild(self, path, req):
        try:
            num = int(path)
        except ValueError:
            num = None
        if num is not None:
            build_status = self.builder_status.getBuild(num)
            if build_status:
                if self.builder_control:
                    build_control = self.builder_control.getBuild(num)
                else:
                    build_control = None
                return StatusResourceBuild(build_status, build_control,
                                           self.builder_control)

        return HtmlResource.getChild(self, path, req)

