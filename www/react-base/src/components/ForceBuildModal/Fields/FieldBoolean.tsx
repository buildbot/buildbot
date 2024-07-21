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

import {ForceSchedulerFieldBoolean} from "buildbot-data-js";
import {ForceBuildModalFieldsState} from "../ForceBuildModalFieldsState";
import {observer} from "mobx-react";

type FieldBooleanProps = {
  field: ForceSchedulerFieldBoolean;
  fieldsState: ForceBuildModalFieldsState;
}

export const FieldBoolean = observer(({field, fieldsState}: FieldBooleanProps) => {
  const state = fieldsState.fields.get(field.fullName)!;

  return (
    <div className="form-group">
      <div className="col-sm-10 col-sm-offset-2">
        <div className="checkbox">
          <label>
            <input
              data-bb-test-id={`force-field-${field.fullName}`}
              type="checkbox" checked={state.value}
              onChange={event => fieldsState.setValue(field.fullName,
                event.target.checked)} /> {field.label}
          </label>
        </div>
      </div>
    </div>
  );
});
