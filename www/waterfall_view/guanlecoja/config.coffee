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
    name: 'waterfall_view'
    dir: build: 'buildbot_waterfall_view/static'
    bower:
        testdeps:
            "angular":
                version: ANGULAR_TAG
                files: "angular.js"
            "angular-mocks":
                version: ANGULAR_TAG
                files: "angular-mocks.js"
            "guanlecoja-ui":
                version: '~1.5.0'
                files: ['vendors.js', 'scripts.js']
            "d3":
                version: "3.4.11"
                files: "d3.js"
            'buildbot-data':
                version: '~1.0.14'
                files: 'dist/scripts.js'
            # TODO these are dependencies of buildbot-data, could be included
            tabex:
                version: '*'
                files: 'dist/tabex.js'
            dexie:
                version: '*'
                files: 'dist/latest/Dexie.js'
    karma:
        # we put tests first, so that we have angular, and fake app defined
        files: ["tests.js", "scripts.js", 'fixtures.js']
