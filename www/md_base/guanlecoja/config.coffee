### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
ANGULAR_TAG = "~1.3.15"
ANGULAR_MATERIAL_TAG = "~0.8.3"
module.exports =

    ### ###########################################################################################
    #   Directories
    ### ###########################################################################################
    dir:
        # The build folder is where the app resides once it's completely built
        build: 'buildbot_www/static'
        


    ### ###########################################################################################
    #   This is a collection of file patterns
    ### ###########################################################################################

    ### ###########################################################################################
    #   This is a collection of file patterns
    ### ###########################################################################################
    bower:
        # JavaScript libraries (order matters)
        deps:
            moment:
                version: "~2.6.0"
                files: 'moment.js'
            angular:
                version: ANGULAR_TAG
                files: 'angular.js'
            "angular-animate":
                version: ANGULAR_TAG
                files: 'angular-animate.js'
            "angular-aria":
                version: ANGULAR_TAG
                files: 'angular-aria.js'
            "angular-material":
                version: ANGULAR_MATERIAL_TAG
                files: 'angular-material.js'
        testdeps:
            "angular-mocks":
                version: "~1.3.15"
                files: "angular-mocks.js"
