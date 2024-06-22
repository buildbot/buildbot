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

import {observer} from "mobx-react";
import {Card} from "react-bootstrap";
import {FaSlidersH} from "react-icons/fa";
import {buildbotSetupPlugin} from "buildbot-plugin-support";
import {
  GlobalSettings,
  globalSettings,
  SettingGroup,
  SettingItem, SettingValue
} from "../../plugins/GlobalSettings";
import {FieldBoolean} from "./Fields/FieldBoolean";
import {FieldChoiceCombo} from "./Fields/FieldChoiceCombo";
import {FieldFloat} from "./Fields/FieldFloat";
import {FieldInteger} from "./Fields/FieldInteger";
import {FieldString} from "./Fields/FieldString";

const computeMasterCfgSnippet = (settings: GlobalSettings) => {
  let code = "c['www']['ui_default_config'] = { \n";
  for (let groupName in settings.groups) {
    const group = settings.groups[groupName];
    for (let item of Object.values(group.items)) {
      if ((item.value !== item.defaultValue) && (item.value !== null)) {
        let value = JSON.stringify(item.value);
        if (value === "true") {
          value = "True";
        }
        if (value === "false") {
          value = "False";
        }
        code += `    '${groupName}.${item.name}': ${value},\n`;
      }
    }
  }
  code += "}\n";
  return code;
};

export const SettingsView = observer(() => {
  const masterCfgOverrideSnippet = computeMasterCfgSnippet(globalSettings);

  const renderGroupItem = (groupName: string, item: SettingItem) => {
    const itemSelector = `${groupName}.${item.name}`;
    const setSetting = (value: SettingValue) => {
      globalSettings.setSetting(itemSelector, value);
      globalSettings.save();
    };

    if (item.type === 'boolean') {
      return <FieldBoolean item={item} setSetting={setSetting}/>;
    }

    if (item.type === 'integer') {
      return <FieldInteger item={item} setSetting={setSetting}/>
    }

    if (item.type === 'float') {
      return <FieldFloat item={item} setSetting={setSetting}/>
    }

    if (item.type === 'string') {
      return <FieldString item={item} setSetting={setSetting}/>;
    }

    if (item.type === 'choice_combo') {
      return <FieldChoiceCombo item={item} setSetting={setSetting}/>;
    }

    return (
      <div className="alert alert-danger">
        bad item type: {item.type} should be one of: bool, choices, integer, text
      </div>
    );
  };

  const renderGroup = (group: SettingGroup) => {
    return (
      <Card key={group.name}>
        <Card.Header>
          <Card.Title>{group.caption}</Card.Title>
        </Card.Header>
        <Card.Body>
          <form data-bb-test-id={`settings-group-${group.name}`}
                name={group.name}>
            {Object.values(group.items).map(item => (
              <div key={item.name}>
                <div className="col-md-12">
                  {renderGroupItem(group.name, item)}
                </div>
              </div>
            ))}
          </form>
        </Card.Body>
      </Card>
    );
  }

  return (
    <div className="container">
      {Object.values(globalSettings.groups).map(group => renderGroup(group))}
      <Card>
        <Card.Header>
          <Card.Title>Override defaults for all users</Card.Title>
        </Card.Header>
        <Card.Body>
          <p>To override defaults for all users, put following code in master.cfg</p>
          <pre>{masterCfgOverrideSnippet}</pre>
        </Card.Body>
      </Card>
    </div>
  );
});

buildbotSetupPlugin((reg) => {
  reg.registerMenuGroup({
    name: 'settings',
    caption: 'Settings',
    icon: <FaSlidersH/>,
    order: 99,
    route: '/settings',
    parentName: null,
  });

  reg.registerRoute({
    route: "/settings",
    group: null,
    element: () => <SettingsView/>,
  });
});
