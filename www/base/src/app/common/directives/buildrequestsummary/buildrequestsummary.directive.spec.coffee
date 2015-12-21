beforeEach module 'app'

describe 'buildrequest summary controller', ->
    $scope = $rootScope = $q = $timeout = null
    goneto = createController = null
    dataService = null
    # overrride "$state"
    beforeEach module(($provide) ->
        $provide.value "$state",
                        go: (args...) -> goneto = args
        null  # those module callbacks need to return null!
    )

    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        $scope = $rootScope.$new()
        $scope.buildrequestid = 1
        $timeout = $injector.get('$timeout')
        $controller = $injector.get('$controller')
        $q = $injector.get('$q')
        dataService = $injector.get('dataService')
        # stub out the actual backend of mqservice
        createController = ->
            return $controller '_buildrequestsummaryController',
                $scope: $scope
    beforeEach(inject(injected))

    it 'should get the buildrequest', ->
        buildrequests = [{buildrequestid: 1}]
        dataService.when('buildrequests/1', buildrequests)
        expect(dataService.get).not.toHaveBeenCalled()
        controller = createController()
        expect(dataService.get).toHaveBeenCalledWith('buildrequests', $scope.buildrequestid)
        $scope.$apply()
        expect($scope.buildrequest.buildrequestid).toBe(1)

    it 'should query for builds again if first query returns 0', ->
        buildrequests = [{buildrequestid: 1}]
        dataService.when('buildrequests/1', buildrequests)
        builds = []
        dataService.when('builds', {buildrequestid: 1}, builds)

        controller = createController()
        expect(dataService.get).toHaveBeenCalledWith('buildrequests', 1)
        $scope.$apply()

        $scope.buildrequest.claimed = true
        $scope.$apply()
        expect(dataService.get).toHaveBeenCalledWith('builds', {buildrequestid: 1})
        lastCount = dataService.get.calls.count()
        expect($scope.builds.length).toBe(builds.length)

        builds = [{buildid: 1}, {buildid: 2}]
        dataService.when('builds', {buildrequestid: 1}, builds)

        $timeout.flush()
        expect(dataService.get).toHaveBeenCalledWith('builds', {buildrequestid: 1})
        count = dataService.get.calls.count()
        expect(count).toBe(lastCount + 1)
        expect($scope.builds.length).toBe(builds.length)
