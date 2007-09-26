
from zope.interface import Interface
from twisted.web import html, resource
from buildbot.status import builder
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, EXCEPTION


class ITopBox(Interface):
    """I represent a box in the top row of the waterfall display: the one
    which shows the status of the last build for each builder."""
    pass

class ICurrentBox(Interface):
    """I represent the 'current activity' box, just above the builder name."""
    pass

class IBox(Interface):
    """I represent a box in the waterfall display."""
    pass

class IHTMLLog(Interface):
    pass

css_classes = {SUCCESS: "success",
               WARNINGS: "warnings",
               FAILURE: "failure",
               EXCEPTION: "exception",
               }

ROW_TEMPLATE = '''
<div class="row">
  <span class="label">%(label)s</span>
  <span class="field">%(field)s</span>
</div>
'''

def make_row(label, field):
    """Create a name/value row for the HTML.

    `label` is plain text; it will be HTML-encoded.

    `field` is a bit of HTML structure; it will not be encoded in
    any way.
    """
    label = html.escape(label)
    return ROW_TEMPLATE % {"label": label, "field": field}

colormap = {
    'green': '#72ff75',
    }
def td(text="", parms={}, **props):
    data = ""
    data += "  "
    #if not props.has_key("border"):
    #    props["border"] = 1
    props.update(parms)
    if props.has_key("bgcolor"):
        props["bgcolor"] = colormap.get(props["bgcolor"], props["bgcolor"])
    comment = props.get("comment", None)
    if comment:
        data += "<!-- %s -->" % comment
    data += "<td"
    class_ = props.get('class_', None)
    if class_:
        props["class"] = class_
    for prop in ("align", "bgcolor", "colspan", "rowspan", "border",
                 "valign", "halign", "class"):
        p = props.get(prop, None)
        if p != None:
            data += " %s=\"%s\"" % (prop, p)
    data += ">"
    if not text:
        text = "&nbsp;"
    if isinstance(text, list):
        data += "<br />".join(text)
    else:
        data += text
    data += "</td>\n"
    return data

def build_get_class(b):
    """
    Return the class to use for a finished build or buildstep,
    based on the result.
    """
    # FIXME: this getResults duplicity might need to be fixed
    result = b.getResults()
    #print "THOMAS: result for b %r: %r" % (b, result)
    if isinstance(b, builder.BuildStatus):
        result = b.getResults()
    elif isinstance(b, builder.BuildStepStatus):
        result = b.getResults()[0]
        # after forcing a build, b.getResults() returns ((None, []), []), ugh
        if isinstance(result, tuple):
            result = result[0]
    else:
        raise TypeError, "%r is not a BuildStatus or BuildStepStatus" % b

    if result == None:
        # FIXME: this happens when a buildstep is running ?
        return "running"
    return builder.Results[result]

class Box:
    # a Box wraps an Event. The Box has HTML <td> parameters that Events
    # lack, and it has a base URL to which each File's name is relative.
    # Events don't know about HTML.
    spacer = False
    def __init__(self, text=[], color=None, class_=None, urlbase=None,
                 **parms):
        self.text = text
        self.color = color
        self.class_ = class_
        self.urlbase = urlbase
        self.show_idle = 0
        if parms.has_key('show_idle'):
            del parms['show_idle']
            self.show_idle = 1
            
        self.parms = parms
        # parms is a dict of HTML parameters for the <td> element that will
        # represent this Event in the waterfall display.

    def td(self, **props):
        props.update(self.parms)
        text = self.text
        if not text and self.show_idle:
            text = ["[idle]"]
        return td(text, props, bgcolor=self.color, class_=self.class_)


class HtmlResource(resource.Resource):
    # this is a cheap sort of template thingy
    contentType = "text/html; charset=UTF-8"
    title = "Dummy"
    addSlash = False # adapted from Nevow

    def getChild(self, path, request):
        if self.addSlash and path == "" and len(request.postpath) == 0:
            return self
        return resource.Resource.getChild(self, path, request)

    def render(self, request):
        if self.addSlash and request.prepath[-1] != '':
            request.redirect(request.URLPath().child(''))
            return ''

        data = self.content(request)
        if isinstance(data, unicode):
            data = data.encode("utf-8")
        request.setHeader("content-type", self.contentType)
        if request.method == "HEAD":
            request.setHeader("content-length", len(data))
            return ''
        return data

    def getStatus(self, request):
        return request.site.buildbot_service.getStatus()
    def getControl(self, request):
        return request.site.buildbot_service.getControl()

    def getChangemaster(self, request):
        return request.site.buildbot_service.parent.change_svc

    def path_to_root(self, request):
        # /waterfall : ['waterfall'] -> ''
        # /somewhere/lower : ['somewhere', 'lower'] -> '../'
        # /somewhere/indexy/ : ['somewhere', 'indexy', ''] -> '../../'
        # / : [] -> ''
        if request.prepath:
            segs = len(request.prepath) - 1
        else:
            segs = 0
        root = "../" * segs
        return root

    def getTitle(self, request):
        return self.title

    def fillTemplate(self, template, request):
        s = request.site.buildbot_service
        values = s.template_values.copy()
        values['root'] = self.path_to_root(request)
        # e.g. to reference the top-level 'buildbot.css' page, use
        # "%(root)sbuildbot.css"
        values['title'] = self.getTitle(request)
        return template % values

    def content(self, request):
        s = request.site.buildbot_service
        data = ""
        data += self.fillTemplate(s.header, request)
        data += "<head>\n"
        for he in s.head_elements:
            data += " " + self.fillTemplate(he, request) + "\n"
            data += self.head(request)
        data += "</head>\n\n"

        data += '<body %s>\n' % " ".join(['%s="%s"' % (k,v)
                                          for (k,v) in s.body_attrs.items()])
        data += self.body(request)
        data += "</body>\n"
        data += self.fillTemplate(s.footer, request)
        return data

    def head(self, request):
        return ""

    def body(self, request):
        return "Dummy\n"

class StaticHTML(HtmlResource):
    def __init__(self, body, title):
        HtmlResource.__init__(self)
        self.bodyHTML = body
        self.title = title
    def body(self, request):
        return self.bodyHTML

MINUTE = 60
HOUR = 60*MINUTE
DAY = 24*HOUR
WEEK = 7*DAY
MONTH = 30*DAY

def plural(word, words, num):
    if int(num) == 1:
        return "%d %s" % (num, word)
    else:
        return "%d %s" % (num, words)

def abbreviate_age(age):
    if age <= 90:
        return "%s ago" % plural("second", "seconds", age)
    if age < 90*MINUTE:
        return "about %s ago" % plural("minute", "minutes", age / MINUTE)
    if age < DAY:
        return "about %s ago" % plural("hour", "hours", age / HOUR)
    if age < 2*WEEK:
        return "about %s ago" % plural("day", "days", age / DAY)
    if age < 2*MONTH:
        return "about %s ago" % plural("week", "weeks", age / WEEK)
    return "a long time ago"
