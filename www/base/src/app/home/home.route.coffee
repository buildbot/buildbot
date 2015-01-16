class State extends Config
    constructor: ($stateProvider, glMenuServiceProvider, bbSettingsServiceProvider) ->

        # Name of the state
        name = 'home'

        # Menu configuration
        glMenuServiceProvider.addGroup
            name: name
            caption: 'Home'
            icon: 'home'
            order: 1

        bbSettingsServiceProvider.addSettingsGroup
            name:name
            caption: 'Home related settings'
            items:[
                    type:'bool'
                    name:'checkbox1'
                    default_value: false
                ,
                    type:'choices'
                    name:'radio'
                    default_value: 'radio1'
                    answers: [
                        { name: 'radio1' }
                        { name: 'radio2' }
                    ]
                ,
                    type:'text'
                    name:'Default welcome message'
                    default_value: 'Hello!'
            ]

        cfg =
            group: name
            caption: 'Home'

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/'
            data: cfg
