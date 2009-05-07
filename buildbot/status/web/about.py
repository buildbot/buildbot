
from buildbot.status.web.base import HtmlResource, env
import buildbot
import twisted
import sys
import jinja2

class AboutBuildbot(HtmlResource):
    title = "About this Buildbot"

    def body(self, request):
        template = env.get_template("about.html");
        template.autoescape = True
        return template.render(buildbot=buildbot.version, 
                               twisted=twisted.__version__,
                               jinja=jinja2.__version__, 
                               python=sys.version,
                               platform=sys.platform)
