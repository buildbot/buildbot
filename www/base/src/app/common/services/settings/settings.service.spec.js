/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('settingsService', function() {
    let bbSettingsServiceProviderRef = "";
    beforeEach(angular.mock.module('common', function(bbSettingsServiceProvider) {
        bbSettingsServiceProviderRef = bbSettingsServiceProvider;
        bbSettingsServiceProvider.ui_default_config = {
            'User.config_overriden': 100
        };

        localStorage.clear();
        bbSettingsServiceProvider.addSettingsGroup({
            name:'User',
            caption: 'User related settings',
            items:[{
                type:'bool',
                name:'checkbox1',
                default_value: false
            }
            , {
                type:'integer',
                name:'config_overriden',
                default_value: 10
            }
            , {
                type:'choices',
                name:'radio',
                default_value: 'radio1',
                answers: [
                    { name: 'radio1' },
                    { name: 'radio2' }
                ]
            }
            ]});

        bbSettingsServiceProvider.addSettingsGroup({
            name:'Release',
            caption: 'Release related settings',
            items:[{
                type:'bool',
                name:'checkbox_release',
                default_value: false
            }
            , {
                type:'bool',
                name:'checkbox_release2',
                default_value: false
            }
            , {
                type:'bool',
                name:'checkbox_release3',
                default_value: false
            }
            , {
                type:'choices',
                name,
                default_value: 'radio1',
                answers: [
                    { name: 'radio1' },
                    { name: 'radio2' }
                ]
            }
            ]});
    })
    );

    it('should merge groups when old group has values already set', inject(function(bbSettingsService) {
        localStorage.clear();
        const old_group = {
            name:'Auth',
            caption: 'Auth related settings',
            items:[{
                type:'bool',
                name:'radio1',
                value: true,
                default_value: false
            }
            ]
        };
        const new_group = {
            name:'Auth',
            caption: 'Auth related settings',
            items:[{
                type:'bool',
                name:'radio1',
                default_value: false
            }
            , {
                type:'bool',
                name:'radio2',
                default_value: false
            }
            ]
        };
        const group_result = bbSettingsServiceProviderRef._mergeNewGroup(old_group, new_group);
        expect(group_result).toEqual({
            name:'Auth',
            caption: 'Auth related settings',
            items:[{
                type:'bool',
                name:'radio1',
                value: true,
                default_value: false
            }
            , {
                type:'bool',
                name:'radio2',
                value:false,
                default_value: false
            }
            ]});}));

    it('should merge groups when new group is defined with no items', inject(function(bbSettingsService) {
        localStorage.clear();
        const old_group = {
            name:'Auth',
            caption: 'Auth related settings',
            items:[{
                type:'bool',
                name:'radio1',
                value: true,
                default_value: false
            }
            ]
        };
        const new_group = {
            name:'Auth',
            caption: 'Auth related settings',
            items:[]
        };
        const group_result = bbSettingsServiceProviderRef._mergeNewGroup(old_group, new_group);
        expect(group_result).toEqual({
            name:'Auth',
            caption: 'Auth related settings',
            items:[]});}));

    it('should merge groups when old group is defined with no items', inject(function(bbSettingsService) {
        localStorage.clear();
        const old_group = {
            name:'System',
            caption: 'System related settings',
            items:[]
        };
        const new_group = {
            name:'System',
            caption: 'System related settings',
            items:[{
                type:'bool',
                name:'checkbox_system',
                default_value: false
            }
            , {
                type:'bool',
                name:'checkbox_system2',
                default_value: false
            }
            ]
        };
        const group_result = bbSettingsServiceProviderRef._mergeNewGroup(old_group, new_group);
        expect(group_result).toEqual({
            name:'System',
            caption: 'System related settings',
            items:[{
                type:'bool',
                name:'checkbox_system',
                value:false,
                default_value: false
            }
            , {
                type:'bool',
                name:'checkbox_system2',
                value:false,
                default_value: false
            }
            ]});}));

    it('should merge groups when new group is undefined', inject(function(bbSettingsService) {
        localStorage.clear();
        const old_group = {
            name:'System',
            caption: 'System related settings',
            items:[{
                type:'bool',
                name:'checkbox_system',
                default_value: false
            }
            , {
                type:'bool',
                name:'checkbox_system2',
                default_value: false
            }
            ]
        };
        const group_result = bbSettingsServiceProviderRef._mergeNewGroup(old_group, undefined);
        expect(group_result).toBeUndefined();
    })
    );

    it('should merge groups when old group is undefined', inject(function(bbSettingsService) {
        localStorage.clear();
        const new_group = {
            name:'Auth',
            caption: 'Auth related settings',
            items:[{
                type:'bool',
                name:'radio1',
                default_value: false
            }
            , {
                type:'bool',
                name:'radio2',
                default_value: false
            }
            ]
        };
        const group_result = bbSettingsServiceProviderRef._mergeNewGroup(undefined, new_group);
        expect(group_result).toEqual({
            name:'Auth',
            caption: 'Auth related settings',
            items:[{
                type:'bool',
                name:'radio1',
                value: false,
                default_value: false
            }
            , {
                type:'bool',
                name:'radio2',
                value: false,
                default_value: false
            }
            ]});}));

    it('should not add a group without name', inject(function(bbSettingsService) {
        localStorage.clear();
        const group = {
            caption: 'Auth related settings',
            items:[{
                type:'bool',
                name:'radio1',
                default_value: false
            }
            , {
                type:'bool',
                name:'radio2',
                default_value: false
            }
            ]
        };
        const exceptionRun = function() {
            let group_result;
            return group_result = bbSettingsServiceProviderRef.addSettingsGroup(group);
        };
        expect(exceptionRun).toThrow();
    })
    );


    it('should merge groups when new group has item with no default value', inject(function(bbSettingsService) {
        localStorage.clear();
        const old_group = {
            name:'System',
            caption: 'System related settings',
            items:[]
        };
        const new_group = {
            name:'System',
            caption: 'System related settings',
            items:[{
                type:'bool',
                name:'checkbox_system',
                default_value: false
            }
            , {
                type:'bool',
                name:'checkbox_system2'
            }
            ]
        };
        const group_result = bbSettingsServiceProviderRef._mergeNewGroup(old_group, new_group);
        expect(group_result).toEqual({
            name:'System',
            caption: 'System related settings',
            items:[{
                type:'bool',
                name:'checkbox_system',
                value: false,
                default_value: false
            }
            , {
                type:'bool',
                name:'checkbox_system2',
                value: undefined
            }
            ]});}));


    it('should generate correct settings', inject(function(bbSettingsService) {
        const groups = bbSettingsService.getSettingsGroups();
        expect(groups['Release']).toEqual({
            name:'Release',
            caption: 'Release related settings',
            items:[{
                type:'bool',
                name:'checkbox_release',
                value:false,
                default_value: false
            }
            , {
                type:'bool',
                name:'checkbox_release2',
                value: false,
                default_value: false
            }
            , {
                type:'bool',
                name:'checkbox_release3',
                value:false,
                default_value: false
            }
            , {
                type:'choices',
                name,
                default_value: 'radio1',
                value:'radio1',
                answers: [
                    { name: 'radio1' },
                    { name: 'radio2' }
                ]
            }
            ]});}));

    it('should return correct setting', inject(function(bbSettingsService) {
        const userSetting1 = bbSettingsService.getSetting('User.checkbox1');
        const userSetting2 = bbSettingsService.getSetting('User.whatever');
        const userSetting3 = bbSettingsService.getSetting('UserAA.User_checkbox1');
        expect(userSetting1).toBeDefined();
        expect(userSetting2).toBeUndefined();
        expect(userSetting3).toBeUndefined();
    })
    );

    it('should save correct settings', inject(function(bbSettingsService) {
        const checkbox = bbSettingsService.getSetting('User.checkbox1');
        expect(checkbox.value).toBe(false);
        checkbox.value = true;
        bbSettingsService.save();
        const storageGroups = angular.fromJson(localStorage.getItem('settings'));
        const storageCheckbox = storageGroups['User'].items[0].value;
        expect(storageCheckbox).toBeTruthy();
    })
    );

    it('should be overriden by master.cfg', inject(function(bbSettingsService) {
        let to_override = bbSettingsService.getSetting('User.config_overriden');
        expect(to_override.value).toEqual(100);
        to_override.value = 200;
        bbSettingsService.save();
        const storageGroups = angular.fromJson(localStorage.getItem('settings'));
        to_override = storageGroups['User'].items[1].value;
        expect(to_override).toEqual(200);
    })
    );
});
