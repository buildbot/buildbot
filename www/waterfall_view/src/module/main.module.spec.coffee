beforeEach ->
    module 'waterfall_view'

describe 'Waterfall view controller', ->
    createController = scope = $rootScope = $state = null

    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        scope = $rootScope.$new()
        $compile = $injector.get('$compile')
        $controller = $injector.get('$controller')
        $state = $injector.get('$state')

        elem = angular.element('<div></div>')
        elem.append($compile('<ui-view></ui-view>')(scope))

        # Create new controller
        createController = ->
            $controller 'waterfallController as w',
                $scope: scope

    beforeEach(inject(injected))

    it 'should be defined', (done) ->
        $rootScope.$on '$stateChangeSuccess', ->
            createController()
            expect($state.current.name).toBe('waterfall')
            expect(scope.w).toBeDefined()
            done()
        $state.transitionTo('waterfall')
        $rootScope.$digest()

    #it "should load #{config.plugins.waterfall_view.limit} builds", ->
    #    $state.transitionTo('waterfall')
    #    $rootScope.$apply()
    #    expect(scope.w.builds).toBeDefined()
    #    expect(scope.w.builds.length).toBe(config.plugins.waterfall_view.limit)