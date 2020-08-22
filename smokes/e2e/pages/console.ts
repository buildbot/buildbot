// this file contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";
import { by, element, ExpectedConditions as EC } from 'protractor';
import { bbrowser } from '../utils';

export class ConsolePage extends BasePage {
    constructor() {
        super();
    }

    async go() {
        await bbrowser.get('#/console');
        await bbrowser.wait(EC.urlContains('#/console'),
                            "URL does not contain #/console");
    }

    async countSuccess() {
        return await element.all(By.css('.badge-status.results_SUCCESS')).count();
    }
}
