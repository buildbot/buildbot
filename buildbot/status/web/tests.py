
from twisted.web.error import NoResource
from twisted.web import html

from buildbot.status.web.base import HtmlResource

# /builders/$builder/builds/$buildnum/tests/$testname
class TestResult(HtmlResource):
    title = "Test Logs"

    def __init__(self, name, test_result):
        HtmlResource.__init__(self)
        self.name = name
        self.test_result = test_result

    def body(self, request):
        dotname = ".".join(self.name)
        logs = self.test_result.getLogs()
        lognames = logs.keys()
        lognames.sort()
        data = "<h1>%s</h1>\n" % html.escape(dotname)
        for name in lognames:
            data += "<h2>%s</h2>\n" % html.escape(name)
            data += "<pre>" + logs[name] + "</pre>\n\n"

        return data


# /builders/$builder/builds/$buildnum/tests
class TestsResource(HtmlResource):
    title = "Test Results"

    def __init__(self, build_status):
        HtmlResource.__init__(self)
        self.build_status = build_status
        self.test_results = build_status.getTestResults()

    def body(self, request):
        r = self.test_results
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
            result = self.test_results[name]
            return TestResult(name, result)
        except KeyError:
            return NoResource("No such test name '%s'" % html.escape(path))
