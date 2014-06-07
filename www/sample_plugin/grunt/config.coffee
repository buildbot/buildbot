### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
module.exports =

    ### ###########################################################################################
    #   Name of the plugin
    ### ###########################################################################################
    name: 'sample_plugin'

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
                'src/libs/d3/d3.js'
            ]

            # JavaScript libraries used during testing only
            js_unit: [

            ]