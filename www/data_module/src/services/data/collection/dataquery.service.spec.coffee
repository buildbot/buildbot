describe 'dataquery service', ->
    beforeEach module 'bbData'

    DataQuery = testArray = $rootScope = wrappedDataQuery = undefined
    injected = ($injector) ->
        DataQuery = $injector.get('DataQuery')
        $rootScope = $injector.get('$rootScope')

        testArray = [
                builderid: 1
                buildid: 3
                buildrequestid: 1
                complete: false
                complete_at: null
                started_at: 1417802797
            ,
                builderid: 2
                buildid: 1
                buildrequestid: 1
                complete: true
                complete_at: 1417803429
                started_at: 1417803026
            ,
                builderid: 1
                buildid: 2
                buildrequestid: 1
                complete: true
                complete_at: 1417803038
                started_at: 1417803025
          ]
        class WrappedDataQuery
            filter: (array, query) ->
                q = new DataQuery(query)
                array = angular.copy(array)
                q.filter(array)
                return array
            sort: (array, order) ->
                q = new DataQuery({order})
                array = angular.copy(array)
                q.sort(array, order)
                return array
            limit: (array, limit) ->
                q = new DataQuery({limit})
                array = angular.copy(array)
                q.limit(array, limit)
                return array
        wrappedDataQuery = new WrappedDataQuery()
    beforeEach(inject(injected))

    it 'should be defined', ->
        expect(DataQuery).toBeDefined()

    describe 'filter(array, filters)', ->

        it 'should filter the array (one filter)', ->
            result = wrappedDataQuery.filter(testArray, complete: false)
            expect(result.length).toBe(1)
            expect(result).toContain(testArray[0])

        it 'should filter the array (more than one filters)', ->
            result = wrappedDataQuery.filter(testArray, complete: true, buildrequestid: 1)
            expect(result.length).toBe(2)
            expect(result).toContain(testArray[1])
            expect(result).toContain(testArray[2])

        it 'should filter the array (eq - equal)', ->
            result = wrappedDataQuery.filter(testArray, 'complete__eq': true)
            expect(result.length).toBe(2)
            expect(result).toContain(testArray[1])
            expect(result).toContain(testArray[2])

        it 'should filter the array (two eq)', ->
            result = wrappedDataQuery.filter(testArray, 'buildid__eq': [1, 2])
            expect(result.length).toBe(2)
            expect(result).toContain(testArray[1])
            expect(result).toContain(testArray[2])

        it 'should treat empty eq criteria as no restriction', ->
            result = wrappedDataQuery.filter(testArray, 'buildid__eq': [])
            expect(result.length).toBe(3)

        it 'should filter the array (ne - not equal)', ->
            result = wrappedDataQuery.filter(testArray, 'complete__ne': true)
            expect(result.length).toBe(1)
            expect(result).toContain(testArray[0])

        it 'should filter the array (lt - less than)', ->
            result = wrappedDataQuery.filter(testArray, 'buildid__lt': 3)
            expect(result.length).toBe(2)
            expect(result).toContain(testArray[1])
            expect(result).toContain(testArray[2])

        it 'should filter the array (le - less than or equal to)', ->
            result = wrappedDataQuery.filter(testArray, 'buildid__le': 3)
            expect(result.length).toBe(3)

        it 'should filter the array (gt - greater than)', ->
            result = wrappedDataQuery.filter(testArray, 'started_at__gt': 1417803025)
            expect(result.length).toBe(1)
            expect(result).toContain(testArray[1])

        it 'should filter the array (ge - greater than or equal to)', ->
            result = wrappedDataQuery.filter(testArray, 'started_at__ge': 1417803025)
            expect(result.length).toBe(2)
            expect(result).toContain(testArray[1])
            expect(result).toContain(testArray[2])

        it 'should convert on/off, true/false, yes/no to boolean', ->
            resultTrue = wrappedDataQuery.filter(testArray, complete: true)
            resultFalse = wrappedDataQuery.filter(testArray, complete: false)

            result = wrappedDataQuery.filter(testArray, complete: 'on')
            expect(result).toEqual(resultTrue)
            result = wrappedDataQuery.filter(testArray, complete: 'true')
            expect(result).toEqual(resultTrue)
            result = wrappedDataQuery.filter(testArray, complete: 'yes')
            expect(result).toEqual(resultTrue)

            result = wrappedDataQuery.filter(testArray, complete: 'off')
            expect(result).toEqual(resultFalse)
            result = wrappedDataQuery.filter(testArray, complete: 'false')
            expect(result).toEqual(resultFalse)
            result = wrappedDataQuery.filter(testArray, complete: 'no')
            expect(result).toEqual(resultFalse)

    describe 'sort(array, order)', ->

        it 'should sort the array (one parameter)', ->
            result = wrappedDataQuery.sort(testArray, 'buildid')
            expect(result[0]).toEqual(testArray[1])
            expect(result[1]).toEqual(testArray[2])
            expect(result[2]).toEqual(testArray[0])

        it 'should sort the array (one parameter, - reverse)', ->
            result = wrappedDataQuery.sort(testArray, '-buildid')
            expect(result[0]).toEqual(testArray[0])
            expect(result[1]).toEqual(testArray[2])
            expect(result[2]).toEqual(testArray[1])

        it 'should sort the array (more parameter)', ->
            result = wrappedDataQuery.sort(testArray, ['builderid', '-buildid'])
            expect(result[0]).toEqual(testArray[0])
            expect(result[1]).toEqual(testArray[2])
            expect(result[2]).toEqual(testArray[1])

    describe 'limit(array, limit)', ->

        it 'should slice the array', ->
            result = wrappedDataQuery.limit(testArray, 1)
            expect(result.length).toBe(1)
            expect(result[0]).toEqual(testArray[0])

        it 'should return the array when the limit >= array.length', ->
            result = wrappedDataQuery.limit(testArray, 3)
            expect(result.length).toBe(3)
            expect(result[2]).toEqual(testArray[2])
