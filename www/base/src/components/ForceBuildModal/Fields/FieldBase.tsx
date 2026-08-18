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

import {ForceSchedulerFieldBoolean} from 'buildbot-data-js';
import {ForceBuildModalFieldsState} from '../ForceBuildModalFieldsState';
import {observer} from 'mobx-react';
import {useEffect} from 'react';

type FieldBaseProps = {
  field: ForceSchedulerFieldBoolean;
  fieldsState: ForceBuildModalFieldsState;
  children: JSX.Element | JSX.Element[] | string;
};

export const FieldBase = observer(({field, fieldsState, children}: FieldBaseProps) => {
  const state = fieldsState.fields.get(field.fullName)!;

  let classNames = 'form-group';
  if (state.errors.length > 0) {
    classNames += ' has-error';
  }

  const errors: JSX.Element[] = [];
  for (const error of state.errors) {
    errors.push(<div className={'bb-force-build-modal-field-error'}>{error}</div>);
  }

  useEffect(() => {
    if (field.autopopulate === null) {
      return;
    }
    const autopopulateFields = field.autopopulate[state.value];
    if (autopopulateFields === undefined) {
      return;
    }

    for (const targetFieldname in autopopulateFields) {
      const targetFieldState = fieldsState.fields.get(targetFieldname);
      if (targetFieldState === undefined) {
        console.error(
          `[${field.fullName}] bad autopopulate (for value: ${state.value}) configuration: ${targetFieldname} is not a field name`,
        );
        continue;
      }
      targetFieldState.setValue(autopopulateFields[targetFieldname]);
    }
  }, [state.value, field.autopopulate, field.fullName, fieldsState.fields]);

  return (
    <div>
      <div className={classNames}>
        {errors}
        <div
          uib-popover="{{field.errors}}"
          popover-title="{{field.label}}"
          popover-is-open="field.haserrors"
          popover-trigger="none"
        ></div>
        {children}
      </div>
    </div>
  );
});
