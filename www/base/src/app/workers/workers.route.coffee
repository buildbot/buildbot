class State extends Config
    constructor: ($stateProvider, bbSettingsServiceProvider) ->

        # Name of the state
        name = 'workers'

        # Menu Configuration
        cfg =
            group: "builds"
            caption: 'Workers'

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/workers?numbuilds'
            data: cfg

        # worker page is actually same as worker, just filtered
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: 'worker'
            url: '/workers/:worker?numbuilds'
            data: {}

        bbSettingsServiceProvider.addSettingsGroup
            name:'Workers'
            caption: 'Workers page related settings'
            items:[
                type:'bool'
                name:'show_old_workers'
                caption:'Show old workers'
                default_value: false
            ]
