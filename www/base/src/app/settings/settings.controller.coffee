class Settings extends Controller
    constructor: ($scope, bbSettingsService) ->
        # All settings definition
        # 

        $scope.settingsGroups = bbSettingsService.getSettingsGroups()
        
        $scope.$watch('settingsGroups', (newGroups) -> 
            bbSettingsService.save()
        , true)

