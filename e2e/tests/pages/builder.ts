/*
  This file is part of Buildbot.  Buildbot is free software: you can
  redistribute it and/or modify it under the terms of the GNU General Public
  License as published by the Free Software Foundation, version 2.

  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
  FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
  details.

  You should have received a copy of the GNU General Public License along with
  this program; if not, write to the Free Software Foundation, Inc., 51
  Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

  Copyright Buildbot Team Members
*/

import {expect, Page} from "@playwright/test";
import {BasePage} from "./base";

export class BuilderPage {
  static async gotoBuildersList(page: Page) {
    await page.goto('/#/builders');
    await BasePage.waitUntilFinishedLoading(page);
  }

  static async goto(page: Page, builder: string) {
    await BuilderPage.gotoBuildersList(page);
    await page.getByRole('link', {name: builder, exact: true}).click();
    await page.waitForURL(/\/#\/builders\/[0-9]+$/);
    await BasePage.waitUntilFinishedLoading(page);
  }

  static async gotoForce(page: Page, builder: string, forceName: string) {
    await BuilderPage.goto(page, builder);
    await page.locator(`button:text("${forceName}")`).first().click();
    await expect(page.locator(".modal-title.h4")).toBeEnabled();
  }

  static async gotoBuild(page: Page, builder: string, buildRef: string) {
    await BuilderPage.goto(page, builder);
    await BuilderPage.buildLinkByBuildRef(page, buildRef).click();
    await page.waitForURL(/\/#\/builders\/[0-9]\/builds\/[0-9]+$/);
    await BasePage.waitUntilFinishedLoading(page);
  }

  static async getLastFinishedBuildNumber(page: Page) {
    const finishedBuildCss =
      '.bb-badge-round.results_SUCCESS, ' +
      '.bb-badge-round.results_WARNINGS, ' +
      '.bb-badge-round.results_FAILURE, ' +
      '.bb-badge-round.results_SKIPPED, ' +
      '.bb-badge-round.results_EXCEPTION, ' +
      '.bb-badge-round.results_RETRY, ' +
      '.bb-badge-round.results_CANCELLED ';

    const el = page.getByTestId('build-link').and(page.locator(finishedBuildCss));
    if (await el.count() > 0) {
      const text = await el.first().textContent();
      if (text === null) {
        return 0;
      }

      const m = /.*\(([0-9]*)\)/.exec(text);
      if (m !== null) {
        return Number.parseInt(m[1]);
      }
      return Number.parseInt(text);
    }
    return 0;
  }


  static async getBuildResult(page: Page, buildNumber: number) {
    const links = BuilderPage.buildLinkByBuildRef(page, buildNumber.toString());

    const resultTypes = [
      ['.bb-badge-round.results_SUCCESS', "SUCCESS"],
      ['.bb-badge-round.results_WARNINGS', "WARNINGS"],
      ['.bb-badge-round.results_FAILURE', "FAILURE"],
      ['.bb-badge-round.results_SKIPPED', "SKIPPED"],
      ['.bb-badge-round.results_EXCEPTION', "EXCEPTION"],
      ['.bb-badge-round.results_RETRY', "RETRY"],
      ['.bb-badge-round.results_CANCELLED', "CANCELLED"]
    ];

    for (let i = 0; i < resultTypes.length; ++i) {
      const css = resultTypes[i][0];
      const resultType = resultTypes[i][1];

      if (await links.and(page.locator(css)).count() > 0) {
        return resultType;
      }
    }

    return "NOT FOUND";
  }

  static buildLinkByBuildRef(page: Page, buildRef: string) {
    return page.getByTestId("build-link").and(page.locator(`:text("${buildRef}")`));
  }

  static async waitBuildFinished(page: Page, reference: number) {
    await expect.configure({ timeout: 30000 }).poll(async () => {
      const currentBuildCount = await BuilderPage.getLastFinishedBuildNumber(page);
      return currentBuildCount === reference;
    }, {
      message: "build count has been incremented",
    }).toBeTruthy();
  }

  static async waitGoToBuild(page: Page, expectedBuildNumber: number) {
    await expect.poll(async () => {
      let buildUrl = page.url();
      const split = buildUrl.split("/");
      const buildsPart = split[split.length-2];
      const number = Number.parseInt(split[split.length-1]);
      if (buildsPart !== "builds") {
        return false;
      }
      return (number === expectedBuildNumber);
    }, {
      message: "went into build"
    }).toBeTruthy();
  }

  static async clickStopButton(page: Page) {
    await page.locator('button:text("Stop")').click();
  }

  static async clickPreviousButtonAndWait(page: Page) {
    await BasePage.waitUntilUrlChanged(page, async () => {
      await page.getByRole("link", {name: "Previous"}).click();
    });
    await BasePage.waitUntilFinishedLoading(page);
  }

  static async clickNextButtonAndWait(page: Page) {
    await BasePage.waitUntilUrlChanged(page, async () => {
      await page.getByRole("link", {name: "Next"}).click();
    });
    await BasePage.waitUntilFinishedLoading(page);
  }

  static async clickRebuildButton(page: Page) {
    await BasePage.waitUntilUrlChanged(page, async () => {
      await page.getByRole("button", {name: "Rebuild"}).click();
    });
  }

  static async checkBuilderURL(page: Page, builder: string) {
    await expect(page.locator(`a:text("${builder}")`).count()).toBeGreaterThan(0);
  }
}
