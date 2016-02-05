describe 'Collection', ->
    beforeEach module 'bbData'

    Collection = $q = $rootScope = tabexService = indexedDBService = c = $timeout = $filter = undefined
    injected = ($injector) ->
        $q = $injector.get('$q')
        $rootScope = $injector.get('$rootScope')
        Collection = $injector.get('Collection')
        $timeout = $injector.get('$timeout')
        $filter = $injector.get('$filter')

    beforeEach(inject(injected))

    describe "simple collection", ->
        beforeEach ->
            c = new Collection('builds')

        it 'should be defined', ->
            expect(Collection).toBeDefined()
            expect(c).toBeDefined()

        it 'should be like an array', ->
            expect(angular.isArray(c)).toBeTruthy()

        it 'should be filterable with angular.filter', ->
            c.from [
                buildid: 1
            ,
                buildid: 2
            ]
            filtered = $filter('filter')(c, {buildid:1})
            expect(filtered.length).toBe(1)

        it 'empty collection should be filterable with angular.filter', ->
            filtered = $filter('filter')(c, {buildid:1})
            expect(filtered.length).toBe(0)

        it 'should have a put function, which does not add twice for the same id', ->
            c.put(buildid: 1)
            expect(c.length).toEqual(1)
            c.put(buildid: 1)
            expect(c.length).toEqual(1)
            c.put(buildid: 2)
            expect(c.length).toEqual(2)

        it 'should have a from function, which iteratively inserts data', ->
            c.from [
                buildid: 1
            ,
                buildid: 2
            ,
                buildid: 2
            ]
            expect(c.length).toEqual(2)

        it "should order the updates correctly", ->
            c.listener k: "builds/1/update", m: {buildid: 1, value:1}
            c.initial [
                buildid: 1
                value: 0
            ]
            expect(c[0].value).toEqual(1)
            c.listener k: "builds/1/update", m: {buildid: 1, value:2}
            expect(c[0].value).toEqual(2)

    describe "queried collection", ->
        beforeEach ->
            c = new Collection('builds', {order:'-buildid', limit:2})

        it 'should have a from function, which iteratively inserts data', ->
            c.from [
                buildid: 1
            ,
                buildid: 2
            ,
                buildid: 2
            ]
            expect(c.length).toEqual(2)
            c.from [
                buildid: 3
            ,
                buildid: 4
            ,
                buildid: 5
            ]
            expect(c.length).toEqual(2)
            expect(c[0].buildid).toEqual(5)
            expect(c[1].buildid).toEqual(4)

        it 'should call the event handlers', ->
            spyOn(c, 'onNew')
            spyOn(c, 'onChange')
            spyOn(c, 'onUpdate')
            c.from [
                buildid: 1
            ,
                buildid: 2
            ,
                buildid: 2
            ]
            $timeout.flush()
            expect(c.onNew.calls.count()).toEqual(2)
            expect(c.onUpdate.calls.count()).toEqual(1)
            expect(c.onChange.calls.count()).toEqual(1)
            c.onNew.calls.reset()
            c.onUpdate.calls.reset()
            c.onChange.calls.reset()
            c.from [
                buildid: 3
            ,
                buildid: 4
            ,
                buildid: 5
            ]
            $timeout.flush()
            expect(c.onNew.calls.count()).toEqual(2)
            expect(c.onUpdate.calls.count()).toEqual(0)
            expect(c.onChange.calls.count()).toEqual(1)


    describe "singleid collection", ->
        beforeEach ->
            c = new Collection('builds/1')

        it "should manage the updates correctly", ->
            c.listener k: "builds/1/update", m: {buildid: 1, value:1}
            c.listener k: "builds/2/update", m: {buildid: 2, value:2}
            c.initial [
                buildid: 1
                value: 0
            ]
            expect(c.length).toEqual(1)
            expect(c[0].value).toEqual(1)
            c.listener k: "builds/1/update", m: {buildid: 1, value:2}
            expect(c[0].value).toEqual(2)
