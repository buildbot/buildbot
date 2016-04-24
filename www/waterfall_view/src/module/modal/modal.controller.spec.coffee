beforeEach ->
    # Mock modalService
    module ($provide) ->
        $provide.service '$uibModalInstance', -> close: ->
        null

describe 'Waterfall modal controller', ->
    createController = $rootScope = $uibModalInstance = scope = null

    injected = ($injector) ->
        $controller = $injector.get('$controller')
        $rootScope = $injector.get('$rootScope')
        $uibModalInstance = $injector.get('$uibModalInstance')
        scope = $rootScope.$new()

        createController = ->
            $controller 'waterfallModalController as m',
                $scope: scope
                selectedBuild: {}

    beforeEach(inject(injected))

    it 'should be defined', ->
        createController()
        m = scope.m
        expect(m).toBeDefined()
        # close function should be to defined
        expect(m.close).toBeDefined()
        expect(typeof m.close).toBe('function')

    it 'should call close() on stateChangeStart event', ->
        createController()
        m = scope.m
        spyOn(m, 'close')
        $rootScope.$broadcast('$stateChangeStart')
        expect(m.close).toHaveBeenCalled()

    it 'should call $uibModalInstance.close on close()', ->
        createController()
        m = scope.m
        spyOn($uibModalInstance, 'close')
        expect($uibModalInstance.close).not.toHaveBeenCalled()
        m.close()
        expect($uibModalInstance.close).toHaveBeenCalled()
