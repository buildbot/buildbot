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

import {ForceSchedulerFieldText} from "buildbot-data-js";
import {ForceBuildModalFieldsState} from "../ForceBuildModalFieldsState";
import {observer} from "mobx-react";
import {FieldBase} from "./FieldBase";

type FieldTextProps = {
  field: ForceSchedulerFieldText;
  fieldsState: ForceBuildModalFieldsState;
}

export const FieldText = observer(({field, fieldsState}: FieldTextProps) => {
  const state = fieldsState.fields.get(field.fullName)!;

  return (
    <FieldBase field={field} fieldsState={fieldsState}>
      <label htmlFor={field.fullName} className="control-label col-sm-10">{field.label}</label>
      <div className="col-sm-10">
        <textarea data-bb-test-id={`force-field-${field.fullName}`}
                  className="form-control" rows={field.rows} value={state.value}
                  onChange={event => fieldsState.setValue(field.fullName, event.target.value)}/>
      </div>
    </FieldBase>
  );
});
