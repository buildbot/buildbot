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

export class SettingsPage {

  static async goto(page: Page) {
    await page.goto('/#/settings');
    await BasePage.waitUntilFinishedLoading(page);
  }

  static getItem(page: Page, group: string, name: string) {
    return page.getByTestId(`settings-group-${group}`).getByTestId(`settings-field-${name}`);
  }

  static async changeScallingFactor(page: Page, value: string) {
    await SettingsPage.getItem(page, "Waterfall", "scaling_waterfall").fill(value);
  }

  static async checkBuildersBuildFetchLimit(page: Page, value: number) {
    expect(await SettingsPage.getItem(page, "Builders", "buildFetchLimit").getAttribute("value"))
      .toEqual(value.toString());
  }

  static async checkScallingFactor(page: Page, value: string) {
    expect(await SettingsPage.getItem(page, "Waterfall", "scaling_waterfall").getAttribute("value"))
      .toEqual(value);
  }

  static async changeColumnWidth(page: Page, value: string) {
    await SettingsPage.getItem(page, "Waterfall", "min_column_width_waterfall").fill(value);
  }

  static async checkColumnWidth(page: Page, value: string) {
    expect(await SettingsPage.getItem(page, "Waterfall", "min_column_width_waterfall")
      .getAttribute("value")).toEqual(value);
  }

  static async changeLazyLoadingLimit(page: Page, value: string) {
    await SettingsPage.getItem(page, "Waterfall", "lazy_limit_waterfall").fill(value);
  }

  static async checkLazyLoadingLimit(page: Page, value: string) {
    expect(await SettingsPage.getItem(page, "Waterfall", "lazy_limit_waterfall")
      .getAttribute("value")).toEqual(value);
  }

  static async changeIdleTime(page: Page, value: string) {
    await SettingsPage.getItem(page, "Waterfall", "idle_threshold_waterfall").fill(value);
  }

  static async checkIdleTime(page: Page, value: string) {
    expect(await SettingsPage.getItem(page, "Waterfall", "idle_threshold_waterfall")
      .getAttribute("value")).toEqual(value);
  }

  static async changeMaxBuild(page: Page, value: string) {
    await SettingsPage.getItem(page, "Console", "buildLimit").fill(value);
  }

  static async checkMaxBuild(page: Page, value: string) {
    expect(await SettingsPage.getItem(page, "Console", "buildLimit")
      .getAttribute("value")).toEqual(value);
  }

  static async changeMaxRecentsBuilders(page: Page, value: string) {
    await SettingsPage.getItem(page, "Console", "changeLimit").fill(value);
  }

  static async checkMaxRecentsBuilders(page: Page, value: string) {
    expect(await SettingsPage.getItem(page, "Console", "changeLimit")
      .getAttribute("value")).toEqual(value);
  }
}
