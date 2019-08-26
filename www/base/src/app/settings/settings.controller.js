/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class SettingsController {
    constructor($scope, bbSettingsService) {
        // All settings definition
        //

        $scope.settingsGroups = bbSettingsService.getSettingsGroups();

        $scope.$watch('settingsGroups', function(newGroups) {
            bbSettingsService.save();
            computeMasterCfgSnippet();
        }
        , true);
        var computeMasterCfgSnippet = function() {
            let code = "c['www']['ui_default_config'] = { \n";
            const object = bbSettingsService.getSettingsGroups();
            for (let groupName in object) {
                const group = object[groupName];
                for (let item of Array.from(group.items)) {
                    if ((item.value !== item.default_value) && (item.value !== null)) {
                        let value = JSON.stringify(item.value);
                        if (value === "true") {
                            value = "True";
                        }
                        if (value === "false") {
                            value = "False";
                        }
                        code += `    '${groupName}.${item.name}': ${value},\n`;
                    }
                }
            }
            code += "}\n";
            return $scope.master_cfg_override_snippet = code;
        };
        computeMasterCfgSnippet();
    }
}


angular.module('app')
.controller('settingsController', ['$scope', 'bbSettingsService', SettingsController]);
