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

export class WorkerPage {
  static async gotoWorkerList(page: Page) {
    await page.goto('/#/workers');
    await BasePage.waitUntilFinishedLoading(page);
  }

  static async gotoWorker(page: Page, workerName: string) {
    await BasePage.waitUntilUrlChanged(page, async () => {
      await page.locator("tr").locator("td").nth(2).getByText(workerName).click();
    });
    await BasePage.waitUntilFinishedLoading(page);
  }

  static async gotoBuildLink(page: Page, builderName: string, buildNumber: number) {
    await BasePage.waitUntilUrlChanged(page, async () => {
      await page.locator("tr")
        .filter({has: page.locator("td").nth(0).getByText(builderName)})
        .filter({has: page.locator("td").nth(1).getByText(buildNumber.toString())})
        .locator("td").nth(1).getByText(buildNumber.toString()).click();
    });
    await BasePage.waitUntilFinishedLoading(page);
  }
}
