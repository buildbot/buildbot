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

import {ForceSchedulerFieldChoiceString} from "buildbot-data-js";
import {ForceBuildModalFieldsState} from "../ForceBuildModalFieldsState";
import {observer} from "mobx-react";
import {FieldBase} from "./FieldBase";
import {Form} from "react-bootstrap";

type FieldChoiceStringProps = {
  field: ForceSchedulerFieldChoiceString;
  fieldsState: ForceBuildModalFieldsState;
}

export const FieldChoiceString = observer(({field, fieldsState}: FieldChoiceStringProps) => {
  const state = fieldsState.fields.get(field.fullName)!;

  return (
    <FieldBase field={field} fieldsState={fieldsState}>
      <Form.Label className="col-sm-10">{field.label}</Form.Label>
      <div className="col-sm-10">
        <Form.Control as="select" multiple={field.multiple} value={state.value}
                      onChange={event => fieldsState.setValue(field.fullName, event.target.value)}>
          {field.choices.map(choice => (<option>{choice}</option>))}
        </Form.Control>
        { !field.strict && !field.multiple
          ? <input data-bb-test-id={`force-field-${field.fullName}`}
                   className="select-editable form-control" type="text" value={state.value}
                   onChange={event => fieldsState.setValue(field.fullName, event.target.value)}/>
          : <></>
        }
      </div>
    </FieldBase>
  );
});
