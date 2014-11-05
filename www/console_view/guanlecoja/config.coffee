### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
ANGULAR_TAG = "~1.3.0"
module.exports =

    ### ###########################################################################################
    #   Name of the plugin
    ### ###########################################################################################
    name: 'console_view'
    dir: build: 'buildbot_console_view/static'
    bower:
        testdeps:
            "guanlecoja-ui":
                version: '~1.0.5'
                files: 'scripts.js'
            "angular-mocks":
                version: ANGULAR_TAG
                files: "angular-mocks.js"

    karma:
        # we put tests first, so that we have angular, and fake app defined
        files: ["tests.js", "scripts.js", 'fixtures.js']
