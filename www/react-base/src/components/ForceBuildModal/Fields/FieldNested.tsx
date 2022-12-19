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
  ForceSchedulerFieldNested
} from "../../../data/classes/Forcescheduler";
import FieldAny from "./FieldAny";
import {Card, Tab, Tabs} from "react-bootstrap";

const shouldHideField = (field: ForceSchedulerFieldBase) => {
  if (field.hide) {
    return true;
  }
  if (field.type === 'nested') {
    const fields = (field as ForceSchedulerFieldNested).fields;
    for (const f of fields) {
      if (!shouldHideField(f)) {
        return false;
      }
    }
    // all sub-fields are hidden - hide parent field too
    return true;
  }
  return false;
}

const filteredMap = (fields: ForceSchedulerFieldBase[],
                     callbackFn: (f: ForceSchedulerFieldBase, index: number) => JSX.Element) => {
  // .filter(...).map(...) cannot be used because the indexes of the original array need to be preserved in the callback
  const res: JSX.Element[] = [];
  for (let i = 0; i < fields.length; ++i) {
    const field = fields[i];
    if (shouldHideField(field)) {
      continue;
    }
    res.push(callbackFn(field, i));
  }
  return res;
}

type FieldNestedProps = {
  field: ForceSchedulerFieldNested;
  fieldsState: ForceBuildModalFieldsState;
}

const FieldNested = observer(({field, fieldsState}: FieldNestedProps) => {

  const columns = field.columns ?? 1;
  const columnClass = `col-sm-${(12 / columns).toString()}`;

  if (field.layout === 'tabs') {
    return (
      <div>
        <Tabs>
          {
            filteredMap(field.fields, (f, index) => (
              <Tab key={f.name === "" ? index : f.name} title={f.tablabel} className={columnClass}>
                <FieldAny field={f} fieldsState={fieldsState}></FieldAny>
              </Tab>
            ))
          }
        </Tabs>
      </div>
    );
  }

  if (field.layout === 'vertical') {
    return (
      <Card>
        { field.label !== null && field.label !== '' ? <Card.Header>{field.label}</Card.Header> : <></> }
        <Card.Body>
          <div className="row">
            {
              filteredMap(field.fields, (f, index) => (
                <div key={f.name === "" ? index : f.name} className={columnClass}>
                  <FieldAny field={f} fieldsState={fieldsState}></FieldAny>
                </div>
              ))
            }
          </div>
        </Card.Body>
      </Card>
    )
  }

  // layout === simple
  return (
    <div className="row">
      {
        filteredMap(field.fields, (f, index) => (
          <div key={f.name === "" ? index : f.name} className={columnClass}>
            <FieldAny field={f} fieldsState={fieldsState}></FieldAny>
          </div>
        ))
      }
    </div>
  );
});

export default FieldNested;
