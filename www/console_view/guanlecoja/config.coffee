### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
ANGULAR_TAG = "~1.4.6"
module.exports =

    ### ###########################################################################################
    #   Name of the plugin
    ### ###########################################################################################
    name: 'console_view'
    dir: build: 'buildbot_console_view/static'
    bower:
        testdeps:
            "guanlecoja-ui":
                version: '~1.5.0'
                files: ['vendors.js', 'scripts.js']
            "angular-mocks":
                version: ANGULAR_TAG
                files: "angular-mocks.js"
            'buildbot-data':
                version: '~1.0.14'
                files: 'dist/buildbot-data.js'

    karma:
        # we put tests first, so that we have angular, and fake app defined
        files: ["tests.js", "scripts.js", 'fixtures.js']
