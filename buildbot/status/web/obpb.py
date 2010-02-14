import urllib

from buildbot.interfaces import IControl, IStatusReceiver
from buildbot.status.web.base import HtmlResource, map_branches, \
     build_get_class, ICurrentBox, path_to_root

# /one_box_per_builder
#  accepts builder=, branch=
class OneBoxPerBuilder(HtmlResource):
    """This shows a narrow table with one row per builder. The leftmost column
    contains the builder name. The next column contains the results of the
    most recent build. The right-hand column shows the builder's current
    activity.

    builder=: show only builds for this builder. Multiple builder= arguments
              can be used to see builds from any builder in the set.
    """

    title = "Latest Build"

    def content(self, req, cxt):
        status = self.getStatus(req)

        builders = req.args.get("builder", status.getBuilderNames())
        branches = [b for b in req.args.get("branch", []) if b]

        cxt['branches'] = branches
        bs = cxt['builders'] = []
        
        building = 0
        online = 0
        base_builders_url = path_to_root(req) + "builders/"
        for bn in builders:
            bld = { 'link': base_builders_url + urllib.quote(bn, safe=''),
                    'name': bn }
            bs.append(bld)

            builder = status.getBuilder(bn)
            builds = list(builder.generateFinishedBuilds(map_branches(branches),
                                                         num_builds=1))
            if builds:
                b = builds[0]
                bld['build_url'] = (bld['link'] + "/builds/%d" % b.getNumber())
                try:
                    label = b.getProperty("got_revision")
                except KeyError:
                    label = None
                if not label or len(str(label)) > 20:
                    label = "#%d" % b.getNumber()
                
                bld['build_label'] = label
                bld['build_text'] = " ".join(b.getText())
                bld['build_css_class'] = build_get_class(b)

            current_box = ICurrentBox(builder).getBox(status)
            bld['current_box'] = current_box.td()

            builder_status = builder.getState()[0]
            if builder_status == "building":
                building += 1
                online += 1
            elif builder_status != "offline":
                online += 1
                
        cxt['authz'] = self.getAuthz(req)
        cxt['num_building'] = online
        cxt['num_online'] = online

        template = req.site.buildbot_service.templates.get_template("oneboxperbuilder.html")
        return template.render(**cxt)
    

