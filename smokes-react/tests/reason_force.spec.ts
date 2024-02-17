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

import {test} from "@playwright/test";
import {ForcePage} from "./pages/force";
import {HomePage} from './pages/home';
import {BuilderPage} from './pages/builder';

test.describe('force and cancel', function() {
  test.afterEach(async ({page}) => {
    await HomePage.waitAllBuildsFinished(page);
  });

  test('should create a build', async ({page}) => {
    await BuilderPage.gotoBuildersList(page);
    await BuilderPage.goto(page, "runtests");
    const lastbuild = await BuilderPage.getLastFinishedBuildNumber(page);
    await BuilderPage.gotoForce(page, "runtests", "force");
    await ForcePage.clickStartButtonAndWaitRedirectToBuild(page);
    await BuilderPage.goto(page, "runtests");
    await BuilderPage.waitBuildFinished(page, lastbuild + 1);
  });

  test('should create a build with a dedicated reason and cancel it', async ({page}) => {
    await BuilderPage.gotoBuildersList(page);
    await BuilderPage.goto(page, "runtests");
    await BuilderPage.gotoForce(page, "runtests", "force");
    await ForcePage.clickCancelButton(page);
  });

  test('should create a build with a dedicated reason and Start it',
      async ({page}) => {
    await BuilderPage.gotoBuildersList(page);
    await BuilderPage.goto(page, "runtests");
    await BuilderPage.gotoForce(page, "runtests", "force");
    await ForcePage.setReason(page, "New Test Reason");
    await ForcePage.setProjectName(page, "BBOT9");
    await ForcePage.setBranchName(page, "Gerrit Branch");
    await ForcePage.setRepo(page, "http://name.com");
    await ForcePage.setRevisionName(page, "12345");
    await ForcePage.clickStartButtonAndWaitRedirectToBuild(page);
  });
});
