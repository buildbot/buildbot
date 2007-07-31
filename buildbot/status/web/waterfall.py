# -*- test-case-name: buildbot.test.test_web -*-

from zope.interface import implements
from twisted.python import log, components
from twisted.web import html
import urllib

import time

from buildbot import interfaces, util
from buildbot import version
from buildbot.status import builder

from buildbot.status.web.base import Box, HtmlResource, IBox, ICurrentBox, \
     ITopBox, td, build_get_class



class CurrentBox(components.Adapter):
    # this provides the "current activity" box, just above the builder name
    implements(ICurrentBox)

    def formatETA(self, eta):
        if eta is None:
            return []
        if eta < 0:
            return ["Soon"]
        abstime = time.strftime("%H:%M:%S", time.localtime(util.now()+eta))
        return ["ETA in", "%d secs" % eta, "at %s" % abstime]

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
            color = "yellow"
            text = ["building"]
            if builds:
                for b in builds:
                    eta = b.getETA()
                    if eta:
                        text.extend(self.formatETA(eta))
        elif state == "offline":
            color = "red"
            text = ["offline"]
        elif state == "idle":
            color = "white"
            text = ["idle"]
        elif state == "waiting":
            color = "yellow"
            text = ["waiting"]
        else:
            # just in case I add a state and forget to update this
            color = "white"
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
            text.extend(["next at", 
                         time.strftime("%H:%M:%S", time.localtime(t)),
                         "[%d secs]" % (t - util.now()),
                         ])
            # TODO: the upcoming-builds box looks like:
            #  ['waiting', 'next at', '22:14:15', '[86 secs]']
            # while the currently-building box is reversed:
            #  ['building', 'ETA in', '2 secs', 'at 22:12:50']
            # consider swapping one of these to make them look the same. also
            # consider leaving them reversed to make them look different.
        return Box(text, color=color, class_="Activity " + state)

components.registerAdapter(CurrentBox, builder.BuilderStatus, ICurrentBox)


class BuildTopBox(components.Adapter):
    # this provides a per-builder box at the very top of the display,
    # showing the results of the most recent build
    implements(IBox)

    def getBox(self):
        assert interfaces.IBuilderStatus(self.original)
        b = self.original.getLastFinishedBuild()
        if not b:
            return Box(["none"], "white", class_="LastBuild")
        name = b.getBuilder().getName()
        number = b.getNumber()
        url = "%s/builds/%d" % (name, number)
        text = b.getText()
        # TODO: add logs?
        # TODO: add link to the per-build page at 'url'
        c = b.getColor()
        class_ = build_get_class(b)
        return Box(text, c, class_="LastBuild %s" % class_)
components.registerAdapter(BuildTopBox, builder.BuilderStatus, ITopBox)

class BuildBox(components.Adapter):
    # this provides the yellow "starting line" box for each build
    implements(IBox)

    def getBox(self):
        b = self.original
        name = b.getBuilder().getName()
        number = b.getNumber()
        url = "builders/%s/builds/%d" % (urllib.quote(name, safe=''), number)
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

class StepBox(components.Adapter):
    implements(IBox)

    def getBox(self):
        b = self.original.getBuild()
        urlbase = "builders/%s/builds/%d/steps/%s" % (
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
                url = urlbase + "/logs/%s" % urllib.quote(name)
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

    def getChangemaster(self, request):
        # TODO: this wants to go away, access it through IStatus
        return request.site.buildbot_service.parent.change_svc

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
            safename = urllib.quote(name, safe='')
            data += td( "<a href=\"builders/%s\">%s</a>" % (safename, name),
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

        showEvents = False
        if request.args.get("show_events", ["false"])[0].lower() == "true":
            showEvents = True

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
            gen = insertGaps(s.eventGenerator(), lastEventTime)
            sourceGenerators.append(gen)
            # get the first event
            sourceEvents.append(get_event_from(gen))
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

