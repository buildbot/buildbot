# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members


from zope.interface import implements
from twisted.python import components
from twisted.spread import pb
from twisted.web import server
from twisted.web.resource import Resource
from twisted.web.error import NoResource

from buildbot import interfaces
from buildbot.status import logfile
from buildbot.status.web.base import IHTMLLog, HtmlResource, path_to_root

class ChunkConsumer:
    implements(interfaces.IStatusLogConsumer)

    def __init__(self, original, textlog):
        self.original = original
        self.textlog = textlog
    def registerProducer(self, producer, streaming):
        self.producer = producer
        self.original.registerProducer(producer, streaming)
    def unregisterProducer(self):
        self.original.unregisterProducer()
    def writeChunk(self, chunk):
        formatted = self.textlog.content([chunk])
        try:
            if isinstance(formatted, unicode):
                formatted = formatted.encode('utf-8')
            self.original.write(formatted)
        except pb.DeadReferenceError:
            self.producing.stopProducing()
    def finish(self):
        self.textlog.finished()


# /builders/$builder/builds/$buildnum/steps/$stepname/logs/$logname
class TextLog(Resource):
    # a new instance of this Resource is created for each client who views
    # it, so we can afford to track the request in the Resource.
    implements(IHTMLLog)

    asText = False
    subscribed = False

    def __init__(self, original):
        Resource.__init__(self)
        self.original = original

    def getChild(self, path, req):
        if path == "text":
            self.asText = True
            return self
        return Resource.getChild(self, path, req)

    def content(self, entries):
        html_entries = []
        text_data = ''
        for type, entry in entries:
            if type >= len(logfile.ChunkTypes) or type < 0:
                # non-std channel, don't display
                continue
            
            is_header = type == logfile.HEADER

            if not self.asText:
                # jinja only works with unicode, or pure ascii, so assume utf-8 in logs
                if not isinstance(entry, unicode):
                    entry = unicode(entry, 'utf-8', 'replace')
                html_entries.append(dict(type = logfile.ChunkTypes[type], 
                                         text = entry,
                                         is_header = is_header))
            elif not is_header:
                text_data += entry

        if self.asText:
            return text_data
        else:
            return self.template.module.chunks(html_entries)

    def render_HEAD(self, req):
        self._setContentType(req)

        # vague approximation, ignores markup
        req.setHeader("content-length", self.original.length)
        return ''

    def render_GET(self, req):
        self._setContentType(req)
        self.req = req

        if not self.asText:
            self.template = req.site.buildbot_service.templates.get_template("logs.html")                
            
            data = self.template.module.page_header(
                    pageTitle = "Log File contents",
                    texturl = req.childLink("text"),
                    path_to_root = path_to_root(req))
            data = data.encode('utf-8')                   
            req.write(data)

        self.original.subscribeConsumer(ChunkConsumer(req, self))
        return server.NOT_DONE_YET

    def _setContentType(self, req):
        if self.asText:
            req.setHeader("content-type", "text/plain; charset=utf-8")
        else:
            req.setHeader("content-type", "text/html; charset=utf-8")
        
    def finished(self):
        if not self.req:
            return
        try:
            if not self.asText:
                data = self.template.module.page_footer()
                data = data.encode('utf-8')
                self.req.write(data)
            self.req.finish()
        except pb.DeadReferenceError:
            pass
        # break the cycle, the Request's .notifications list includes the
        # Deferred (from req.notifyFinish) that's pointing at us.
        self.req = None
        
        # release template
        self.template = None

components.registerAdapter(TextLog, interfaces.IStatusLog, IHTMLLog)


class HTMLLog(Resource):
    implements(IHTMLLog)

    def __init__(self, original):
        Resource.__init__(self)
        self.original = original

    def render(self, request):
        request.setHeader("content-type", "text/html")
        return self.original.html

components.registerAdapter(HTMLLog, logfile.HTMLLogFile, IHTMLLog)


class LogsResource(HtmlResource):
    addSlash = True

    def __init__(self, step_status):
        HtmlResource.__init__(self)
        self.step_status = step_status

    def getChild(self, path, req):
        for log in self.step_status.getLogs():
            if path == log.getName():
                if log.hasContents():
                    return IHTMLLog(interfaces.IStatusLog(log))
                return NoResource("Empty Log '%s'" % path)
        return HtmlResource.getChild(self, path, req)
