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

import './ForceBuildModal.less';
import {Button, Modal} from "react-bootstrap";
import {useContext, useState} from "react";
import {
  ControlParams,
  Forcescheduler,
  ForceSchedulerFieldBase,
  ForceSchedulerFieldNested
} from "buildbot-data-js";
import {ConfigContext} from "buildbot-ui";
import {observer, useLocalObservable} from "mobx-react";
import {ForceBuildModalFieldsState} from "./ForceBuildModalFieldsState";
import {FieldNested} from "./Fields/FieldNested";

const visitFields = (fields: ForceSchedulerFieldBase[],
                     callback: (field: ForceSchedulerFieldBase) => void)  => {
  for (let field of fields) {
    if (field.type === 'nested') {
      visitFields((field as ForceSchedulerFieldNested).fields, callback);
    } else {
      callback(field);
    }
  }
}

const flattenFields = (fields: ForceSchedulerFieldBase[])  => {
  let flatFields: ForceSchedulerFieldBase[] = [];
  visitFields(fields, field => flatFields.push(field));
  return flatFields;
}

type ForceBuildModalProps = {
  scheduler: Forcescheduler;
  builderid: number;
  onClose: (buildRequestNumber: string | null) => void;
}

export const ForceBuildModal = observer(({scheduler, builderid, onClose}: ForceBuildModalProps) => {
  const config = useContext(ConfigContext);

  const fields = flattenFields(scheduler.all_fields);

  visitFields(scheduler.all_fields, field => {
    if (field.type === 'username') {
      // The backend will fill the value automatically
      if (config.user.email !== null) {
        field.hide = true;
      }
    }
  })

  const fieldsState = useLocalObservable(() => new ForceBuildModalFieldsState());
  for (let field of fields) {
    fieldsState.setupField(field.fullName, field.default);
  }

  const rootField: ForceSchedulerFieldNested = {
    type: 'nested',
    layout: 'simple',
    fields: scheduler.all_fields,
    columns: 1,
    // the following are not actually used
    name: "dummy",
    fullName: "dummy",
    label: "",
    tablabel: "",
    default: "",
    multiple: false,
    regex: null,
    hide: false,
    maxsize: null,
    autopopulate: null,
  };

  const [error, setError] = useState<string|null>(null);
  const [disableStartButton, setDisableStartButton] = useState(false);

  const onStartBuild = () => {
    setDisableStartButton(true);

    const params: ControlParams = {
      builderid: builderid.toString()
    };

    for (const field of fields) {
      const value = fieldsState.getValue(field.fullName);
      if (value !== null) {
        params[field.fullName] = value;
      }
    }

    const forceBuildStart = async () => {
      try {
        const res = await scheduler.control('force', params);
        if (res.result === undefined || res.result.length === 0) {
          setDisableStartButton(false);
          setError("Invalid response from Buildbot");
          return;
        }
        const buildrequestIds = Object.values<number>(res.result[1])
        if (typeof buildrequestIds[0] !== "number") {
          setDisableStartButton(false);
          setError("Invalid response from Buildbot");
          return;
        }

        onClose(buildrequestIds[0].toString());
      } catch (e: any) {
        setDisableStartButton(false);
        setError(null);
        fieldsState.clearErrors();

        if (e === null || e.message === undefined) {
          setError("Unknown error");
          return;
        }

        if (e.name !== 'AxiosError') {
          setError(e.message);
          return;
        }

        const data = e.response.data;
        if (data.error === undefined) {
          setError("Unknown error");
          return;
        }

        if (data.error.code === -32602) {
          for (const k in data.error.message) {
            const v = data.error.message[k];
            fieldsState.addError(k, v);
          }
        } else {
          if (data.error.message !== undefined) {
            setError(data.error.message);
          }
        }
      }
    }

    forceBuildStart();
  };

  return (
    <Modal className="bb-forcebuild-modal" show={true} onHide={() => onClose(null)}>
      <Modal.Header closeButton>
        <Modal.Title>{scheduler.label}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        { error !== null
          ? <div className="alert alert-danger">{error}</div>
          : <></>
        }
        <FieldNested field={rootField} fieldsState={fieldsState}/>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="default" onClick={() => onClose(null)}>
          Cancel
        </Button>
        <Button variant="primary" disabled={disableStartButton} onClick={onStartBuild}>
          Start build
        </Button>
      </Modal.Footer>
    </Modal>
  );
});
