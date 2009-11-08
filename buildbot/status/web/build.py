
from twisted.web import html
from twisted.web.util import Redirect, DeferredResource
from twisted.internet import defer, reactor

import urllib, time
from twisted.python import log
from buildbot.status.web.base import HtmlResource, make_row, make_stop_form, \
     css_classes, path_to_builder, path_to_slave, make_name_user_passwd_form

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

        cxt = {}
        cxt['path_to_root'] = self.path_to_root(req)
        cxt['project_name'] = projectName
        cxt['b'] = b
        cxt['path_to_builder'] = path_to_builder(req, b.getBuilder())
        
        if not b.isFinished():
            when = b.getETA()
            if when is not None:
                cxt['when'] = when
                cxt['when_time'] = time.strftime("%H:%M:%S",
                                                time.localtime(time.time() + when))
                
               
            if self.build_control is not None:
                cxt['stop_url'] = urllib.quote(req.childLink("stop")) 
                cxt['is_using_user_passwd'] = self.isUsingUserPasswd(req)
                # data += make_stop_form(stopURL, self.isUsingUserPasswd(req))
        else: 
            cxt['result_css'] = css_classes[b.getResults()]
            if b.getTestResults():
                cxt['tests_link'] = req.childLink("tests")
                
        ss = cxt['ss'] = b.getSourceStamp()
        
        if ss.branch is None and ss.revision is None and ss.patch is None and not ss.changes:
            cxt['most_recent_rev_build'] = True
            
        
        got_revision = None
        try:
            got_revision = b.getProperty("got_revision")
        except KeyError:
            pass
        if got_revision:
            got_revision = str(got_revision)
            if len(got_revision) > 40:
                got_revision = "[revision string too long]"
            cxt['got_revision'] = got_revision

        try:
            cxt['slave_url'] = path_to_slave(req, status.getSlave(b.getSlavename()))
        except KeyError:
            pass

        cxt['steps'] = []

        for s in b.getSteps():
            step = {'name': s.getName() }
            cxt['steps'].append(step)
            
            if s.isFinished():
                step['css_class'] = css_classes[s.getResults()[0]]
            elif s.isStarted():
                step['css_class'] = "running"

            step['link'] = req.childLink("steps/%s" % urllib.quote(s.getName()))
            step['text'] = " ".join(s.getText())

            step['logs']= []
            for l in s.getLogs():
                logname = l.getName()
                step['logs'].append({ 'link': req.childLink("steps/%s/logs/%s" %
                                           (urllib.quote(s.getName()),
                                            urllib.quote(logname))), 
                                      'name': logname })

        ps = cxt['properties'] = []
        for name, value, source in b.getProperties().asList():
            value = str(value)
            p = { 'name': name, 'value': value, 'source': source}            
            if len(value) > 500:
                p['short_value'] = value[:500]

            ps.append(p)

        
        cxt['responsible_users'] = list(b.getResponsibleUsers())

        (start, end) = b.getTimes()
        cxt['start'] = time.ctime(start)
        if end:
            cxt['end'] = time.ctime(end)
            cxt['elapsed'] = util.formatInterval(end - start)
            
        cxt['resubmit'] = b.isFinished() and self.builder_control is not None     
        if cxt['resubmit']:               
            cxt['exactly'] = (ss.revision is not None) or b.getChanges()
            cxt['rebuild_url'] = urllib.quote(req.childLink("rebuild"))
            cxt['name_user_passwd_form'] = make_name_user_passwd_form(self.isUsingUserPasswd(req))
            cxt['reason_row'] = make_row("Reason for re-running build:",
                                         "<input type='text' name='comments' />")
            
        template = self.templates.get_template("build.html");
        data = template.render(**cxt)
        data += self.footer(req)
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
        reason = ("The web-page 'stop build' button was pressed by "
                  "'%s': %s\n" % (name, comments))
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
                  "'%s': %s\n" % (name, comments))
        if not bc or not b.isFinished():
            log.msg("could not rebuild: bc=%s, isFinished=%s"
                    % (bc, b.isFinished()))
            # TODO: indicate an error
        else:
            bc.resubmitBuild(b, reason)
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

