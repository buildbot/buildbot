### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
module.exports =

    ### ###########################################################################################
    #   Name of the plugin
    ### ###########################################################################################
    name: 'console_view'
    plugin: true

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
        # JavaScript
        js: [
            'src/module/**/*.js'
            '!src/module/**/*.spec.js'
        ]

        # JavaScript test
        js_unit: [
            'src/module/**/*.spec.js'
        ]

        # CoffeeScript
        coffee: [
            'src/module/**/*.coffee'
            '!src/module/**/*.spec.coffee'
        ]

        # CoffeeScript test
        coffee_unit: [
            'src/module/**/*.spec.coffee'
            'test/**/*.coffee'
        ]

        # Jade templates
        templates: [
            'src/module/**/*.tpl.jade'
        ]

        # Jade index
        index: [

        ]

        # Less stylesheets
        less: [
            'src/styles/styles.less'
            'src/module/**/*.less'
        ]

        # Images
        images: [
            'src/img/**/*.{png,jpg,gif,ico}'
        ]

        # Fonts
        fonts: [
        ]

        # Common files
        common: [
            'src/common/*'
        ]

        # Library files
        library:

            # JavaScript libraries
            js: [

            ]

            # JavaScript libraries used during testing only
            js_unit: [
                'src/libs/angular/angular.js'
                'src/libs/angular-mocks/angular-mocks.js'
                'src/libs/angular-ui-router/release/angular-ui-router.js'
            ]
