/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS205: Consider reworking code to avoid use of IIFEs
 * DS206: Consider reworking classes to avoid initClass
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
beforeEach(function() {
    angular.mock.module(function($provide) {
        $provide.service('$uibModal', function() { return {open() {}}; });
    });

    // Mock bbSettingsProvider
    angular.mock.module(function($provide) {
        $provide.provider('bbSettingsService', (function() {
            let group = undefined;
            const Cls = class {
                static initClass() {
                    group = {};
                }
                addSettingsGroup(g) { return g.items.map(function(i) {
                    if (i.name === 'lazy_limit_waterfall') {
                        i.default_value = 2;
                    }
                    return group[i.name] = {value: i.default_value};
                }); }
                $get() {
                    return {
                        getSettingsGroup() {
                            return group;
                        },
                        save() {}
                    };
                }
            };
            Cls.initClass();
            return Cls;
        })()
        );
    });

    angular.mock.module('waterfall_view');
});

describe('Waterfall view controller', function() {
    let $document, $state, $timeout, $uibModal, $window, bbSettingsService, dataService, elem, w;
    let $rootScope = ($state = (elem = (w = ($document = ($window = ($uibModal = ($timeout =
        (bbSettingsService = ($rootElement = (dataService = null))))))))));

    const masters = [{
        masterid: 1,
        name: 'master1',
        active: true,
    }
    ,{
        masterid: 2,
        name: 'master2',
        active: false,
    }
    ];

    const builders = [{
        builderid: 1,
        name: 'builder1',
        masterids: [1],
        tags: [""],
    }
    , {
        builderid: 2,
        name: 'builder2',
        masterids: [1],
        tags: [""],
    }
    , {
        builderid: 3,
        name: 'builder3',
        masterids: [1],
        tags: [""],
    }
    , {
        builderid: 4,
        name: 'builder4',
        masterids: [1],
        tags: [""],
    }
    , {
        builderid: 5,
        name: 'builder5',
        masterids: [2],
        tags: [""],
    }
    ];

    const builds = [{
        buildid: 1,
        builderid: 1,
        started_at: 1403059709,
        complete_at: 1403059772,
        complete: true,
        results: 'success'
    }
    , {
        buildid: 2,
        builderid: 2,
        buildrequestid: 1,
        started_at: 1403059802,
        complete_at: 1403060287,
        complete: true,
        results: 'success'
    }
    , {
        buildid: 3,
        builderid: 2,
        buildrequestid: 2,
        started_at: 1403059710,
        complete_at: 1403060278,
        complete: true,
        results: 'failure'
    }
    , {
        buildid: 4,
        builderid: 3,
        buildrequestid: 2,
        started_at: 1403060250,
        complete_at: 0,
        complete: false
    }
    ];

    const buildrequests = [{
        builderid: 1,
        buildrequestid: 1,
        buildsetid: 1
    }
    , {
        builderid: 1,
        buildrequestid: 2,
        buildsetid: 1
    }
    , {
        builderid: 1,
        buildrequestid: 3,
        buildsetid: 2
    }
    ];

    const injected = function($injector) {
        $rootElement = $injector.get('$rootElement');
        $rootScope = $injector.get('$rootScope');
        let scope = $rootScope.$new();
        const $compile = $injector.get('$compile');
        const $controller = $injector.get('$controller');
        $state = $injector.get('$state');
        $document = $injector.get('$document');
        $window = $injector.get('$window');
        $uibModal = $injector.get('$uibModal');
        $timeout = $injector.get('$timeout');
        bbSettingsService = $injector.get('bbSettingsService');
        dataService = $injector.get('dataService');

        dataService.when('masters', masters);
        dataService.when('builds', {limit: 2}, builds.slice(0, 2));
        dataService.when('builders', builders);
        dataService.when('buildrequests', buildrequests);
        dataService.when('builds/1/steps', [{buildid: 1}]);

        mockBody = $compile('<body>')(scope);
        $rootElement.append(mockBody);
        elem = $compile('<div><ui-view></ui-view></div>')(scope);
        $document.find('body').append(elem);

        $state.transitionTo('waterfall');
        $rootScope.$digest();
        elem = elem.children();
        const waterfall = elem.children();
        scope = waterfall.scope();
        w = waterfall.controller();
        spyOn(w, 'mouseOver').and.callThrough();
        spyOn(w, 'mouseOut').and.callThrough();
        spyOn(w, 'mouseMove').and.callThrough();
        spyOn(w, 'click').and.callThrough();
        spyOn(w, 'loadMore').and.callThrough();
        // Data is loaded
        $timeout.flush();
    };

    beforeEach(inject(injected));

    // make sure we remove the element from the dom
    afterEach(function() {
        expect($document.find('svg').length).toEqual(2);
        elem.remove();
        expect($document.find('svg').length).toEqual(0);
    });

    it('should be defined', () => expect(w).toBeDefined());

    it('should bind the masters, builds, and builders to scope', function() {
        const group = bbSettingsService.getSettingsGroup();
        const limit = group.lazy_limit_waterfall.value;
        expect(w.$scope.masters).toBeDefined();
        expect(w.$scope.masters.length).not.toBe(0);
        expect(w.builds).toBeDefined();
        expect(w.builds.length).toBe(limit);
        expect(w.builders).toBeDefined();
        expect(w.builders.length).not.toBe(0);
    });

    it('should create svg elements', function() {
        expect(elem.find('svg').length).toBeGreaterThan(1);
        expect(elem.find('g').length).toBeGreaterThan(1);
    });

    it('should remove body class called hundredpercent on destroy', function() {
        expect(w.$rootElement.find('body').hasClass('hundredpercent')).toBeTruthy();
        w.$scope.$destroy();
        expect(w.$rootElement.find('body').hasClass('hundredpercent')).toBeFalsy();
    });

    it('should check if builder has active master or not', function() {
        expect(w.hasActiveMaster(builders[3])).toBeTruthy();
        expect(w.hasActiveMaster(builders[4])).toBeFalsy();
    });

    it('should rerender the waterfall on resize', function() {
        spyOn(w, 'render').and.callThrough();
        expect(w.render).not.toHaveBeenCalled();
        angular.element($window).triggerHandler('resize');
        expect(w.render).toHaveBeenCalled();
    });

    it('should rerender the waterfall on builds data change', function() {
        dataService.when('builds', builds);
        spyOn(w, 'render').and.callThrough();
        expect(w.render).not.toHaveBeenCalled();
        // force load more
        w.buildLimit = 0;
        w.loadMore();
        $timeout.flush();
        expect(w.render).toHaveBeenCalled();
    });

    it('should rerender the waterfall on masters data change', function() {
        spyOn(w, 'render').and.callThrough();
        expect(w.render).not.toHaveBeenCalled();
        w.$scope.masters.onChange();
        expect(w.render).toHaveBeenCalled();
    });

    it('should rerender the waterfall on builders data change', function() {
        spyOn(w, 'render').and.callThrough();
        expect(w.render).not.toHaveBeenCalled();
        w.all_builders.onChange();
        expect(w.render).toHaveBeenCalled();
    });

    it('should lazy load data on scroll', function() {
        spyOn(w, 'getHeight').and.returnValue(900);
        const e = d3.select('.inner-content');
        const n = e.node();
        w.loadMore.calls.reset();
        let callCount = w.loadMore.calls.count();
        expect(callCount).toBe(0);
        angular.element(n).triggerHandler('scroll');
        callCount = w.loadMore.calls.count();
        expect(callCount).toBe(1);
    });

    it('height should be scalable', function() {
        const height = w.getInnerHeight();
        const group = bbSettingsService.getSettingsGroup();
        const oldSetting = group.scaling_waterfall.value;
        w.incrementScaleFactor();
        w.render();
        const newHeight = w.getInnerHeight();
        expect(newHeight).toBe(height * 1.5);
        const newSetting = group.scaling_waterfall.value;
        expect(newSetting).toBe(oldSetting * 1.5);
    });

    it('should have string representations of result codes', function() {
        const testBuild = {
            complete: false,
            started_at: 0
        };
        expect(w.getResultClassFromThing(testBuild)).toBe('pending');
        testBuild.complete = true;
        expect(w.getResultClassFromThing(testBuild)).toBe('unknown');
        const results = {
            0: 'success',
            1: 'warnings',
            2: 'failure',
            3: 'skipped',
            4: 'exception',
            5: 'cancelled'
        };

        for (let i = 0; i <= 5; i++) {
            testBuild.results = i;
            expect(w.getResultClassFromThing(testBuild)).toBe(results[i]);
        }
    });
});
