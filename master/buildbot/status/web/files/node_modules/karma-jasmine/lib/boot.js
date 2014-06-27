/**
 * Jasmine 2.0 standalone `boot.js` modified for Karma.
 * This file is registered in `index.js`. This version
 * does not include `HtmlReporter` setup.
 */
(function(){

  /**
   * Require Jasmine's core files. Specifically, this requires and
   * attaches all of Jasmine's code to the `jasmine` reference.
   */
  window.jasmine = jasmineRequire.core(jasmineRequire);


  /**
   * Create the Jasmine environment. This is used to run all specs
   * in a project.
   */
  var env = jasmine.getEnv();

  var focusedSuites = [];
  var focusedSpecs  = [];
  var insideFocusedSuite = false;

  var focuseSpec = function(env, description, body) {
    var spec = env.it(description, body);
    focusedSpecs.push(spec.id);
    return spec;
  };

  var focuseSuite = function(env, description, body) {
    if (insideFocusedSuite) {
      return env.describe(description, body);
    }

    insideFocusedSuite = true;
    var suite = env.describe(description, body);
    insideFocusedSuite = false
    focusedSuites.push(suite.id);
    return suite;
  };


  /**
   * Build up the functions that will be exposed as the Jasmine
   * public interface.
   */
  var jasmineInterface = {
    describe: function(description, specDefinitions) {
      return env.describe(description, specDefinitions);
    },

    xdescribe: function(description, specDefinitions) {
      return env.xdescribe(description, specDefinitions);
    },

    ddescribe: function(description, specDefinitions) {
      return focuseSuite(env, description, specDefinitions);
    },

    it: function(desc, func) {
      return env.it(desc, func);
    },

    xit: function(desc, func) {
      return env.xit(desc, func);
    },

    iit: function(desc, func) {
      return focuseSpec(env, desc, func);
    },

    beforeEach: function(beforeEachFunction) {
      return env.beforeEach(beforeEachFunction);
    },

    afterEach: function(afterEachFunction) {
      return env.afterEach(afterEachFunction);
    },

    expect: function(actual) {
      return env.expect(actual);
    },

    pending: function() {
      return env.pending();
    },

    spyOn: function(obj, methodName) {
      return env.spyOn(obj, methodName);
    },

    jsApiReporter: new jasmine.JsApiReporter({
      timer: new jasmine.Timer()
    })
  };


  /**
   * Add all of the Jasmine global/public interface to the proper
   * global, so a project can use the public interface directly.
   * For example, calling `describe` in specs instead of
   * `jasmine.getEnv().describe`.
   */
  for (var property in jasmineInterface) {
    if (jasmineInterface.hasOwnProperty(property)) {
      window[property] = jasmineInterface[property];
    }
  }

  env.executeFiltered = function() {
    if (focusedSpecs.length) {
      env.execute(focusedSpecs);
    } else if (focusedSuites.length) {
      env.execute(focusedSuites);
    } else {
      env.execute();
    }
  };


  /**
   * Expose the interface for adding custom equality testers.
   */
  jasmine.addCustomEqualityTester = function(tester) {
    env.addCustomEqualityTester(tester);
  };


  /**
   * Expose the interface for adding custom expectation matchers
   */
  jasmine.addMatchers = function(matchers) {
    return env.addMatchers(matchers);
  };


  /**
   * Expose the mock interface for the JavaScript timeout functions
   */
  jasmine.clock = function() {
    return env.clock;
  };


})();
