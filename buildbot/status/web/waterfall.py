# -*- test-case-name: buildbot.test.test_web -*-

from zope.interface import implements
from twisted.python import log, components
from twisted.web import html
import urllib

import time
import operator

from buildbot import interfaces, util
from buildbot import version
from buildbot.status import builder

from buildbot.status.web.base import Box, HtmlResource, IBox, ICurrentBox, \
     ITopBox, td, build_get_class, path_to_build, path_to_step, map_branches



class CurrentBox(components.Adapter):
    # this provides the "current activity" box, just above the builder name
    implements(ICurrentBox)

    def formatETA(self, prefix, eta):
        if eta is None:
            return []
        if eta < 60:
            return ["< 1 min"]
        eta_parts = ["~"]
        eta_secs = eta
        if eta_secs > 3600:
            eta_parts.append("%d hrs" % (eta_secs / 3600))
            eta_secs %= 3600
        if eta_secs > 60:
            eta_parts.append("%d mins" % (eta_secs / 60))
            eta_secs %= 60
        abstime = time.strftime("%H:%M", time.localtime(util.now()+eta))
        return [prefix, " ".join(eta_parts), "at %s" % abstime]

    def getBox(self, status):
        # getState() returns offline, idle, or building
        state, builds = self.original.getState()

        # look for upcoming builds. We say the state is "waiting" if the
        # builder is otherwise idle and there is a scheduler which tells us a
        # build will be performed some time in the near future. TODO: this
        # functionality used to be in BuilderStatus.. maybe this code should
        # be merged back into it.
        upcoming = []
        builderName = self.original.getName()
        for s in status.getSchedulers():
            if builderName in s.listBuilderNames():
                upcoming.extend(s.getPendingBuildTimes())
        if state == "idle" and upcoming:
            state = "waiting"

        if state == "building":
            text = ["building"]
            if builds:
                for b in builds:
                    eta = b.getETA()
                    text.extend(self.formatETA("ETA in", eta))
        elif state == "offline":
            text = ["offline"]
        elif state == "idle":
            text = ["idle"]
        elif state == "waiting":
            text = ["waiting"]
        else:
            # just in case I add a state and forget to update this
            text = [state]

        # TODO: for now, this pending/upcoming stuff is in the "current
        # activity" box, but really it should go into a "next activity" row
        # instead. The only times it should show up in "current activity" is
        # when the builder is otherwise idle.

        # are any builds pending? (waiting for a slave to be free)
        pbs = self.original.getPendingBuilds()
        if pbs:
            text.append("%d pending" % len(pbs))
        for t in upcoming:
            eta = t - util.now()
            text.extend(self.formatETA("next in", eta))
        return Box(text, class_="Activity " + state)

components.registerAdapter(CurrentBox, builder.BuilderStatus, ICurrentBox)


class BuildTopBox(components.Adapter):
    # this provides a per-builder box at the very top of the display,
    # showing the results of the most recent build
    implements(IBox)

    def getBox(self, req):
        assert interfaces.IBuilderStatus(self.original)
        branches = [b for b in req.args.get("branch", []) if b]
        builder = self.original
        builds = list(builder.generateFinishedBuilds(map_branches(branches),
                                                     num_builds=1))
        if not builds:
            return Box(["none"], class_="LastBuild")
        b = builds[0]
        name = b.getBuilder().getName()
        number = b.getNumber()
        url = path_to_build(req, b)
        text = b.getText()
        tests_failed = b.getSummaryStatistic('tests-failed', operator.add, 0)
        if tests_failed: text.extend(["Failed tests: %d" % tests_failed])
        # TODO: maybe add logs?
        # TODO: add link to the per-build page at 'url'
        class_ = build_get_class(b)
        return Box(text, class_="LastBuild %s" % class_)
components.registerAdapter(BuildTopBox, builder.BuilderStatus, ITopBox)

class BuildBox(components.Adapter):
    # this provides the yellow "starting line" box for each build
    implements(IBox)

    def getBox(self, req):
        b = self.original
        number = b.getNumber()
        url = path_to_build(req, b)
        reason = b.getReason()
        text = ('<a title="Reason: %s" href="%s">Build %d</a>'
                % (html.escape(reason), url, number))
        class_ = "start"
        if b.isFinished() and not b.getSteps():
            # the steps have been pruned, so there won't be any indication
            # of whether it succeeded or failed.
            class_ = build_get_class(b)
        return Box([text], class_="BuildStep " + class_)
components.registerAdapter(BuildBox, builder.BuildStatus, IBox)

class StepBox(components.Adapter):
    implements(IBox)

    def getBox(self, req):
        urlbase = path_to_step(req, self.original)
        text = self.original.getText()
        if text is None:
            log.msg("getText() gave None", urlbase)
            text = []
        text = text[:]
        logs = self.original.getLogs()
        for num in range(len(logs)):
            name = logs[num].getName()
            if logs[num].hasContents():
                url = urlbase + "/logs/%s" % urllib.quote(name)
                text.append("<a href=\"%s\">%s</a>" % (url, html.escape(name)))
            else:
                text.append(html.escape(name))
        urls = self.original.getURLs()
        ex_url_class = "BuildStep external"
        for name, target in urls.items():
            text.append('[<a href="%s" class="%s">%s</a>]' %
                        (target, ex_url_class, html.escape(name)))
        class_ = "BuildStep " + build_get_class(self.original)
        return Box(text, class_=class_)
components.registerAdapter(StepBox, builder.BuildStepStatus, IBox)


class EventBox(components.Adapter):
    implements(IBox)

    def getBox(self, req):
        text = self.original.getText()
        class_ = "Event"
        return Box(text, class_=class_)
components.registerAdapter(EventBox, builder.Event, IBox)
        

class Spacer:
    implements(interfaces.IStatusEvent)

    def __init__(self, start, finish):
        self.started = start
        self.finished = finish

    def getTimes(self):
        return (self.started, self.finished)
    def getText(self):
        return []

class SpacerBox(components.Adapter):
    implements(IBox)

    def getBox(self, req):
        #b = Box(["spacer"], "white")
        b = Box([])
        b.spacer = True
        return b
components.registerAdapter(SpacerBox, Spacer, IBox)

def insertGaps(g, showEvents, lastEventTime, idleGap=2):
    debug = False

    e = g.next()
    starts, finishes = e.getTimes()
    if debug: log.msg("E0", starts, finishes)
    if finishes == 0:
        finishes = starts
    if debug: log.msg("E1 finishes=%s, gap=%s, lET=%s" % \
                      (finishes, idleGap, lastEventTime))
    if finishes is not None and finishes + idleGap < lastEventTime:
        if debug: log.msg(" spacer0")
        yield Spacer(finishes, lastEventTime)

    followingEventStarts = starts
    if debug: log.msg(" fES0", starts)
    yield e

    while 1:
        e = g.next()
        if not showEvents and isinstance(e, builder.Event):
            continue
        starts, finishes = e.getTimes()
        if debug: log.msg("E2", starts, finishes)
        if finishes == 0:
            finishes = starts
        if finishes is not None and finishes + idleGap < followingEventStarts:
            # there is a gap between the end of this event and the beginning
            # of the next one. Insert an idle event so the waterfall display
            # shows a gap here.
            if debug:
                log.msg(" finishes=%s, gap=%s, fES=%s" % \
                        (finishes, idleGap, followingEventStarts))
            yield Spacer(finishes, followingEventStarts)
        yield e
        followingEventStarts = starts
        if debug: log.msg(" fES1", starts)

HELP = '''
<form action="../waterfall" method="GET">

<h1>The Waterfall Display</h1>

<p>The Waterfall display can be controlled by adding query arguments to the
URL. For example, if your Waterfall is accessed via the URL
<tt>http://buildbot.example.org:8080</tt>, then you could add a
<tt>branch=</tt> argument (described below) by going to
<tt>http://buildbot.example.org:8080?branch=beta4</tt> instead. Remember that
query arguments are separated from each other with ampersands, but they are
separated from the main URL with a question mark, so to add a
<tt>branch=</tt> and two <tt>builder=</tt> arguments, you would use
<tt>http://buildbot.example.org:8080?branch=beta4&amp;builder=unix&amp;builder=macos</tt>.</p>

<h2>Limiting the Displayed Interval</h2>

<p>The <tt>last_time=</tt> argument is a unix timestamp (seconds since the
start of 1970) that will be used as an upper bound on the interval of events
displayed: nothing will be shown that is more recent than the given time.
When no argument is provided, all events up to and including the most recent
steps are included.</p>

<p>The <tt>first_time=</tt> argument provides the lower bound. No events will
be displayed that occurred <b>before</b> this timestamp. Instead of providing
<tt>first_time=</tt>, you can provide <tt>show_time=</tt>: in this case,
<tt>first_time</tt> will be set equal to <tt>last_time</tt> minus
<tt>show_time</tt>. <tt>show_time</tt> overrides <tt>first_time</tt>.</p>

<p>The display normally shows the latest 200 events that occurred in the
given interval, where each timestamp on the left hand edge counts as a single
event. You can add a <tt>num_events=</tt> argument to override this this.</p>

<h2>Showing non-Build events</h2>

<p>By passing <tt>show_events=true</tt>, you can add the "buildslave
attached", "buildslave detached", and "builder reconfigured" events that
appear in-between the actual builds.</p>

%(show_events_input)s

<h2>Showing only the Builders with failures</h2>

<p>By adding the <tt>failures_only=true</tt> argument, the display will be limited
to showing builders that are currently failing. A builder is considered
failing if the last finished build was not successful, a step in the current
build(s) failed, or if the builder is offline.

%(failures_only_input)s

<h2>Showing only Certain Branches</h2>

<p>If you provide one or more <tt>branch=</tt> arguments, the display will be
limited to builds that used one of the given branches. If no <tt>branch=</tt>
arguments are given, builds from all branches will be displayed.</p>

Erase the text from these "Show Branch:" boxes to remove that branch filter.

%(show_branches_input)s

<h2>Limiting the Builders that are Displayed</h2>

<p>By adding one or more <tt>builder=</tt> arguments, the display will be
limited to showing builds that ran on the given builders. This serves to
limit the display to the specific named columns. If no <tt>builder=</tt>
arguments are provided, all Builders will be displayed.</p>

<p>To view a Waterfall page with only a subset of Builders displayed, select
the Builders you are interested in here.</p>

%(show_builders_input)s


<h2>Auto-reloading the Page</h2>

<p>Adding a <tt>reload=</tt> argument will cause the page to automatically
reload itself after that many seconds.</p>

%(show_reload_input)s

<h2>Reload Waterfall Page</h2>

<input type="submit" value="View Waterfall" />
</form>
'''

class WaterfallHelp(HtmlResource):
    title = "Waterfall Help"

    def __init__(self, categories=None):
        HtmlResource.__init__(self)
        self.categories = categories

    def body(self, request):
        data = ''
        status = self.getStatus(request)

        showEvents_checked = ''
        if request.args.get("show_events", ["false"])[0].lower() == "true":
            showEvents_checked = 'checked="checked"'
        show_events_input = ('<p>'
                             '<input type="checkbox" name="show_events" '
                             'value="true" %s>'
                             'Show non-Build events'
                             '</p>\n'
                             ) % showEvents_checked

        failuresOnly_checked = ''
        if request.args.get("failures_only", ["false"])[0].lower() == "true":
            failuresOnly_checked = 'checked="checked"'
        failures_only_input = ('<p>'
                               '<input type="checkbox" name="failures_only" '
                               'value="true" %s>'
                               'Show failures only'
                               '</p>\n'
                               ) % failuresOnly_checked

        branches = [b
                    for b in request.args.get("branch", [])
                    if b]
        branches.append('')
        show_branches_input = '<table>\n'
        for b in branches:
            show_branches_input += ('<tr>'
                                    '<td>Show Branch: '
                                    '<input type="text" name="branch" '
                                    'value="%s">'
                                    '</td></tr>\n'
                                    ) % (html.escape(b),)
        show_branches_input += '</table>\n'

        # this has a set of toggle-buttons to let the user choose the
        # builders
        showBuilders = request.args.get("show", [])
        showBuilders.extend(request.args.get("builder", []))
        allBuilders = status.getBuilderNames(categories=self.categories)

        show_builders_input = '<table>\n'
        for bn in allBuilders:
            checked = ""
            if bn in showBuilders:
                checked = 'checked="checked"'
            show_builders_input += ('<tr>'
                                    '<td><input type="checkbox"'
                                    ' name="builder" '
                                    'value="%s" %s></td> '
                                    '<td>%s</td></tr>\n'
                                    ) % (bn, checked, bn)
        show_builders_input += '</table>\n'

        # a couple of radio-button selectors for refresh time will appear
        # just after that text
        show_reload_input = '<table>\n'
        times = [("none", "None"),
                 ("60", "60 seconds"),
                 ("300", "5 minutes"),
                 ("600", "10 minutes"),
                 ]
        current_reload_time = request.args.get("reload", ["none"])
        if current_reload_time:
            current_reload_time = current_reload_time[0]
        if current_reload_time not in [t[0] for t in times]:
            times.insert(0, (current_reload_time, current_reload_time) )
        for value, name in times:
            checked = ""
            if value == current_reload_time:
                checked = 'checked="checked"'
            show_reload_input += ('<tr>'
                                  '<td><input type="radio" name="reload" '
                                  'value="%s" %s></td> '
                                  '<td>%s</td></tr>\n'
                                  ) % (html.escape(value), checked, html.escape(name))
        show_reload_input += '</table>\n'

        fields = {"show_events_input": show_events_input,
                  "show_branches_input": show_branches_input,
                  "show_builders_input": show_builders_input,
                  "show_reload_input": show_reload_input,
                  "failures_only_input": failures_only_input,
                  }
        data += HELP % fields
        return data

class WaterfallStatusResource(HtmlResource):
    """This builds the main status page, with the waterfall display, and
    all child pages."""

    def __init__(self, categories=None, num_events=200, num_events_max=None):
        HtmlResource.__init__(self)
        self.categories = categories
        self.num_events=num_events
        self.num_events_max=num_events_max
        self.putChild("help", WaterfallHelp(categories))

    def getTitle(self, request):
        status = self.getStatus(request)
        p = status.getProjectName()
        if p:
            return "BuildBot: %s" % p
        else:
            return "BuildBot"

    def getChangemaster(self, request):
        # TODO: this wants to go away, access it through IStatus
        return request.site.buildbot_service.getChangeSvc()

    def get_reload_time(self, request):
        if "reload" in request.args:
            try:
                reload_time = int(request.args["reload"][0])
                return max(reload_time, 15)
            except ValueError:
                pass
        return None

    def head(self, request):
        head = ''
        reload_time = self.get_reload_time(request)
        if reload_time is not None:
            head += '<meta http-equiv="refresh" content="%d">\n' % reload_time
        return head

    def isSuccess(self, builderStatus):
        # Helper function to return True if the builder is not failing.
        # The function will return false if the current state is "offline",
        # the last build was not successful, or if a step from the current
        # build(s) failed.

        # Make sure the builder is online.
        if builderStatus.getState()[0] == 'offline':
            return False

        # Look at the last finished build to see if it was success or not.
        lastBuild = builderStatus.getLastFinishedBuild()
        if lastBuild and lastBuild.getResults() != builder.SUCCESS:
            return False

        # Check all the current builds to see if one step is already
        # failing.
        currentBuilds = builderStatus.getCurrentBuilds()
        if currentBuilds:
            for build in currentBuilds:
                for step in build.getSteps():
                    if step.getResults()[0] == builder.FAILURE:
                        return False

        # The last finished build was successful, and all the current builds
        # don't have any failed steps.
        return True

    def body(self, request):
        "This method builds the main waterfall display."

        status = self.getStatus(request)
        data = ''

        projectName = status.getProjectName()
        projectURL = status.getProjectURL()

        phase = request.args.get("phase",["2"])
        phase = int(phase[0])

        # we start with all Builders available to this Waterfall: this is
        # limited by the config-file -time categories= argument, and defaults
        # to all defined Builders.
        allBuilderNames = status.getBuilderNames(categories=self.categories)
        builders = [status.getBuilder(name) for name in allBuilderNames]

        # but if the URL has one or more builder= arguments (or the old show=
        # argument, which is still accepted for backwards compatibility), we
        # use that set of builders instead. We still don't show anything
        # outside the config-file time set limited by categories=.
        showBuilders = request.args.get("show", [])
        showBuilders.extend(request.args.get("builder", []))
        if showBuilders:
            builders = [b for b in builders if b.name in showBuilders]

        # now, if the URL has one or category= arguments, use them as a
        # filter: only show those builders which belong to one of the given
        # categories.
        showCategories = request.args.get("category", [])
        if showCategories:
            builders = [b for b in builders if b.category in showCategories]

        # If the URL has the failures_only=true argument, we remove all the
        # builders that are not currently red or won't be turning red at the end
        # of their current run.
        failuresOnly = request.args.get("failures_only", ["false"])[0]
        if failuresOnly.lower() == "true":
            builders = [b for b in builders if not self.isSuccess(b)]

        builderNames = [b.name for b in builders]

        if phase == -1:
            return self.body0(request, builders)
        (changeNames, builderNames, timestamps, eventGrid, sourceEvents) = \
                      self.buildGrid(request, builders)
        if phase == 0:
            return self.phase0(request, (changeNames + builderNames),
                               timestamps, eventGrid)
        # start the table: top-header material
        data += '<table border="0" cellspacing="0">\n'

        if projectName and projectURL:
            # TODO: this is going to look really ugly
            topleft = '<a href="%s">%s</a><br />last build' % \
                      (projectURL, projectName)
        else:
            topleft = "last build"
        data += ' <tr class="LastBuild">\n'
        data += td(topleft, align="right", colspan=2, class_="Project")
        for b in builders:
            box = ITopBox(b).getBox(request)
            data += box.td(align="center")
        data += " </tr>\n"

        data += ' <tr class="Activity">\n'
        data += td('current activity', align='right', colspan=2)
        for b in builders:
            box = ICurrentBox(b).getBox(status)
            data += box.td(align="center")
        data += " </tr>\n"
        
        data += " <tr>\n"
        TZ = time.tzname[time.localtime()[-1]]
        data += td("time (%s)" % TZ, align="center", class_="Time")
        data += td('<a href="%s">changes</a>' % request.childLink("../changes"),
                   align="center", class_="Change")
        for name in builderNames:
            safename = urllib.quote(name, safe='')
            data += td('<a href="%s">%s</a>' %
                       (request.childLink("../builders/%s" % safename), name),
                       align="center", class_="Builder")
        data += " </tr>\n"

        if phase == 1:
            f = self.phase1
        else:
            f = self.phase2
        data += f(request, changeNames + builderNames, timestamps, eventGrid,
                  sourceEvents)

        data += "</table>\n"


        def with_args(req, remove_args=[], new_args=[], new_path=None):
            # sigh, nevow makes this sort of manipulation easier
            newargs = req.args.copy()
            for argname in remove_args:
                newargs[argname] = []
            if "branch" in newargs:
                newargs["branch"] = [b for b in newargs["branch"] if b]
            for k,v in new_args:
                if k in newargs:
                    newargs[k].append(v)
                else:
                    newargs[k] = [v]
            newquery = "&".join(["%s=%s" % (urllib.quote(k), urllib.quote(v))
                                 for k in newargs
                                 for v in newargs[k]
                                 ])
            if new_path:
                new_url = new_path
            elif req.prepath:
                new_url = req.prepath[-1]
            else:
                new_url = ''
            if newquery:
                new_url += "?" + newquery
            return new_url

        if timestamps:
            bottom = timestamps[-1]
            nextpage = with_args(request, ["last_time"],
                                 [("last_time", str(int(bottom)))])
            data += '[<a href="%s">next page</a>]\n' % nextpage

        helpurl = self.path_to_root(request) + "waterfall/help"
        helppage = with_args(request, new_path=helpurl)
        data += '[<a href="%s">help</a>]\n' % helppage

        if self.get_reload_time(request) is not None:
            no_reload_page = with_args(request, remove_args=["reload"])
            data += '[<a href="%s">Stop Reloading</a>]\n' % no_reload_page

        data += "<br />\n"
	data += self.footer(status, request)

        return data

    def body0(self, request, builders):
        # build the waterfall display
        data = ""
        data += "<h2>Basic display</h2>\n"
        data += '<p>See <a href="%s">here</a>' % request.childLink("../waterfall")
        data += " for the waterfall display</p>\n"
                
        data += '<table border="0" cellspacing="0">\n'
        names = map(lambda builder: builder.name, builders)

        # the top row is two blank spaces, then the top-level status boxes
        data += " <tr>\n"
        data += td("", colspan=2)
        for b in builders:
            text = ""
            state, builds = b.getState()
            if state != "offline":
                text += "%s<br />\n" % state #b.getCurrentBig().text[0]
            else:
                text += "OFFLINE<br />\n"
            data += td(text, align="center")

        # the next row has the column headers: time, changes, builder names
        data += " <tr>\n"
        data += td("Time", align="center")
        data += td("Changes", align="center")
        for name in names:
            data += td('<a href="%s">%s</a>' %
                       (request.childLink("../" + urllib.quote(name)), name),
                       align="center")
        data += " </tr>\n"

        # all further rows involve timestamps, commit events, and build events
        data += " <tr>\n"
        data += td("04:00", align="bottom")
        data += td("fred", align="center")
        for name in names:
            data += td("stuff", align="center")
        data += " </tr>\n"

        data += "</table>\n"
        return data
    
    def buildGrid(self, request, builders):
        debug = False
        # TODO: see if we can use a cached copy

        showEvents = False
        if request.args.get("show_events", ["false"])[0].lower() == "true":
            showEvents = True
        filterCategories = request.args.get('category', [])
        filterBranches = [b for b in request.args.get("branch", []) if b]
        filterBranches = map_branches(filterBranches)
        maxTime = int(request.args.get("last_time", [util.now()])[0])
        if "show_time" in request.args:
            minTime = maxTime - int(request.args["show_time"][0])
        elif "first_time" in request.args:
            minTime = int(request.args["first_time"][0])
        else:
            minTime = None
        spanLength = 10  # ten-second chunks
        req_events=int(request.args.get("num_events", [self.num_events])[0])
        if self.num_events_max and req_events > self.num_events_max:
            maxPageLen = self.num_events_max
        else:
            maxPageLen = req_events

        # first step is to walk backwards in time, asking each column
        # (commit, all builders) if they have any events there. Build up the
        # array of events, and stop when we have a reasonable number.
            
        commit_source = self.getChangemaster(request)

        lastEventTime = util.now()
        sources = [commit_source] + builders
        changeNames = ["changes"]
        builderNames = map(lambda builder: builder.getName(), builders)
        sourceNames = changeNames + builderNames
        sourceEvents = []
        sourceGenerators = []

        def get_event_from(g):
            try:
                while True:
                    e = g.next()
                    # e might be builder.BuildStepStatus,
                    # builder.BuildStatus, builder.Event,
                    # waterfall.Spacer(builder.Event), or changes.Change .
                    # The showEvents=False flag means we should hide
                    # builder.Event .
                    if not showEvents and isinstance(e, builder.Event):
                        continue
                    break
                event = interfaces.IStatusEvent(e)
                if debug:
                    log.msg("gen %s gave1 %s" % (g, event.getText()))
            except StopIteration:
                event = None
            return event

        for s in sources:
            gen = insertGaps(s.eventGenerator(filterBranches,
                                              filterCategories),
                             showEvents,
                             lastEventTime)
            sourceGenerators.append(gen)
            # get the first event
            sourceEvents.append(get_event_from(gen))
        eventGrid = []
        timestamps = []

        lastEventTime = 0
        for e in sourceEvents:
            if e and e.getTimes()[0] > lastEventTime:
                lastEventTime = e.getTimes()[0]
        if lastEventTime == 0:
            lastEventTime = util.now()

        spanStart = lastEventTime - spanLength
        debugGather = 0

        while 1:
            if debugGather: log.msg("checking (%s,]" % spanStart)
            # the tableau of potential events is in sourceEvents[]. The
            # window crawls backwards, and we examine one source at a time.
            # If the source's top-most event is in the window, is it pushed
            # onto the events[] array and the tableau is refilled. This
            # continues until the tableau event is not in the window (or is
            # missing).

            spanEvents = [] # for all sources, in this span. row of eventGrid
            firstTimestamp = None # timestamp of first event in the span
            lastTimestamp = None # last pre-span event, for next span

            for c in range(len(sourceGenerators)):
                events = [] # for this source, in this span. cell of eventGrid
                event = sourceEvents[c]
                while event and spanStart < event.getTimes()[0]:
                    # to look at windows that don't end with the present,
                    # condition the .append on event.time <= spanFinish
                    if not IBox(event, None):
                        log.msg("BAD EVENT", event, event.getText())
                        assert 0
                    if debug:
                        log.msg("pushing", event.getText(), event)
                    events.append(event)
                    starts, finishes = event.getTimes()
                    firstTimestamp = util.earlier(firstTimestamp, starts)
                    event = get_event_from(sourceGenerators[c])
                if debug:
                    log.msg("finished span")

                if event:
                    # this is the last pre-span event for this source
                    lastTimestamp = util.later(lastTimestamp,
                                               event.getTimes()[0])
                if debugGather:
                    log.msg(" got %s from %s" % (events, sourceNames[c]))
                sourceEvents[c] = event # refill the tableau
                spanEvents.append(events)

            # only show events older than maxTime. This makes it possible to
            # visit a page that shows what it would be like to scroll off the
            # bottom of this one.
            if firstTimestamp is not None and firstTimestamp <= maxTime:
                eventGrid.append(spanEvents)
                timestamps.append(firstTimestamp)

            if lastTimestamp:
                spanStart = lastTimestamp - spanLength
            else:
                # no more events
                break
            if minTime is not None and lastTimestamp < minTime:
                break

            if len(timestamps) > maxPageLen:
                break
            
            
            # now loop
            
        # loop is finished. now we have eventGrid[] and timestamps[]
        if debugGather: log.msg("finished loop")
        assert(len(timestamps) == len(eventGrid))
        return (changeNames, builderNames, timestamps, eventGrid, sourceEvents)
    
    def phase0(self, request, sourceNames, timestamps, eventGrid):
        # phase0 rendering
        if not timestamps:
            return "no events"
        data = ""
        for r in range(0, len(timestamps)):
            data += "<p>\n"
            data += "[%s]<br />" % timestamps[r]
            row = eventGrid[r]
            assert(len(row) == len(sourceNames))
            for c in range(0, len(row)):
                if row[c]:
                    data += "<b>%s</b><br />\n" % sourceNames[c]
                    for e in row[c]:
                        log.msg("Event", r, c, sourceNames[c], e.getText())
                        lognames = [loog.getName() for loog in e.getLogs()]
                        data += "%s: %s: %s<br />" % (e.getText(),
                                                         e.getTimes()[0],
                                                         lognames)
                else:
                    data += "<b>%s</b> [none]<br />\n" % sourceNames[c]
        return data
    
    def phase1(self, request, sourceNames, timestamps, eventGrid,
               sourceEvents):
        # phase1 rendering: table, but boxes do not overlap
        data = ""
        if not timestamps:
            return data
        lastDate = None
        for r in range(0, len(timestamps)):
            chunkstrip = eventGrid[r]
            # chunkstrip is a horizontal strip of event blocks. Each block
            # is a vertical list of events, all for the same source.
            assert(len(chunkstrip) == len(sourceNames))
            maxRows = reduce(lambda x,y: max(x,y),
                             map(lambda x: len(x), chunkstrip))
            for i in range(maxRows):
                data += " <tr>\n";
                if i == 0:
                    stuff = []
                    # add the date at the beginning, and each time it changes
                    today = time.strftime("<b>%d %b %Y</b>",
                                          time.localtime(timestamps[r]))
                    todayday = time.strftime("<b>%a</b>",
                                             time.localtime(timestamps[r]))
                    if today != lastDate:
                        stuff.append(todayday)
                        stuff.append(today)
                        lastDate = today
                    stuff.append(
                        time.strftime("%H:%M:%S",
                                      time.localtime(timestamps[r])))
                    data += td(stuff, valign="bottom", align="center",
                               rowspan=maxRows, class_="Time")
                for c in range(0, len(chunkstrip)):
                    block = chunkstrip[c]
                    assert(block != None) # should be [] instead
                    # bottom-justify
                    offset = maxRows - len(block)
                    if i < offset:
                        data += td("")
                    else:
                        e = block[i-offset]
                        box = IBox(e).getBox(request)
                        box.parms["show_idle"] = 1
                        data += box.td(valign="top", align="center")
                data += " </tr>\n"
        
        return data
    
    def phase2(self, request, sourceNames, timestamps, eventGrid,
               sourceEvents):
        data = ""
        if not timestamps:
            return data
        # first pass: figure out the height of the chunks, populate grid
        grid = []
        for i in range(1+len(sourceNames)):
            grid.append([])
        # grid is a list of columns, one for the timestamps, and one per
        # event source. Each column is exactly the same height. Each element
        # of the list is a single <td> box.
        lastDate = time.strftime("<b>%d %b %Y</b>",
                                 time.localtime(util.now()))
        for r in range(0, len(timestamps)):
            chunkstrip = eventGrid[r]
            # chunkstrip is a horizontal strip of event blocks. Each block
            # is a vertical list of events, all for the same source.
            assert(len(chunkstrip) == len(sourceNames))
            maxRows = reduce(lambda x,y: max(x,y),
                             map(lambda x: len(x), chunkstrip))
            for i in range(maxRows):
                if i != maxRows-1:
                    grid[0].append(None)
                else:
                    # timestamp goes at the bottom of the chunk
                    stuff = []
                    # add the date at the beginning (if it is not the same as
                    # today's date), and each time it changes
                    todayday = time.strftime("<b>%a</b>",
                                             time.localtime(timestamps[r]))
                    today = time.strftime("<b>%d %b %Y</b>",
                                          time.localtime(timestamps[r]))
                    if today != lastDate:
                        stuff.append(todayday)
                        stuff.append(today)
                        lastDate = today
                    stuff.append(
                        time.strftime("%H:%M:%S",
                                      time.localtime(timestamps[r])))
                    grid[0].append(Box(text=stuff, class_="Time",
                                       valign="bottom", align="center"))

            # at this point the timestamp column has been populated with
            # maxRows boxes, most None but the last one has the time string
            for c in range(0, len(chunkstrip)):
                block = chunkstrip[c]
                assert(block != None) # should be [] instead
                for i in range(maxRows - len(block)):
                    # fill top of chunk with blank space
                    grid[c+1].append(None)
                for i in range(len(block)):
                    # so the events are bottom-justified
                    b = IBox(block[i]).getBox(request)
                    b.parms['valign'] = "top"
                    b.parms['align'] = "center"
                    grid[c+1].append(b)
            # now all the other columns have maxRows new boxes too
        # populate the last row, if empty
        gridlen = len(grid[0])
        for i in range(len(grid)):
            strip = grid[i]
            assert(len(strip) == gridlen)
            if strip[-1] == None:
                if sourceEvents[i-1]:
                    filler = IBox(sourceEvents[i-1]).getBox(request)
                else:
                    # this can happen if you delete part of the build history
                    filler = Box(text=["?"], align="center")
                strip[-1] = filler
            strip[-1].parms['rowspan'] = 1
        # second pass: bubble the events upwards to un-occupied locations
        # Every square of the grid that has a None in it needs to have
        # something else take its place.
        noBubble = request.args.get("nobubble",['0'])
        noBubble = int(noBubble[0])
        if not noBubble:
            for col in range(len(grid)):
                strip = grid[col]
                if col == 1: # changes are handled differently
                    for i in range(2, len(strip)+1):
                        # only merge empty boxes. Don't bubble commit boxes.
                        if strip[-i] == None:
                            next = strip[-i+1]
                            assert(next)
                            if next:
                                #if not next.event:
                                if next.spacer:
                                    # bubble the empty box up
                                    strip[-i] = next
                                    strip[-i].parms['rowspan'] += 1
                                    strip[-i+1] = None
                                else:
                                    # we are above a commit box. Leave it
                                    # be, and turn the current box into an
                                    # empty one
                                    strip[-i] = Box([], rowspan=1,
                                                    comment="commit bubble")
                                    strip[-i].spacer = True
                            else:
                                # we are above another empty box, which
                                # somehow wasn't already converted.
                                # Shouldn't happen
                                pass
                else:
                    for i in range(2, len(strip)+1):
                        # strip[-i] will go from next-to-last back to first
                        if strip[-i] == None:
                            # bubble previous item up
                            assert(strip[-i+1] != None)
                            strip[-i] = strip[-i+1]
                            strip[-i].parms['rowspan'] += 1
                            strip[-i+1] = None
                        else:
                            strip[-i].parms['rowspan'] = 1
        # third pass: render the HTML table
        for i in range(gridlen):
            data += " <tr>\n";
            for strip in grid:
                b = strip[i]
                if b:
                    # convert data to a unicode string, whacking any non-ASCII characters it might contain
                    s = b.td()
                    if isinstance(s, unicode):
                        s = s.encode("utf-8", "replace")
                    data += s
                else:
                    if noBubble:
                        data += td([])
                # Nones are left empty, rowspan should make it all fit
            data += " </tr>\n"
        return data

