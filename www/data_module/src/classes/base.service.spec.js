describe('Base class', function() {
    let $q, dataService, socketService;
    beforeEach(angular.mock.module('bbData'));

    let Base = (dataService = (socketService = ($q = null)));
    const injected = function($injector) {
        Base = $injector.get('Base');
        dataService = $injector.get('dataService');
        socketService = $injector.get('socketService');
        $q = $injector.get('$q');
    };

    beforeEach(inject(injected));

    it('should be defined', () => expect(Base).toBeDefined());

    it('should merge the passed in object with the instance', function() {
        const object = {a: 1, b: 2};
        const base = new Base(object, 'ab');
        expect(base.a).toEqual(object.a);
        expect(base.b).toEqual(object.b);
    });

    it('should have loadXxx function for child endpoints', function() {
        const children = ['a', 'bcd', 'ccc'];
        const base = new Base({}, 'ab', children);
        expect(angular.isFunction(base.loadA)).toBeTruthy();
        expect(angular.isFunction(base.loadBcd)).toBeTruthy();
        expect(angular.isFunction(base.loadCcc)).toBeTruthy();
    });
});
