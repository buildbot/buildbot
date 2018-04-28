// this file will contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";

export class ForcePage extends BasePage {
    constructor() {
        {
          super();
          let thisFn = (() => { return this; }).toString();
          let thisName = thisFn.slice(thisFn.indexOf('return') + 6 + 1, thisFn.indexOf(';')).trim();
        }
    }

    setInputText(cssLabel, value) {
        const setInputValue = element(By.css(`forcefield label[for=${cssLabel}] + div input`));
        setInputValue.clear();
        setInputValue.sendKeys(value);
        expect(setInputValue.getAttribute('value')).toBe(value);
    }

    setReason(reason) {
        return this.setInputText("reason", reason);
    }

    setYourName(yourName) {
        return this.setInputText("username", yourName);
    }

    setProjectName(projectName) {
        return this.setInputText("project", projectName);
    }

    setBranchName(branchName) {
        return this.setInputText("branch", branchName);
    }

    setRepo(repo) {
        return this.setInputText("repository", repo);
    }

    setRevisionName(RevisionName) {
        return this.setInputText("revision", RevisionName);
    }

    getStartButton() {
        return element(By.buttonText('Start Build'));
    }

    getCancelButton() {
        return element(By.buttonText('Cancel'));
    }

    getCancelWholeQueue() {
        return element(By.buttonText('Cancel Whole Queue'));
    }

    getStopButton() {
        return element(By.buttonText('Stop'));
    }
}
