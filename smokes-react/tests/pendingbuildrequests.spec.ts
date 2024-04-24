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

import {expect, test} from "@playwright/test";
import {ForcePage} from "./pages/force";
import {HomePage} from './pages/home';
import {PendingBuildrequestsPage} from './pages/pendingbuildrequests';
import {BuilderPage} from './pages/builder';

test.describe('pending build requests', function() {
  test.afterEach(async ({page}) => {
    await HomePage.waitAllBuildsFinished(page);
  });

  test('shows', async ({page}) => {
    await BuilderPage.gotoBuildersList(page);
    await BuilderPage.gotoForce(page, "slowruntests", "force");
    await ForcePage.clickStartButtonAndWait(page);
    await BuilderPage.gotoForce(page, "slowruntests", "force");
    await ForcePage.clickStartButtonAndWait(page);

    // hopefully we'll see at least one buildrequest by the time we get to
    // the pending build requests page
    await PendingBuildrequestsPage.goto(page);

    await expect.poll(async () => {
      return (await PendingBuildrequestsPage.getAllBuildrequestRows(page).count());
    }, {
      message: "found at least one buildrequest"
    }).toBeGreaterThan(0);

    const br = await PendingBuildrequestsPage.getAllBuildrequestRows(page).first();
    await expect.poll(async () => {
      return (await br.locator('td').nth(1).locator('a').textContent());
    }, {
      message: "found at least one buildrequest with correct name"
    }).toMatch('slowruntests');

    // kill remaining builds
    let gotAlert = false;
    page.on('dialog', async dialog => {
      gotAlert = true;
      await dialog.accept()
    });

    await BuilderPage.goto(page, "slowruntests");
    await ForcePage.clickCancelWholeQueue(page);
    await expect.poll(() => gotAlert, {
      message: "found confirmation alert"
    }).toBeTruthy();
  });
});
