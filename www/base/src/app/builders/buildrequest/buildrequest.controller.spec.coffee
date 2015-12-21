beforeEach module 'app'

describe 'buildrequest controller', ->
    dataService = $scope = $httpBackend = $rootScope = null
    $timeout = createController = $stateParams = null
    goneto  = null
    # overrride "$state"
    beforeEach module(($provide) ->
        $provide.value "$state", go: (args...) -> goneto = args
        $provide.value "$stateParams", buildrequest: 1
        null  # those module callbacks need to return null!
    )

    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        $scope = $rootScope.$new()
        $timeout = $injector.get('$timeout')
        $stateParams = $injector.get('$stateParams')
        $controller = $injector.get('$controller')
        $q = $injector.get('$q')
        dataService = $injector.get('dataService')
        createController = ->
            return $controller 'buildrequestController',
                $scope: $scope
    beforeEach(inject(injected))

    it 'should query for buildrequest', ->
        dataService.when('buildrequests/1', [{buildrequestid: 1, builderid: 1, buildsetid: 1}])
        dataService.when('builders/1', [{builderid: 1}])
        dataService.when('buildsets/1', [{buildsetid: 1}])
        controller = createController()
        $rootScope.$apply()
        expect(dataService.get).toHaveBeenCalledWith('buildrequests', 1)
        $scope.buildrequest.claimed = true
        dataService.when('builds', {buildrequestid: 1}, [{buildid: 1}, {buildid: 2}])
        $rootScope.$apply()
        expect($scope.builds[0]).toBeDefined()

    it 'should query for builds again if first query returns 0', ->
        dataService.when('buildrequests/1', [{buildrequestid: 1, builderid: 1, buildsetid: 1}])
        dataService.when('builders/1', [{builderid: 1}])
        dataService.when('buildsets/1', [{buildsetid: 1}])
        controller = createController()
        $rootScope.$apply()
        $scope.buildrequest.claimed = true
        dataService.when('builds', {buildrequestid: 1}, [])
        $rootScope.$apply()
        expect($scope.builds.length).toBe(0)

        dataService.when('builds', {buildrequestid: 1}, [{}, {}])
        $timeout.flush()
        $rootScope.$apply()
        expect($scope.builds.length).toBe(2)

    it 'should go to build page if build started', ->
        dataService.when('buildrequests/1', [{buildrequestid: 1, builderid: 3, buildsetid: 1}])
        dataService.when('builders/3', [{builderid: 3}])
        dataService.when('buildsets/1', [{buildsetid: 1}])
        $stateParams.redirect_to_build = 1
        controller = createController()
        $rootScope.$apply()
        $scope.buildrequest.claimed = true
        dataService.when('builds', {buildrequestid: 1}, [{buildid: 1, builderid: 3, number: 1}])
        $timeout.flush()
        $rootScope.$apply()
        expect(goneto).toEqual(['build', { builder : 3, build : 1 }])
