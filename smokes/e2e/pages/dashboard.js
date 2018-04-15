/*
 * decaffeinate suggestions:
 * DS001: Remove Babel/TypeScript constructor workaround
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
// this file will contains the different generic functions which
// will be called by the different tests
// inspired by this methodology
// http://www.lindstromhenrik.com/using-protractor-with-coffeescript/

const BasePage = require("./base.coffee");

class DashboardPage extends BasePage {
    constructor() {
        {
          // Hack: trick Babel/TypeScript into allowing this before super.
          if (false) { super(); }
          let thisFn = (() => { return this; }).toString();
          let thisName = thisFn.slice(thisFn.indexOf('return') + 6 + 1, thisFn.indexOf(';')).trim();
          eval(`${thisName} = this;`);
        }
    }

    go() {
        return browser.get('#/mydashboard');
    }
}

module.exports = DashboardPage;
