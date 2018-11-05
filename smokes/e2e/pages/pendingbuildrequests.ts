// this file will contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";
import { browser, by, element, ExpectedConditions as EC } from 'protractor';

export class PendingBuildrequestsPage extends BasePage {

    constructor() {
        super();
    }

    async go() {
        await browser.get('#/pendingbuildrequests');
        await browser.wait(EC.urlContains('#/pendingbuildrequests'),
                           10000,
                           "URL does not contain #/pendingbuildrequests");
    }

    getAllBuildrequestRows() {
        return element.all(By.css("td .badge-status")).all(By.xpath('../../..'));
    }
}
