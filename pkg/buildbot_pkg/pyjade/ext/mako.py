import os
import sys

from pyjade import Parser, Compiler as _Compiler
from pyjade.runtime import attrs as _attrs
from pyjade.utils import process
ATTRS_FUNC = '__pyjade_attrs'
ITER_FUNC = '__pyjade_iter'

def attrs(attrs, terse=False):
    return _attrs(attrs, terse, MakoUndefined)

class Compiler(_Compiler):
    useRuntime = True
    def compile_top(self):
        return '# -*- coding: utf-8 -*-\n<%%! from pyjade.runtime import attrs as %s, iteration as %s\nfrom mako.runtime import Undefined %%>' % (ATTRS_FUNC,ITER_FUNC)

    def interpolate(self, text, escape=True):
        return self._interpolate(text,lambda x:'${%s}'%x)

    def visitCodeBlock(self,block):
        if self.mixing > 0:
          self.buffer('${caller.body() if caller else ""}')
        else:
          self.buffer('<%%block name="%s">'%block.name)
          if block.mode=='append': self.buffer('${parent.%s()}'%block.name)
          self.visitBlock(block)
          if block.mode=='prepend': self.buffer('${parent.%s()}'%block.name)
          self.buffer('</%block>')

    def visitMixin(self,mixin):
        self.mixing += 1
        if not mixin.call:
          self.buffer('<%%def name="%s(%s)">'%(mixin.name,mixin.args))
          self.visitBlock(mixin.block)
          self.buffer('</%def>')
        elif mixin.block:
          self.buffer('<%%call expr="%s(%s)">'%(mixin.name,mixin.args))
          self.visitBlock(mixin.block)
          self.buffer('</%call>')
        else:
          self.buffer('${%s(%s)}'%(mixin.name,mixin.args))
        self.mixing -= 1

    def visitAssignment(self,assignment):
        self.buffer('<%% %s = %s %%>'%(assignment.name,assignment.val))

    def visitExtends(self,node):
        path = self.format_path(node.path)
        self.buffer('<%%inherit file="%s"/>'%(path))

    def visitInclude(self,node):
        path = self.format_path(node.path)
        self.buffer('<%%include file="%s"/>'%(path))
        self.buffer('<%%namespace file="%s" import="*"/>'%(path))


    def visitConditional(self,conditional):
        TYPE_CODE = {
            'if': lambda x: 'if %s'%x,
            'unless': lambda x: 'if not %s'%x,
            'elif': lambda x: 'elif %s'%x,
            'else': lambda x: 'else'
        }
        self.buf.append('\\\n%% %s:\n'%TYPE_CODE[conditional.type](conditional.sentence))
        if conditional.block:
            self.visit(conditional.block)
            for next in conditional.next:
              self.visitConditional(next)
        if conditional.type in ['if','unless']: self.buf.append('\\\n% endif\n')


    def visitVar(self,var,escape=False):
        return '${%s%s}'%(var,'| h' if escape else '| n')

    def visitCode(self,code):
        if code.buffer:
            val = code.val.lstrip()
            val = self.var_processor(val)
            self.buf.append(self.visitVar(val, code.escape))
        else:
            self.buf.append('<%% %s %%>'%code.val)

        if code.block:
            # if not code.buffer: self.buf.append('{')
            self.visit(code.block)
            # if not code.buffer: self.buf.append('}')

            if not code.buffer:
              codeTag = code.val.strip().split(' ',1)[0]
              if codeTag in self.autocloseCode:
                  self.buf.append('</%%%s>'%codeTag)

    def visitEach(self,each):
        self.buf.append('\\\n%% for %s in %s(%s,%d):\n'%(','.join(each.keys),ITER_FUNC,each.obj,len(each.keys)))
        self.visit(each.block)
        self.buf.append('\\\n% endfor\n')

    def attributes(self,attrs):
        return "${%s(%s, undefined=Undefined) | n}"%(ATTRS_FUNC,attrs)



def preprocessor(source):
    return process(source,compiler=Compiler)
