/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('Rest service', function() {
    let $httpBackend;
    beforeEach(angular.module('bbData'));
    beforeEach(() =>
        module($provide => $provide.constant('API', '/api/'))
    );

    let restService = ($httpBackend = undefined);
    const injected = function($injector) {
        restService = $injector.get('restService');
        return $httpBackend = $injector.get('$httpBackend');
    };

    beforeEach(inject(injected));

    afterEach(function() {
        $httpBackend.verifyNoOutstandingExpectation();
        return $httpBackend.verifyNoOutstandingRequest();
    });

    it('should be defined', () => expect(restService).toBeDefined());

    it('should make an ajax GET call to /api/endpoint', function() {
        const response = {a: 'A'};
        $httpBackend.whenGET('/api/endpoint').respond(response);

        let gotResponse = null;
        restService.get('endpoint').then(r => gotResponse = r);
        expect(gotResponse).toBeNull();

        $httpBackend.flush();
        return expect(gotResponse).toEqual(response);
    });

    it('should make an ajax GET call to /api/endpoint with parameters', function() {
        const params = {key: 'value'};
        $httpBackend.whenGET('/api/endpoint?key=value').respond(200);

        restService.get('endpoint', params);
        return $httpBackend.flush();
    });

    it('should reject the promise on error', function() {
        const error = 'Internal server error';
        $httpBackend.expectGET('/api/endpoint').respond(500, error);

        let gotResponse = null;
        restService.get('endpoint').then(response => gotResponse = response
        , reason => gotResponse = reason);

        $httpBackend.flush();
        return expect(gotResponse).toBe(error);
    });

    it('should make an ajax POST call to /api/endpoint', function() {
        const response = {};
        const data = {b: 'B'};
        $httpBackend.expectPOST('/api/endpoint', data).respond(response);

        let gotResponse = null;
        restService.post('endpoint', data).then(r => gotResponse = r);

        $httpBackend.flush();
        return expect(gotResponse).toEqual(response);
    });

    it('should reject the promise when the response is not valid JSON', function() {
        const response = 'aaa';

        const data = {b: 'B'};
        $httpBackend.expectPOST('/api/endpoint', data).respond(response);

        let gotResponse = null;
        restService.post('endpoint', data).then(response => gotResponse = response
        , reason => gotResponse = reason);

        $httpBackend.flush();
        expect(gotResponse).not.toBeNull();
        return expect(gotResponse).not.toEqual(response);
    });

    return it('should reject the promise when cancelled', inject(function($rootScope) {
        $httpBackend.expectGET('/api/endpoint').respond({});

        let gotResponse = null;
        let rejected = false;
        const request = restService.get('endpoint');
        request.then(response => gotResponse = response
        , reason => rejected = true);

        request.cancel();
        $rootScope.$apply();
        expect(gotResponse).toBeNull();
        return expect(rejected).toBe(true);
    })
    );
});
