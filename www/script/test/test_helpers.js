/*global define, describe, it, expect, beforeEach, afterEach*/
define(["jquery", "helpers"], function ($, helpers) {
  "use strict";

  describe("A build", function () {

    var now = new Date(),
      build = {
        times: []
      };

    helpers.settings = function () {
      return {oldBuildDays: 7}
    };

    it("is old", function () {
      build.times = [new Date().setDate(now.getDate() - 8) / 1000.0];
      expect(helpers.isBuildOld(build)).toBeTruthy();

      build.times = [new Date().setDate(now.getDate() - 50) / 1000.0];
      expect(helpers.isBuildOld(build)).toBeTruthy();
    });

    it("is new", function () {
      build.times = [new Date().setDate(now.getDate() - 1) / 1000.0];
      expect(helpers.isBuildOld(build)).toBeFalsy();

      build.times = [new Date().setDate(now.getDate() - 3) / 1000.0];
      expect(helpers.isBuildOld(build)).toBeFalsy();
    });

  });

  describe("A project builders history", function () {
    
    it("is saved if local storage is accessible", function () {
      var key = 'testhistorylist'
      helpers.updateBuildersHistoryList(key, 100);
      expect(window.localStorage.getItem(key)).toBe('100');

      helpers.updateBuildersHistoryList(key, 102);
      expect(window.localStorage.getItem(key)).toBe('102');
    });
    
    it("list is empty if localStorage is not accessible", function () {
      var key = 'testhistorylist1'
      spyOn(window, "localStorage").and.callFake(function() {
        throw {
          name: 'System Error',
        };
      });

      var list = helpers.getBuildersHistoryList(key);
      expect(list).toEqual([]);
    });

    it("item is not removed from local storage if local storage is full", function () {
      var key = 'testhistorylist2'
      helpers.updateBuildersHistoryList(key, 100);

      window.localStorage.setItem = function () {
        throw {
          code: 22
        };
      }
      helpers.updateBuildersHistoryList(key, 102);
      expect(window.localStorage.getItem(key)).toBeNull();

      window.localStorage.setItem = function () {
        throw {
          code: 1014,
          name: NS_ERROR_DOM_QUOTA_REACHED,
        };
      }
      helpers.updateBuildersHistoryList(key, 10);
      expect(window.localStorage.getItem(key)).toBeNull();

      window.localStorage.setItem = function () {
        throw {
          number: -2147024882
        };
      }

      helpers.updateBuildersHistoryList(key, 10);
      expect(window.localStorage.getItem(key)).toBeNull();

    });

  });

});