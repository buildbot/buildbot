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

import {ForceSchedulerFieldBoolean} from "../../../data/classes/Forcescheduler";
import {ForceBuildModalFieldsState} from "../ForceBuildModalFieldsState";
import {observer} from "mobx-react";

type FieldBaseProps = {
  field: ForceSchedulerFieldBoolean;
  fieldsState: ForceBuildModalFieldsState;
  children: JSX.Element | JSX.Element[] | string;
}

const FieldBase = observer(({field, fieldsState, children}: FieldBaseProps) => {
  const state = fieldsState.fields.get(field.name)!;

  let classNames = "form-group";
  if (state.errors.length > 0) {
    classNames += " has-error";
  }

  const errors: JSX.Element[] = [];
  for (const error of state.errors) {
    errors.push((
      <div className={"bb-force-build-modal-field-error"}>{error}</div>
    ))
  }

  return (
    <div>
      <div className={classNames}>
        {errors}
        <div uib-popover="{{field.errors}}"
             popover-title="{{field.label}}" popover-is-open="field.haserrors"
             popover-trigger="none">
        </div>
        {children}
      </div>
    </div>
  );
});

export default FieldBase;
