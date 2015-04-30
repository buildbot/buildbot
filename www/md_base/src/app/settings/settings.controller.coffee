class Settings extends Controller
    groups: []

    constructor: ($scope, bbSettingsService) ->
        @groups = bbSettingsService.getSettingsGroups()
        $scope.$watch('settings.groups', ->
            bbSettingsService.save()
        , true)
    
