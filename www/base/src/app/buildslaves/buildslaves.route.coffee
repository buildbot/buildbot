class State extends Config
    constructor: ($stateProvider, bbSettingsServiceProvider) ->

        # Name of the state
        name = 'buildslaves'

        # Menu Configuration
        cfg =
            group: "builds"
            caption: 'Build Slaves'

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/buildslaves'
            data: cfg

        bbSettingsServiceProvider.addSettingsGroup
            name:'Slaves'
            caption: 'Slaves page related settings'
            items:[
                type:'bool'
                name:'show_old_slaves'
                caption:'Show old slaves'
                default_value: false
            ]
