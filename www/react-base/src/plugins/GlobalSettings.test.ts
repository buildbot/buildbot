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

import {describe, expect, it} from "vitest";
import {GlobalSettings} from "./GlobalSettings";

describe('GlobalSettings', () => {
  it('should keep values when group exists', () => {
    const settings = new GlobalSettings();
    settings.addGroup({
      name: 'Group',
      caption: 'group caption',
      items: [{
        type: 'string',
        name: 'setting1',
        caption: 'caption1',
        defaultValue: "default1"
      }],
    });

    settings.setSetting("Auth.setting1", "value1");

    settings.addGroup({
      name: 'Group',
      caption: 'group caption',
      items: [{
        type: 'string',
        name: 'setting2',
        caption: 'caption2',
        defaultValue: "default2"
      }],
    });

    expect(settings.groups['Group']).toEqual({
      "caption": "group caption",
      "items": {
        "setting1": {
          "caption": "caption1",
          "defaultValue": "default1",
          "name": "setting1",
          "type": "string",
          "value": "default1",
          "valueIsSet": false,
        },
        "setting2": {
          "caption": "caption2",
          "defaultValue": "default2",
          "name": "setting2",
          "type": "string",
          "value": "default2",
          "valueIsSet": false,
        }
      },
      "name": "Group"
    });
  });

  it('should support extending empty group', () => {
    const settings = new GlobalSettings();
    settings.addGroup({
      name: 'Group',
      caption: 'group caption',
      items: [],
    });

    settings.addGroup({
      name: 'Group',
      caption: 'group caption',
      items: [{
        type: 'string',
        name: 'setting2',
        caption: 'caption2',
        defaultValue: "default2"
      }],
    });

    expect(settings.groups['Group']).toEqual({
      "caption": "group caption",
      "items": {
        "setting2": {
          "caption": "caption2",
          "defaultValue": "default2",
          "name": "setting2",
          "type": "string",
          "value": "default2",
          "valueIsSet": false,
        }
      },
      "name": "Group"
    });
  });

  it('should support extending non-empty group with empty group', () => {
    const settings = new GlobalSettings();
    settings.addGroup({
      name: 'Group',
      caption: 'group caption',
      items: [{
        type: 'string',
        name: 'setting1',
        caption: 'caption1',
        defaultValue: "default1"
      }],
    });

    settings.addGroup({
      name: 'Group',
      caption: 'group caption',
      items: [],
    });


    expect(settings.groups['Group']).toEqual({
      "caption": "group caption",
      "items": {
        "setting1": {
          "caption": "caption1",
          "defaultValue": "default1",
          "name": "setting1",
          "type": "string",
          "value": "default1",
          "valueIsSet": false,
        },
      },
      "name": "Group"
    });
  });

  it('setting retrieval', () => {
    const settings = new GlobalSettings();
    settings.addGroup({
      name: 'Group',
      caption: 'group caption',
      items: [{
        type: 'string',
        name: 'setting_string',
        caption: 'caption1',
        defaultValue: "default1"
      }, {
        type: 'integer',
        name: 'setting_integer',
        caption: 'caption2',
        defaultValue: 123
      }, {
        type: 'boolean',
        name: 'setting_boolean',
        caption: 'caption3',
        defaultValue: true
      }],
    });
    expect(settings.getSetting("Group.setting_string")).toEqual("default1");
    settings.setSetting("Group.setting_string", 123);
    expect(settings.getSetting("Group.setting_string")).toEqual("123");
    settings.setSetting("Group.setting_string", "321");
    expect(settings.getSetting("Group.setting_string")).toEqual("321");

    expect(settings.getSetting("Group.setting_integer")).toEqual(123);
    settings.setSetting("Group.setting_integer", "567");
    expect(settings.getSetting("Group.setting_integer")).toEqual(567);
    settings.setSetting("Group.setting_integer", "str");
    expect(settings.getSetting("Group.setting_integer")).toEqual(567);
    settings.setSetting("Group.setting_integer", "321");
    expect(settings.getSetting("Group.setting_integer")).toEqual(321);

    expect(settings.getSetting("Group.setting_boolean")).toEqual(true);
    settings.setSetting("Group.setting_boolean", false);
    expect(settings.getSetting("Group.setting_boolean")).toEqual(false);
    settings.setSetting("Group.setting_boolean", "string");
    expect(settings.getSetting("Group.setting_boolean")).toEqual(false);
  });

  it('setting retrieval with overridden default value', () => {
    const settings = new GlobalSettings();
    settings.addGroup({
      name: 'Group',
      caption: 'group caption',
      items: [{
        type: 'string',
        name: 'setting_string',
        caption: 'caption1',
        defaultValue: "default1"
      }, {
        type: 'integer',
        name: 'setting_integer',
        caption: 'caption2',
        defaultValue: 123
      }, {
        type: 'boolean',
        name: 'setting_boolean',
        caption: 'caption3',
        defaultValue: true
      }],
    });
    settings.fillDefaults({
      "Group.setting_string": "default1_override",
      "Group.setting_integer": 321,
      "Group.setting_boolean": false,
    });
    expect(settings.getSetting("Group.setting_string")).toEqual("default1_override");
    settings.setSetting("Group.setting_string", 123);
    expect(settings.getSetting("Group.setting_string")).toEqual("123");
    settings.setSetting("Group.setting_string", "321");
    expect(settings.getSetting("Group.setting_string")).toEqual("321");

    expect(settings.getSetting("Group.setting_integer")).toEqual(321);
    settings.setSetting("Group.setting_integer", "567");
    expect(settings.getSetting("Group.setting_integer")).toEqual(567);
    settings.setSetting("Group.setting_integer", "str");
    expect(settings.getSetting("Group.setting_integer")).toEqual(567);
    settings.setSetting("Group.setting_integer", "321");
    expect(settings.getSetting("Group.setting_integer")).toEqual(321);

    expect(settings.getSetting("Group.setting_boolean")).toEqual(false);
    settings.setSetting("Group.setting_boolean", true);
    expect(settings.getSetting("Group.setting_boolean")).toEqual(true);
    settings.setSetting("Group.setting_boolean", "string");
    expect(settings.getSetting("Group.setting_boolean")).toEqual(true);
  });

  it('setting saving does not save default', () => {
    localStorage.clear();
    const settings = new GlobalSettings();
    settings.addGroup({
      name: 'Group',
      caption: 'group caption',
      items: [{
        type: 'string',
        name: 'setting_string',
        caption: 'caption1',
        defaultValue: "default1"
      }, {
        type: 'integer',
        name: 'setting_integer',
        caption: 'caption2',
        defaultValue: 123
      }, {
        type: 'boolean',
        name: 'setting_boolean',
        caption: 'caption3',
        defaultValue: true
      }],
    });

    settings.fillDefaults({
      "Group.setting_string": "default1_override"
    });
    settings.save();

    expect(localStorage.getItem("settings")).toEqual(
        "{\"Group\":{}}"
    );
    localStorage.clear();
  });

  it('setting saving', () => {
    localStorage.clear();
    const settings = new GlobalSettings();
    settings.addGroup({
      name: 'Group',
      caption: 'group caption',
      items: [{
        type: 'string',
        name: 'setting_string',
        caption: 'caption1',
        defaultValue: "default1"
      }, {
        type: 'integer',
        name: 'setting_integer',
        caption: 'caption2',
        defaultValue: 123
      }, {
        type: 'boolean',
        name: 'setting_boolean',
        caption: 'caption3',
        defaultValue: true
      }],
    });

    settings.setSetting("Group.setting_string", "value1");
    settings.setSetting("Group.setting_integer", 345);
    settings.setSetting("Group.setting_boolean", false);

    settings.save();

    expect(localStorage.getItem("settings")).toEqual(
      "{\"Group\":{\"setting_string\":\"value1\",\"setting_integer\":345,\"setting_boolean\":false}}"
    );
    localStorage.clear();
  });

  it('setting loading', () => {
    localStorage.clear();
    const settings = new GlobalSettings();
    settings.addGroup({
      name: 'Group',
      caption: 'group caption',
      items: [{
        type: 'string',
        name: 'setting_string',
        caption: 'caption1',
        defaultValue: "default1"
      }, {
        type: 'integer',
        name: 'setting_integer',
        caption: 'caption2',
        defaultValue: 123
      }, {
        type: 'boolean',
        name: 'setting_boolean',
        caption: 'caption3',
        defaultValue: true
      }],
    });

    settings.setSetting("Group.setting_string", "value456");
    settings.setSetting("Group.setting_integer", 789);
    settings.setSetting("Group.setting_boolean", true);

    localStorage.setItem("settings",
      "{\"Group\":{\"setting_string\":\"value1\",\"setting_integer\":345,\"setting_boolean\":false}}");
    settings.load();

    expect(settings.getSetting("Group.setting_string")).toEqual("value1");
    expect(settings.getSetting("Group.setting_integer")).toEqual(345);
    expect(settings.getSetting("Group.setting_boolean")).toEqual(false);
    localStorage.clear();
  });

  it('setting loading unset values roundtrip', () => {
    localStorage.clear();
    const settings = new GlobalSettings();
    settings.addGroup({
      name: 'Group',
      caption: 'group caption',
      items: [{
        type: 'string',
        name: 'setting_string',
        caption: 'caption1',
        defaultValue: "default1"
      }, {
        type: 'integer',
        name: 'setting_integer',
        caption: 'caption2',
        defaultValue: 123
      }, {
        type: 'boolean',
        name: 'setting_boolean',
        caption: 'caption3',
        defaultValue: true
      }],
    });

    localStorage.setItem("settings",
        "{\"Group\":{}}");
    settings.load();
    localStorage.clear();
    settings.save();
    expect(localStorage.getItem("settings")).toEqual(
        "{\"Group\":{}}"
    );
    localStorage.clear();
  });

  it('setting loading late group addition', () => {
    localStorage.clear();

    localStorage.setItem("settings",
      "{\"Group\":{\"setting_string\":\"value1\",\"setting_integer\":345,\"setting_boolean\":false}}");

    const frontendConfig = {
      "Group.setting_string" : "value456",
      "Group.setting_integer": "789",
      "Group.setting_integer_2": "234",
      "Group.setting_boolean": "true"
    };

    const settings = new GlobalSettings();
    // early load before Group is added
    settings.fillDefaults(frontendConfig);
    settings.load();

    settings.addGroup({
      name: 'Group',
      caption: 'group caption',
      items: [{
        type: 'string',
        name: 'setting_string',
        caption: 'caption1',
        defaultValue: "default1"
      }, {
        type: 'integer',
        name: 'setting_integer',
        caption: 'caption2',
        defaultValue: 123
      }, {
        type: 'boolean',
        name: 'setting_boolean',
        caption: 'caption3',
        defaultValue: true
      }, {
        type: 'integer',
        name: 'setting_integer_2',
        caption: 'caption4',
        defaultValue: 123
      }]
    });
    settings.fillDefaults(frontendConfig, 'Group');
    settings.load('Group');

    expect(settings.getSetting("Group.setting_string")).toEqual("value1");
    expect(settings.getSetting("Group.setting_integer")).toEqual(345);
    expect(settings.getSetting("Group.setting_boolean")).toEqual(false);
    expect(settings.getSetting("Group.setting_integer_2")).toEqual(234);
    localStorage.clear();
  });
});
