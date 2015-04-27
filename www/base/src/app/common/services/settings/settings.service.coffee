class bbSettings extends Provider('common')
    constructor: ->
        @groups = {}


    _mergeNewGroup: (oldGroup, newGroup) ->
        if not newGroup?
            return undefined
        if not oldGroup?
            item.value = item.default_value for item in newGroup.items
            return newGroup
        else
            for newItem in newGroup.items
                newItem.value = newItem.default_value
                for oldItem in oldGroup.items
                    if newItem.name is oldItem.name and oldItem.value?
                        newItem.value = oldItem.value
            return newGroup

    addSettingsGroup: (group) ->
        storageGroups = angular.fromJson(localStorage.getItem('settings')) || {}
        unless group.name?
            throw Error("Group (with caption : #{group.caption}) must have a correct name property.")
        newGroup = @_mergeNewGroup(storageGroups[group.name], group)
        @groups[newGroup.name] = newGroup
        return @groups

    $get: [ ->
        self = @
        return {
            getSettingsGroups: ->
                self.groups
            getSettingsGroup: (group)->
                ret = {}
                for item in self.groups[group].items
                    ret[item.name] = item
                return ret
            save: ->
                localStorage.setItem('settings', angular.toJson(self.groups))
                null
            getSetting: (settingSelector) ->
                groupAndSettingName = settingSelector.split('.')
                groupName = groupAndSettingName[0]
                settingName = groupAndSettingName[1]
                if self.groups[groupName]?
                    return setting for setting in self.groups[groupName].items when setting.name is settingName
                else
                    return undefined
        }
    ]
