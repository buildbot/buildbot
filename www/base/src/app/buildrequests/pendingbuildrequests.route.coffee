class State extends Config
    constructor: ($stateProvider, bbSettingsServiceProvider) ->

        # Name of the state
        name = 'pendingbuildrequests'

        # Configuration
        cfg =
            group: "builds"
            caption: 'Pending Buildrequests'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/pendingbuildrequests'
            data: cfg

        $stateProvider.state(state)

        bbSettingsServiceProvider.addSettingsGroup
            name:'BuildRequests'
            caption: 'Buildreqests page related settings'
            items:[
                type:'integer'
                name:'buildrequestFetchLimit'
                caption:'Maximum number of pending buildrequests to fetch'
                default_value: 50
            ]
