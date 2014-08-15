beforeEach module 'app'

describe 'recent storage service', ->
    recentStorage = $q = $window = $rootScope = null

    injected = ($injector) ->
        $q = $injector.get('$q')
        $window = $injector.get('$window')
        $rootScope = $injector.get('$rootScope')
        recentStorage = $injector.get('recentStorage')

    beforeEach (inject(injected))

    it 'should store recent builds', (done) ->
        testBuild1 = {link: '/test1', caption: 'test1'}
        testBuild2 = {link: '/test2', caption: 'test2'}
        testBuild3 = {link: '/test3', caption: 'test3'}

        recentStorage.clearAll().then (e) ->
            $q.all([
                recentStorage.addBuild(testBuild1),
                recentStorage.addBuild(testBuild3)
            ])
            .then ->
                recentStorage.getBuilds().then (e) ->
                    resolved = e
                    expect(resolved).not.toBeNull()
                    expect(resolved).toContain(testBuild1)
                    expect(resolved).toContain(testBuild3)
                    expect(resolved).not.toContain(testBuild2)
                    done()
        , ->
            expect($window.indexedDB).toBeUndefined()
            done()
        $rootScope.$digest()

    it 'should store recent builders', (done) ->
        testBuilder1 = {link: '/test1', caption: 'test1'}
        testBuilder2 = {link: '/test2', caption: 'test2'}
        testBuilder3 = {link: '/test3', caption: 'test3'}

        recentStorage.clearAll().then (e) ->
            $q.all([
                recentStorage.addBuilder(testBuilder1),
                recentStorage.addBuilder(testBuilder3)
            ])
            .then ->
                recentStorage.getBuilders().then (e) ->
                    resolved = e
                    expect(resolved).not.toBeNull()
                    expect(resolved).toContain(testBuilder1)
                    expect(resolved).toContain(testBuilder3)
                    expect(resolved).not.toContain(testBuilder2)
                    done()
        , ->
            expect($window.indexedDB).toBeUndefined()
            done()
        $rootScope.$digest()

    it 'should clear all recent builds and builders', (done) ->
        testBuild1 = {link: '/test1', caption: 'test1'}
        testBuild2 = {link: '/test2', caption: 'test2'}
        testBuilder1 = {link: '/test1', caption: 'test1'}
        testBuilder2 = {link: '/test2', caption: 'test2'}

        $q.all([
            recentStorage.addBuild(testBuild1),
            recentStorage.addBuild(testBuild2),
            recentStorage.addBuilder(testBuilder1),
            recentStorage.addBuilder(testBuilder2)
        ])
        .then ->
            recentStorage.clearAll().then (e) ->
                recentStorage.getAll().then (e) ->
                    resolved = e
                    expect(resolved).toBeDefined()
                    expect(resolved.recent_builds.length).toBe(0)
                    expect(resolved.recent_builders.length).toBe(0)
                    done()
        , ->
            expect($window.indexedDB).toBeUndefined()
            done()
        $rootScope.$digest()
