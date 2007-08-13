
from twisted.web import html
from buildbot.status.web.base import HtmlResource
import buildbot
import twisted
import sys

class AboutBuildbot(HtmlResource):
    title = "About this Buildbot"

    def body(self, request):
        data = ''
        data += '<h1>Welcome to the Buildbot</h1>\n'
        data += '<h2>Version Information</h2>\n'
        data += '<ul>\n'
        data += ' <li>Buildbot: %s</li>\n' % html.escape(buildbot.version)
        data += ' <li>Twisted: %s</li>\n' % html.escape(twisted.__version__)
        data += ' <li>Python: %s</li>\n' % html.escape(sys.version)
        data += ' <li>Buildmaster platform: %s</li>\n' % html.escape(sys.platform)
        data += '</ul>\n'

        data += '''
<h2>Source code</h2>

<p>Buildbot is a free software project, released under the terms of the
<a href="http://www.gnu.org/licenses/gpl.html">GNU GPL</a>.</p>

<p>Please visit the <a href="http://buildbot.net/">Buildbot Home Page</a> for
more information, including documentation, bug reports, and source
downloads.</p>
'''
        return data

