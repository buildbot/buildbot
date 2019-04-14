class Changes
    constructor: ($log, $scope, dataService, bbSettingsService) ->
        $scope.settings = bbSettingsService.getSettingsGroup("Changes")
        $scope.$watch('settings', ->
            bbSettingsService.save()
        , true)
        changesFetchLimit = $scope.settings.changesFetchLimit.value

        data = dataService.open().closeOnDestroy($scope)
        #  unlike other order, this particular order by changeid is optimised by the backend
        $scope.changes = data.getChanges(limit: changesFetchLimit, order:'-changeid')


angular.module('app')
.controller('changesController', ['$log', '$scope', 'dataService', 'bbSettingsService', Changes])