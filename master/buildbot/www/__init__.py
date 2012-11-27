try:
    from buildbot_www import static_dir, index_html
except ImportError:
    print "Please install the 'buildbot_www' package, either from pypi or from the buildbot source tree"
    print "this package contains optimized javascript code for the buildbot ui"
    import sys
    sys.exit(1)
__all__ = [static_dir, index_html]
