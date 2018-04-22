import re
import os
import six

class Compiler(object):
    RE_INTERPOLATE = re.compile(r'(\\)?([#!]){(.*?)}')
    doctypes = {
        '5': '<!DOCTYPE html>'
      , 'xml': '<?xml version="1.0" encoding="utf-8" ?>'
      , 'default': '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
      , 'transitional': '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
      , 'strict': '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">'
      , 'frameset': '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Frameset//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-frameset.dtd">'
      , '1.1': '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">'
      , 'basic': '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML Basic 1.1//EN" "http://www.w3.org/TR/xhtml-basic/xhtml-basic11.dtd">'
      , 'mobile': '<!DOCTYPE html PUBLIC "-//WAPFORUM//DTD XHTML Mobile 1.2//EN" "http://www.openmobilealliance.org/tech/DTD/xhtml-mobile12.dtd">'
    }
    inlineTags = [
        'a'
      , 'abbr'
      , 'acronym'
      , 'b'
      , 'br'
      , 'code'
      , 'em'
      , 'font'
      , 'i'
      , 'img'
      , 'ins'
      , 'kbd'
      , 'map'
      , 'samp'
      , 'small'
      , 'span'
      , 'strong'
      , 'sub'
      , 'sup'
      , 'textarea'
    ]
    selfClosing = [
        'meta'
      , 'img'
      , 'link'
      , 'input'
      , 'area'
      , 'base'
      , 'col'
      , 'br'
      , 'hr'
    ]
    autocloseCode = 'if,for,block,filter,autoescape,with,trans,spaceless,comment,cache,macro,localize,compress,raw'.split(',')

    filters = {}

    def __init__(self, node, **options):
        self.options = options
        self.node = node
        self.hasCompiledDoctype = False
        self.hasCompiledTag = False
        self.pp = options.get('pretty', True)
        self.debug = options.get('compileDebug', False) is not False
        self.filters.update(options.get('filters', {}))
        self.doctypes.update(options.get('doctypes', {}))
        # self.var_processor = options.get('var_processor', lambda x: x)
        self.selfClosing.extend(options.get('selfClosing', []))
        self.autocloseCode.extend(options.get('autocloseCode', []))
        self.inlineTags.extend(options.get('inlineTags', []))
        self.useRuntime = options.get('useRuntime', True)
        self.extension = options.get('extension', None) or '.jade'
        self.indents = 0
        self.doctype = None
        self.terse = False
        self.xml = False
        self.mixing = 0
        self.variable_start_string = options.get("variable_start_string", "{{")
        self.variable_end_string = options.get("variable_end_string", "}}")
        if 'doctype' in self.options: self.setDoctype(options['doctype'])
        self.instring = False

    def var_processor(self, var):
        if isinstance(var,six.string_types) and var.startswith('_ '):
            var = '_("%s")'%var[2:]
        return var

    def compile_top(self):
        return ''

    def compile(self):
        self.buf = [self.compile_top()]
        self.lastBufferedIdx = -1
        self.visit(self.node)
        compiled = u''.join(self.buf)
        if isinstance(compiled, six.binary_type):
            compiled = six.text_type(compiled, 'utf8')
        return compiled

    def setDoctype(self, name):
        self.doctype = self.doctypes.get(name or 'default',
                                         '<!DOCTYPE %s>' % name)
        self.terse = name in ['5','html']
        self.xml = self.doctype.startswith('<?xml')

    def buffer(self, str):
        if self.lastBufferedIdx == len(self.buf):
            self.lastBuffered += str
            self.buf[self.lastBufferedIdx - 1] = self.lastBuffered
        else:
            self.buf.append(str)
            self.lastBuffered = str;
            self.lastBufferedIdx = len(self.buf)

    def visit(self, node, *args, **kwargs):
        # debug = self.debug
        # if debug:
        #     self.buf.append('__jade.unshift({ lineno: %d, filename: %s });' % (node.line,('"%s"'%node.filename) if node.filename else '__jade[0].filename'));

        # if node.debug==False and self.debug:
        #     self.buf.pop()
        #     self.buf.pop()

        self.visitNode(node, *args, **kwargs)
        # if debug: self.buf.append('__jade.shift();')

    def visitNode (self, node, *args, **kwargs):
        name = node.__class__.__name__
        if self.instring and name != 'Tag':
            self.buffer('\n')
            self.instring = False
        return getattr(self, 'visit%s' % name)(node, *args, **kwargs)

    def visitLiteral(self, node):
        self.buffer(node.str)

    def visitBlock(self, block):
        for node in block.nodes:
            self.visit(node)

    def visitCodeBlock(self, block):
        self.buffer('{%% block %s %%}' % block.name)
        if block.mode=='prepend':
            self.buffer('%ssuper()%s' % (self.variable_start_string,
                                         self.variable_end_string))
        self.visitBlock(block)
        if block.mode == 'append':
            self.buffer('%ssuper()%s' % (self.variable_start_string,
                                         self.variable_end_string))
        self.buffer('{% endblock %}')

    def visitDoctype(self,doctype=None):
        if doctype and (doctype.val or not self.doctype):
            self.setDoctype(doctype.val or 'default')

        if self.doctype:
            self.buffer(self.doctype)
        self.hasCompiledDoctype = True

    def visitMixin(self,mixin):
        if mixin.block:
            self.buffer('{%% macro %s(%s) %%}' % (mixin.name, mixin.args))
            self.visitBlock(mixin.block)
            self.buffer('{% endmacro %}')
        else:
          self.buffer('%s%s(%s)%s' % (self.variable_start_string, mixin.name,
                                      mixin.args, self.variable_end_string))

    def visitTag(self,tag):
        self.indents += 1
        name = tag.name
        if not self.hasCompiledTag:
            if not self.hasCompiledDoctype and 'html' == name:
                self.visitDoctype()
            self.hasCompiledTag = True

        if self.pp and name not in self.inlineTags and not tag.inline:
            self.buffer('\n' + '  ' * (self.indents - 1))
        if name in self.inlineTags or tag.inline:
            self.instring = False

        closed = name in self.selfClosing and not self.xml
        if tag.text:
            t = tag.text.nodes[0]
            if t.startswith(u'/'):
                if len(t) > 1:
                    raise Exception('%s is self closing and should not have content.' % name)
                closed = True

        self.buffer('<%s' % name)
        self.visitAttributes(tag.attrs)
        self.buffer('/>' if not self.terse and closed else '>')

        if not closed:
            if tag.code: self.visitCode(tag.code)
            if tag.text: self.buffer(self.interpolate(tag.text.nodes[0].lstrip()))
            self.escape = 'pre' == tag.name
            # empirically check if we only contain text
            textOnly = tag.textOnly or not bool(len(tag.block.nodes))
            self.instring = False
            self.visit(tag.block)

            if self.pp and not name in self.inlineTags and not textOnly:
                self.buffer('\n' + '  ' * (self.indents-1))

            self.buffer('</%s>' % name)
        self.indents -= 1

    def visitFilter(self,filter):
        if filter.name not in self.filters:
          if filter.isASTFilter:
            raise Exception('unknown ast filter "%s"' % filter.name)
          else:
            raise Exception('unknown filter "%s"' % filter.name)

        fn = self.filters.get(filter.name)
        if filter.isASTFilter:
            self.buf.append(fn(filter.block, self, filter.attrs))
        else:
            text = ''.join(filter.block.nodes)
            text = self.interpolate(text)
            filter.attrs = filter.attrs or {}
            filter.attrs['filename'] = self.options.get('filename', None)
            self.buffer(fn(text, filter.attrs))

    def _interpolate(self, attr, repl):
        return self.RE_INTERPOLATE.sub(lambda matchobj:repl(matchobj.group(3)),
                                       attr)

    def interpolate(self, text, escape=None):
        def repl(matchobj):
            if escape is None:
                if matchobj.group(2) == '!':
                    filter_string = ''
                else:
                    filter_string = '|escape'
            elif escape is True:
                filter_string = '|escape'
            elif escape is False:
                filter_string = ''

            return self.variable_start_string + matchobj.group(3) + \
                filter_string + self.variable_end_string
        return self.RE_INTERPOLATE.sub(repl, text)

    def visitText(self,text):
        text = ''.join(text.nodes)
        text = self.interpolate(text)
        self.buffer(text)
        if self.pp:
            self.buffer('\n')

    def visitString(self,text):
        instring = not text.inline
        text = ''.join(text.nodes)
        text = self.interpolate(text)
        self.buffer(text)
        self.instring = instring

    def visitComment(self,comment):
        if not comment.buffer: return
        if self.pp:
            self.buffer('\n' + '  ' * (self.indents))
        self.buffer('<!--%s-->' % comment.val)

    def visitAssignment(self,assignment):
        self.buffer('{%% set %s = %s %%}' % (assignment.name, assignment.val))


    def format_path(self,path):
        has_extension = '.' in os.path.basename(path)
        if not has_extension:
            path += self.extension
        return path

    def visitExtends(self,node):
        path = self.format_path(node.path)
        self.buffer('{%% extends "%s" %%}' % (path))

    def visitInclude(self,node):
        path = self.format_path(node.path)
        self.buffer('{%% include "%s" %%}' % (path))

    def visitBlockComment(self, comment):
        if not comment.buffer:
            return
        isConditional = comment.val.strip().startswith('if')
        self.buffer('<!--[%s]>' % comment.val.strip() if isConditional else '<!--%s' % comment.val)
        self.visit(comment.block)
        self.buffer('<![endif]-->' if isConditional else '-->')

    def visitConditional(self, conditional):
        TYPE_CODE = {
            'if': lambda x: 'if %s'%x,
            'unless': lambda x: 'if not %s'%x,
            'elif': lambda x: 'elif %s'%x,
            'else': lambda x: 'else'
        }
        self.buf.append('{%% %s %%}' % TYPE_CODE[conditional.type](conditional.sentence))
        if conditional.block:
            self.visit(conditional.block)
            for next in conditional.next:
              self.visitConditional(next)
        if conditional.type in ['if','unless']:
            self.buf.append('{% endif %}')


    def visitVar(self, var, escape=False):
        var = self.var_processor(var)
        return ('%s%s%s%s' % (self.variable_start_string, var,
                              '|escape' if escape else '', self.variable_end_string))

    def visitCode(self,code):
        if code.buffer:
            val = code.val.lstrip()

            self.buf.append(self.visitVar(val, code.escape))
        else:
            self.buf.append('{%% %s %%}' % code.val)

        if code.block:
            # if not code.buffer: self.buf.append('{')
            self.visit(code.block)
            # if not code.buffer: self.buf.append('}')

            if not code.buffer:
              codeTag = code.val.strip().split(' ', 1)[0]
              if codeTag in self.autocloseCode:
                  self.buf.append('{%% end%s %%}' % codeTag)

    def visitEach(self,each):
        self.buf.append('{%% for %s in %s|__pyjade_iter:%d %%}' % (','.join(each.keys), each.obj, len(each.keys)))
        self.visit(each.block)
        self.buf.append('{% endfor %}')

    def attributes(self,attrs):
        return "%s__pyjade_attrs(%s)%s" % (self.variable_start_string, attrs, self.variable_end_string)

    def visitDynamicAttributes(self, attrs):
        buf, classes, params = [], [], {}
        terse='terse=True' if self.terse else ''
        for attr in attrs:
            if attr['name'] == 'class':
                classes.append('(%s)' % attr['val'])
            else:
                pair = "('%s',(%s))" % (attr['name'], attr['val'])
                buf.append(pair)

        if classes:
            classes = " , ".join(classes)
            buf.append("('class', (%s))" % classes)

        buf = ', '.join(buf)
        if self.terse: params['terse'] = 'True'
        if buf: params['attrs'] = '[%s]' % buf
        param_string = ', '.join(['%s=%s' % (n, v) for n, v in six.iteritems(params)])
        if buf or terse:
            self.buf.append(self.attributes(param_string))

    def visitAttributes(self, attrs):
        temp_attrs = []
        for attr in attrs:
            if (not self.useRuntime and not attr['name']=='class') or attr['static']: #
                if temp_attrs:
                    self.visitDynamicAttributes(temp_attrs)
                    temp_attrs = []
                n, v = attr['name'], attr['val']
                if isinstance(v, six.string_types):
                    if self.useRuntime or attr['static']:
                        self.buf.append(' %s=%s' % (n, v))
                    else:
                        self.buf.append(' %s="%s"' % (n, self.visitVar(v)))
                elif v is True:
                    if self.terse:
                        self.buf.append(' %s' % (n,))
                    else:
                        self.buf.append(' %s="%s"' % (n, n))
            else:
                temp_attrs.append(attr)

        if temp_attrs: self.visitDynamicAttributes(temp_attrs)

    @classmethod
    def register_filter(cls, name, f):
        cls.filters[name] = f

    @classmethod
    def register_autoclosecode(cls, name):
        cls.autocloseCode.append(name)


#1-
