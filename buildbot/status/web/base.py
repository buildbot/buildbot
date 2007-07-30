
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

ROW_TEMPLATE = '''
<div class="row">
  <span class="label">%(label)s</span>
  <span class="field">%(field)s</span>
</div>'''

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
    if type(text) == types.ListType:
        data += string.join(text, "<br />")
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


class HtmlResource(Resource):
    css = None
    contentType = "text/html; charset=UTF-8"
    title = "Dummy"

    def render(self, request):
        data = self.content(request)
        if isinstance(data, unicode):
            data = data.encode("utf-8")
        request.setHeader("content-type", self.contentType)
        if request.method == "HEAD":
            request.setHeader("content-length", len(data))
            return ''
        return data

    def getTitle(self, request):
        return self.title

    def content(self, request):
        data = ('<!DOCTYPE html PUBLIC'
                ' "-//W3C//DTD XHTML 1.0 Transitional//EN"\n'
                '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n'
                '<html'
                ' xmlns="http://www.w3.org/1999/xhtml"'
                ' lang="en"'
                ' xml:lang="en">\n')
        data += "<head>\n"
        data += "  <title>" + self.getTitle(request) + "</title>\n"
        if self.css:
            # TODO: use some sort of relative link up to the root page, so
            # this css can be used from child pages too
            data += ('  <link href="%s" rel="stylesheet" type="text/css"/>\n'
                     % "buildbot.css")
        data += "</head>\n"
        data += '<body vlink="#800080">\n'
        data += self.body(request)
        data += "</body></html>\n"
        return data

    def body(self, request):
        return "Dummy\n"

class StaticHTML(HtmlResource):
    def __init__(self, body, title):
        HtmlResource.__init__(self)
        self.bodyHTML = body
        self.title = title
    def body(self, request):
        return self.bodyHTML

