beforeEach module 'app'

describe 'inspectdata', ->

    $rootScope = $compile = null

    injected = ($injector) ->
        $compile = $injector.get('$compile')
        $rootScope = $injector.get('$rootScope')

    beforeEach inject injected

    it 'should inspect data correctly', ->
        element = $compile('<inspect-data data="testdata"></inspect-data>')($rootScope)
        $rootScope.$digest()

        rowsContainer = element.children().eq(0)

        # test empty data
        expect(rowsContainer.children().length).toBe(0)

        # test object data
        testdata =
            test_number: 123
            test_string: 'a string to display'
            test_link: 'http://a/link/to/display'
            test_https_link: 'https://a/link/to/display'
            test_object:
                test_obj_value1: 1
                test_obj_value2: 'a string'
                test_obj_value3:
                    a_nested: 'object'

        keys = (k for k, _ of testdata)
        test_obj_json_short = JSON.stringify(testdata.test_object)
        test_obj_json_long = JSON.stringify(testdata.test_object, null, 2)

        element = $compile('<inspect-data data="testdata"></inspect-data>')($rootScope)
        $rootScope.testdata = testdata
        $rootScope.$digest()
        rows = element.children().eq(0).children()

        expect(rows.length).toBe(5)
        for i in [0...5]
            row = rows.eq(i)
            key = row.children().eq(0).text()
            expect(key in keys).toBe(true)
            value = row.children().eq(1)

            if key == 'test_object'
                objvalue = value.children().eq(0)
                expect(objvalue.children().length).toBe(2)
                expect(objvalue.children().eq(0).text()).toBe(test_obj_json_short)
                expect(objvalue.children().eq(1).text()).toBe(test_obj_json_long)
            else
                expect(value.text()).toBe('' + testdata[key])

        # test array data
        list_data = []
        for k, v of testdata
            list_data.push [k, v]

        element = $compile('<inspect-data data="testdata"></inspect-data>')($rootScope)
        $rootScope.testdata = testdata
        $rootScope.$digest()
        rows = element.children().eq(0).children()

        for i in [0...5]
            row = rows.eq(i)
            key = row.children().eq(0).text()
            expect(key).toBe(keys[i])
            value = row.children().eq(1)
            if key == 'test_object'
                objvalue = value.children().eq(0)
                expect(objvalue.children().length).toBe(2)
                expect(objvalue.children().eq(0).text()).toBe(test_obj_json_short)
                expect(objvalue.children().eq(1).text()).toBe(test_obj_json_long)
            else
                expect(value.text()).toBe('' + testdata[key])

        # test collapse and expand object field
        objectfield = rows.eq(4)
        objvalue = objectfield.children().eq(1).children().eq(0)
        
        # initial state: short showing, long hiding
        expect(objvalue.children().eq(0).hasClass('ng-hide')).toBe(false)
        expect(objvalue.children().eq(1).hasClass('ng-hide')).toBe(true)

        # click on the field
        objvalue.triggerHandler('click')
        $rootScope.$digest()

        # expanded state: short hiding, long showing
        expect(objvalue.children().eq(0).hasClass('ng-hide')).toBe(true)
        expect(objvalue.children().eq(1).hasClass('ng-hide')).toBe(false)

        # click again to collapse
        objvalue.triggerHandler('click')
        $rootScope.$digest()

        # back to collapsed
        expect(objvalue.children().eq(0).hasClass('ng-hide')).toBe(false)
        expect(objvalue.children().eq(1).hasClass('ng-hide')).toBe(true)
