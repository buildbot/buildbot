from __future__ import absolute_import
from .compiler import Compiler

def register_filter(name=None):
    def decorator(f):
        Compiler.register_filter(name, f)
        return f
    return decorator

@register_filter('cdata')
def cdata_filter(x, y):
    return '<![CDATA[\n%s\n]]>'%x

try:
    import coffeescript
    @register_filter('coffeescript')
    def coffeescript_filter(x, y):
        return '<script>%s</script>' % coffeescript.compile(x)

except ImportError:
    pass

try:
    import markdown
    @register_filter('markdown')
    def markdown_filter(x, y):
        return markdown.markdown(x, output_format='html5')

except ImportError:
    pass
