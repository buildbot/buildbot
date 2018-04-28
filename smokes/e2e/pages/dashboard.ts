// this file will contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";

export class DashboardPage extends BasePage {
    constructor() {
        {
          super();
          let thisFn = (() => { return this; }).toString();
          let thisName = thisFn.slice(thisFn.indexOf('return') + 6 + 1, thisFn.indexOf(';')).trim();
        }
    }

    go() {
        return browser.get('#/mydashboard');
    }
}
