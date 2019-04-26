/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('dataquery service', function() {
    let $rootScope, testArray, wrappedDataQuery;
    beforeEach(angular.mock.module('bbData'));

    let DataQuery = (testArray = ($rootScope = (wrappedDataQuery = undefined)));
    const injected = function($injector) {
        DataQuery = $injector.get('DataQuery');
        $rootScope = $injector.get('$rootScope');

        testArray = [{
                builderid: 1,
                buildid: 3,
                buildrequestid: 1,
                complete: false,
                complete_at: null,
                started_at: 1417802797
            }
            , {
                builderid: 2,
                buildid: 1,
                buildrequestid: 1,
                complete: true,
                complete_at: 1417803429,
                started_at: 1417803026
            }
            , {
                builderid: 1,
                buildid: 2,
                buildrequestid: 1,
                complete: true,
                complete_at: 1417803038,
                started_at: 1417803025
            }
          ];
        class WrappedDataQuery {
            filter(array, query) {
                const q = new DataQuery(query);
                array = angular.copy(array);
                q.filter(array);
                return array;
            }
            sort(array, order) {
                const q = new DataQuery({order});
                array = angular.copy(array);
                q.sort(array, order);
                return array;
            }
            limit(array, limit) {
                const q = new DataQuery({limit});
                array = angular.copy(array);
                q.limit(array, limit);
                return array;
            }
        }
        wrappedDataQuery = new WrappedDataQuery();
    };
    beforeEach(inject(injected));

    it('should be defined', () => expect(DataQuery).toBeDefined());

    describe('filter(array, filters)', function() {

        it('should filter the array (one filter)', function() {
            const result = wrappedDataQuery.filter(testArray, {complete: false});
            expect(result.length).toBe(1);
            expect(result).toContain(testArray[0]);
        });

        it('should filter the array (more than one filters)', function() {
            const result = wrappedDataQuery.filter(testArray, {complete: true, buildrequestid: 1});
            expect(result.length).toBe(2);
            expect(result).toContain(testArray[1]);
            expect(result).toContain(testArray[2]);
        });

        it('should filter the array (eq - equal)', function() {
            const result = wrappedDataQuery.filter(testArray, {'complete__eq': true});
            expect(result.length).toBe(2);
            expect(result).toContain(testArray[1]);
            expect(result).toContain(testArray[2]);
        });

        it('should filter the array (two eq)', function() {
            const result = wrappedDataQuery.filter(testArray, {'buildid__eq': [1, 2]});
            expect(result.length).toBe(2);
            expect(result).toContain(testArray[1]);
            expect(result).toContain(testArray[2]);
        });

        it('should treat empty eq criteria as no restriction', function() {
            const result = wrappedDataQuery.filter(testArray, {'buildid__eq': []});
            expect(result.length).toBe(3);
        });

        it('should filter the array (ne - not equal)', function() {
            const result = wrappedDataQuery.filter(testArray, {'complete__ne': true});
            expect(result.length).toBe(1);
            expect(result).toContain(testArray[0]);
        });

        it('should filter the array (lt - less than)', function() {
            const result = wrappedDataQuery.filter(testArray, {'buildid__lt': 3});
            expect(result.length).toBe(2);
            expect(result).toContain(testArray[1]);
            expect(result).toContain(testArray[2]);
        });

        it('should filter the array (le - less than or equal to)', function() {
            const result = wrappedDataQuery.filter(testArray, {'buildid__le': 3});
            expect(result.length).toBe(3);
        });

        it('should filter the array (gt - greater than)', function() {
            const result = wrappedDataQuery.filter(testArray, {'started_at__gt': 1417803025});
            expect(result.length).toBe(1);
            expect(result).toContain(testArray[1]);
        });

        it('should filter the array (ge - greater than or equal to)', function() {
            const result = wrappedDataQuery.filter(testArray, {'started_at__ge': 1417803025});
            expect(result.length).toBe(2);
            expect(result).toContain(testArray[1]);
            expect(result).toContain(testArray[2]);
        });

        it('should convert on/off, true/false, yes/no to boolean', function() {
            const resultTrue = wrappedDataQuery.filter(testArray, {complete: true});
            const resultFalse = wrappedDataQuery.filter(testArray, {complete: false});

            let result = wrappedDataQuery.filter(testArray, {complete: 'on'});
            expect(result).toEqual(resultTrue);
            result = wrappedDataQuery.filter(testArray, {complete: 'true'});
            expect(result).toEqual(resultTrue);
            result = wrappedDataQuery.filter(testArray, {complete: 'yes'});
            expect(result).toEqual(resultTrue);

            result = wrappedDataQuery.filter(testArray, {complete: 'off'});
            expect(result).toEqual(resultFalse);
            result = wrappedDataQuery.filter(testArray, {complete: 'false'});
            expect(result).toEqual(resultFalse);
            result = wrappedDataQuery.filter(testArray, {complete: 'no'});
            expect(result).toEqual(resultFalse);
        });
    });

    describe('sort(array, order)', function() {

        it('should sort the array (one parameter)', function() {
            const result = wrappedDataQuery.sort(testArray, 'buildid');
            expect(result[0]).toEqual(testArray[1]);
            expect(result[1]).toEqual(testArray[2]);
            expect(result[2]).toEqual(testArray[0]);
        });

        it('should sort the array (one parameter, - reverse)', function() {
            const result = wrappedDataQuery.sort(testArray, '-buildid');
            expect(result[0]).toEqual(testArray[0]);
            expect(result[1]).toEqual(testArray[2]);
            expect(result[2]).toEqual(testArray[1]);
        });

        it('should sort the array (more parameter)', function() {
            const result = wrappedDataQuery.sort(testArray, ['builderid', '-buildid']);
            expect(result[0]).toEqual(testArray[0]);
            expect(result[1]).toEqual(testArray[2]);
            expect(result[2]).toEqual(testArray[1]);
        });
    });

    describe('limit(array, limit)', function() {

        it('should slice the array', function() {
            const result = wrappedDataQuery.limit(testArray, 1);
            expect(result.length).toBe(1);
            expect(result[0]).toEqual(testArray[0]);
        });

        it('should return the array when the limit >= array.length', function() {
            const result = wrappedDataQuery.limit(testArray, 3);
            expect(result.length).toBe(3);
            expect(result[2]).toEqual(testArray[2]);
        });
    });
});
