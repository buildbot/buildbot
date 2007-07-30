

# $builder/builds/NN/stepname
class StatusResourceBuildStep(HtmlResource):
    title = "Build Step"

    def __init__(self, status, step):
        HtmlResource.__init__(self)
        self.status = status
        self.step = step

    def body(self, request):
        s = self.step
        b = s.getBuild()
        data = "<h1>BuildStep %s:#%d:%s</h1>\n" % \
               (b.getBuilder().getName(), b.getNumber(), s.getName())

        if s.isFinished():
            data += ("<h2>Finished</h2>\n"
                     "<p>%s</p>\n" % html.escape("%s" % s.getText()))
        else:
            data += ("<h2>Not Finished</h2>\n"
                     "<p>ETA %s seconds</p>\n" % s.getETA())

        exp = s.getExpectations()
        if exp:
            data += ("<h2>Expectations</h2>\n"
                     "<ul>\n")
            for e in exp:
                data += "<li>%s: current=%s, target=%s</li>\n" % \
                        (html.escape(e[0]), e[1], e[2])
            data += "</ul>\n"
        logs = s.getLogs()
        if logs:
            data += ("<h2>Logs</h2>\n"
                     "<ul>\n")
            for num in range(len(logs)):
                if logs[num].hasContents():
                    # FIXME: If the step name has a / in it, this is broken
                    # either way.  If we quote it but say '/'s are safe,
                    # it chops up the step name.  If we quote it and '/'s
                    # are not safe, it escapes the / that separates the
                    # step name from the log number.
                    data += '<li><a href="%s">%s</a></li>\n' % \
                            (urllib.quote(request.childLink("%d" % num)),
                             html.escape(logs[num].getName()))
                else:
                    data += ('<li>%s</li>\n' %
                             html.escape(logs[num].getName()))
            data += "</ul>\n"

        return data

    def getChild(self, path, request):
        logname = path
        try:
            log = self.step.getLogs()[int(logname)]
            if log.hasContents():
                return IHTMLLog(interfaces.IStatusLog(log))
            return NoResource("Empty Log '%s'" % logname)
        except (IndexError, ValueError):
            return NoResource("No such Log '%s'" % logname)


class StepBox(components.Adapter):
    implements(IBox)

    def getBox(self):
        b = self.original.getBuild()
        urlbase = "%s/builds/%d/step-%s" % (
            urllib.quote(b.getBuilder().getName(), safe=''),
            b.getNumber(),
            urllib.quote(self.original.getName(), safe=''))
        text = self.original.getText()
        if text is None:
            log.msg("getText() gave None", urlbase)
            text = []
        text = text[:]
        logs = self.original.getLogs()
        for num in range(len(logs)):
            name = logs[num].getName()
            if logs[num].hasContents():
                url = "%s/%d" % (urlbase, num)
                text.append("<a href=\"%s\">%s</a>" % (url, html.escape(name)))
            else:
                text.append(html.escape(name))
        urls = self.original.getURLs()
        ex_url_class = "BuildStep external"
        for name, target in urls.items():
            text.append('[<a href="%s" class="%s">%s</a>]' %
                        (target, ex_url_class, html.escape(name)))
        color = self.original.getColor()
        class_ = "BuildStep " + build_get_class(self.original)
        return Box(text, color, class_=class_)
components.registerAdapter(StepBox, builder.BuildStepStatus, IBox)
