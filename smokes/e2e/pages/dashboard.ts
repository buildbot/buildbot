// this file will contains the different generic functions which
// will be called by the different tests

import {browser, by, element, ExpectedConditions as EC} from 'protractor';
import { BasePage } from "./base";

export class DashboardPage extends BasePage {
    constructor() {
        {
          super();
          let thisFn = (() => { return this; }).toString();
          let thisName = thisFn.slice(thisFn.indexOf('return') + 6 + 1, thisFn.indexOf(';')).trim();
        }
    }

    async go() {
        await browser.get('#/mydashboard');
        await browser.wait(EC.urlContains('#/mydashboard'),
                           5000,
                           "URL does not contain #/mydashboard");
    }
}
