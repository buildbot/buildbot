class State extends Config
    constructor: ($stateProvider, bbSettingsServiceProvider) ->

        # Name of the state
        name = 'build'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders/:builder/builds/:build'
            data:
                pageTitle: _.template("Buildbot: builder <%= builder %> build <%= build %>")

        $stateProvider.state(state)
        bbSettingsServiceProvider.addSettingsGroup
            name:'LogPreview'
            caption: 'LogPreview related settings'
            items:[
                type:'integer'
                name:'loadlines'
                caption:'Initial number of lines to load'
                default_value: 40
            ,
                type:'integer'
                name:'maxlines'
                caption:'Maximum number of lines to show'
                default_value: 40
            ]
