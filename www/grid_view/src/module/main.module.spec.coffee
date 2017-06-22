beforeEach ->
    module ($provide) ->
        $provide.service 'resultsService', -> results2class: ->
        null

    # Mock bbSettingsProvider
    module ($provide) ->
        $provide.provider 'bbSettingsService', class
            group = {}
            addSettingsGroup: (g) -> g.items.map (i) ->
                if i.name is 'lazy_limit_waterfall'
                    i.default_value = 2
                group[i.name] = value: i.default_value
            $get: ->
                getSettingsGroup: ->
                    return group
                save: ->
        null
    module 'grid_view'

describe 'Grid view controller', ->
    # Test data
    builders = [
        builderid: 1
        tags: []
    ,
        builderid: 2
        tags: ['a']
    ,
        builderid: 3
        tags: ['a', 'b']
    ,
        builderid: 4
        tags: ['b']
    ]

    builds = [
        buildid: 1
        buildrequestid: 1
        builderid: 1
    ,
        buildid: 2
        buildrequestid: 2
        builderid: 2
    ,
        buildid: 3
        buildrequestid: 3
        builderid: 4
    ,
        buildid: 4
        buildrequestid: 4
        builderid: 3
    ,
        buildid: 5
        buildrequestid: 5
        builderid: 1
    ,
        buildid: 6
        buildrequestid: 6
        builderid: 4
    ,
        buildid: 7
        buildrequestid: 7
        builderid: 3
    ,
        buildid: 8
        buildrequestid: 8
        builderid: 2
    ]

    buildrequests = [
        buildrequestid: 1
        builderid: 1
        buildsetid: 1
    ,
        buildrequestid: 2
        builderid: 2
        buildsetid: 1
    ,
        buildrequestid: 3
        builderid: 1
        buildsetid: 2
    ,
        buildrequestid: 4
        builderid: 3
        buildsetid: 2
    ,
        buildrequestid: 5
        builderid: 4
        buildsetid: 2
    ,
        buildrequestid: 6
        builderid: 4
        buildsetid: 3
    ,
        buildrequestid: 7
        builderid: 3
        buildsetid: 3
    ,
        buildrequestid: 8
        builderid: 2
        buildsetid: 3
    ]

    buildsets = [
        bsid: 1
        sourcestamps: [
            ssid: 1
        ]
    ,
        bsid: 2
        sourcestamps: [
            ssid: 2
        ]
    ,
        bsid: 3
        sourcestamps: [
            ssid: 3
        ]
    ]

    changes = [
        changeid: 3
        branch: 'refs/pull/3333/merge'
        sourcestamp:
            ssid: 3
    ,
        changeid: 1
        branch: 'master'
        sourcestamp:
            ssid: 1
    ,
        changeid: 2
        branch: null
        sourcestamp:
            ssid: 2
    ]

    createController = scope = $rootScope = dataService = null

    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        dataService = $injector.get('dataService')
        scope = $rootScope.$new()
        dataService.when('builds', builds)
        dataService.when('builders', builders)
        dataService.when('changes', changes)
        dataService.when('buildrequests', buildrequests)
        dataService.when('buildsets', buildsets)

        # Create new controller using controller as syntax
        $controller = $injector.get('$controller')
        createController = ->
            return $controller 'gridController as C',
                # Inject controller dependencies
                $scope: scope

    beforeEach(inject(injected))

    it 'should be defined', ->
        createController()
        expect(scope.C).toBeDefined()

    it 'should bind the builds, builders, changes, buildrequests and buildsets to scope', ->
        createController()
        $rootScope.$digest()
        expect(scope.C.builds).toBeDefined()
        expect(scope.C.builds.length).toBe(builds.length)
        expect(scope.C.builders).toBeDefined()
        expect(scope.C.builders.length).toBe(builders.length)
        expect(scope.C.changes).toBeDefined()
        expect(scope.C.changes.length).toBe(changes.length)
        expect(scope.C.buildrequests).toBeDefined()
        expect(scope.C.buildrequests.length).toBe(buildrequests.length)
        expect(scope.C.buildsets).toBeDefined()
        expect(scope.C.buildsets.length).toBe(buildsets.length)

    it 'should list branches', ->
        createController()
        $rootScope.$digest()
        scope.C.onChange()
        expect(scope.branches).toBeDefined()
        expect(scope.branches).toEqual(['refs/pull/3333/merge', 'master'])

    it 'should only list changes of the selected branch', ->
        createController()
        $rootScope.$digest()
        scope.C.branch = 'master'
        scope.C.onChange()
        expect(scope.changes).toBeDefined()
        expect(scope.changes.length).toBe(2)

    it 'should only list builders with builds of the selected branch', ->
        createController()
        $rootScope.$digest()
        scope.C.branch = 'refs/pull/3333/merge'
        scope.C.onChange()
        expect(scope.builders).toBeDefined()
        expect(scope.builders.length).toBe(3)

    it 'should only list builders with the selected tags', ->
        createController()
        $rootScope.$digest()
        scope.C.tags = ['b']
        scope.C.onChange()
        expect(scope.builders).toBeDefined()
        expect(scope.builders.length).toBe(2)
