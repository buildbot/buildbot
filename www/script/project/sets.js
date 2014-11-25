/*global define*/
define(function (require) {
    "use strict";
//-------------------------------------------
// Simple implementation of a Set in javascript
//
// Supports any element type that can uniquely be identified
//    with its string conversion (e.g. toString() operator).
// This includes strings, numbers, dates, etc...
// It does not include objects or arrays though
//    one could implement a toString() operator
//    on an object that would uniquely identify
//    the object.
//
// Uses a javascript object to hold the Set
//
// This is a subset of the Set object designed to be smaller and faster, but
// not as extensible.  This implementation should not be mixed with the Set object
// as in don't pass a miniSet to a Set constructor or vice versa.  Both can exist and be
// used separately in the same project, though if you want the features of the other
// sets, then you should probably just include them and not include miniSet as it's
// really designed for someone who just wants the smallest amount of code to get
// a Set interface.
//
// s.add(key)                      // adds a key to the Set (if it doesn't already exist)
// s.add(key1, key2, key3)         // adds multiple keys
// s.add([key1, key2, key3])       // adds multiple keys
// s.add(otherSet)                 // adds another Set to this Set
// s.add(arrayLikeObject)          // adds anything that a subclass returns true on _isPseudoArray()
// s.remove(key)                   // removes a key from the Set
// s.remove(["a", "b"]);           // removes all keys in the passed in array
// s.remove("a", "b", ["first", "second"]);   // removes all keys specified
// s.has(key)                      // returns true/false if key exists in the Set
// s.isEmpty()                     // returns true/false for whether Set is empty
// s.keys()                        // returns an array of keys in the Set
// s.clear()                       // clears all data from the Set
// s.each(fn)                      // iterate over all items in the Set (return this for method chaining)
//
// All methods return the object for use in chaining except when the point
// of the method is to return a specific value (such as .keys() or .isEmpty())
//-------------------------------------------


// polyfill for Array.isArray
    if (!Array.isArray) {
        Array.isArray = function (vArg) {
            return Object.prototype.toString.call(vArg) === "[object Array]";
        };
    }

    function MiniSet(initialData) {
        // Usage:
        // new MiniSet()
        // new MiniSet(1,2,3,4,5)
        // new MiniSet(["1", "2", "3", "4", "5"])
        // new MiniSet(otherSet)
        // new MiniSet(otherSet1, otherSet2, ...)
        this.data = {};
        this.add.apply(this, arguments);
    }

    MiniSet.prototype = {
        // usage:
        // add(key)
        // add([key1, key2, key3])
        // add(otherSet)
        // add(key1, [key2, key3, key4], otherSet)
        // add supports the EXACT same arguments as the constructor
        add: function () {
            var key;
            for (var i = 0; i < arguments.length; i++) {
                key = arguments[i];
                if (Array.isArray(key)) {
                    for (var j = 0; j < key.length; j++) {
                        this.data[key[j]] = key[j];
                    }
                } else if (key instanceof MiniSet) {
                    var self = this;
                    key.each(function (val, key) {
                        self.data[key] = val;
                    });
                } else {
                    // just a key, so add it
                    this.data[key] = key;
                }
            }
            return this;
        },
        // private: to remove a single item
        // does not have all the argument flexibility that remove does
        _removeItem: function (key) {
            delete this.data[key];
        },
        // usage:
        // remove(key)
        // remove(key1, key2, key3)
        // remove([key1, key2, key3])
        remove: function (key) {
            // can be one or more args
            // each arg can be a string key or an array of string keys
            var item;
            for (var j = 0; j < arguments.length; j++) {
                item = arguments[j];
                if (Array.isArray(item)) {
                    // must be an array of keys
                    for (var i = 0; i < item.length; i++) {
                        this._removeItem(item[i]);
                    }
                } else {
                    this._removeItem(item);
                }
            }
            return this;
        },
        // returns true/false on whether the key exists
        has: function (key) {
            return Object.prototype.hasOwnProperty.call(this.data, key);
        },
        // tells you if the Set is empty or not
        isEmpty: function () {
            for (var key in this.data) {
                if (this.has(key)) {
                    return false;
                }
            }
            return true;
        },
        // returns an array of all keys in the Set
        // returns the original key (not the string converted form)
        keys: function () {
            var results = [];
            this.each(function (data) {
                results.push(data);
            });
            return results;
        },
        // clears the Set
        clear: function () {
            this.data = {};
            return this;
        },
        // iterate over all elements in the Set until callback returns false
        // myCallback(key) is the callback form
        // If the callback returns false, then the iteration is stopped
        // returns the Set to allow method chaining
        each: function (fn) {
            this.eachReturn(fn);
            return this;
        },
        // iterate all elements until callback returns false
        // myCallback(key) is the callback form
        // returns false if iteration was stopped
        // returns true if iteration completed
        eachReturn: function (fn) {
            for (var key in this.data) {
                if (this.has(key)) {
                    if (fn.call(this, this.data[key], key) === false) {
                        return false;
                    }
                }
            }
            return true;
        }
    };

    MiniSet.prototype.constructor = MiniSet;

    return MiniSet;
});