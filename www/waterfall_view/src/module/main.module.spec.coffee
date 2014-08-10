if window.__karma__?
    beforeEach ->
        # Mocked module dependencies
        angular.module 'buildbot.common', []
        angular.module 'ngAnimate', []
        # Mock modalService
        module ($provide) ->
            $provide.service '$modal', ->
            $provide.service '$modalInstance', ->
            null

        module 'buildbot.waterfall_view'

    describe 'Waterfall view', ->
        $state = null

        injected = ($injector) ->
            $state = $injector.get('$state')

        beforeEach(inject(injected))

        it 'should register a new state with the correct configuration', ->
            name = 'waterfall'
            state = $state.get().pop()
            data = state.data
            expect(state.controller).toBe("#{name}Controller")
            expect(state.controllerAs).toBe('w')
            expect(state.templateUrl).toBe("buildbot.waterfall_view/views/#{name}.html")
            expect(state.url).toBe("/#{name}")
            expect(data.tabid).toBe(name)
            expect(data.tabhash).toBe("##{name}")

    describe 'Waterfall view controller', ->
        createController = scope = $rootScope = null

        # Test data

        builders = [
            builderid: 1
        ,
            builderid: 2
        ,
            builderid: 3
        ,
            builderid: 4
        ]
        builders.one = ->

        builds = [
            buildid: 1
            builderid: 1
            buildrequestid: 1
            all: -> bind: -> then: ->
        ,
            buildid: 2
            builderid: 2
            buildrequestid: 1
            all: -> bind: -> then: ->
        ,
            buildid: 3
            builderid: 4
            buildrequestid: 2
            all: -> bind: -> then: ->
        ,
            buildid: 4
            builderid: 3
            buildrequestid: 2
            all: -> bind: -> then: ->
        ]

        buildrequests = [
            builderid: 1
            buildrequestid: 1
            buildsetid: 1
        ,
            builderid: 1
            buildrequestid: 2
            buildsetid: 1
        ,
            builderid: 1
            buildrequestid: 3
            buildsetid: 2
        ]

        injected = ($injector) ->
            $rootScope = $injector.get('$rootScope')
            scope = $rootScope.$new()
            $controller = $injector.get('$controller')
            $window = $injector.get('$window')
            $q = $injector.get('$q')

            deferred = $q.defer()
            deferred.resolve []
            d3ServiceFake = ->
            d3ServiceFake.get = -> deferred.promise

            # Mocked service
            buildbotServiceMock =
                some: ->
                    getList: -> then: ->
                    bind: -> then: ->
                all: (string) =>
                    deferred = $q.defer()
                    switch string
                        when 'builds'
                            deferred.resolve builds
                        when 'builders'
                            deferred.resolve builders
                        when 'buildrequests'
                            deferred.resolve buildrequests
                        else
                            deferred.resolve []
                    bind: -> deferred.promise
                    getList: ->

            # Create new controller using controller as syntax
            createController = ->
                $controller 'waterfallController as w',
                    # Inject controller dependencies
                    $scope: scope
                    $window: $window
                    $q: $q
                    d3Service: d3ServiceFake
                    buildbotService: buildbotServiceMock
                    config: plugins: waterfall_view: {}

        beforeEach(inject(injected))

        it 'should be defined', ->
            createController()
            expect(scope.w).toBeDefined()

        # TODO write tests
