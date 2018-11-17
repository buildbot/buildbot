class Pendingbuildrequests extends Controller
    constructor: ($log, $scope, dataService, bbSettingsService, buildersService, restService) ->
        $scope.settings = bbSettingsService.getSettingsGroup("BuildRequests")
        buildrequestFetchLimit = $scope.settings.buildrequestFetchLimit.value

        data = dataService.open().closeOnDestroy($scope)
        $scope.buildrequests = data.getBuildrequests(limit: buildrequestFetchLimit, order:'-submitted_at', claimed:false)
        $scope.properties = {}
        $scope.buildrequests.onNew = (buildrequest) ->
            restService.get("buildsets/#{buildrequest.buildsetid}/properties").then (response) ->
                buildrequest.properties = response.properties[0]
                _.assign($scope.properties, response.properties[0])
            buildrequest.builder = buildersService.getBuilder(buildrequest.builderid)