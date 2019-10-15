/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS205: Consider reworking code to avoid use of IIFEs
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('Data service', function() {
    let $httpBackend, $q, $rootScope, $timeout, ENDPOINTS, restService, socketService;
    beforeEach(angular.mock.module('bbData'));

    let dataService = (restService = (socketService = (ENDPOINTS = ($rootScope = ($q = ($httpBackend = ($timeout = null)))))));
    const injected = function($injector) {
        dataService = $injector.get('dataService');
        restService = $injector.get('restService');
        $timeout = $injector.get('$timeout');
        socketService = $injector.get('socketService');
        ENDPOINTS = $injector.get('ENDPOINTS');
        $rootScope = $injector.get('$rootScope');
        $q = $injector.get('$q');
        $httpBackend = $injector.get('$httpBackend');
    };

    beforeEach(inject(injected));

    it('should be defined', () => expect(dataService).toBeDefined());

    it('should have getXxx functions for endpoints', () =>
        (() => {
            const result = [];
            for (let e of Array.from(ENDPOINTS)) {
                const E = e[0].toUpperCase() + e.slice(1).toLowerCase();
                expect(dataService[`get${E}`]).toBeDefined();
                result.push(expect(angular.isFunction(dataService[`get${E}`])).toBeTruthy());
            }
            result;
        })()
    );

    describe('get()', function() {
        it('should return a collection', function() {
            const ret = dataService.getBuilds();
            expect(ret.length).toBeDefined();
        });

        it('should call get for the rest api endpoint', function() {
            const d = $q.defer();
            spyOn(restService, 'get').and.returnValue(d.promise);
            expect(restService.get).not.toHaveBeenCalled();
            $rootScope.$apply(() => dataService.get('asd', {subscribe: false}));
            // the query should not contain the subscribe field
            expect(restService.get).toHaveBeenCalledWith('asd', {});
        });

        it('should send startConsuming with the socket path', function() {
            const data = dataService.open();
            const p = $q.resolve([]);
            spyOn(socketService, 'send').and.returnValue(p);
            spyOn(restService, 'get').and.returnValue(p);
            expect(socketService.send).not.toHaveBeenCalled();
            $rootScope.$apply(() => data.getBuilds());
            expect(socketService.send).toHaveBeenCalledWith({
                cmd: 'startConsuming',
                path: 'builds/*/*'
            });
            socketService.send.calls.reset();

            $rootScope.$apply(() => data.getBuilds(1));
            expect(socketService.send).toHaveBeenCalledWith({
                cmd: 'startConsuming',
                path: 'builds/1/*'
            });
            // get same build again, it should not register again
            socketService.send.calls.reset();
            $rootScope.$apply(() => data.getBuilds(1));
            expect(socketService.send).not.toHaveBeenCalled();

            // now we close the accessor, and we should send stopConsuming
            $rootScope.$apply(() => data.close());
            expect(socketService.send).toHaveBeenCalledWith({
                cmd: 'stopConsuming',
                path: 'builds/*/*'
            });
            expect(socketService.send).toHaveBeenCalledWith({
                cmd: 'stopConsuming',
                path: 'builds/1/*'
            });
        });


        it('should not call startConsuming when {subscribe: false} is passed in', function() {
            const d = $q.defer();
            spyOn(restService, 'get').and.returnValue(d.promise);
            spyOn(socketService, 'send').and.returnValue(d.promise);
            expect(socketService.send).not.toHaveBeenCalled();
            $rootScope.$apply(() => dataService.getBuilds({subscribe: false}));
            expect(socketService.send).not.toHaveBeenCalled();
        });

        it('should add the new instance on /new WebSocket message', function() {
            spyOn(restService, 'get').and.returnValue($q.resolve({builds: []}));
            let builds = null;
            $rootScope.$apply(() => builds = dataService.getBuilds({subscribe: false}));
            socketService.eventStream.push({
                k: 'builds/111/new',
                m: { asd: 111
            }
            });
            expect(builds.pop().asd).toBe(111);
        });
    });

    describe('control(method, params)', () =>

        it('should send a jsonrpc message using POST', function() {
            spyOn(restService, 'post');
            expect(restService.post).not.toHaveBeenCalled();
            const method = 'force';
            const params = {a: 1};
            dataService.control("a", 1, method, params);
            expect(restService.post).toHaveBeenCalledWith("a/1", {
                id: 1,
                jsonrpc: '2.0',
                method,
                params
            }
            );
        })
    );

    describe('open()', function() {

        let opened = null;
        beforeEach(() => opened = dataService.open());

        it('should return a new accessor', () => expect(opened).toEqual(jasmine.any(Object)));

        it('should have getXxx functions for endpoints', () =>
            (() => {
                const result = [];
                for (let e of Array.from(ENDPOINTS)) {
                    const E = e[0].toUpperCase() + e.slice(1).toLowerCase();
                    expect(opened[`get${E}`]).toBeDefined();
                    result.push(expect(angular.isFunction(opened[`get${E}`])).toBeTruthy());
                }
                result;
            })()
        );

        it('should call unsubscribe on each subscribed collection on close', function() {
            const p = $q.resolve({builds: [{buildid:1}, {buildid:2}, {buildid:3}]});
            spyOn(restService, 'get').and.returnValue(p);
            let builds = null;
            $rootScope.$apply(() => builds = opened.getBuilds({subscribe: false}));
            expect(builds.length).toBe(3);
            spyOn(builds, 'close');
            opened.close();
            expect(builds.close).toHaveBeenCalled();
        });

        it('should call close when the $scope is destroyed', function() {
            spyOn(opened, 'close');
            const scope = $rootScope.$new();
            opened.closeOnDestroy(scope);
            expect(opened.close).not.toHaveBeenCalled();
            scope.$destroy();
            expect(opened.close).toHaveBeenCalled();
        });

        it('should work with mock calls as well', function() {
            let builds;
            dataService.when('builds/1', [{buildid: 1, builderid: 1}]);
            builds = opened.getBuilds(1, {subscribe: false});
        });
    });

    describe('when()', () =>
        it('should autopopulate ids', function(done) {
            dataService.when('builds', [{}, {}, {}]);
            dataService.getBuilds().onChange = function(builds) {
                expect(builds.length).toBe(3);
                expect(builds[1].buildid).toBe(2);
                expect(builds[2].buildid).toBe(3);
                done();
            };
            $timeout.flush();
        })
    );
});
