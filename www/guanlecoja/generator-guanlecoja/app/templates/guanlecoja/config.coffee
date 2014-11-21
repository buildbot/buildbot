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
        build: 'static'
        <% if (!coffee) { %>

    ### ###########################################################################################
    #   This is a collection of file patterns
    ### ###########################################################################################
    files:

        app: [
            'src/**/*.module.js'
        ]

        # scripts (could be coffee or js)
        scripts: [
            'src/**/*.js'
            '!src/**/*.spec.js'
        ]

        # Javascript tests
        tests: [
            'test/**/*.js'
            'src/**/*.spec.js'
        ]
        <% } %>


    ### ###########################################################################################
    #   This is a collection of file patterns
    ### ###########################################################################################

    ### ###########################################################################################
    #   This is a collection of file patterns
    ### ###########################################################################################
    bower:
        # JavaScript libraries (order matters)
        deps:
            "guanlecoja-ui":
                version: '1.1.2'
                files: ['vendors.js', 'scripts.js']
            "font-awesome":
                version: "4.1.0"
                files: []
            "bootstrap":
                version: "3.1.1"
                files: []
        testdeps:
            "angular-mocks":
                version: "~1.2.22"
                files: "angular-mocks.js"
