describe 'settingsService', ->
    beforeEach module "guanlecoja.ui", (bbSettingsServiceProvider) ->
        # _bbSettingsServiceProvider = bbSettingsServiceProvider
        createCheckbox = (name) ->
            checkbox=
                type:'bool'
                name:name
                default_value: false
            return checkbox
        createRadio = (name) ->
            radio=
                type:'choices'
                name:name
                default_value: 'radio1'
                answers: [
                    { name: 'radio1' }
                    { name: 'radio2' }
                ]
            return radio


        bbSettingsServiceProvider.addSettingsGroup
            name:'User'
            caption: 'User related settings'
            items:[
                createCheckbox 'checkbox1'
                createRadio 'radio1'
            ]

        # console.log(createRadio 'radio1')
        bbSettingsServiceProvider.addSettingsGroup
            name:'Builders'
            caption: 'Builders related settings'
            items:[
                createCheckbox 'checkbox1',
                createRadio 'radio1',
                createRadio 'radio2',
                createRadio 'radio3'
            ]
        null

    it 'should generate correct settings', inject (bbSettingsService) ->
        groups = bbSettingsService.getSettingsGroups()
        console.log(groups['Builders'].items[0])
        console.log(groups['Builders'].items[1])
        expect(groups['Builders'].items.length).toEqual(4)
        expect(groups['User'].items.length).toEqual(2)
        expect(groups['User'].items[2].value).toEqual('radio1')

    it 'should return correct settings', inject (bbSettingsService) ->
        userSetting1 = bbSettingsService.getSetting('User.checkbox1')
        userSetting2 = bbSettingsService.getSetting('User.testfdsfsdfds')
        # userSetting3 = bbSettingsService.getSetting('Test.checkbox1')
        expect(userSetting1).toBeDefined()
        expect(userSetting2).toBeUndefined()
        # expect(userSetting3).toBeUndefined()

    it 'should save correct settings', inject (bbSettingsService) ->
        checkbox = bbSettingsService.getSetting('User.checkbox1')
        checkbox.value = true
        bbSettingsService.save()
        storageGroups = angular.fromJson(localStorage.getItem('settings'))
        storageCheckbox = storageGroups['User'].items[0].value 
        expect(storageCheckbox).toBe(checkbox.value)
