class bbSettings extends Provider
    constructor: ->
        storageGroups = angular.fromJson(localStorage.getItem('settings'))
        @groups = if storageGroups? then storageGroups else {}

    format = (item, groupName) ->
        item.value = item.default_value
        item.name = groupName + "_" + item.name
        return item

    addSettingsGroup: (group) ->
        if not @groups[group.name]?
            format(item, group.name) for item in group.items
            @groups[group.name] = group
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
                return setting for setting in self.groups[groupName].items when setting.name is settingName
        }
    ]
