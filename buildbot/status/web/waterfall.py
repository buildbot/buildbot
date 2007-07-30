# -*- test-case-name: buildbot.test.test_web -*-

from __future__ import generators

from twisted.python import log, components
import urllib, re

from twisted.internet import defer, reactor
from twisted.web.resource import Resource
from twisted.web import static, html, server, distrib
from twisted.web.error import NoResource
from twisted.web.util import Redirect, DeferredResource
from twisted.application import strports
from twisted.spread import pb
from zope.interface import Interface, implements

import sys, string, types, time, os.path

from buildbot import interfaces, util
from buildbot import version
from buildbot.sourcestamp import SourceStamp
from buildbot.status import builder, base
from buildbot.changes import changes
from buildbot.process.base import BuildRequest

from buildbot.status.web.changes import StatusResourceChanges
from buildbot.status.web.builder import StatusResourceBuilder
from buildbot.status.web.build import StatusResourceBuild
from buildbot.status.web.step import StatusResourceBuildStep



class EventBox(components.Adapter):
    implements(IBox)

    def getBox(self):
        text = self.original.getText()
        color = self.original.getColor()
        class_ = "Event"
        if color:
            class_ += " " + color
        return Box(text, color, class_=class_)
components.registerAdapter(EventBox, builder.Event, IBox)
        

class Spacer(builder.Event):
    def __init__(self, start, finish):
        self.started = start
        self.finished = finish

class SpacerBox(components.Adapter):
    implements(IBox)

    def getBox(self):
        #b = Box(["spacer"], "white")
        b = Box([])
        b.spacer = True
        return b
components.registerAdapter(SpacerBox, Spacer, IBox)
    
def insertGaps(g, lastEventTime, idleGap=2):
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


class WaterfallStatusResource(HtmlResource):
    """This builds the main status page, with the waterfall display, and
    all child pages."""

    def __init__(self, categories=None, css=None):
        HtmlResource.__init__(self)
        self.categories = categories
        self.css = css

    def getTitle(self, request):
        status = self.getStatus(request)
        p = status.getProjectName()
        if p:
            return "BuildBot: %s" % p
        else:
            return "BuildBot"

    def getStatus(self, request):
        return self.status
    def getControl(self, request):
        return self.control
    def getChangemaster(self, request):
        return self.changemaster

    def body(self, request):
        "This method builds the main waterfall display."

        status = self.getStatus(request)
        data = ''

        projectName = status.getProjectName()
        projectURL = status.getProjectURL()

        phase = request.args.get("phase",["2"])
        phase = int(phase[0])

        showBuilders = request.args.get("show", None)
        allBuilders = status.getBuilderNames(categories=self.categories)
        if showBuilders:
            builderNames = []
            for b in showBuilders:
                if b not in allBuilders:
                    continue
                if b in builderNames:
                    continue
                builderNames.append(b)
        else:
            builderNames = allBuilders
        builders = map(lambda name: status.getBuilder(name),
                       builderNames)

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
            topleft = "<a href=\"%s\">%s</a><br />last build" % \
                      (projectURL, projectName)
        else:
            topleft = "last build"
        data += ' <tr class="LastBuild">\n'
        data += td(topleft, align="right", colspan=2, class_="Project")
        for b in builders:
            box = ITopBox(b).getBox()
            data += box.td(align="center")
        data += " </tr>\n"

        data += ' <tr class="Activity">\n'
        data += td('current activity', align='right', colspan=2)
        for b in builders:
            box = ICurrentBox(b).getBox(status)
            data += box.td(align="center")
        data += " </tr>\n"
        
        data += " <tr>\n"
        TZ = time.tzname[time.daylight]
        data += td("time (%s)" % TZ, align="center", class_="Time")
        name = changeNames[0]
        data += td(
                "<a href=\"%s\">%s</a>" % (urllib.quote(name, safe=''), name),
                align="center", class_="Change")
        for name in builderNames:
            data += td(
                #"<a href=\"%s\">%s</a>" % (request.childLink(name), name),
                "<a href=\"%s\">%s</a>" % (urllib.quote(name, safe=''), name),
                align="center", class_="Builder")
        data += " </tr>\n"

        if phase == 1:
            f = self.phase1
        else:
            f = self.phase2
        data += f(request, changeNames + builderNames, timestamps, eventGrid,
                  sourceEvents)

        data += "</table>\n"

        data += "<hr />\n"

        bburl = "http://buildbot.net/?bb-ver=%s" % urllib.quote(version)
        data += "<a href=\"%s\">Buildbot-%s</a> " % (bburl, version)
        if projectName:
            data += "working for the "
            if projectURL:
                data += "<a href=\"%s\">%s</a> project." % (projectURL,
                                                            projectName)
            else:
                data += "%s project." % projectName
        data += "<br />\n"
        # TODO: push this to the right edge, if possible
        data += ("Page built: " +
                 time.strftime("%a %d %b %Y %H:%M:%S",
                               time.localtime(util.now()))
                 + "\n")
        return data

    def body0(self, request, builders):
        # build the waterfall display
        data = ""
        data += "<h2>Basic display</h2>\n"
        data += "<p>See <a href=\"%s\">here</a>" % \
                urllib.quote(request.childLink("waterfall"))
        data += " for the waterfall display</p>\n"
                
        data += '<table border="0" cellspacing="0">\n'
        names = map(lambda builder: builder.name, builders)

        # the top row is two blank spaces, then the top-level status boxes
        data += " <tr>\n"
        data += td("", colspan=2)
        for b in builders:
            text = ""
            color = "#ca88f7"
            state, builds = b.getState()
            if state != "offline":
                text += "%s<br />\n" % state #b.getCurrentBig().text[0]
            else:
                text += "OFFLINE<br />\n"
                color = "#ffe0e0"
            data += td(text, align="center", bgcolor=color)

        # the next row has the column headers: time, changes, builder names
        data += " <tr>\n"
        data += td("Time", align="center")
        data += td("Changes", align="center")
        for name in names:
            data += td(
                "<a href=\"%s\">%s</a>" % (urllib.quote(request.childLink(name)), name),
                align="center")
        data += " </tr>\n"

        # all further rows involve timestamps, commit events, and build events
        data += " <tr>\n"
        data += td("04:00", align="bottom")
        data += td("fred", align="center")
        for name in names:
            data += td("stuff", align="center", bgcolor="red")
        data += " </tr>\n"

        data += "</table>\n"
        return data
    
    def buildGrid(self, request, builders):
        debug = False

        # XXX: see if we can use a cached copy

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
        for s in sources:
            gen = insertGaps(s.eventGenerator(), lastEventTime)
            sourceGenerators.append(gen)
            # get the first event
            try:
                e = gen.next()
                event = interfaces.IStatusEvent(e)
                if debug:
                    log.msg("gen %s gave1 %s" % (gen, event.getText()))
            except StopIteration:
                event = None
            sourceEvents.append(event)
        eventGrid = []
        timestamps = []
        spanLength = 10  # ten-second chunks
        tooOld = util.now() - 12*60*60 # never show more than 12 hours
        maxPageLen = 200

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
                    try:
                        event = sourceGenerators[c].next()
                        #event = interfaces.IStatusEvent(event)
                        if debug:
                            log.msg("gen[%s] gave2 %s" % (sourceNames[c],
                                                          event.getText()))
                    except StopIteration:
                        event = None
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

            if firstTimestamp is not None:
                eventGrid.append(spanEvents)
                timestamps.append(firstTimestamp)
            

            if lastTimestamp:
                spanStart = lastTimestamp - spanLength
            else:
                # no more events
                break
            if lastTimestamp < tooOld:
                pass
                #break
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
                        data += "%s: %s: %s %s<br />" % (e.getText(),
                                                         e.getTimes()[0],
                                                         e.getColor(),
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
                        box = IBox(e).getBox()
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
                    b = IBox(block[i]).getBox()
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
                    filler = IBox(sourceEvents[i-1]).getBox()
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
                    data += b.td()
                else:
                    if noBubble:
                        data += td([])
                # Nones are left empty, rowspan should make it all fit
            data += " </tr>\n"
        return data


class StatusResource(Resource):
    status = None
    control = None
    favicon = None
    robots_txt = None

    def __init__(self, status, control, changemaster, categories, css):
        """
        @type  status:       L{buildbot.status.builder.Status}
        @type  control:      L{buildbot.master.Control}
        @type  changemaster: L{buildbot.changes.changes.ChangeMaster}
        """
        Resource.__init__(self)
        self.status = status
        self.control = control
        self.changemaster = changemaster
        self.css = css
        waterfall = WaterfallStatusResource(categories, css)
        waterfall.status = self.status
        waterfall.control = control
        waterfall.changemaster = changemaster
        self.putChild("", waterfall)

    def render(self, request):
        request.redirect(request.prePathURL() + '/')
        request.finish()

    def getChild(self, path, request):
        if path == "robots.txt" and self.robots_txt:
            return static.File(self.robots_txt)
        if path == "buildbot.css" and self.css:
            return static.File(self.css)
        if path == "changes":
            return StatusResourceChanges(self.status, self.changemaster)
        if path == "favicon.ico":
            if self.favicon:
                return static.File(self.favicon)
            return NoResource("No favicon.ico registered")

        if path in self.status.getBuilderNames():
            builder = self.status.getBuilder(path)
            control = None
            if self.control:
                control = self.control.getBuilder(path)
            return StatusResourceBuilder(self.status, builder, control)

        return NoResource("No such Builder '%s'" % path)

if hasattr(sys, "frozen"):
    # all 'data' files are in the directory of our executable
    here = os.path.dirname(sys.executable)
    buildbot_icon = os.path.abspath(os.path.join(here, "buildbot.png"))
    buildbot_css = os.path.abspath(os.path.join(here, "classic.css"))
else:
    # running from source
    # the icon is sibpath(__file__, "../buildbot.png") . This is for
    # portability.
    up = os.path.dirname
    buildbot_icon = os.path.abspath(os.path.join(up(up(up(__file__))),
                                                 "buildbot.png"))
    buildbot_css = os.path.abspath(os.path.join(up(__file__), "classic.css"))

class Waterfall(base.StatusReceiverMultiService):
    """I implement the primary web-page status interface, called a 'Waterfall
    Display' because builds and steps are presented in a grid of boxes which
    move downwards over time. The top edge is always the present. Each column
    represents a single builder. Each box describes a single Step, which may
    have logfiles or other status information.

    All these pages are served via a web server of some sort. The simplest
    approach is to let the buildmaster run its own webserver, on a given TCP
    port, but it can also publish its pages to a L{twisted.web.distrib}
    distributed web server (which lets the buildbot pages be a subset of some
    other web server).

    Since 0.6.3, BuildBot defines class attributes on elements so they can be
    styled with CSS stylesheets. Buildbot uses some generic classes to
    identify the type of object, and some more specific classes for the
    various kinds of those types. It does this by specifying both in the
    class attributes where applicable, separated by a space. It is important
    that in your CSS you declare the more generic class styles above the more
    specific ones. For example, first define a style for .Event, and below
    that for .SUCCESS

    The following CSS class names are used:
        - Activity, Event, BuildStep, LastBuild: general classes
        - waiting, interlocked, building, offline, idle: Activity states
        - start, running, success, failure, warnings, skipped, exception:
          LastBuild and BuildStep states
        - Change: box with change
        - Builder: box for builder name (at top)
        - Project
        - Time

    @type parent: L{buildbot.master.BuildMaster}
    @ivar parent: like all status plugins, this object is a child of the
                  BuildMaster, so C{.parent} points to a
                  L{buildbot.master.BuildMaster} instance, through which
                  the status-reporting object is acquired.
    """

    compare_attrs = ["http_port", "distrib_port", "allowForce",
                     "categories", "css", "favicon", "robots_txt"]

    def __init__(self, http_port=None, distrib_port=None, allowForce=True,
                 categories=None, css=buildbot_css, favicon=buildbot_icon,
                 robots_txt=None):
        """To have the buildbot run its own web server, pass a port number to
        C{http_port}. To have it run a web.distrib server

        @type  http_port: int or L{twisted.application.strports} string
        @param http_port: a strports specification describing which port the
                          buildbot should use for its web server, with the
                          Waterfall display as the root page. For backwards
                          compatibility this can also be an int. Use
                          'tcp:8000' to listen on that port, or
                          'tcp:12345:interface=127.0.0.1' if you only want
                          local processes to connect to it (perhaps because
                          you are using an HTTP reverse proxy to make the
                          buildbot available to the outside world, and do not
                          want to make the raw port visible).

        @type  distrib_port: int or L{twisted.application.strports} string
        @param distrib_port: Use this if you want to publish the Waterfall
                             page using web.distrib instead. The most common
                             case is to provide a string that is an absolute
                             pathname to the unix socket on which the
                             publisher should listen
                             (C{os.path.expanduser(~/.twistd-web-pb)} will
                             match the default settings of a standard
                             twisted.web 'personal web server'). Another
                             possibility is to pass an integer, which means
                             the publisher should listen on a TCP socket,
                             allowing the web server to be on a different
                             machine entirely. Both forms are provided for
                             backwards compatibility; the preferred form is a
                             strports specification like
                             'unix:/home/buildbot/.twistd-web-pb'. Providing
                             a non-absolute pathname will probably confuse
                             the strports parser.

        @type  allowForce: bool
        @param allowForce: if True, present a 'Force Build' button on the
                           per-Builder page that allows visitors to the web
                           site to initiate a build. If False, don't provide
                           this button.

        @type  favicon: string
        @param favicon: if set, provide the pathname of an image file that
                        will be used for the 'favicon.ico' resource. Many
                        browsers automatically request this file and use it
                        as an icon in any bookmark generated from this site.
                        Defaults to the buildbot/buildbot.png image provided
                        in the distribution. Can be set to None to avoid
                        using a favicon at all.

        @type  robots_txt: string
        @param robots_txt: if set, provide the pathname of a robots.txt file.
                           Many search engines request this file and obey the
                           rules in it. E.g. to disallow them to crawl the
                           status page, put the following two lines in
                           robots.txt::
                              User-agent: *
                              Disallow: /
        """

        base.StatusReceiverMultiService.__init__(self)
        assert allowForce in (True, False) # TODO: implement others
        if type(http_port) is int:
            http_port = "tcp:%d" % http_port
        self.http_port = http_port
        if distrib_port is not None:
            if type(distrib_port) is int:
                distrib_port = "tcp:%d" % distrib_port
            if distrib_port[0] in "/~.": # pathnames
                distrib_port = "unix:%s" % distrib_port
        self.distrib_port = distrib_port
        self.allowForce = allowForce
        self.categories = categories
        self.css = css
        self.favicon = favicon
        self.robots_txt = robots_txt

    def __repr__(self):
        if self.http_port is None:
            return "<Waterfall on path %s>" % self.distrib_port
        if self.distrib_port is None:
            return "<Waterfall on port %s>" % self.http_port
        return "<Waterfall on port %s and path %s>" % (self.http_port,
                                                       self.distrib_port)

    def setServiceParent(self, parent):
        """
        @type  parent: L{buildbot.master.BuildMaster}
        """
        base.StatusReceiverMultiService.setServiceParent(self, parent)
        self.setup()

    def setup(self):
        status = self.parent.getStatus()
        if self.allowForce:
            control = interfaces.IControl(self.parent)
        else:
            control = None
        change_svc = self.parent.change_svc
        sr = StatusResource(status, control, change_svc, self.categories,
                            self.css)
        sr.favicon = self.favicon
        sr.robots_txt = self.robots_txt
        self.site = server.Site(sr)

        if self.http_port is not None:
            s = strports.service(self.http_port, self.site)
            s.setServiceParent(self)
        if self.distrib_port is not None:
            f = pb.PBServerFactory(distrib.ResourcePublisher(self.site))
            s = strports.service(self.distrib_port, f)
            s.setServiceParent(self)
