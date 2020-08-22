// this file will contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";
import { by, element, ExpectedConditions as EC } from 'protractor';
import { bbrowser } from '../utils';

export class HomePage extends BasePage {

    constructor(){
        super();
    }

    async go() {
        await bbrowser.get('#/');
        await bbrowser.wait(EC.urlContains('#/'),
                            "URL does not contain #/");
    }

    getPanel() {
        return element.all(By.css(".panel-title"));
    }

    getAnonymousButton() {
        const anonymousButton = element(By.css('[ng-class="loginCollapsed ? \'\':\'open\'"'));
        return anonymousButton;
    }

    getLoginButton() {
        return element(By.buttonText('Login'));
    }

    async setUserText(value) {
        const setUserValue = element.all(By.css('[ng-model="username"]'));
        await setUserValue.clear();
        await setUserValue.sendKeys(value);
    }

    async setPasswordText(value) {
        const setPasswordValue = element.all(By.css('[ng-model="password"]'));
        await setPasswordValue.clear();
        await setPasswordValue.sendKeys(value);
    }

    async waitAllBuildsFinished() {
        await this.go();
        const self = this;
        const noRunningBuilds = async () => {
            let text = await element.all(By.css("h4")).getText();
            text = text.join(" ");
            return text.toLowerCase().indexOf("0 builds running") >= 0;
        }
        await bbrowser.wait(noRunningBuilds, "Builds are still running");
    }
}
