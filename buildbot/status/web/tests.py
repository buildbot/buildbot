
# $builder/builds/NN/tests/TESTNAME
class StatusResourceTestResult(HtmlResource):
    title = "Test Logs"

    def __init__(self, status, name, result):
        HtmlResource.__init__(self)
        self.status = status
        self.name = name
        self.result = result

    def body(self, request):
        dotname = ".".join(self.name)
        logs = self.result.getLogs()
        lognames = logs.keys()
        lognames.sort()
        data = "<h1>%s</h1>\n" % html.escape(dotname)
        for name in lognames:
            data += "<h2>%s</h2>\n" % html.escape(name)
            data += "<pre>" + logs[name] + "</pre>\n\n"

        return data


# $builder/builds/NN/tests
class StatusResourceTestResults(HtmlResource):
    title = "Test Results"

    def __init__(self, status, results):
        HtmlResource.__init__(self)
        self.status = status
        self.results = results

    def body(self, request):
        r = self.results
        data = "<h1>Test Results</h1>\n"
        data += "<ul>\n"
        testnames = r.keys()
        testnames.sort()
        for name in testnames:
            res = r[name]
            dotname = ".".join(name)
            data += " <li>%s: " % dotname
            # TODO: this could break on weird test names. At the moment,
            # test names only come from Trial tests, where the name
            # components must be legal python names, but that won't always
            # be a restriction.
            url = request.childLink(dotname)
            data += "<a href=\"%s\">%s</a>" % (url, " ".join(res.getText()))
            data += "</li>\n"
        data += "</ul>\n"
        return data

    def getChild(self, path, request):
        try:
            name = tuple(path.split("."))
            result = self.results[name]
            return StatusResourceTestResult(self.status, name, result)
        except KeyError:
            return NoResource("No such test name '%s'" % path)

