### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
module.exports =

    ### ###########################################################################################
    #   Directories
    ### ###########################################################################################
    dir:
        # The build folder is where the app resides once it's completely built
        build: 'buildbot_www'

    ### ###########################################################################################
    #   This is a collection of file patterns
    ### ###########################################################################################
    files:
        # Library files
        library:

            # JavaScript libraries
            js: [
                'src/libs/jquery/dist/jquery.js'
                'src/libs/angular/angular.js'

                'src/libs/angular-animate/angular-animate.js'
                'src/libs/angular-bootstrap/ui-bootstrap-tpls.js'
                'src/libs/angular-ui-router/release/angular-ui-router.js'
                'src/libs/angular-recursion/angular-recursion.js'

                'src/libs/lodash/dist/lodash.js'
                'src/libs/moment/moment.js'
                'src/libs/underscore.string/lib/underscore.string.js'
                'src/libs/restangular/dist/restangular.js'
            ]
