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
import {BuilderPage} from './pages/builder';
import {SettingsPage} from './pages/settings';

test.describe('manage settings', function() {
  test.describe('base', () => {
    test('Builders.buildFetchLimit uses default value from config', async ({page}) => {
      await BuilderPage.gotoBuildersList(page);
      await SettingsPage.goto(page);
      await SettingsPage.checkBuildersBuildFetchLimit(page, 201);
    })
  });

  test.describe('waterfall', () => {
    test('change the "scalling factor" and check it', async ({page}) => {
      const scalingFactor = '10';
      await BuilderPage.gotoBuildersList(page);
      await SettingsPage.goto(page);
      await SettingsPage.changeScallingFactor(page, scalingFactor);
      await BuilderPage.gotoBuildersList(page);
      await SettingsPage.goto(page);
      await SettingsPage.checkScallingFactor(page, scalingFactor);
    })

    test('change the "minimum column width" and check it', async ({page}) => {
      const scalingWidth = '450';
      await BuilderPage.gotoBuildersList(page);
      await SettingsPage.goto(page);
      await SettingsPage.changeColumnWidth(page, scalingWidth);
      await BuilderPage.gotoBuildersList(page);
      await SettingsPage.goto(page);
      await SettingsPage.checkColumnWidth(page, scalingWidth);
    })

    test('change the "lazy loading limit" and check it', async ({page}) => {
      const lazyLoadingLimit = '30';
      await BuilderPage.gotoBuildersList(page);
      await SettingsPage.goto(page);
      await SettingsPage.changeLazyLoadingLimit(page, lazyLoadingLimit);
      await BuilderPage.gotoBuildersList(page);
      await SettingsPage.goto(page);
      await SettingsPage.checkLazyLoadingLimit(page, lazyLoadingLimit);
    })

    test('change the "idle time threshold" and check it', async ({page}) => {
      const idleTimeThreshold = '15';
      await BuilderPage.gotoBuildersList(page);
      await SettingsPage.goto(page);
      await SettingsPage.changeIdleTime(page, idleTimeThreshold);
      await BuilderPage.gotoBuildersList(page);
      await SettingsPage.goto(page);
      await SettingsPage.checkIdleTime(page, idleTimeThreshold);
    })
  });

  test.describe('console', () => {
    test('change the "number of builds to fetch" and check it', async ({page}) => {
      const buildsToFetch = '130';
      await BuilderPage.gotoBuildersList(page);
      await SettingsPage.goto(page);
      await SettingsPage.changeMaxBuild(page, buildsToFetch);
      await BuilderPage.gotoBuildersList(page);
      await SettingsPage.goto(page);
      await SettingsPage.checkMaxBuild(page, buildsToFetch);
    })

    test('change the "number of changes to fetch" and check it', async ({page}) => {
      const changesToFetch = '45';
      await BuilderPage.gotoBuildersList(page);
      await SettingsPage.goto(page);
      await SettingsPage.changeMaxRecentsBuilders(page, changesToFetch);
      await BuilderPage.gotoBuildersList(page);
      await SettingsPage.goto(page);
      await SettingsPage.checkMaxRecentsBuilders(page, changesToFetch);
    })
  });
});
