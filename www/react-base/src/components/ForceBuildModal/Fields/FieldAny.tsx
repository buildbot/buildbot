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
import {ForceBuildModalFieldsState} from "../ForceBuildModalFieldsState";
import {
  ForceSchedulerFieldBase,
  ForceSchedulerFieldBoolean,
  ForceSchedulerFieldChoiceString,
  ForceSchedulerFieldInt,
  ForceSchedulerFieldNested,
  ForceSchedulerFieldString,
  ForceSchedulerFieldText,
  ForceSchedulerFieldUserName
} from "../../../data/classes/Forcescheduler";
import FieldNested from "./FieldNested";
import FieldString from "./FieldString";
import FieldText from "./FieldText";
import FieldInt from "./FieldInt";
import FieldBoolean from "./FieldBoolean";
import FieldUserName from "./FieldUserName";
import FieldChoiceString from "./FieldChoiceString";

type FieldAnyProps = {
  field: ForceSchedulerFieldBase;
  fieldsState: ForceBuildModalFieldsState;
}

const FieldAny = observer(({field, fieldsState}: FieldAnyProps) => {
  if (field.type === 'text') {
    return <FieldString field={field as ForceSchedulerFieldString} fieldsState={fieldsState}/>
  }
  if (field.type === 'textarea') {
    return <FieldText field={field as ForceSchedulerFieldText} fieldsState={fieldsState}/>
  }
  if (field.type === 'int') {
    return <FieldInt field={field as ForceSchedulerFieldInt} fieldsState={fieldsState}/>
  }
  if (field.type === 'bool') {
    return <FieldBoolean field={field as ForceSchedulerFieldBoolean} fieldsState={fieldsState}/>
  }
  if (field.type === 'username') {
    return <FieldUserName field={field as ForceSchedulerFieldUserName} fieldsState={fieldsState}/>
  }
  if (field.type === 'choices') {
    return <FieldChoiceString field={field as ForceSchedulerFieldChoiceString}
                              fieldsState={fieldsState}/>
  }
  if (field.type === 'nested') {
    return <FieldNested field={field as ForceSchedulerFieldNested} fieldsState={fieldsState}/>
  }
  return (<></>);
});

export default FieldAny;
