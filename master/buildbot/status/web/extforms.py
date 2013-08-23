from buildbot.status.web.base import HtmlResource
import buildbot
import twisted
import sys
import jinja2




class extFormsResource(HtmlResource):
    pageTitle = "Katana"

    def content(self, req, cxt):
        cxt.update(dict(buildbot=buildbot.version, 
                               twisted=twisted.__version__,
                               jinja=jinja2.__version__, 
                               python=sys.version,
                               platform=sys.platform))
        cxt['fbuildsch'] = req.args
        

        template = req.site.buildbot_service.templates.get_template("extforms.html")
        template.autoescape = True
        return template.render(**cxt)