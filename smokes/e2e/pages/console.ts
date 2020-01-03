// this file contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";
import { browser, by, element, ExpectedConditions as EC } from 'protractor';

export class ConsolePage extends BasePage {
    constructor() {
        super();
    }

    async go() {
        await browser.get('#/console');
        await browser.wait(EC.urlContains('#/console'),
                           10000,
                           "URL does not contain #/console");
    }

    async countSuccess() {
        return await element.all(By.css('.badge-status.results_SUCCESS')).count();
    }
}
