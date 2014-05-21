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
        # The temp folder is where the projects are compiled during development
        temp: '.temp'
        # The build folder is where the app resides once it's completely built
        build: 'buildbot_www'

    ### ###########################################################################################
    #   This is a collection of file patterns
    ### ###########################################################################################
    files:
        # JavaScript
        js: [
            'src/app/**/*.js'
            '!src/app/**/*.spec.js'
        ]

        # JavaScript test
        js_unit: [
            'src/app/**/*.spec.js'
        ]

        # CoffeeScript
        coffee: [
            'src/app/**/*.coffee'
            '!src/app/**/*.spec.coffee'
        ]

        # CoffeeScript test
        coffee_unit: [
            'test/**/*.coffee'
        ]

        # Jade templates
        templates: [
            'src/app/**/*.tpl.jade'
        ]

        # Jade index
        index: [
            'src/app/index.jade'
        ]

        # Less stylesheets
        less: [
            'src/styles/styles.less'
            'src/app/**/*.less'
        ]

        # Images
        images: [
            'src/img/**/*.{png,jpg,gif,ico}'
        ]

        # Fonts
        fonts: [
            'src/libs/font-awesome/fonts/*'
        ]

        # Common files
        common: [
            'src/common/*'
        ]

        # Library files
        library:

            # JavaScript libraries
            js: [
                'src/libs/jquery/dist/jquery.js'
                'src/libs/angular/angular.js'
                'src/libs/requirejs/require.js'

                'src/libs/angular-animate/angular-animate.js'
                'src/libs/angular-bootstrap/ui-bootstrap-tpls.js'
                'src/libs/angular-ui-router/release/angular-ui-router.js'
                'src/libs/angular-recursion/angular-recursion.js'

                'src/libs/lodash/dist/lodash.js'
                'src/libs/moment/moment.js'
                'src/libs/underscore.string/lib/underscore.string.js'
                'src/libs/restangular/dist/restangular.js'
            ]

            # JavaScript libraries used during testing only
            js_unit: [
                'src/libs/angular-mocks/angular-mocks.js'
            ]