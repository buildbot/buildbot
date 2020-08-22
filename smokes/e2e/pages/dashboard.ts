// this file will contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";
import { browser, by, element, ExpectedConditions as EC } from 'protractor';
import { bbrowser } from '../utils';

export class DashboardPage extends BasePage {
    constructor() {
        super();
    }

    async go() {
        await bbrowser.get('#/mydashboard');
        await bbrowser.wait(EC.urlContains('#/mydashboard'),
                            "URL does not contain #/mydashboard");
        var buildLink = element.all(By.linkText("runtests/1")).first();
        await bbrowser.wait(EC.elementToBeClickable(buildLink),
                            "runtests/1 link not clickable");
        await buildLink.click();
    }
}
