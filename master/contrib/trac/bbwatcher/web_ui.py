import re

import pkg_resources

from api import BuildBotSystem
from genshi.builder import tag
from trac.config import Option
from trac.core import Component
from trac.core import implements
from trac.mimeview.api import Context
# Interfaces
from trac.timeline.api import ITimelineEventProvider
from trac.util.datefmt import to_datetime
from trac.util.datefmt import to_timestamp
from trac.web import IRequestHandler
from trac.web.chrome import INavigationContributor
from trac.web.chrome import ITemplateProvider
from trac.wiki.formatter import format_to_oneliner


class TracBuildBotWatcher(Component):
    implements(ITimelineEventProvider, IRequestHandler, ITemplateProvider,
               INavigationContributor)
    buildbot_url = Option('bbwatcher', 'buildmaster', '127.0.0.1:8010',
                          'The location of the BuildBot webserver. Do not include the /xmlrpc')

    BUILDER_REGEX = r'/buildbot/builder(?:/(.+))?$'
    BUILDER_RE = re.compile(BUILDER_REGEX)
    # Template Provider

    def get_htdocs_dirs(self):
        return []

    def get_templates_dirs(self):
        return [pkg_resources.resource_filename('bbwatcher', 'templates')]

    # Nav Contributor
    def get_active_navigation_item(self, req):
        return 'buildbot'

    def get_navigation_items(self, req):
        yield 'mainnav', 'buildbot', tag.a('BuildBot', href=req.href.buildbot())

    # Timeline Methods
    def get_timeline_filters(self, req):
        yield ('bbwatcher', 'Builds', False)

    def get_timeline_events(self, req, start, stop, filters):
        try:
            master = BuildBotSystem(self.buildbot_url)
        except Exception as e:
            print 'Error hitting BuildBot', e
            return
        # This was a comprehension: the loop is clearer
        for build in master.getAllBuildsInInterval(to_timestamp(start), to_timestamp(stop)):
            # BuildBot builds are reported as
            # (builder_name, num, end, branch, rev, results, text)
            print 'Reporting build', build
            yield ('build', to_datetime(build[2]), '', build)

    def render_timeline_event(self, context, field, event):
        builder_name, num, end, branch, rev, results, text = event[3]
        if field == 'url':
            return None
        elif field == 'title':
            return tag('Build ', tag.a('#%s' % num, href=context.href.buildbot('builder/%s/%s' % (builder_name, num))),
                       ' of ', builder_name, ' ', results == 'success' and tag.span('passed', style="color: #080") or tag.span('failed', style="color: #f00"))
        elif field == 'description':
            return format_to_oneliner(self.env, context, 'Built from %s' % (rev and 'r%s sources' % rev or 'local changes (see TryBuildUsage)'))

    # RequestHandler
    def _handle_builder(self, req):
        m = self.BUILDER_RE.match(req.path_info)
        try:
            builder = m.group(1) or None
        except Exception as e:
            builder = None
        master = BuildBotSystem(self.buildbot_url)
        if builder is None:
            data = {'names': master.getAllBuilders()}
            return 'bbw_allbuilders.html', data, 'text/html'
        else:
            class Foo:
                pass
            b = Foo()
            b.name = str(builder)
            b.current = 'CURRENT-TEXT'
            b.recent = []
            b.slaves = []
            data = {'builder': b}
            try:
                master = BuildBotSystem(self.buildbot_url)
                data = {'builder': master.getBuilder(builder)}
            except Exception as e:
                print 'Error fetching builder stats', e
            data['context'] = Context.from_request(req, ('buildbot', builder))
            return 'bbw_builder.html', data, 'text/html'

    def match_request(self, req):
        return req.path_info.startswith('/buildbot') and 1 or 0

    def process_request(self, req):
        if req.path_info.startswith('/buildbot/builder'):
            return self._handle_builder(req)
        return 'bbw_welcome.html', {'url': self.buildbot_url}, 'text/html'
