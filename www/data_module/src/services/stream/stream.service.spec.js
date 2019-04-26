describe('Stream service', function() {
    let stream;
    beforeEach(angular.mock.module('bbData'));

    let Stream = (stream = null);
    const injected = function($injector) {
        Stream = $injector.get('Stream');
        stream = new Stream();
    };

    beforeEach(inject(injected));

    it('should be defined', function() {
        expect(Stream).toBeDefined();
        expect(stream).toBeDefined();
    });

    it('should add the listener to listeners on subscribe call', function() {
        const { listeners } = stream;
        expect(listeners.length).toBe(0);

        stream.subscribe(function() {});
        expect(listeners.length).toBe(1);
    });

    it('should add a unique id to each listener passed in to subscribe', function() {
        const { listeners } = stream;

        const listener1 = function() {};
        const listener2 = function() {};

        stream.subscribe(listener1);
        stream.subscribe(listener2);

        expect(listener1.id).toBeDefined();
        expect(listener2.id).toBeDefined();
        expect(listener1.id).not.toBe(listener2.id);
    });

    it('should return the unsubscribe function on subscribe call', function() {
        const { listeners } = stream;
        const listener = function() {};
        const otherListener = function() {};

        const unsubscribe = stream.subscribe(listener);
        stream.subscribe(otherListener);
        expect(listeners).toContain(listener);

        unsubscribe();
        expect(listeners).not.toContain(listener);
        expect(listeners).toContain(otherListener);
    });

    it('should call all listeners on push call', function() {
        const data = {a: 'A', b: 'B'};
        const listeners = {
            first(data) { expect(data).toEqual({a: 'A', b: 'B'}); },
            second(data) { expect(data).toEqual({a: 'A', b: 'B'}); }
        };

        spyOn(listeners, 'first').and.callThrough();
        spyOn(listeners, 'second').and.callThrough();

        stream.subscribe(listeners.first);
        stream.subscribe(listeners.second);

        expect(listeners.first).not.toHaveBeenCalled();
        expect(listeners.second).not.toHaveBeenCalled();

        stream.push(data);

        expect(listeners.first).toHaveBeenCalled();
        expect(listeners.second).toHaveBeenCalled();
    });

    it('should remove all listeners on destroy call', function() {
        const { listeners } = stream;
        expect(listeners.length).toBe(0);

        stream.subscribe(function() {});
        stream.subscribe(function() {});
        expect(listeners.length).not.toBe(0);

        stream.destroy();
        expect(listeners.length).toBe(0);
    });

    it('should call the unsubscribe listener on unsubscribe call', function() {
        spyOn(stream, 'onUnsubscribe');

        const listener = function() {};
        const unsubscribe = stream.subscribe(listener);

        expect(stream.onUnsubscribe).not.toHaveBeenCalled();
        unsubscribe();
        expect(stream.onUnsubscribe).toHaveBeenCalledWith(listener);
    });
});
