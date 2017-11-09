beforeEach module 'app'

describe 'buildrequest summary controller', ->
    $scope = $rootScope = $q = $timeout = null
    goneto = createController = null
    dataService = null
    # override "$state"
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
        buildrequests = [{buildrequestid: 1, builderid: 2, buildsetid: 3}]
        dataService.expect('buildrequests/1', buildrequests)
        dataService.expect('buildsets/3', buildrequests)
        dataService.expect('builders/2', buildrequests)
        expect(dataService.get).not.toHaveBeenCalled()
        controller = createController()
        $timeout.flush()
        dataService.verifyNoOutstandingExpectation()
        expect($scope.buildrequest.buildrequestid).toBe(1)

    it 'should query for builds again if first query returns 0', ->
        buildrequests = [{buildrequestid: 1, builderid: 2, buildsetid: 3}]
        dataService.expect('buildrequests/1', buildrequests)
        dataService.expect('buildsets/3', buildrequests)
        dataService.expect('builders/2', buildrequests)
        builds = []

        controller = createController()
        $timeout.flush()
        dataService.verifyNoOutstandingExpectation()

        dataService.expect('builds', {buildrequestid: 1}, builds)

        $scope.$apply ->
            $scope.buildrequest.claimed = true
        $timeout.flush()

        dataService.verifyNoOutstandingExpectation()
        expect($scope.builds.length).toBe(builds.length)

        builds = [{buildid: 1, buildrequestid: 1}, {buildid: 2, buildrequestid: 1}]
        $scope.builds.from(builds)

        $timeout.flush()
        dataService.verifyNoOutstandingExpectation()
        expect($scope.builds.length).toBe(builds.length)
