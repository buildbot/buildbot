# -*- test-case-name: buildbot.test.test_web_status_json -*-
# Original Copyright (c) 2010 The Chromium Authors.

"""Simple JSON exporter."""

import datetime
import os
import re

from twisted.web import error, html, resource

from buildbot.status.web.base import HtmlResource
from buildbot.util import json


_IS_INT = re.compile('^[-+]?\d+$')


FLAGS = """\
  - as_text
    - By default, application/json is used. Setting as_text=1 change the type
      to text/plain and implicitly sets compact=0 and filter=1. Mainly useful to
      look at the result in a web browser.
  - compact
    - By default, the json data is compact and defaults to 1. For easier to read
      indented output, set compact=0.
  - select
    - By default, most children data is listed. You can do a random selection
      of data by using select=<sub-url> multiple times to coagulate data.
      "select=" includes the actual url otherwise it is skipped.
  - filter
    - Filters out null, false, and empty string, list and dict. This reduce the
      amount of useless data sent.

"""

EXAMPLES = """\
  - /json
    - Root node, that *doesn't* mean all the data. Many things (like logs) must
      be explicitly queried for performance reasons.
  - /json/builders/
    - All builders.
  - /json/builders/<A_BUILDER>
    - A specific builder as compact text.
  - /json/builders/<A_BUILDER>/builds
    - All *cached* builds.
  - /json/builders/<A_BUILDER>/builds/_all
    - All builds. Warning, reads all previous build data.
  - /json/builders/<A_BUILDER>/builds/<A_BUILD>
    - Where <A_BUILD> is either positive, a build number, or negative, a past
      build.
  - /json/builders/<A_BUILDER>/builds/-1/source_stamp/changes
    - Build changes
  - /json/builders/<A_BUILDER>/builds?select=-1&select=-2
    - Two last builds on '<A_BUILDER>' builder.
  - /json/builders/<A_BUILDER>/builds?select=-1/source_stamp/changes&select=-2/source_stamp/changes
    - Changes of the two last builds on '<A_BUILDER>' builder.
  - /json/builders/<A_BUILDER>/slaves
    - Slaves associated to this builder.
  - /json/builders/<A_BUILDER>?select=&select=slaves
    - Builder information plus details information about its slaves. Neat eh?
  - /json/slaves/<A_SLAVE>
    - A specific slave.
  - /json?select=slaves/<A_SLAVE>/&select=project&select=builders/<A_BUILDER>/builds/<A_BUILD>
    - A selection of random unrelated stuff as an random example. :)
"""


def RequestArg(request, arg, default):
    return request.args.get(arg, [default])[0]


def RequestArgToBool(request, arg, default):
    value = RequestArg(request, arg, default)
    if value in (False, True):
        return value
    value = value.lower()
    if value in ('1', 'true'):
        return True
    if value in ('0', 'false'):
        return False
    # Ignore value.
    return default


def TwistedWebErrorAsDict(self, request):
    """Additional method for twisted.web.error.Error."""
    result = {}
    result['http_error'] = self.status
    result['response'] = self.response
    return result


def TwistedWebErrorPageAsDict(self, request):
    """Additional method for twisted.web.error.Error."""
    result = {}
    result['http_error'] = self.code
    result['response'] = self.brief
    result['detail'] = self.detail
    return result


# Add .asDict() method to twisted.web.error.Error to simplify the code below.
error.Error.asDict = TwistedWebErrorAsDict
error.PageRedirect.asDict = TwistedWebErrorAsDict
error.ErrorPage.asDict = TwistedWebErrorPageAsDict
error.NoResource.asDict = TwistedWebErrorPageAsDict
error.ForbiddenResource.asDict = TwistedWebErrorPageAsDict


def FilterOut(data):
    """Returns a copy with None, False, "", [], () and {} removed.
    Warning: converts tuple to list."""
    if isinstance(data, (list, tuple)):
        # Recurse in every items and filter them out.
        items = map(FilterOut, data)
        if not filter(lambda x: not x in ('', False, None, [], {}, ()), items):
            return None
        return items
    elif isinstance(data, dict):
        return dict(filter(lambda x: not x[1] in ('', False, None, [], {}, ()),
                           [(k, FilterOut(v)) for (k, v) in data.iteritems()]))
    else:
        return data


class JsonResource(resource.Resource):
    """Base class for json data."""

    contentType = "application/json"
    cache_seconds = 60
    help = None
    title = None
    level = 0

    def __init__(self, status):
        """Adds transparent lazy-child initialization."""
        resource.Resource.__init__(self)
        # buildbot.status.builder.Status
        self.status = status
        if self.help:
            title = ''
            if self.title:
                title = self.title + ' help'
            self.putChild('help',
                          HelpResource(self.help, title=title, parent_node=self))

    def getChildWithDefault(self, path, request):
        """Adds transparent support for url ending with /"""
        if path == "" and len(request.postpath) == 0:
            return self
        # Equivalent to resource.Resource.getChildWithDefault()
        if self.children.has_key(path):
            return self.children[path]
        return self.getChild(path, request)

    def putChild(self, name, res):
        """Adds the resource's level for help links generation."""

        def RecurseFix(res, level):
            res.level = level + 1
            for c in res.children.itervalues():
                RecurseFix(c, res.level)

        RecurseFix(res, self.level)
        resource.Resource.putChild(self, name, res)

    def render_GET(self, request):
        """Renders a HTTP GET at the http request level."""
        data = self.content(request)
        if isinstance(data, unicode):
            data = data.encode("utf-8")
        if RequestArgToBool(request, 'as_text', False):
            request.setHeader("content-type", 'text/plain')
        else:
            request.setHeader("content-type", self.contentType)
            request.setHeader("content-disposition",
                              "attachment; filename=\"%s.json\"" % request.path)
        # Make sure we get fresh pages.
        if self.cache_seconds:
            now = datetime.datetime.utcnow()
            expires = now + datetime.timedelta(seconds=self.cache_seconds)
            request.setHeader("Expires",
                              expires.strftime("%a, %d %b %Y %H:%M:%S GMT"))
            request.setHeader("Pragma", "no-cache")
        return data

    def content(self, request):
        """Renders the json dictionaries."""
        # Implement filtering at global level and every child.
        select = request.args.get('select')
        if select is not None:
            del request.args['select']
            # Do not render self.asDict()!
            data = {}
            # Remove superfluous /
            select = [s.strip('/') for s in select]
            select.sort(cmp=lambda x,y: cmp(x.count('/'), y.count('/')),
                        reverse=True)
            for item in select:
                # Start back at root.
                node = data
                # Implementation similar to twisted.web.resource.getChildForRequest
                # but with a hacked up request.
                child = self
                prepath = request.prepath[:]
                postpath = request.postpath[:]
                request.postpath = filter(None, item.split('/'))
                while request.postpath and not child.isLeaf:
                    pathElement = request.postpath.pop(0)
                    node[pathElement] = {}
                    node = node[pathElement]
                    request.prepath.append(pathElement)
                    child = child.getChildWithDefault(pathElement, request)
                node.update(child.asDict(request))
                request.prepath = prepath
                request.postpath = postpath
        else:
            data = self.asDict(request)
        as_text = RequestArgToBool(request, 'as_text', False)
        filter_out = RequestArgToBool(request, 'filter', as_text)
        if filter_out:
            data = FilterOut(data)
        if RequestArgToBool(request, 'compact', not as_text):
            return json.dumps(data, sort_keys=True, separators=(',',':'))
        else:
            return json.dumps(data, sort_keys=True, indent=2)

    def asDict(self, request):
        """Generates the json dictionary.

        By default, renders every childs."""
        if self.children:
            data = {}
            for name in self.children:
                child = self.getChildWithDefault(name, request)
                if isinstance(child, JsonResource):
                    data[name] = child.asDict(request)
                # else silently pass over non-json resources.
            return data
        else:
            raise NotImplementedError()


def ToHtml(text):
    """Convert a string in a wiki-style format into HTML."""
    indent = 0
    in_item = False
    output = []
    for line in text.splitlines(False):
        match = re.match(r'^( +)\- (.*)$', line)
        if match:
            if indent < len(match.group(1)):
                output.append('<ul>')
                indent = len(match.group(1))
            elif indent > len(match.group(1)):
                while indent > len(match.group(1)):
                    output.append('</ul>')
                    indent -= 2
            if in_item:
                # Close previous item
                output.append('</li>')
            output.append('<li>')
            in_item = True
            line = match.group(2)
        elif indent:
            if line.startswith((' ' * indent) + '  '):
                # List continuation
                line = line.strip()
            else:
                # List is done
                if in_item:
                    output.append('</li>')
                    in_item = False
                while indent > 0:
                    output.append('</ul>')
                    indent -= 2

        if line.startswith('/'):
            if not '?' in line:
                line_full = line + '?as_text=1'
            else:
                line_full = line + '&as_text=1'
            output.append('<a href="' + html.escape(line_full) + '">' +
                html.escape(line) + '</a>')
        else:
            output.append(html.escape(line).replace('  ', '&nbsp;&nbsp;'))
        if not in_item:
            output.append('<br>')

    if in_item:
        output.append('</li>')
    while indent > 0:
        output.append('</ul>')
        indent -= 2
    return '\n'.join(output)


class HelpResource(HtmlResource):
    def __init__(self, text, title, parent_node):
        HtmlResource.__init__(self)
        self.text = text
        self.title = title
        self.parent_node = parent_node

    def content(self, request, cxt):
        cxt['level'] = self.parent_node.level
        cxt['text'] = ToHtml(self.text)
        cxt['children'] = [ n for n in self.parent_node.children.keys() if n != 'help' ]
        cxt['flags'] = ToHtml(FLAGS)
        cxt['examples'] = ToHtml(EXAMPLES).replace(
                'href="/json',
                'href="%sjson' % (self.level * '../'))

        template = request.site.buildbot_service.templates.get_template("jsonhelp.html")
        return template.render(**cxt)

class BuilderJsonResource(JsonResource):
    help = """Describe a single builder.
"""
    title = 'Builder'

    def __init__(self, status, builder_status):
        JsonResource.__init__(self, status)
        self.builder_status = builder_status
        self.putChild('builds', BuildsJsonResource(status, builder_status))
        self.putChild('slaves', BuilderSlavesJsonResources(status,
                                                           builder_status))

    def asDict(self, request):
        # buildbot.status.builder.BuilderStatus
        return self.builder_status.asDict()


class BuildersJsonResource(JsonResource):
    help = """List of all the builders defined on a master.
"""
    title = 'Builders'

    def __init__(self, status):
        JsonResource.__init__(self, status)
        for builder_name in self.status.getBuilderNames():
            self.putChild(builder_name,
                          BuilderJsonResource(status,
                                              status.getBuilder(builder_name)))


class BuilderSlavesJsonResources(JsonResource):
    help = """Describe the slaves attached to a single builder.
"""
    title = 'BuilderSlaves'

    def __init__(self, status, builder_status):
        JsonResource.__init__(self, status)
        self.builder_status = builder_status
        for slave_name in self.builder_status.slavenames:
            self.putChild(slave_name,
                          SlaveJsonResource(status,
                                            self.status.getSlave(slave_name)))


class BuildJsonResource(JsonResource):
    help = """Describe a single build.
"""
    title = 'Build'

    def __init__(self, status, build_status):
        JsonResource.__init__(self, status)
        self.build_status = build_status
        self.putChild('source_stamp',
                      SourceStampJsonResource(status,
                                              build_status.getSourceStamp()))
        self.putChild('steps', BuildStepsJsonResource(status, build_status))

    def asDict(self, request):
        return self.build_status.asDict()


class AllBuildsJsonResource(JsonResource):
    help = """All the builds that were run on a builder.
"""
    title = 'AllBuilds'

    def __init__(self, status, builder_status):
        JsonResource.__init__(self, status)
        self.builder_status = builder_status

    def getChild(self, path, request):
        # Dynamic childs.
        if isinstance(path, int) or _IS_INT.match(path):
            build_status = self.builder_status.getBuild(int(path))
            if build_status:
                build_status_number = str(build_status.getNumber())
                # Happens with negative numbers.
                child = self.children.get(build_status_number)
                if child:
                    return child
                # Create it on-demand.
                child = BuildJsonResource(self.status, build_status)
                # Cache it. Never cache negative numbers.
                # TODO(maruel): Cleanup the cache once it's too heavy!
                self.putChild(build_status_number, child)
                return child
        return JsonResource.getChild(self, path, request)

    def asDict(self, request):
        results = {}
        # If max > buildCacheSize, it'll trash the cache...
        max = int(RequestArg(request, 'max',
                             self.builder_status.buildCacheSize))
        for i in range(0, max):
            child = self.getChildWithDefault(-i, request)
            if not isinstance(child, BuildJsonResource):
                continue
            results[child.build_status.getNumber()] = child.asDict(request)
        return results


class BuildsJsonResource(AllBuildsJsonResource):
    help = """Builds that were run on a builder.
"""
    title = 'Builds'

    def __init__(self, status, builder_status):
        AllBuildsJsonResource.__init__(self, status, builder_status)
        self.putChild('_all', AllBuildsJsonResource(status, builder_status))

    def getChild(self, path, request):
        # Transparently redirects to _all if path is not ''.
        return self.children['_all'].getChildWithDefault(path, request)

    def asDict(self, request):
        # This would load all the pickles and is way too heavy, especially that
        # it would trash the cache:
        # self.children['builds'].asDict(request)
        # TODO(maruel) This list should also need to be cached but how?
        builds = dict([
            (int(file), None)
            for file in os.listdir(self.builder_status.basedir)
            if _IS_INT.match(file)
        ])
        return builds


class BuildStepJsonResource(JsonResource):
    help = """A single build step.
"""
    title = 'BuildStep'

    def __init__(self, status, build_step_status):
        # buildbot.status.builder.BuildStepStatus
        JsonResource.__init__(self, status)
        self.build_step_status = build_step_status
        # TODO self.putChild('logs', LogsJsonResource())

    def asDict(self, request):
        return self.build_step_status.asDict()


class BuildStepsJsonResource(JsonResource):
    help = """A list of build steps that occurred during a build.
"""
    title = 'BuildSteps'

    def __init__(self, status, build_status):
        JsonResource.__init__(self, status)
        self.build_status = build_status
        # The build steps are constantly changing until the build is done so
        # keep a reference to build_status instead

    def getChild(self, path, request):
        # Dynamic childs.
        build_set_status = None
        if isinstance(path, int) or _IS_INT.match(path):
            build_set_status = self.build_status.getSteps[int(path)]
        else:
            steps_dict = dict([(step.getName(), step)
                               for step in self.build_status.getStep()])
            build_set_status = steps_dict.get(path)
        if build_set_status:
            # Create it on-demand.
            child = BuildStepJsonResource(status, build_step_status)
            # Cache it.
            index = self.build_status.getSteps().index(build_step_status)
            self.putChild(str(index), child)
            self.putChild(build_set_status.getName(), child)
            return child
        return JsonResource.getChild(self, path, request)

    def asDict(self, request):
        # Only use the number and not the names!
        results = {}
        index = 0
        for step in self.build_status.getStep():
            results[index] = step
            index += 1
        return results


class ChangeJsonResource(JsonResource):
    help = """Describe a single change that originates from a change source.
"""
    title = 'Change'

    def __init__(self, status, change):
        # buildbot.changes.changes.Change
        JsonResource.__init__(self, status)
        self.change = change

    def asDict(self, request):
        return self.change.asDict()


class ChangesJsonResource(JsonResource):
    help = """List of changes.
"""
    title = 'Changes'

    def __init__(self, status, changes):
        JsonResource.__init__(self, status)
        for c in changes:
            # TODO(maruel): Problem with multiple changes with the same number.
            # Probably try server hack specific so we could fix it on this side
            # instead. But there is still the problem with multiple pollers from
            # different repo where the numbers could clash.
            number = str(c.number)
            while number in self.children:
                # TODO(maruel): Do something better?
                number = str(int(c.number)+1)
            self.putChild(number, ChangeJsonResource(status, c))

    def asDict(self, request):
        """Don't throw an exception when there is no child."""
        if not self.children:
            return {}
        return JsonResource.asDict(self, request)


class ChangeSourcesJsonResource(JsonResource):
    help = """Describe a change source.
"""
    title = 'ChangeSources'

    def asDict(self, request):
        result = {}
        n = 0
        for c in self.status.getChangeSources():
            # buildbot.changes.changes.ChangeMaster
            change = {}
            change['description'] = c.describe()
            result[n] = change
            n += 1
        return result


class ProjectJsonResource(JsonResource):
    help = """Project-wide settings.
"""
    title = 'Project'

    def asDict(self, request):
        return self.status.asDict()


class SlaveJsonResource(JsonResource):
    help = """Describe a slave.
"""
    title = 'Slave'

    def __init__(self, status, slave_status):
        JsonResource.__init__(self, status)
        self.slave_status = slave_status
        self.name = self.slave_status.getName()
        self.builders = None

    def getBuilders(self):
        if self.builders is None:
            # Figure out all the builders to which it's attached
            self.builders = []
            for builderName in self.status.getBuilderNames():
                if self.name in self.status.getBuilder(builderName).slavenames:
                    self.builders.append(builderName)
        return self.builders

    def asDict(self, request):
        results = self.slave_status.asDict()
        # Enhance it by adding more informations.
        results['builders'] = {}
        for builderName in self.getBuilders():
            builds = []
            builder_status = self.status.getBuilder(builderName)
            for i in range(1, builder_status.buildCacheSize - 1):
                build_status = builder_status.getBuild(-i)
                if not build_status or not build_status.isFinished():
                    # If not finished, it will appear in runningBuilds.
                    break
                if build_status.getSlavename() == self.name:
                    builds.append(build_status.getNumber())
            results['builders'][builderName] = builds
        return results


class SlavesJsonResource(JsonResource):
    help = """List the registered slaves.
"""
    title = 'Slaves'

    def __init__(self, status):
        JsonResource.__init__(self, status)
        for slave_name in status.getSlaveNames():
            self.putChild(slave_name,
                          SlaveJsonResource(status,
                                            status.getSlave(slave_name)))


class SourceStampJsonResource(JsonResource):
    help = """Describe the sources for a BuildRequest.
"""
    title = 'SourceStamp'

    def __init__(self, status, source_stamp):
        # buildbot.sourcestamp.SourceStamp
        JsonResource.__init__(self, status)
        self.source_stamp = source_stamp
        self.putChild('changes',
                      ChangesJsonResource(status, source_stamp.changes))
        # TODO(maruel): Should redirect to the patch's url instead.
        #if source_stamp.patch:
        #  self.putChild('patch', StaticHTML(source_stamp.path))

    def asDict(self, request):
        return self.source_stamp.asDict()


class JsonStatusResource(JsonResource):
    """Retrieves all json data."""
    help = """JSON status

Root page to give a fair amount of information in the current buildbot master
status. You may want to use a child instead to reduce the load on the server.

For help on any sub directory, use url /child/help
"""
    title = 'Buildbot JSON'

    def __init__(self, status):
        JsonResource.__init__(self, status)
        self.level = 1
        self.putChild('builders', BuildersJsonResource(status))
        self.putChild('change_sources', ChangeSourcesJsonResource(status))
        self.putChild('project', ProjectJsonResource(status))
        self.putChild('slaves', SlavesJsonResource(status))
        # This needs to be called before the first HelpResource().body call.
        self.hackExamples()

    def content(self, request):
        result = JsonResource.content(self, request)
        # This is done to hook the downloaded filename.
        request.path = 'buildbot'
        return result

    def hackExamples(self):
        global EXAMPLES
        # Find the first builder with a previous build or select the last one.
        builder = None
        for b in self.status.getBuilderNames():
            builder = self.status.getBuilder(b)
            if builder.getBuild(-1):
                break
        if not builder:
            return
        EXAMPLES = EXAMPLES.replace('<A_BUILDER>', builder.getName())
        build = builder.getBuild(-1)
        if build:
            EXAMPLES = EXAMPLES.replace('<A_BUILD>', str(build.getNumber()))
        if builder.slavenames:
            EXAMPLES = EXAMPLES.replace('<A_SLAVE>', builder.slavenames[0])

# vim: set ts=4 sts=4 sw=4 et:
