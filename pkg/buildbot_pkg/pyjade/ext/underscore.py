import os
from itertools import count
from pyjade import Parser, Compiler as _Compiler
from pyjade.runtime import attrs
from pyjade.utils import process
import six

def process_param(key, value, terse=False):
    if terse:
        if (key == value) or (value is True):
            return key
    if isinstance(value, six.binary_type):
        value = value.decode('utf8')
    return '''%s="%s"''' % (key, value)

class Compiler(_Compiler):
    def __init__(self, *args, **kws):
      _Compiler.__init__(self, *args, **kws)
      self._i = count()

    def visitAssignment(self,assignment):
        self.buffer('<%% var %s = %s; %%>'%(assignment.name,assignment.val))

    def visitCode(self,code):
        if code.buffer:
            val = code.val.lstrip()
            self.buf.append('<%%%s %s %%>'%('=' if code.escape else '-', val))
        else:
            self.buf.append('<%% %s'%code.val) #for loop

        if code.block:
            self.buf.append(' { %>') #for loop
            # if not code.buffer: self.buf.append('{')
            self.visit(code.block)
            # if not code.buffer: self.buf.append('}')

            if not code.buffer:
              codeTag = code.val.strip().split(' ',1)[0]
              if codeTag in self.autocloseCode:
                  self.buf.append('<% } %>')
        elif not code.buffer:
            self.buf.append('; %>') #for loop
          
 
    def visitEach(self,each):
        #self.buf.append('{%% for %s in %s %%}'%(','.join(each.keys),each.obj))
        __i = self._i.next()
        self.buf.append('<%% for (_i_%s = 0, _len_%s = %s.length; _i_%s < _len_%s; _i_%s++) { ' %(__i, __i, each.obj, __i, __i, __i))
        if len(each.keys) > 1:
          for i, k in enumerate(each.keys):
            self.buf.append('%s = %s[_i_%s][%s];' % (k, each.obj, __i, i))
        else:
          for k in each.keys:
            self.buf.append('%s = %s[_i_%s];' % (k, each.obj, __i))
        self.buf.append(' %>')
        self.visit(each.block)
        self.buf.append('<% } %>')

    def _do_eval(self, value):
        if isinstance(value, six.string_types):
            value = value.encode('utf-8')
        try:
            value = eval(value, {}, {})
        except:
            return "<%%= %s %%>" % value
        return value

    def _get_value(self, attr):
        value = attr['val']
        if attr['static']:
            return attr['val']
        if isinstance(value, six.string_types):
            return self._do_eval(value)
        else:
            return attr['name']

    def visitAttributes(self,attrs):
        classes = []
        params = []
        for attr in attrs:
            if attr['name'] == 'class':
                value = self._get_value(attr)
                if isinstance(value, list):
                    classes.extend(value)
                else:
                    classes.append(value)
            else:
                value = self._get_value(attr)
                if (value is not None) and (value is not False):
                    params.append((attr['name'], value))
        if classes:
            classes = [six.text_type(c) for c in classes]
            params.append(('class', " ".join(classes)))
        if params:
            self.buf.append(" "+" ".join([process_param(k, v, self.terse) for (k,v) in params]))

    def visitConditional(self,conditional):
        TYPE_CODE = {
            'if': lambda x: 'if (%s)'%x,
            'unless': lambda x: 'if (!%s)'%x,
            'elif': lambda x: '} else if (%s)'%x,
            'else': lambda x: '} else'
        }
        self.buf.append('\n<%% %s { %%>'%TYPE_CODE[conditional.type](conditional.sentence))
        if conditional.block:
            self.visit(conditional.block)
            for next in conditional.next:
              self.visitConditional(next)
        if conditional.type in ['if','unless']: self.buf.append('\n<% } %>\n')
        
    def interpolate(self, text, escape=True):
        return self._interpolate(text,lambda x:'<%%= %s %%>'%x)
