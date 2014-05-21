### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
module.exports =

    ### ###########################################################################################
    #   Name of the plugin
    ### ###########################################################################################
    name: 'codeparameter'

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
        ]

        # JavaScript test
        js_unit: [
        ]

        # CoffeeScript
        coffee: [
            'src/module/**/*.coffee'
            '!src/module/**/*.spec.coffee'
        ]

        # CoffeeScript test
        coffee_unit: [
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
        ]

        # Library files
        library:

            # JavaScript libraries
            js: [
                'src/libs/angular-ui-ace/ui-ace.js'
            ]

            # JavaScript libraries used during testing only
            js_unit: [

            ]