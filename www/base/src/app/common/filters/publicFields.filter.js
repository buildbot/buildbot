/*
 * decaffeinate suggestions:
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class PublicFields {
    constructor() {
        return function(object) {
            if ((object == null)) {
                return object;
            }
            if (object._publicfields == null) { object._publicfields = {}; }
            for (let k in object) {
                const v = object[k];
                if ((k.indexOf('_') !== 0) && object.hasOwnProperty(k)) {
                    object._publicfields[k] = v;
                }
            }
            return object._publicfields;
        };
    }
}


angular.module('common')
.filter('publicFields', [PublicFields]);
