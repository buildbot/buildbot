describe 'settingsService', ->
    bbSettingsServiceProviderRef = ""
    beforeEach module 'common', (bbSettingsServiceProvider) ->
        bbSettingsServiceProviderRef = bbSettingsServiceProvider

        localStorage.clear()
        bbSettingsServiceProvider.addSettingsGroup
            name:'User'
            caption: 'User related settings'
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
            ]

        bbSettingsServiceProvider.addSettingsGroup
            name:'Release'
            caption: 'Release related settings'
            items:[
                type:'bool'
                name:'checkbox_release'
                default_value: false
            ,
                type:'bool'
                name:'checkbox_release2'
                default_value: false
            ,
                type:'bool'
                name:'checkbox_release3'
                default_value: false
            ,
                type:'choices'
                name:name
                default_value: 'radio1'
                answers: [
                    { name: 'radio1' }
                    { name: 'radio2' }
                ]
            ]
        null

    it 'should merge groups when old group has values already set', inject (bbSettingsService) ->
        localStorage.clear()
        old_group =
            name:'Auth'
            caption: 'Auth related settings'
            items:[
                type:'bool'
                name:'radio1'
                value: true
                default_value: false
            ]
        new_group =
            name:'Auth'
            caption: 'Auth related settings'
            items:[
                type:'bool'
                name:'radio1'
                default_value: false
            ,
                type:'bool'
                name:'radio2'
                default_value: false
            ]
        group_result = bbSettingsServiceProviderRef._mergeNewGroup(old_group, new_group)
        expect(group_result).toEqual
            name:'Auth'
            caption: 'Auth related settings'
            items:[
                type:'bool'
                name:'radio1'
                value: true
                default_value: false
            ,
                type:'bool'
                name:'radio2',
                value:false
                default_value: false
            ]

    it 'should merge groups when new group is defined with no items', inject (bbSettingsService) ->
        localStorage.clear()
        old_group =
            name:'Auth'
            caption: 'Auth related settings'
            items:[
                type:'bool'
                name:'radio1'
                value: true
                default_value: false
            ]
        new_group =
            name:'Auth'
            caption: 'Auth related settings'
            items:[]
        group_result = bbSettingsServiceProviderRef._mergeNewGroup(old_group, new_group)
        expect(group_result).toEqual
            name:'Auth'
            caption: 'Auth related settings'
            items:[]

    it 'should merge groups when old group is defined with no items', inject (bbSettingsService) ->
        localStorage.clear()
        old_group =
            name:'System'
            caption: 'System related settings'
            items:[]
        new_group =
            name:'System'
            caption: 'System related settings'
            items:[
                type:'bool'
                name:'checkbox_system'
                default_value: false
            ,
                type:'bool'
                name:'checkbox_system2'
                default_value: false
            ]
        group_result = bbSettingsServiceProviderRef._mergeNewGroup(old_group, new_group)
        expect(group_result).toEqual
            name:'System'
            caption: 'System related settings'
            items:[
                type:'bool'
                name:'checkbox_system',
                value:false
                default_value: false
            ,
                type:'bool'
                name:'checkbox_system2',
                value:false
                default_value: false
            ]

    it 'should merge groups when new group is undefined', inject (bbSettingsService) ->
        localStorage.clear()
        old_group =
            name:'System'
            caption: 'System related settings'
            items:[
                type:'bool'
                name:'checkbox_system'
                default_value: false
            ,
                type:'bool'
                name:'checkbox_system2'
                default_value: false
            ]
        group_result = bbSettingsServiceProviderRef._mergeNewGroup(old_group, undefined)
        expect(group_result).toBeUndefined()

    it 'should merge groups when old group is undefined', inject (bbSettingsService) ->
        localStorage.clear()
        new_group =
            name:'Auth'
            caption: 'Auth related settings'
            items:[
                type:'bool'
                name:'radio1'
                default_value: false
            ,
                type:'bool'
                name:'radio2'
                default_value: false
            ]
        group_result = bbSettingsServiceProviderRef._mergeNewGroup(undefined, new_group)
        expect(group_result).toEqual
            name:'Auth'
            caption: 'Auth related settings'
            items:[
                type:'bool'
                name:'radio1'
                value: false
                default_value: false
            ,
                type:'bool'
                name:'radio2'
                value: false
                default_value: false
            ]

    it 'should not add a group without name', inject (bbSettingsService) ->
        localStorage.clear()
        group =
            caption: 'Auth related settings'
            items:[
                type:'bool'
                name:'radio1'
                default_value: false
            ,
                type:'bool'
                name:'radio2'
                default_value: false
            ]
        exceptionRun = ->
            group_result = bbSettingsServiceProviderRef.addSettingsGroup(group)
        expect(exceptionRun).toThrow()


    it 'should merge groups when new group has item with no default value', inject (bbSettingsService) ->
        localStorage.clear()
        old_group =
            name:'System'
            caption: 'System related settings'
            items:[]
        new_group =
            name:'System'
            caption: 'System related settings'
            items:[
                type:'bool'
                name:'checkbox_system'
                default_value: false
            ,
                type:'bool'
                name:'checkbox_system2'
            ]
        group_result = bbSettingsServiceProviderRef._mergeNewGroup(old_group, new_group)
        expect(group_result).toEqual
            name:'System'
            caption: 'System related settings'
            items:[
                type:'bool'
                name:'checkbox_system'
                value: false
                default_value: false
            ,
                type:'bool'
                name:'checkbox_system2'
                value: undefined
            ]


    it 'should generate correct settings', inject (bbSettingsService) ->
        groups = bbSettingsService.getSettingsGroups()
        expect(groups['Release']).toEqual
            name:'Release'
            caption: 'Release related settings'
            items:[
                type:'bool'
                name:'checkbox_release'
                value:false
                default_value: false
            ,
                type:'bool'
                name:'checkbox_release2'
                value: false
                default_value: false
            ,
                type:'bool'
                name:'checkbox_release3'
                value:false
                default_value: false
            ,
                type:'choices'
                name:name
                default_value: 'radio1'
                value:'radio1'
                answers: [
                    { name: 'radio1' }
                    { name: 'radio2' }
                ]
            ]

    it 'should return correct setting', inject (bbSettingsService) ->
        userSetting1 = bbSettingsService.getSetting('User.checkbox1')
        userSetting2 = bbSettingsService.getSetting('User.whatever')
        userSetting3 = bbSettingsService.getSetting('UserAA.User_checkbox1')
        expect(userSetting1).toBeDefined()
        expect(userSetting2).toBeUndefined()
        expect(userSetting3).toBeUndefined()

    it 'should save correct settings', inject (bbSettingsService) ->
        checkbox = bbSettingsService.getSetting('User.checkbox1')
        expect(checkbox.value).toBe(false)
        checkbox.value = true
        bbSettingsService.save()
        storageGroups = angular.fromJson(localStorage.getItem('settings'))
        storageCheckbox = storageGroups['User'].items[0].value
        expect(storageCheckbox).toBeTruthy()
