beforeEach module 'app'

describe 'buildrequest controller', ->
    dataService = $scope = $rootScope = null
    createController = $stateParams = modal = $httpBackend = $timeout = null

    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        $scope = $rootScope.$new()
        $timeout = $injector.get('$timeout')
        $controller = $injector.get('$controller')
        $q = $injector.get('$q')
        dataService = $injector.get('dataService')
        $httpBackend = $injector.get('$httpBackend')

        modal = {}
        createController = ->
            return $controller 'forceDialogController',
                $scope: $scope
                builderid: 1
                schedulerid: 'forcesched'
                modal: modal
    beforeEach(inject(injected))

    it 'should query for forcecheduler', ->
        dataService.when('forceschedulers/forcesched', [{all_fields:['foo': 'int']}])
        controller = createController()
        $rootScope.$apply()

    it 'should call forcecheduler control api when ok', ->
        dataService.when('forceschedulers/forcesched', [{name: "forcesched", all_fields:['foo': 'int']}])
        controller = createController()
        $timeout.flush()
        $httpBackend.when('POST', 'api/v2/forceschedulers/forcesched') .respond("{}")
        $scope.ok()
        $rootScope.$apply()
