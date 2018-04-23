class State extends Config
    constructor: ($stateProvider, bbSettingsServiceProvider) ->

        # Name of the state
        name = 'changes'

        # Configuration
        cfg =
            group: "builds"
            caption: 'Last Changes'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/changes'
            data: cfg

        $stateProvider.state(state)

        bbSettingsServiceProvider.addSettingsGroup
            name:'Changes'
            caption: 'Changes page related settings'
            items:[
                type:'integer'
                name:'changesFetchLimit'
                caption:'Maximum number of changes to fetch'
                default_value: 50
            ]
