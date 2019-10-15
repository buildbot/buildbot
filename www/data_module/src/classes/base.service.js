/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Base {
    constructor(dataService, socketService, dataUtilsService) {
        let BaseInstance;
        return (BaseInstance = class BaseInstance {
            constructor(object, _endpoint, childEndpoints) {
                this._endpoint = _endpoint;
                if (childEndpoints == null) { childEndpoints = []; }
                if (!angular.isString(this._endpoint)) {
                    throw new TypeError(`Parameter 'endpoint' must be a string, not ${typeof this.endpoint}`);
                }

                this.$accessor = null;
                // add object fields to the instance
                this.update(object);

                // generate loadXXX functions
                this.constructor.generateFunctions(childEndpoints);

                // get the id of the class type
                const classId = dataUtilsService.classId(this._endpoint);
                this._id = this[classId];

                // reset endpoint to base
                if (this._id != null) {
                    this._endpoint = dataUtilsService.type(this._endpoint);
                }
            }

            setAccessor(a) {
                return this.$accessor = a;
            }

            update(o) {
                return angular.extend(this, o);
            }

            get(...args) {
                return dataService.get(this._endpoint, this._id, ...Array.from(args));
            }

            control(method, params) {
                return dataService.control(this._endpoint, this._id, method, params);
            }

            // generate endpoint functions for the class
            static generateFunctions(endpoints) {
                return endpoints.forEach(e => {
                    // capitalize endpoint names
                    const E = dataUtilsService.capitalize(e);
                    // adds loadXXX functions to the prototype
                    this.prototype[`load${E}`] = function(...args) {
                        return this[e] = this.get(e, ...Array.from(args));
                    };

                    // adds getXXX functions to the prototype
                    return this.prototype[`get${E}`] = function(...args) {
                        let query;
                        [args, query] = Array.from(dataUtilsService.splitOptions(args));
                        if (this.$accessor) {
                            if (query.subscribe == null) { query.subscribe = true; }
                            query.accessor = this.$accessor;
                        }
                        return this.get(e, ...Array.from(args), query);
                    };
                });
            }
        });
    }
}


angular.module('bbData')
.factory('Base', ['dataService', 'socketService', 'dataUtilsService', Base]);
