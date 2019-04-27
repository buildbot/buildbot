/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS201: Simplify complex destructure assignments
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class DataUtils {
    constructor() {
        let dataUtilsService;
        return new (dataUtilsService = class dataUtilsService {
            // capitalize first word
            capitalize(string) {
                return string[0].toUpperCase() + string.slice(1).toLowerCase();
            }

            // returns the type of the endpoint
            type(arg) {
                let a = this.copyOrSplit(arg);
                a = a.filter(e => e !== '*');
                // if the argument count is even, the last argument is an id
                if ((a.length % 2) === 0) { a.pop(); }
                let type = a.pop();
                if (type === "contents") {
                    type = "logchunks";
                }
                return type;
            }
            // singularize the type name
            singularType(arg) {
                return this.type(arg).replace(/s$/, '');
            }

            className(arg) {
                return this.capitalize(this.singularType(arg));
            }

            classId(arg) {
                if (this.singularType(arg) === "forcescheduler") {
                    return "name";
                }
                if (this.singularType(arg) === "buildset") {
                    return "bsid";
                }
                return this.singularType(arg) + "id";
            }

            socketPath(arg) {
                const a = this.copyOrSplit(arg);
                // if the argument count is even, the last argument is an id
                // Format of properties endpoint is an exception
                // and needs to be properties/*, not properties/*/*
                const stars = ['*'];
                // is it odd?
                if (((a.length % 2) === 1) && !arg.endsWith("/properties")) { stars.push('*'); }
                return a.concat(stars).join('/');
            }

            socketPathRE(socketPath) {
                return new RegExp(`^${socketPath.replace(/\*/g, "[^/]+")}$`);
            }

            restPath(arg) {
                let a = this.copyOrSplit(arg);
                a = a.filter(e => e !== '*');
                return a.join('/');
            }

            endpointPath(arg) {
                // if the argument count is even, the last argument is an id
                let a = this.copyOrSplit(arg);
                a = a.filter(e => e !== '*');
                // is it even?
                if ((a.length % 2) === 0) { a.pop(); }
                return a.join('/');
            }

            copyOrSplit(arrayOrString) {
                if (angular.isArray(arrayOrString)) {
                    // return a copy
                    return arrayOrString.slice();
                } else if (angular.isString(arrayOrString)) {
                    // split the string to get an array
                    return arrayOrString.split('/');
                } else {
                    throw new TypeError(`Parameter 'arrayOrString' must be a array or a string, not ${typeof arrayOrString}`);
                }
            }

            unWrap(object, path) {
                return object[this.type(path)];
            }

            splitOptions(args) {
                // keep defined arguments only
                let accessor;
                args = args.filter(e => e != null);

                let query = {}; // default
                // get the query parameters
                const last = args[args.length - 1];
                const subscribe = (accessor = null);

                if (angular.isObject(last)) {
                    query = args.pop();
                }

                return [args, query];
            }

            parse(object) {
                for (let k in object) {
                    const v = object[k];
                    try {
                        object[k] = angular.fromJson(v);
                    } catch (error) {}
                } // ignore
                return object;
            }

            numberOrString(str = null) {
                // if already a number
                if (angular.isNumber(str)) { return str; }
                // else parse string to integer
                const number = parseInt(str, 10);
                if (!isNaN(number)) { return number; } else { return str; }
            }

            emailInString(string) {
                if (!angular.isString(string)) {
                    throw new TypeError(`Parameter 'string' must be a string, not ${typeof string}`);
                }
                const emailRegex = /[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*/;
                try {
                    return emailRegex.exec(string).pop() || '';
                } catch (error) {
                    return '';
                }
            }
        });
    }
}


angular.module('bbData')
.service('dataUtilsService', [DataUtils]);
