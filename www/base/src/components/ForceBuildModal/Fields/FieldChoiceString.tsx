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
import {FaRegQuestionCircle} from "react-icons/fa";
import {observer} from "mobx-react";
import {FieldBase} from "./FieldBase";
import {Form} from "react-bootstrap";
import {Tooltip} from 'react-tooltip'
import Select, { ActionMeta, PropsValue, SingleValue, MultiValue } from 'react-select';
import CreatableSelect from 'react-select/creatable';

type FieldChoiceStringProps = {
  field: ForceSchedulerFieldChoiceString;
  fieldsState: ForceBuildModalFieldsState;
}

interface SelectOption {
  readonly value: string,
  readonly label: string,
}

const ValueToSelectOption = (value: string): SelectOption => { return {value: value, label: value} };

export const FieldChoiceString = observer(({field, fieldsState}: FieldChoiceStringProps) => {
  const state = fieldsState.fields.get(field.fullName)!;
  if (field.multiple && !Array.isArray(state.value)) {
    fieldsState.setValue(field.fullName, state.value ? [state.value] : []);
  }

  const onChange = (
    newValue: PropsValue<SelectOption>,
    _actionMeta: ActionMeta<SelectOption>
  ) => {
    fieldsState.setValue(
      field.fullName,
      (
        field.multiple  ? (newValue as MultiValue<SelectOption>).map(e => e.value)
                        : (newValue as SingleValue<SelectOption>)?.value ?? null
      )
    );
  };
  let options = field.choices.map(ValueToSelectOption);
  if (!field.multiple && !field.default && !field.choices.includes(field.default)) {
    options = [{value: field.default, label: 'Select an option'}, ...options];
  }

  const props = {
    isMulti: field.multiple,
    defaultValue: field.multiple ? (state.value as string[]).map(ValueToSelectOption) : ValueToSelectOption(state.value as string),
    onChange,
    options,
  };

  return (
    <FieldBase field={field} fieldsState={fieldsState}>
      <Form.Label className="col-sm-10">{field.label}
        {field.tooltip && (
          <span data-tooltip-id="my-tooltip" data-tooltip-html={field.tooltip}>
            <FaRegQuestionCircle className="tooltip-icon"/>
          </span>
        )}
        <Tooltip id="my-tooltip" clickable/>
      </Form.Label>
      <div className="col-sm-10" data-bb-test-id={`force-field-${field.fullName}`}>
        {
          field.strict ?
          <Select<SelectOption, boolean> {...props} /> :
          <CreatableSelect<SelectOption, boolean> {...props} />
        }
      </div>
    </FieldBase>
  );
});
