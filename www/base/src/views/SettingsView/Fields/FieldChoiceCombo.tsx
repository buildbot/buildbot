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
import {Form} from "react-bootstrap";
import {SettingItem, SettingValue} from "../../../plugins/GlobalSettings";

type FieldChoiceCombo = {
  item: SettingItem;
  setSetting: (value: SettingValue) => void
};

export const FieldChoiceCombo = observer(({item, setSetting}: FieldChoiceCombo) => {
  return (
    <div className="form-group">
      <label>{item.caption}</label>
      <Form.Control as="select" className="my-1 mr-sm-2" data-bb-test-id={`settings-field-${item.name}`}
          id="inlineFormCustomSelectPref" custom defaultValue={item.value as string}
          onChange={event => { console.log(`set ${event.target.value}`); setSetting(event.target.value); }}>
        {
          item.choices === undefined ? <></> : item.choices.map(ch => (<option value={ch}>{ch}</option>))
        }
      </Form.Control>
    </div>
  );
});