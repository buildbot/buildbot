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
        buildbotService.all('buildslaves').bind $scope,
            onchild: (buildslave) ->
                buildslave.some('builds', order: '-started_at', complete: false).bind $scope,
                dest:buildslave

        $scope.settings = bbSettingsService.getSettingsGroup("Slaves")
        $scope.$watch('settings', ->
            bbSettingsService.save()
        , true)

        $scope.slavestatus = {}
        # Updates the status of a given slave
        updateSlaveStatus = (slave) ->
            status = if slave.connected_to.length > 0 then "online" else "not connected"
            # Looking in our scope fields if there's a match
            if status == "online"
                if slave.builds.length > 0
                    status = "running"
                else
                    status = "idle"
            $scope.slavestatus[slave.name] = status

        # Updates the status of all slaves
        updateSlavesStatus = (a, b) ->
            for slave in $scope.buildslaves
                updateSlaveStatus(slave)

        $scope.$watch('buildslaves', updateSlavesStatus, true)



