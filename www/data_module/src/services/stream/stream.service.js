/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS205: Consider reworking code to avoid use of IIFEs
 * DS206: Consider reworking classes to avoid initClass
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Stream {
    constructor() {
        let StreamInstance;
        return StreamInstance = (function() {
            StreamInstance = class StreamInstance {
                static initClass() {
                    // the unsubscribe listener will be called on each unsubscribe call
                    this.prototype.onUnsubscribe = null;
                    this.prototype.listeners = [];
                }

                subscribe(listener) {
                    if (!angular.isFunction(listener)) {
                        throw new TypeError(`Parameter 'listener' must be a function, not ${typeof listener}`);
                    }

                    listener.id = this.generateId();
                    this.listeners.push(listener);

                    // unsubscribe
                    return () => {
                        const i = this.listeners.indexOf(listener);
                        const removed = this.listeners.splice(i, 1);
                        // call the unsubscribe listener if it's a function
                        if (angular.isFunction(this.onUnsubscribe)) {
                            return this.onUnsubscribe(listener);
                        }
                    };
                }

                push(data) {
                    // call each listener
                    return Array.from(this.listeners).map((listener) => listener(data));
                }

                destroy() {
                    // @listeners = [], but keep the reference
                    while (this.listeners.length > 0) {
                        this.listeners.pop();
                    }
                }

                generateId() {
                    if (this.lastId == null) { this.lastId = 0; }
                    return this.lastId++;
                }
            };
            StreamInstance.initClass();
            return StreamInstance;
        })();
    }
}


angular.module('bbData')
.factory('Stream', [Stream]);
