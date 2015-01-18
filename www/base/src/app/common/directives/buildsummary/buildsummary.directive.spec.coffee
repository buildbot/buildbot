beforeEach module 'app'

describe 'buildsummary controller', ->
    buildbotService = mqService = $scope = $httpBackend = $rootScope = null
    $timeout = createController = $stateParams = results = baseurl = null
    goneto  = null

    injected = ($injector) ->
        $httpBackend = $injector.get('$httpBackend')
        $location = $injector.get('$location')
        decorateHttpBackend($httpBackend)
        results = $injector.get('RESULTS')
        $rootScope = $injector.get('$rootScope')
        $scope = $rootScope.$new()
        $scope.buildid = 1
        $scope.condensed = 0
        $httpBackend.expectDataGET('builds/1')
        $httpBackend.expectDataGET('builders/1')
        $httpBackend.expectDataGET 'builds/1/steps',
            nChilds:2
        $httpBackend.expectDataGET 'steps/1/logs',
            nChilds:2
        mqService = $injector.get('mqService')
        $timeout = $injector.get('$timeout')
        $stateParams = $injector.get('$stateParams')
        $controller = $injector.get('$controller')
        $q = $injector.get('$q')
        baseurl = $location.absUrl().split("#")[0]

        # stub out the actual backend of mqservice
        spyOn(mqService,"setBaseUrl").and.returnValue(null)
        spyOn(mqService,"startConsuming").and.returnValue($q.when( -> ))
        spyOn(mqService,"stopConsuming").and.returnValue(null)
        buildbotService = $injector.get('buildbotService')
        createController = ->
            return $controller '_buildsummaryController',
                '$scope': $scope

    beforeEach(inject(injected))

    afterEach ->
        $httpBackend.verifyNoOutstandingExpectation()
        $httpBackend.verifyNoOutstandingRequest()

    it 'should provide correct isStepDisplayed when condensed', ->
        $scope.condensed = 1
        controller = createController()
        $httpBackend.flush()
        expect($scope.isStepDisplayed(results:results.SUCCESS)).toBe(false)
        expect($scope.isStepDisplayed(results:results.WARNING)).toBe(false)
        expect($scope.isStepDisplayed(results:results.FAILURE)).toBe(false)
        $scope.toggleDetails()
        expect($scope.isStepDisplayed(results:results.SUCCESS)).toBe(false)
        expect($scope.isStepDisplayed(results:results.WARNING)).toBe(true)
        expect($scope.isStepDisplayed(results:results.FAILURE)).toBe(true)
        $scope.toggleDetails()
        expect($scope.isStepDisplayed(results:results.SUCCESS)).toBe(true)
        expect($scope.isStepDisplayed(results:results.WARNING)).toBe(true)
        expect($scope.isStepDisplayed(results:results.FAILURE)).toBe(true)
        $scope.toggleDetails()
        expect($scope.isStepDisplayed(results:results.SUCCESS)).toBe(false)
        expect($scope.isStepDisplayed(results:results.WARNING)).toBe(false)
        expect($scope.isStepDisplayed(results:results.FAILURE)).toBe(false)

    it 'should provide correct isStepDisplayed when not condensed', ->
        $scope.condensed = 0
        controller = createController()
        $httpBackend.flush()
        expect($scope.isStepDisplayed(results:results.SUCCESS)).toBe(true)
        expect($scope.isStepDisplayed(results:results.WARNING)).toBe(true)
        expect($scope.isStepDisplayed(results:results.FAILURE)).toBe(true)
        $scope.toggleDetails()
        expect($scope.isStepDisplayed(results:results.SUCCESS)).toBe(false)
        expect($scope.isStepDisplayed(results:results.WARNING)).toBe(false)
        expect($scope.isStepDisplayed(results:results.FAILURE)).toBe(false)
        $scope.toggleDetails()
        expect($scope.isStepDisplayed(results:results.SUCCESS)).toBe(false)
        expect($scope.isStepDisplayed(results:results.WARNING)).toBe(true)
        expect($scope.isStepDisplayed(results:results.FAILURE)).toBe(true)
        $scope.toggleDetails()

    it 'should provide correct getBuildRequestIDFromURL', ->
        controller = createController()
        $httpBackend.flush()
        expect($scope.getBuildRequestIDFromURL("#{baseurl}#buildrequests/123"))
        .toBe(123)

    it 'should provide correct isBuildRequestURL', ->
        controller = createController()
        $httpBackend.flush()
        expect($scope.isBuildRequestURL("#{baseurl}#buildrequests/123"))
        .toBe(true)
        expect($scope.isBuildRequestURL("http://otherdomain:5000/#buildrequests/123"))
        .toBe(false)
        expect($scope.isBuildRequestURL("#{baseurl}#builds/123"))
        .toBe(false)
        expect($scope.isBuildRequestURL("#{baseurl}#buildrequests/bla"))
        .toBe(false)

    it 'should provide correct isBuildURL', ->
        controller = createController()
        $httpBackend.flush()
        expect($scope.isBuildURL("#{baseurl}#builders/123/builds/123"))
        .toBe(true)
        expect($scope.isBuildURL("#{baseurl}#builders/sdf/builds/123"))
        .toBe(false)
