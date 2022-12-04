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
            field.fields.filter(f => !shouldHideField(f)).map(f => (
              <Tab title={f.tablabel} className={columnClass}>
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
          <div className="form-horizontal">
            {
              field.fields.filter(f => !shouldHideField(f)).map(f => (
                <div className={columnClass}>
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
    <div className="form-horizontal">
      {
        field.fields.filter(f => !shouldHideField(f)).map(f => (
          <div className={columnClass}>
            <FieldAny field={f} fieldsState={fieldsState}></FieldAny>
          </div>
        ))
      }
    </div>
  );
});

export default FieldNested;
