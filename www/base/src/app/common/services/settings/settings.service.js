/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS206: Consider reworking classes to avoid initClass
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class bbSettings {
    static initClass() {

        this.prototype.$get = [ function() {
            let groupAndSettingName, groupName, item, settingName;
            const self = this;
            if (self.ui_default_config != null) {
                for (let settingSelector in self.ui_default_config) {
                    const v = self.ui_default_config[settingSelector];
                    groupAndSettingName = settingSelector.split('.');
                    if (groupAndSettingName.length !== 2) {
                        console.log(`bad setting name ${settingSelector}`);
                        continue;
                    }
                    [groupName, settingName] = Array.from(groupAndSettingName);
                    if ((self.groups[groupName] == null)) {
                        console.log(`bad setting name ${settingSelector}: group does not exist`);
                        continue;
                    }
                    for (item of Array.from(self.groups[groupName].items)) {
                        if ((item.name === settingName) && (item.value === item.default_value)) {
                            item.value = v;
                        }
                    }
                }
            }

            return {
                getSettingsGroups() {
                    return self.groups;
                },
                getSettingsGroup(group){
                    const ret = {};
                    for (item of Array.from(self.groups[group].items)) {
                        ret[item.name] = item;
                    }
                    return ret;
                },
                save() {
                    localStorage.setItem('settings', angular.toJson(self.groups));
                    return null;
                },
                getSetting(settingSelector) {
                    groupAndSettingName = settingSelector.split('.');
                    groupName = groupAndSettingName[0];
                    settingName = groupAndSettingName[1];
                    if (self.groups[groupName] != null) {
                        for (let setting of Array.from(self.groups[groupName].items)) { if (setting.name === settingName) { return setting; } }
                    } else {
                        return undefined;
                    }
                }
            };
        }
        ];
    }
    constructor(config) {
        this.groups = {};
        this.ui_default_config = config.ui_default_config;
    }

    _mergeNewGroup(oldGroup, newGroup) {
        if ((newGroup == null)) {
            return undefined;
        }
        if ((oldGroup == null)) {
            for (let item of Array.from(newGroup.items)) { item.value = item.default_value; }
            return newGroup;
        } else {
            for (let newItem of Array.from(newGroup.items)) {
                newItem.value = newItem.default_value;
                for (let oldItem of Array.from(oldGroup.items)) {
                    if ((newItem.name === oldItem.name) && (oldItem.value != null)) {
                        newItem.value = oldItem.value;
                    }
                }
            }
            return newGroup;
        }
    }

    addSettingsGroup(group) {
        const storageGroups = angular.fromJson(localStorage.getItem('settings')) || {};
        if (group.name == null) {
            throw Error(`Group (with caption : ${group.caption}) must have a correct name property.`);
        }
        const newGroup = this._mergeNewGroup(storageGroups[group.name], group);
        this.groups[newGroup.name] = newGroup;
        return this.groups;
    }
}
bbSettings.initClass();


angular.module('common')
.provider('bbSettingsService', ['config', bbSettings]);
