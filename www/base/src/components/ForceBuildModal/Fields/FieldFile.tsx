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

import {ForceSchedulerFieldFile} from 'buildbot-data-js';
import {ForceBuildModalFieldsState} from '../ForceBuildModalFieldsState';
import {FaRegQuestionCircle, FaFile} from 'react-icons/fa';
import {observer} from 'mobx-react';
import {FieldBase} from './FieldBase';
import {Tooltip} from 'react-tooltip';
import {ChangeEvent, useRef, useState} from 'react';

type FieldFileProps = {
  field: ForceSchedulerFieldFile;
  fieldsState: ForceBuildModalFieldsState;
};

// If user selects a big file, then the UI will be completely blocked
// while browser tries to display it in the textarea
// so to avoid that we go through a safe value, and play the double binding game
export const MAX_DISPLAY_CHAR = 10000;

const isSafeValue = (value: string): boolean => {
  return value.length < MAX_DISPLAY_CHAR;
};

export const FieldFile = observer(({field, fieldsState}: FieldFileProps) => {
  const state = fieldsState.fields.get(field.fullName)!;

  const [safeValue, setSafeValue] = useState<boolean>(isSafeValue(state.value));
  const fileInput = useRef<HTMLInputElement | null>(null);

  const setFieldValueSafe = (value: string) => {
    setSafeValue(isSafeValue(value));
    state.setValue(value);
  };

  const onFileInputChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.item(0);
    const fileContent = (await file?.text()) ?? '';
    setFieldValueSafe(fileContent);
  };

  const humanReadableSize = (value: string): string => {
    const numberOfBytes = new Blob([value]).size;

    // Shameless copy from https://developer.mozilla.org/en-US/docs/Web/API/File_API/Using_files_from_web_applications#example_showing_files_size
    const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB'];
    const exponent = Math.min(
      Math.floor(Math.log(numberOfBytes) / Math.log(1024)),
      units.length - 1,
    );
    const approx = numberOfBytes / 1024 ** exponent;
    const output =
      exponent === 0 ? `${numberOfBytes} bytes` : `${approx.toFixed(3)} ${units[exponent]}`;

    return output;
  };

  return (
    <FieldBase field={field} fieldsState={fieldsState}>
      <label htmlFor={field.fullName} className="control-label col-sm-2">
        {field.label}
        {field.tooltip && (
          <span data-tooltip-id="my-tooltip" data-tooltip-html={field.tooltip}>
            <FaRegQuestionCircle className="tooltip-icon" />
          </span>
        )}
        <Tooltip id="my-tooltip" clickable />
      </label>
      <div className="col-sm-9">
        {safeValue ? (
          <textarea
            data-bb-test-id={`force-field-${field.fullName}-text`}
            id={field.fullName}
            value={state.value}
            onChange={(event) => setFieldValueSafe(event.target.value)}
          />
        ) : (
          <label data-bb-test-id={`force-field-${field.fullName}-label`}>
            {humanReadableSize(state.value)} file
          </label>
        )}
      </div>
      <div className="col-sm-1">
        <input
          data-bb-test-id={`force-field-${field.fullName}-file-input`}
          ref={fileInput}
          type="file"
          style={{display: 'none'}}
          onChange={(event) => void onFileInputChange(event)}
        />
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          className="btn btn-sm btn-outline-dark"
        >
          <FaFile />
        </button>
      </div>
    </FieldBase>
  );
});
