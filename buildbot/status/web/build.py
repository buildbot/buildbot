
from twisted.web import html
from twisted.web.util import Redirect, DeferredResource
from twisted.internet import defer, reactor

import urllib, time
from twisted.python import log
from buildbot.status.web.base import HtmlResource, \
     css_classes, path_to_build, path_to_builder, path_to_slave, \
     getAndCheckProperties, path_to_authfail

from buildbot.status.web.step import StepsResource
from buildbot import util, interfaces



# /builders/$builder/builds/$buildnum
class StatusResourceBuild(HtmlResource):
    addSlash = True

    def __init__(self, build_status):
        HtmlResource.__init__(self)
        self.build_status = build_status

    def getTitle(self, request):
        return ("Buildbot: %s Build #%d" %
                (self.build_status.getBuilder().getName(),
                 self.build_status.getNumber()))

    def content(self, req, cxt):
        b = self.build_status
        status = self.getStatus(req)

        cxt['b'] = b
        cxt['path_to_builder'] = path_to_builder(req, b.getBuilder())
        
        if not b.isFinished():
            when = b.getETA()
            if when is not None:
                cxt['when'] = util.formatInterval(when)
                cxt['when_time'] = time.strftime("%H:%M:%S",
                                                time.localtime(time.time() + when))
                
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
            cxt['got_revision'] = str(got_revision)

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
                (start, end) = s.getTimes()
                step['time_to_run'] = util.formatInterval(end - start)
            elif s.isStarted():
                step['css_class'] = "running"
                step['time_to_run'] = "running"
            else:
                step['css_class'] = "not_started"
                step['time_to_run'] = ""

            step['link'] = req.childLink("steps/%s" % urllib.quote(s.getName()))
            step['text'] = " ".join(s.getText())
            step['urls'] = map(lambda x:dict(url=x[1],logname=x[0]), s.getURLs().items())

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
        else:
            now = util.now()
            cxt['elapsed'] = util.formatInterval(now - start)
            
        cxt['exactly'] = (ss.revision is not None) or b.getChanges()

        cxt['build_url'] = path_to_build(req, b)
        cxt['authz'] = self.getAuthz(req)

        template = req.site.buildbot_service.templates.get_template("build.html")
        return template.render(**cxt)

    def stop(self, req, auth_ok=False):
        # check if this is allowed
        if not auth_ok:
            if not self.getAuthz(req).actionAllowed('stopBuild', req, self.build_status):
                return Redirect(path_to_authfail(req))

        b = self.build_status
        log.msg("web stopBuild of build %s:%s" % \
                (b.getBuilder().getName(), b.getNumber()))
        name = req.args.get("username", ["<unknown>"])[0]
        comments = req.args.get("comments", ["<no reason specified>"])[0]
        # html-quote both the username and comments, just to be safe
        reason = ("The web-page 'stop build' button was pressed by "
                  "'%s': %s\n" % (html.escape(name), html.escape(comments)))

        c = interfaces.IControl(self.getBuildmaster(req))
        bldrc = c.getBuilder(self.build_status.getBuilder().getName())
        if bldrc:
            bldc = bldrc.getBuild(self.build_status.getNumber())
            if bldc:
                bldc.stopBuild(reason)

        # we're at http://localhost:8080/svn-hello/builds/5/stop?[args] and
        # we want to go to: http://localhost:8080/svn-hello
        r = Redirect(path_to_builder(req, self.build_status.getBuilder()))
        d = defer.Deferred()
        reactor.callLater(1, d.callback, r)
        return DeferredResource(d)

    def rebuild(self, req):
        # check auth
        if not self.getAuthz(req).actionAllowed('forceBuild', req, self.build_status.getBuilder()):
            return Redirect(path_to_authfail(req))

        # get a control object
        c = interfaces.IControl(self.getBuildmaster(req))
        bc = c.getBuilder(self.build_status.getBuilder().getName())

        b = self.build_status
        builder_name = b.getBuilder().getName()
        log.msg("web rebuild of build %s:%s" % (builder_name, b.getNumber()))
        name = req.args.get("username", ["<unknown>"])[0]
        comments = req.args.get("comments", ["<no reason specified>"])[0]
        reason = ("The web-page 'rebuild' button was pressed by "
                  "'%s': %s\n" % (name, comments))
        extraProperties = getAndCheckProperties(req)
        if not bc or not b.isFinished() or extraProperties is None:
            log.msg("could not rebuild: bc=%s, isFinished=%s"
                    % (bc, b.isFinished()))
            # TODO: indicate an error
        else:
            bc.rebuildBuild(b, reason, extraProperties)
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

        r = Redirect(path_to_builder(req, self.build_status.getBuilder()))
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

        return HtmlResource.getChild(self, path, req)

# /builders/$builder/builds
class BuildsResource(HtmlResource):
    addSlash = True

    def __init__(self, builder_status):
        HtmlResource.__init__(self)
        self.builder_status = builder_status

    def content(self, req, cxt):
        return "subpages shows data for each build"

    def getChild(self, path, req):
        try:
            num = int(path)
        except ValueError:
            num = None
        if num is not None:
            build_status = self.builder_status.getBuild(num)
            if build_status:
                return StatusResourceBuild(build_status)

        return HtmlResource.getChild(self, path, req)

