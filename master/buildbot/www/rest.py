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

import datetime
import re
from twisted.internet import defer
from twisted.python import log
from twisted.web import server
from buildbot.www import resource
from buildbot.data import base, exceptions as data_exceptions
from buildbot.util import json
from buildbot.status.web.status_json import JsonStatusResource

class RestRootResource(resource.Resource):
    version_classes = {}

    @classmethod
    def addApiVersion(cls, version, version_cls):
        cls.version_classes[version] = version_cls
        version_cls.apiVersion = version

    def __init__(self, master):
        resource.Resource.__init__(self, master)

        min_vers = master.config.www.get('rest_minimum_version', 0)
        for version, klass in self.version_classes.iteritems():
            if version >= min_vers:
                self.putChild('v%d' % version, klass(master))

        latest = max(self.version_classes.iterkeys())
        self.putChild('latest', self.version_classes[latest](master))

    def render(self, request):
        request.setHeader("content-type", 'application/json')
        min_vers = self.master.config.www.get('rest_minimum_version', 0)
        api_versions = dict( ('v%d' % v, '%sapi/v%d' % (self.base_url, v))
                             for v in self.version_classes
                             if v > min_vers)
        return json.dumps(dict(api_versions=api_versions))

# API version 1 was the 0.8.x status_json.py API

class V1RootResource(JsonStatusResource):
    def __init__(self, master):
        self.master = master
        JsonStatusResource.__init__(self,master.status)

class V2RootResource(resource.Resource):
    # rather than construct the entire possible hierarchy of Rest resources,
    # this is marked as a leaf node, and any remaining path items are parsed
    # during rendering
    isLeaf = True

    knownArgs = set(['as_text', 'filter', 'compact', 'callback'])

    def render(self, request):
        @defer.inlineCallbacks
        def render():
            reqPath = request.postpath
            # strip an empty string from the end (trailing slash)
            if reqPath and reqPath[-1] == '':
                reqPath = reqPath[:-1]

            # calculate the request options
            reqOptions = {}
            for option in set(request.args) - self.knownArgs:
                reqOptions[option] = request.args[option][0]

            def write_error(msg):
                request.setResponseCode(404)
                # prefer text/plain here, since this is most likely user error
                request.setHeader('content-type', 'text/plain')
                request.write(json.dumps(dict(error=msg)))

            # get the value
            try:
                data = yield self.master.data.get(reqOptions, tuple(reqPath))
            except data_exceptions.InvalidPathError:
                write_error("invalid path")
                return
            except data_exceptions.InvalidOptionException:
                write_error("invalid option")
                return

            if data is None:
                write_error("no data")
                return

            # format the output based on request parameters
            as_text = self._booleanArg(request, 'as_text', False)
            filter = self._booleanArg(request, 'filter', as_text)
            compact = self._booleanArg(request, 'compact', not as_text)
            callback = request.args.get('callback', [None])[0]

            # set up the content type
            if as_text:
                request.setHeader("content-type", 'text/plain')
            else:
                request.setHeader("content-type", 'application/json')
                request.setHeader("content-disposition",
                            "attachment; filename=\"%s.json\"" % request.path)

            # set up caching
            cache_seconds = self.master.config.www.get('json_cache_seconds', 0)
            if cache_seconds:
                now = datetime.datetime.utcnow()
                expires = now + datetime.timedelta(seconds=cache_seconds)
                request.setHeader("Expires",
                                expires.strftime("%a, %d %b %Y %H:%M:%S GMT"))
                request.setHeader("Pragma", "no-cache")

            # filter and render the data
            if filter:
                data = self._filterEmpty(data)

            if compact:
                data = json.dumps(data, default=self._render_links,
                                        sort_keys=True, separators=(',',':'))
            else:
                data = json.dumps(data, default=self._render_links,
                                        sort_keys=True, indent=2)

            if isinstance(data, unicode):
                data = data.encode("utf-8")

            if callback:
                # Only accept things that look like identifiers for now
                if re.match(r'^[a-zA-Z$][a-zA-Z$0-9.]*$', callback):
                    data = '%s(%s);' % (callback, data)
                request.setHeader("Access-Control-Allow-Origin", "*")

            if isinstance(data, unicode):
                data = data.encode("utf-8")
            if request.method == "HEAD":
                request.setHeader("content-length", len(data))
                request.write('')
            else:
                request.write(data)

        d = render()
        @d.addCallback
        def finish(_):
            try:
                request.finish()
            except RuntimeError:
                # this occurs when the client has already disconnected; ignore
                # it (see #2027)
                log.msg("http client disconnected before results were sent")

        @d.addErrback
        def fail(f):
            log.err(f, 'ugh')
            request.processingFailed(f)
            return None
        return server.NOT_DONE_YET

        @d.addErrback
        def eb(f):
            request.processingFailed(f)
            return None

    def _booleanArg(self, request, arg, default):
        value = request.args.get(arg, [default])[0]
        if value in (False, True):
            return value
        value = value.lower()
        if value in ('1', 'true'):
            return True
        if value in ('0', 'false'):
            return False
        # Ignore value.
        return default

    def _filterEmpty(self, data):
        empty = ('', False, None, [], {}, ())
        if isinstance(data, (list, tuple)):
            filtered = (self._filterEmpty(x) for x in data)
            return [ x for x in filtered if x not in empty ]
        elif isinstance(data, dict):
            filtered = ((k, self._filterEmpty(v))
                        for (k, v) in data.iteritems())
            return dict(x for x in filtered if x[1] not in empty)
        else:
            return data

    def _render_links(self, obj):
        if isinstance(obj, base.Link):
            return "%sapi/v%d/%s" % (self.base_url, self.apiVersion,
                                    '/'.join(obj.path))

RestRootResource.addApiVersion(1, V1RootResource)
RestRootResource.addApiVersion(2, V2RootResource)
