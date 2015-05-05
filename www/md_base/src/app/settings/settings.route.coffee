class State extends Config
    constructor: (menuServiceProvider, bbSettingsServiceProvider, $stateProvider) ->

        # Name of the state
        name = 'settings'

        menuServiceProvider.addItem
            name: name
            caption: 'Settings'
            icon: 'toggle'
            order: 20

        # Add testing settings group
        # TODO: remove this after all pages is finished and all actual settings
        # has been settled down.
        bbSettingsServiceProvider.addSettingsGroup
            name: 'test_settings'
            caption: 'Test Settings'
            description: 'This is a settings group for testing components of different types.'
            items: [
                type: 'integer'
                name: 'test_integer'
                caption: 'Integer field'
                default_value: 10
                max_value: 20
                min_value: 1
            ,
                type: 'bool'
                name: 'test_bool'
                caption: 'Checkbox field'
                default_value: true
            ,
                type: 'text'
                name: 'test_text'
                caption: 'Text field'
                default_value: ''
            ,
                type: 'choices'
                name: 'test_choices'
                caption: 'Choice field'
                default_value: ''
                options: [
                    value: 'opt1'
                    caption: 'Option 1'
                ,
                    value: 'opt2'
                    caption: 'Option 2'
                ,
                    value: 'opt3'
                    caption: 'Option 3'
                ]
            ]

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            controllerAs: name
            templateUrl: "views/#{name}.html"
            name: name
            url: "/#{name}"
