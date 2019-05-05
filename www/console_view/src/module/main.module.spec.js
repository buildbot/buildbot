/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS206: Consider reworking classes to avoid initClass
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
beforeEach(function() {
    angular.mock.module(function($provide) {
        $provide.service('$uibModal', function() { return {open() {}}; });
    });
    angular.mock.module(function($provide) {
        $provide.service('resultsService', function() { return {results2class() {}}; });
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
    angular.mock.module('console_view');
});

describe('Console view', function() {
    let $state = null;
    beforeEach(inject($injector => $state = $injector.get('$state'))
    );

    it('should register a new state with the correct configuration', function() {
        const name = 'console';
        const state = $state.get().pop();
        const { data } = state;
        expect(state.controller).toBe(`${name}Controller`);
        expect(state.controllerAs).toBe('c');
        expect(state.url).toBe(`/${name}`);
    });
});

describe('Console view controller', function() {
    // Test data

    let $rootScope, $timeout, $window, dataService, scope;
    let builders = [{
        builderid: 1,
        masterids: [1]
    }
    , {
        builderid: 2,
        masterids: [1]
    }
    , {
        builderid: 3,
        masterids: [1]
    }
    , {
        builderid: 4,
        masterids: [1]
    }
    ];

    const builds1 = [{
        buildid: 1,
        builderid: 1,
        buildrequestid: 1
    }
    , {
        buildid: 2,
        builderid: 2,
        buildrequestid: 1
    }
    , {
        buildid: 3,
        builderid: 4,
        buildrequestid: 2
    }
    , {
        buildid: 4,
        builderid: 3,
        buildrequestid: 2
    }
    ];

    const builds2 = [{
        buildid: 5,
        builderid: 2,
        buildrequestid: 3
    }
    ];

    const builds = builds1.concat(builds2);

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

    const buildsets = [{
        bsid: 1,
        sourcestamps: [
            {ssid: 1}
        ]
    }
    , {
        bsid: 2,
        sourcestamps: [
            {ssid: 2}
        ]
    }
    ];

    const changes = [{
        changeid: 1,
        sourcestamp: {
            ssid: 1
        }
    }
    ];
    let createController = (scope = ($rootScope = (dataService = ($window = ($timeout = null)))));

    const injected = function($injector) {
        const $q = $injector.get('$q');
        $rootScope = $injector.get('$rootScope');
        $window = $injector.get('$window');
        $timeout = $injector.get('$timeout');
        dataService = $injector.get('dataService');
        scope = $rootScope.$new();
        dataService.when('builds', builds);
        dataService.when('builders', builders);
        dataService.when('changes', changes);
        dataService.when('buildrequests', buildrequests);
        dataService.when('buildsets', buildsets);

        // Create new controller using controller as syntax
        const $controller = $injector.get('$controller');
        createController = () =>
            $controller('consoleController as c', {
                // Inject controller dependencies
                $q,
                $window,
                $scope: scope
            }
            )
        ;
    };

    beforeEach(inject(injected));

    it('should be defined', function() {
        createController();
        expect(scope.c).toBeDefined();
    });

    it('should bind the builds, builders, changes, buildrequests and buildsets to scope', function() {
        createController();
        $rootScope.$digest();
        $timeout.flush();
        expect(scope.c.builds).toBeDefined();
        expect(scope.c.builds.length).toBe(builds.length);
        expect(scope.c.all_builders).toBeDefined();
        expect(scope.c.all_builders.length).toBe(builders.length);
        expect(scope.c.changes).toBeDefined();
        expect(scope.c.changes.length).toBe(changes.length);
        expect(scope.c.buildrequests).toBeDefined();
        expect(scope.c.buildrequests.length).toBe(buildrequests.length);
        expect(scope.c.buildsets).toBeDefined();
        expect(scope.c.buildsets.length).toBe(buildsets.length);
    });

    it('should match the builds with the change', function() {
        createController();
        $timeout.flush();
        $rootScope.$digest();
        $timeout.flush();
        expect(scope.c.changes[0]).toBeDefined();
        expect(scope.c.changes[0].builders).toBeDefined();
        ({ builders } = scope.c.changes[0]);
        expect(builders[0].builds[0].buildid).toBe(1);
        expect(builders[1].builds[0].buildid).toBe(2);
        expect(builders[2].builds[0].buildid).toBe(4);
        expect(builders[3].builds[0].buildid).toBe(3);
    });

    xit('should match sort the builders by tag groups', function() {
        createController();
        const _builders = FIXTURES['builders.fixture.json'].builders;
        for (let builder of Array.from(_builders)) {
            builder.hasBuild = true;
        }
        scope.c.sortBuildersByTags(_builders);
        expect(_builders.length).toBe(scope.c.builders.length);
        expect(scope.c.tag_lines.length).toEqual(5);
    });
});
