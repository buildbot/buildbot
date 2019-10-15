/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('Data utils service', function() {
    beforeEach(angular.mock.module('bbData'));

    let dataUtilsService = undefined;
    const injected = $injector => dataUtilsService = $injector.get('dataUtilsService');

    beforeEach(inject(injected));

    it('should be defined', () => expect(dataUtilsService).toBeDefined());

    describe('capitalize(string)', () =>

        it('should capitalize the parameter string', function() {
            let result = dataUtilsService.capitalize('test');
            expect(result).toBe('Test');

            result = dataUtilsService.capitalize('t');
            expect(result).toBe('T');
        })
    );

    describe('type(arg)', () =>

        it('should return the type of the parameter endpoint', function() {
            let result = dataUtilsService.type('asd/1');
            expect(result).toBe('asd');

            result = dataUtilsService.type('asd/1/bnm');
            expect(result).toBe('bnm');
        })
    );

    describe('singularType(arg)', () =>

        it('should return the singular the type name of the parameter endpoint', function() {
            let result = dataUtilsService.singularType('tests/1');
            expect(result).toBe('test');

            result = dataUtilsService.singularType('tests');
            expect(result).toBe('test');
        })
    );

    describe('socketPath(arg)', () =>

        it('should return the WebSocket subscribe path of the parameter path', function() {
            let result = dataUtilsService.socketPath('asd/1/bnm');
            expect(result).toBe('asd/1/bnm/*/*');

            result = dataUtilsService.socketPath('asd/1');
            expect(result).toBe('asd/1/*');
        })
    );

    describe('socketPathRE(arg)', () =>

        it('should return the WebSocket subscribe path of the parameter path', function() {
            let result = dataUtilsService.socketPathRE('asd/1/*');
            expect(result.test("asd/1/new")).toBeTruthy();

            result = dataUtilsService.socketPathRE('asd/1/bnm/*/*').source;
            expect([
                '^asd\\/1\\/bnm\\/[^\\/]+\\/[^\\/]+$',
                '^asd\\/1\\/bnm\\/[^/]+\\/[^/]+$'
            ]).toContain(result);

            result = dataUtilsService.socketPathRE('asd/1/*').source;
            expect([
                '^asd\\/1\\/[^\\/]+$',
                '^asd\\/1\\/[^/]+$'
            ]).toContain(result);
        })
    );


    describe('restPath(arg)', () =>

        it('should return the rest path of the parameter WebSocket subscribe path', function() {
            let result = dataUtilsService.restPath('asd/1/bnm/*/*');
            expect(result).toBe('asd/1/bnm');

            result = dataUtilsService.restPath('asd/1/*');
            expect(result).toBe('asd/1');
        })
    );

    describe('endpointPath(arg)', () =>

        it('should return the endpoint path of the parameter rest or WebSocket path', function() {
            let result = dataUtilsService.endpointPath('asd/1/bnm/*/*');
            expect(result).toBe('asd/1/bnm');

            result = dataUtilsService.endpointPath('asd/1/*');
            expect(result).toBe('asd');
        })
    );

    describe('copyOrSplit(arrayOrString)', function() {

        it('should copy an array', function() {
            const array = [1, 2, 3];
            const result = dataUtilsService.copyOrSplit(array);
            expect(result).not.toBe(array);
            expect(result).toEqual(array);
        });

        it('should split a string', function() {
            const string = 'asd/123/bnm';
            const result = dataUtilsService.copyOrSplit(string);
            expect(result).toEqual(['asd', '123', 'bnm']);
        });
    });

    describe('unWrap(data, path)', () =>

        it('should return the array of the type based on the path', function() {
            const data = {
                asd: [{'data': 'data'}],
                meta: {}
            };
            let result = dataUtilsService.unWrap(data, 'bnm/1/asd');
            expect(result).toBe(data.asd);

            result = dataUtilsService.unWrap(data, 'bnm/1/asd/2');
            expect(result).toBe(data.asd);
        })
    );

    describe('parse(object)', () =>

        it('should parse fields from JSON', function() {
            const test = {
                a: 1,
                b: 'asd3',
                c: angular.toJson(['a', 1, 2]),
                d: angular.toJson({asd: [], bsd: {}})
            };

            const copy = angular.copy(test);
            copy.c = angular.toJson(copy.c);
            copy.d = angular.toJson(copy.d);

            const parsed = dataUtilsService.parse(test);

            expect(parsed).toEqual(test);
        })
    );

    describe('numberOrString(string)', function() {

        it('should convert a string to a number if possible', function() {
            const result = dataUtilsService.numberOrString('12');
            expect(result).toBe(12);
        });

        it('should return the string if it is not a number', function() {
            const result = dataUtilsService.numberOrString('w3as');
            expect(result).toBe('w3as');
        });
    });

    describe('emailInString(string)', () =>

        it('should return an email from a string', function() {
            let email = dataUtilsService.emailInString('foo <bar@foo.com>');
            expect(email).toBe('bar@foo.com');
            email = dataUtilsService.emailInString('bar@foo.com');
            expect(email).toBe('bar@foo.com');
        })
    );
});
