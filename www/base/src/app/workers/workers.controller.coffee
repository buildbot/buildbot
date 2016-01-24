class Workers extends Controller
    constructor: ($scope, dataService, bbSettingsService) ->
        $scope.maybeGetMasterNameFromBuilderMaster = (buildermaster) ->
            activeMasters = 0
            for master in $scope.masters
                if master.active
                    activeMasters += 1

            if activeMasters > 1
                return "(" + $scope.masters.get(buildermaster.masterid).name.split(":")[0] + ")"
            return ""

        data = dataService.open().closeOnDestroy($scope)

        $scope.builders = data.getBuilders()
        $scope.masters = data.getMasters()
        $scope.workers = data.getWorkers()

        $scope.settings = bbSettingsService.getSettingsGroup("Slaves")
        $scope.$watch('settings', ->
            bbSettingsService.save()
        , true)
