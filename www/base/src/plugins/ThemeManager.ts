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

import {buildbotSetupPlugin} from 'buildbot-plugin-support';
import {globalSettings} from './GlobalSettings';
import {autorun} from 'mobx';

const darkThemeVariables: Record<string, string> = {
  'bb-avatar-bg-color': '#3a3a4c',
  'bb-background-color': '#1e1e2e',
  'bb-border-color': '#3a3a4c',
  'bb-btn-background-color': '#2a2a3c',
  'bb-btn-border-color': '#4a4a5c',
  'bb-btn-hover-background-color': '#3a3a4c',
  'bb-btn-hover-border-color': '#5a5a6c',
  'bb-card-bg-color': '#2a2a3c',
  'bb-card-border-color': '#3a3a4c',
  'bb-card-header-text-color': '#d4d4d8',
  'bb-dropdown-bg-color': '#2a2a3c',
  'bb-dropdown-border-color': '#3a3a4c',
  'bb-dropdown-hover-bg-color': '#33334a',
  'bb-highlight-border-color': '#e7d100',
  'bb-home-card-header-bg-color': '#1a5276',
  'bb-link-color': '#79b8e8',
  'bb-muted-text-color': '#a0a0b0',
  'bb-navbar-link-color': '#a0a0b0',
  'bb-navbar-separator-color': '#4a4a5c',
  'bb-panel-separator-bg-color': '#3a3a4c',
  'bb-sidebar-background-color': '#1a1a2e',
  'bb-sidebar-button-current-background-color': '#16162a',
  'bb-sidebar-button-current-text-color': '#b0b8d0',
  'bb-sidebar-button-hover-background-color': '#0f0f1e',
  'bb-sidebar-button-hover-text-color': '#fff',
  'bb-sidebar-button-text-color': '#b0b8d0',
  'bb-sidebar-footer-background-color': '#16162a',
  'bb-sidebar-header-background-color': '#16162a',
  'bb-sidebar-header-text-color': '#e0e0e0',
  'bb-sidebar-stripe-current-color': '#8c5e10',
  'bb-sidebar-stripe-hover-color': '#e99d1a',
  'bb-sidebar-title-text-color': '#7a8bb5',
  'bb-tag-active-bg-color': '#3d8b3d',
  'bb-tag-bg-color': '#4a4a5c',
  'bb-text-color': '#d4d4d8',
};

const lightThemeVariables: Record<string, string> = {
  'bb-avatar-bg-color': '#ccc',
  'bb-background-color': '#fff',
  'bb-border-color': '#ddd',
  'bb-btn-background-color': '#fff',
  'bb-btn-border-color': '#ccc',
  'bb-btn-hover-background-color': '#e6e6e6',
  'bb-btn-hover-border-color': '#adadad',
  'bb-card-bg-color': '#f5f5f5',
  'bb-card-border-color': '#ddd',
  'bb-card-header-text-color': '#333',
  'bb-dropdown-bg-color': '#f7f7f7',
  'bb-dropdown-border-color': '#ebebeb',
  'bb-dropdown-hover-bg-color': '#f5f5f5',
  'bb-highlight-border-color': '#ffff00',
  'bb-home-card-header-bg-color': '#337ab7',
  'bb-link-color': '#337ab7',
  'bb-muted-text-color': '#555',
  'bb-navbar-separator-color': '#ccc',
  'bb-panel-separator-bg-color': '#ddd',
  'bb-sidebar-background-color': '#30426a',
  'bb-sidebar-button-current-background-color': '#273759',
  'bb-sidebar-button-current-text-color': '#b2bfdc',
  'bb-sidebar-button-hover-background-color': '#1b263d',
  'bb-sidebar-button-hover-text-color': '#fff',
  'bb-sidebar-button-text-color': '#b2bfdc',
  'bb-sidebar-footer-background-color': '#273759',
  'bb-sidebar-header-background-color': '#273759',
  'bb-sidebar-header-text-color': '#fff',
  'bb-sidebar-stripe-current-color': '#8c5e10',
  'bb-sidebar-stripe-hover-color': '#e99d1a',
  'bb-sidebar-title-text-color': '#627cb7',
  'bb-tag-active-bg-color': '#5cb85c',
  'bb-tag-bg-color': '#777',
  'bb-text-color': '#333',
};

// Portal overrides for elements rendered outside #root (tooltips, popovers, modals).
// Injected as a runtime <style> tag appended to <head> so it loads after all other
// stylesheets (including the ui package's bundled Bootstrap CSS).
const portalOverrides = `
.tooltip .tooltip-inner {
  background-color: var(--bb-background-color) !important;
  color: var(--bb-text-color) !important;
}
.tooltip .arrow::before {
  border-top-color: var(--bb-background-color) !important;
}
.tooltip.bs-tooltip-bottom .arrow::before {
  border-bottom-color: var(--bb-background-color) !important;
}
.tooltip.bs-tooltip-left .arrow::before {
  border-left-color: var(--bb-background-color) !important;
}
.tooltip.bs-tooltip-right .arrow::before {
  border-right-color: var(--bb-background-color) !important;
}
.tooltip .card {
  background-color: var(--bb-background-color) !important;
  border-color: var(--bb-card-border-color) !important;
  color: var(--bb-text-color) !important;
}
.tooltip .card-header {
  background-color: var(--bb-card-bg-color) !important;
  border-bottom-color: var(--bb-card-border-color) !important;
  color: var(--bb-text-color) !important;
}
.tooltip .list-group-item {
  background-color: var(--bb-background-color) !important;
  border-color: var(--bb-card-border-color) !important;
  color: var(--bb-text-color) !important;
}
.popover {
  background-color: var(--bb-background-color) !important;
  border-color: var(--bb-border-color) !important;
  color: var(--bb-text-color) !important;
}
.popover-header {
  background-color: var(--bb-card-bg-color) !important;
  border-bottom-color: var(--bb-border-color) !important;
  color: var(--bb-text-color) !important;
}
.popover-body {
  color: var(--bb-text-color) !important;
}
`;

let portalStyleElement: HTMLStyleElement | null = null;

function ensurePortalOverrides() {
  if (portalStyleElement) return;
  portalStyleElement = document.createElement('style');
  portalStyleElement.textContent = portalOverrides;
  document.head.appendChild(portalStyleElement);
}

function applyTheme(mode: string) {
  const root = document.documentElement;
  const variables = mode === 'Dark' ? darkThemeVariables : lightThemeVariables;
  for (const [name, value] of Object.entries(variables)) {
    root.style.setProperty(`--${name}`, value);
  }
  ensurePortalOverrides();
}

buildbotSetupPlugin((reg) => {
  reg.registerSettingGroup({
    name: 'Appearance',
    caption: 'Appearance settings',
    items: [
      {
        type: 'choice_combo',
        name: 'theme',
        caption: 'Theme',
        choices: ['Light', 'Dark'],
        defaultValue: 'Light',
      },
    ],
  });

  autorun(() => {
    const theme = globalSettings.getChoiceComboSetting('Appearance.theme');
    if (theme) {
      applyTheme(theme);
    }
  });
});
