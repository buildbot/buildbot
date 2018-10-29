class Pendingbuildrequests extends Controller
    constructor: ($log, $scope, dataService, bbSettingsService) ->
        $scope.settings = bbSettingsService.getSettingsGroup("BuildRequests")
        $scope.$watch('settings', ->
            bbSettingsService.save()
        , true)
        buildrequestFetchLimit = $scope.settings.buildrequestFetchLimit.value

        data = dataService.open().closeOnDestroy($scope)
        $scope.buildrequests = data.getBuildrequests(limit: buildrequestFetchLimit, order:'-submitted_at', claimed:false)
        $scope.buildrequests.onNew = (buildrequest) ->
            data.getBuildsets(buildrequest.buildsetid).onNew = (buildset) ->
                buildset.getProperties().onNew = (properties) ->
                    buildrequest.properties = properties
            data.getBuilders(buildrequest.builderid).onNew = (builder) ->
                buildrequest.builder = builder
