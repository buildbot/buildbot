// this file will contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";
import { browser, by, element, ExpectedConditions as EC } from 'protractor';
import { bbrowser } from '../utils';

export class PendingBuildrequestsPage extends BasePage {

    constructor() {
        super();
    }

    async go() {
        await bbrowser.get('#/pendingbuildrequests');
        await bbrowser.wait(EC.urlContains('#/pendingbuildrequests'),
                            "URL does not contain #/pendingbuildrequests");
    }

    getAllBuildrequestRows() {
        return element.all(By.css("td .badge-status")).all(By.xpath('../../..'));
    }
}
