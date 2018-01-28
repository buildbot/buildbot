class Settings extends Controller
    constructor: ($scope, bbSettingsService) ->
        # All settings definition
        #

        $scope.settingsGroups = bbSettingsService.getSettingsGroups()

        $scope.$watch('settingsGroups', (newGroups) ->
            bbSettingsService.save()
            computeMasterCfgSnippet()
        , true)
        computeMasterCfgSnippet = ->
            code = "c['www']['ui_default_config'] = { \n"
            for groupName, group of bbSettingsService.getSettingsGroups()
                for item in group.items
                    if item.value != item.default_value and item.value != null
                        value = JSON.stringify(item.value)
                        if value == "true"
                            value = "True"
                        if value == "false"
                            value = "False"
                        code += "    '#{groupName}.#{item.name}': #{value},\n"
            code += "}\n"
            $scope.master_cfg_override_snippet = code
        computeMasterCfgSnippet()
