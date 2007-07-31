
from zope.interface import implements
from twisted.web.error import NoResource
from twisted.web import html
from twisted.web.util import Redirect, DeferredResource
from twisted.internet import defer, reactor

import urllib
from twisted.python import components, log
from buildbot.status import builder
from buildbot.status.web.base import HtmlResource, Box, IBox, \
     build_get_class, make_row

from buildbot.status.web.tests import StatusResourceTestResults
from buildbot.status.web.step import StatusResourceBuildStep

# $builder/builds/NN
class StatusResourceBuild(HtmlResource):
    title = "Build"

    def __init__(self, status, build, builderControl, buildControl):
        HtmlResource.__init__(self)
        self.status = status
        self.build = build
        self.builderControl = builderControl
        self.control = buildControl

    def body(self, request):
        b = self.build
        buildbotURL = self.status.getBuildbotURL()
        projectName = self.status.getProjectName()
        data = '<div class="title"><a href="%s">%s</a></div>\n'%(buildbotURL,
                                                                 projectName)
        # the color in the following line gives python-mode trouble
        data += ("<h1>Build <a href=\"%s\">%s</a>:#%d</h1>\n"
                 % (self.status.getURLForThing(b.getBuilder()),
                    b.getBuilder().getName(), b.getNumber()))
        data += "<h2>Buildslave:</h2>\n %s\n" % html.escape(b.getSlavename())
        data += "<h2>Reason:</h2>\n%s\n" % html.escape(b.getReason())

        branch, revision, patch = b.getSourceStamp()
        data += "<h2>SourceStamp:</h2>\n"
        data += " <ul>\n"
        if branch:
            data += "  <li>Branch: %s</li>\n" % html.escape(branch)
        if revision:
            data += "  <li>Revision: %s</li>\n" % html.escape(str(revision))
        if patch:
            data += "  <li>Patch: YES</li>\n" # TODO: provide link to .diff
        if b.getChanges():
            data += "  <li>Changes: see below</li>\n"
        if (branch is None and revision is None and patch is None
            and not b.getChanges()):
            data += "  <li>build of most recent revision</li>\n"
        data += " </ul>\n"
        if b.isFinished():
            data += "<h2>Results:</h2>\n"
            data += " ".join(b.getText()) + "\n"
            if b.getTestResults():
                url = request.childLink("tests")
                data += "<h3><a href=\"%s\">test results</a></h3>\n" % url
        else:
            data += "<h2>Build In Progress</h2>"
            if self.control is not None:
                stopURL = urllib.quote(request.childLink("stop"))
                data += """
                <form action="%s" class='command stopbuild'>
                <p>To stop this build, fill out the following fields and
                push the 'Stop' button</p>\n""" % stopURL
                data += make_row("Your name:",
                                 "<input type='text' name='username' />")
                data += make_row("Reason for stopping build:",
                                 "<input type='text' name='comments' />")
                data += """<input type="submit" value="Stop Builder" />
                </form>
                """

        if b.isFinished() and self.builderControl is not None:
            data += "<h3>Resubmit Build:</h3>\n"
            # can we rebuild it exactly?
            exactly = (revision is not None) or b.getChanges()
            if exactly:
                data += ("<p>This tree was built from a specific set of \n"
                         "source files, and can be rebuilt exactly</p>\n")
            else:
                data += ("<p>This tree was built from the most recent "
                         "revision")
                if branch:
                    data += " (along some branch)"
                data += (" and thus it might not be possible to rebuild it \n"
                         "exactly. Any changes that have been committed \n"
                         "after this build was started <b>will</b> be \n"
                         "included in a rebuild.</p>\n")
            rebuildURL = urllib.quote(request.childLink("rebuild"))
            data += ('<form action="%s" class="command rebuild">\n'
                     % rebuildURL)
            data += make_row("Your name:",
                             "<input type='text' name='username' />")
            data += make_row("Reason for re-running build:",
                             "<input type='text' name='comments' />")
            data += '<input type="submit" value="Rebuild" />\n'
            data += '</form>\n'

        data += "<h2>Steps and Logfiles:</h2>\n"
        if b.getLogs():
            data += "<ol>\n"
            for s in b.getSteps():
                data += (" <li><a href=\"%s\">%s</a> [%s]\n"
                         % (self.status.getURLForThing(s), s.getName(),
                            " ".join(s.getText())))
                if s.getLogs():
                    data += "  <ol>\n"
                    for logfile in s.getLogs():
                        data += ("   <li><a href=\"%s\">%s</a></li>\n" %
                                 (self.status.getURLForThing(logfile),
                                  logfile.getName()))
                    data += "  </ol>\n"
                data += " </li>\n"
            data += "</ol>\n"

        data += ("<h2>Blamelist:</h2>\n"
                 " <ol>\n")
        for who in b.getResponsibleUsers():
            data += "  <li>%s</li>\n" % html.escape(who)
        data += (" </ol>\n"
                 "<h2>All Changes</h2>\n")
        changes = b.getChanges()
        if changes:
            data += "<ol>\n"
            for c in changes:
                data += "<li>" + c.asHTML() + "</li>\n"
            data += "</ol>\n"
        #data += html.PRE(b.changesText()) # TODO
        return data

    def stop(self, request):
        log.msg("web stopBuild of build %s:%s" % \
                (self.build.getBuilder().getName(),
                 self.build.getNumber()))
        name = request.args.get("username", ["<unknown>"])[0]
        comments = request.args.get("comments", ["<no reason specified>"])[0]
        reason = ("The web-page 'stop build' button was pressed by "
                  "'%s': %s\n" % (name, comments))
        self.control.stopBuild(reason)
        # we're at http://localhost:8080/svn-hello/builds/5/stop?[args] and
        # we want to go to: http://localhost:8080/svn-hello/builds/5 or
        # http://localhost:8080/
        #
        #return Redirect("../%d" % self.build.getNumber())
        r = Redirect("../../..")
        d = defer.Deferred()
        reactor.callLater(1, d.callback, r)
        return DeferredResource(d)

    def rebuild(self, request):
        log.msg("web rebuild of build %s:%s" % \
                (self.build.getBuilder().getName(),
                 self.build.getNumber()))
        name = request.args.get("username", ["<unknown>"])[0]
        comments = request.args.get("comments", ["<no reason specified>"])[0]
        reason = ("The web-page 'rebuild' button was pressed by "
                  "'%s': %s\n" % (name, comments))
        if not self.builderControl or not self.build.isFinished():
            log.msg("could not rebuild: bc=%s, isFinished=%s"
                    % (self.builderControl, self.build.isFinished()))
            # TODO: indicate an error
        else:
            self.builderControl.resubmitBuild(self.build, reason)
        # we're at http://localhost:8080/svn-hello/builds/5/rebuild?[args] and
        # we want to go to the top, at http://localhost:8080/
        r = Redirect("../../..")
        d = defer.Deferred()
        reactor.callLater(1, d.callback, r)
        return DeferredResource(d)

    def getChild(self, path, request):
        if path == "tests":
            return StatusResourceTestResults(self.status,
                                             self.build.getTestResults())
        if path == "stop":
            return self.stop(request)
        if path == "rebuild":
            return self.rebuild(request)
        if path.startswith("step-"):
            stepname = path[len("step-"):]
            steps = self.build.getSteps()
            for s in steps:
                if s.getName() == stepname:
                    return StatusResourceBuildStep(self.status, s)
            return NoResource("No such BuildStep '%s'" % stepname)
        return NoResource("No such resource '%s'" % path)

class BuildBox(components.Adapter):
    # this provides the yellow "starting line" box for each build
    implements(IBox)

    def getBox(self):
        b = self.original
        name = b.getBuilder().getName()
        number = b.getNumber()
        url = "%s/builds/%d" % (urllib.quote(name, safe=''), number)
        reason = b.getReason()
        text = ('<a title="Reason: %s" href="%s">Build %d</a>'
                % (html.escape(reason), url, number))
        color = "yellow"
        class_ = "start"
        if b.isFinished() and not b.getSteps():
            # the steps have been pruned, so there won't be any indication
            # of whether it succeeded or failed. Color the box red or green
            # to show its status
            color = b.getColor()
            class_ = build_get_class(b)
        return Box([text], color=color, class_="BuildStep " + class_)
components.registerAdapter(BuildBox, builder.BuildStatus, IBox)
