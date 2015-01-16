class bbSettings extends Provider
    constructor: ->
        @groups = {}


    mergeNewGroup: (oldGroup, newGroup) ->
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
        newGroup = @mergeNewGroup(storageGroups[group.name], group)
        @groups[newGroup.name] = newGroup
        return @groups

    $get: [ ->
        self = @
        return {
            getSettingsGroups: -> 
                self.groups
            save: ->
                localStorage.setItem('settings', angular.toJson(self.groups))
                null
            getSetting: (settingSelector) ->
                groupName = settingSelector.split('.')[0]
                settingName = settingSelector.split('.')[1]
                if self.groups[groupName]?
                    return setting for setting in self.groups[groupName].items when setting.name is settingName
                else
                    return undefined
        }
    ]
