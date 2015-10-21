class Buildslaves extends Controller
    constructor: ($scope, buildbotService, bbSettingsService) ->
        $scope.maybeGetMasterNameFromBuilderMaster = (buildermaster) ->
            activeMasters = 0
            for master in $scope.masters
                if master.active
                    activeMasters += 1

            if activeMasters > 1
                return "(" + $scope.mastersById[buildermaster.masterid].name.split(":")[0] + ")"
            return ""
        $scope.buildersById = {}
        buildbotService.all('builders').bind $scope,
            onchild: (builder) ->
                $scope.buildersById[builder.builderid] = builder
        $scope.mastersById = {}
        buildbotService.all('masters').bind $scope,
            onchild: (master) ->
                $scope.mastersById[master.masterid] = master
        buildbotService.all('buildslaves').bind($scope)

        $scope.settings = bbSettingsService.getSettingsGroup("Slaves")
        $scope.$watch('settings', ->
            bbSettingsService.save()
        , true)
