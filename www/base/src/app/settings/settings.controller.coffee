class Settings extends Controller
    constructor: ($scope, config, bbSettingsService) ->
        # All settings definition
        # 

        $scope.settingsGroups = bbSettingsService.getSettingsGroups()
        
        $scope.$watch('settingsGroups', (newGroups) -> 
            bbSettingsService.save()
        , true)

