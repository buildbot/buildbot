class Buildslaves extends Controller
    constructor: ($scope, dataService, bbSettingsService) ->
        $scope.maybeGetMasterNameFromBuilderMaster = (buildermaster) ->
            activeMasters = 0
            for master in $scope.masters
                if master.active
                    activeMasters += 1

            if activeMasters > 1
                return "(" + $scope.mastersById[buildermaster.masterid].name.split(":")[0] + ")"
            return ""

        data = dataService.open($scope)

        $scope.buildersById = {}
        data.getBuilders().then (builders) ->
            $scope.builders = builders
            builders.forEach (builder) ->
                $scope.buildersById[builder.builderid] = builder

        $scope.mastersById = {}
        data.getMasters().then (masters) ->
            $scope.masters = masters
            masters.forEach (master) ->
                $scope.mastersById[master.masterid] = master

        $scope.buildslaves = data.getBuildslaves().getArray()

        $scope.settings = bbSettingsService.getSettingsGroup("Slaves")
        $scope.$watch('settings', ->
            bbSettingsService.save()
        , true)
