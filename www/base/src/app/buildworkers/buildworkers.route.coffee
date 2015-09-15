class State extends Config
    constructor: ($stateProvider, bbSettingsServiceProvider) ->

        # Name of the state
        name = 'buildworkers'

        # Menu Configuration
        cfg =
            group: "builds"
            caption: 'Build Workers'

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/buildworkers'
            data: cfg

        bbSettingsServiceProvider.addSettingsGroup
            name:'Workers'
            caption: 'Workers page related settings'
            items:[
                type:'bool'
                name:'show_old_workers'
                caption:'Show old workers'
                default_value: false
            ]
