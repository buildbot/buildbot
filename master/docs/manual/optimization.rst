.. _Optimization:

Optimization
============

If you're feeling your Buildbot is running a bit slow, here are some tricks that may help you, but use them at your own risk.

Properties load speedup
-----------------------

For example, if most of your build properties are strings, you can gain an approx. 30% speedup if you put this snippet of code inside your master.cfg file::

    def speedup_json_loads():
        import json, re

        original_decode = json._default_decoder.decode
        my_regexp = re.compile(r'^\[\"([^"]*)\",\s+\"([^"]*)\"\]$')
        def decode_with_re(str, *args, **kw):
            m = my_regexp.match(str)
            try:
                return list(m.groups())
            except Exception:
                return original_decode(str, *args, **kw)
        json._default_decoder.decode = decode_with_re

    speedup_json_loads()

It patches json decoder so that it would first try to extract a value from JSON that is a list of two strings (which is the case for a property being a string), and would fallback to general JSON decoder on any error.
