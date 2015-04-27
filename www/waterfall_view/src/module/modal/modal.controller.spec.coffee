beforeEach ->
    # Mock modalService
    module ($provide) ->
        $provide.service '$modalInstance', -> close: ->
        null

describe 'Waterfall modal controller', ->
    createController = $rootScope = $modalInstance = scope = null

    injected = ($injector) ->
        $controller = $injector.get('$controller')
        $rootScope = $injector.get('$rootScope')
        $modalInstance = $injector.get('$modalInstance')
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

    it 'should call $modalInstance.close on close()', ->
        createController()
        m = scope.m
        spyOn($modalInstance, 'close')
        expect($modalInstance.close).not.toHaveBeenCalled()
        m.close()
        expect($modalInstance.close).toHaveBeenCalled()
