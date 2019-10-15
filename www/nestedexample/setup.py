#!/usr/bin/env python

try:
    from buildbot_pkg import setup_www_plugin
except ImportError:
    import sys
    print('Please install buildbot_pkg module in order to install that '
          'package, or use the pre-build .whl modules available on pypi',
          file=sys.stderr)
    sys.exit(1)

setup_www_plugin(
    name='buildbot-nestedexample',
    description='"An example of a custom nested parameter"',
    author=u'Ion Alberdi',
    author_email=u'ialberdi@intel.com',
    url='http://buildbot.net/',
    version='0.0.1',
    packages=['buildbot_nestedexample'],
    install_requires=[
        'klein'
    ],
    package_data={
        '': [
            'VERSION',
            'static/*'
        ]
    },
    entry_points="""
        [buildbot.www]
        nestedexample = buildbot_nestedexample:ep
    """,
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)'
    ],
)
