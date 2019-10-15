/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS203: Remove `|| {}` from converted for-own loops
 * DS205: Consider reworking code to avoid use of IIFEs
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class DataQuery {
    constructor($http, $q, API) {
        let DataQueryClass;
        return (DataQueryClass = class DataQueryClass {
            constructor(query) {
                if (query == null) { query = {}; }
                this.query = query;
                this.filters = {};
                for (let fieldAndOperator in query) {
                    let value = query[fieldAndOperator];
                    if (['field', 'limit', 'offset', 'order', 'property'].indexOf(fieldAndOperator) < 0) {
                        if (['on', 'true', 'yes'].indexOf(value) > -1) { value = true;
                        } else if (['off', 'false', 'no'].indexOf(value) > -1) { value = false; }
                        this.filters[fieldAndOperator] = value;
                    }
                }
            }

            computeQuery(array) {
                // 1. filtering
                this.filter(array);

                // 2. sorting
                const order = this.query != null ? this.query.order : undefined;
                this.sort(array, order);

                // 3. limit
                const limit = this.query != null ? this.query.limit : undefined;
                return this.limit(array, limit);
            }


            isFiltered(v) {
                const cmpByOp = {};
                for (let fieldAndOperator in this.filters) {
                    const value = this.filters[fieldAndOperator];
                    const [field, operator] = Array.from(fieldAndOperator.split('__'));
                    let cmp = false;
                    switch (operator) {
                        case 'ne': cmp = v[field] !== value; break;
                        case 'lt': cmp = v[field] <  value; break;
                        case 'le': cmp = v[field] <= value; break;
                        case 'gt': cmp = v[field] >  value; break;
                        case 'ge': cmp = v[field] >= value; break;
                        default: cmp = (v[field] === value) ||
                            (angular.isArray(v[field]) && Array.from(v[field]).includes(value)) ||
                            (angular.isArray(value) && (value.length === 0)) ||
                            (angular.isArray(value) && Array.from(value).includes(v[field])) ||
                            // private fields added by the data service
                            (v[`_${field}`] === value) ||
                            (angular.isArray(v[`_${field}`]) && Array.from(v[`_${field}`]).includes(value)) ||
                            (angular.isArray(value) && Array.from(value).includes(v[`_${field}`]));
                    }
                    cmpByOp[fieldAndOperator] = cmpByOp[fieldAndOperator] || cmp;
                }
                for (let op of Object.keys(cmpByOp || {})) {
                    v = cmpByOp[op];
                    if (!v) { return false; }
                }
                return true;
            }

            filter(array) {
                let i = 0;
                return (() => {
                    const result = [];
                    while (i < array.length) {
                        const v = array[i];
                        if (this.isFiltered(v)) {
                            result.push(i += 1);
                        } else {
                            result.push(array.splice(i, 1));
                        }
                    }
                    return result;
                })();
            }

            sort(array, order) {
                const compare = function(property) {
                    let reverse = false;
                    if (property[0] === '-') {
                        property = property.slice(1);
                        reverse = true;
                    }

                    return function(a, b) {
                        if (reverse) { [a, b] = Array.from([b, a]); }

                        if (a[property] < b[property]) { return -1;
                        } else if (a[property] > b[property]) { return 1;
                        } else { return 0; }
                    };
                };
                if (angular.isString(order)) {
                    return array.sort(compare(order));
                } else if (angular.isArray(order)) {
                    return array.sort(function(a, b) {
                        for (let o of Array.from(order)) {
                            const f = compare(o)(a, b);
                            if (f) { return f; }
                        }
                        return 0;
                    });
                }
            }

            limit(array, limit) {
                while (array.length > limit) {
                    array.pop();
                }
            }
        });
    }
}


angular.module('bbData')
.factory('DataQuery', ['$http', '$q', 'API', DataQuery]);
