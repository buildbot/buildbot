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

import './RawData.scss';
import moment from "moment";
import {useState} from "react";
import _ from "underscore";
import {isObservableArray, isObservableObject} from "mobx";
import {ArrowExpander} from "buildbot-ui";

const isArrayRaw = (v: any) => {
  return _.isArray(v) || isObservableArray(v);
}
const isObjectRaw = (v: any) => {
  return (_.isObject(v) || isObservableObject(v)) && !isArrayRaw(v);
}

const isArrayOfObjectsRaw = (v: any) => {
  return isArrayRaw(v) && v.length > 0 && isObjectRaw(v[0]);
}

export const displayBuildRequestEntry = (key: string, value: any) : string => {
  if (key === "claimed_at" || key === "complete_at" || key === "submitted_at") {
    try {
      return `${value} (${moment(Number.parseInt(value.toString()) * 1000).format()})`;
    } catch (error) {
      return value.toString();
    }
  }
  return value.toString();
}

export const displayBuildsetEntry = (key: string, value: any) : string => {
  if (key === "complete_at" || key === "created_at" || key === "submitted_at") {
    // created_at is for dictionaries in sourcestamps list
    try {
      return `${value} (${moment(Number.parseInt(value.toString()) * 1000).format()})`;
    } catch (error) {
      return value.toString();
    }
  }
  return value.toString();
}

type RawDataProps = {
  data: {[key: string]: any};
  displayCallback?: (key: string, value: any) => string;
}

export const RawData = ({data, displayCallback}: RawDataProps) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const renderArrayElements = (value: any[]) => {
    return (
      <ul>
        {value.map((v, index) => (
          <li key={index}>
            <RawData data={v} displayCallback={displayCallback}/>
          </li>
        ))}
      </ul>
    );
  }

  const renderDataElement = (key: string, value: any) => {
    if (value === null) {
      return <dd>{"null"}&nbsp;</dd>;
    }
    if (value === undefined) {
      return <dd>{"undefined"}&nbsp;</dd>;
    }
    if (isArrayOfObjectsRaw(value)) {
      return (
        <dd>
          <ArrowExpander isExpanded={isExpanded} setIsExpanded={setIsExpanded}/>
          {isExpanded ? renderArrayElements(value as any[]) : <span>{JSON.stringify(value)}</span>}
        </dd>
      );
    }
    if (isObjectRaw(value)) {
      return (
        <dd>
          <ArrowExpander isExpanded={isExpanded} setIsExpanded={setIsExpanded}/>
          {isExpanded ? <div><RawData data={value} displayCallback={displayCallback}/></div> : <></>}
        </dd>
      )
    }

    const displayValue = displayCallback === undefined ? value.toString() : displayCallback(key, value);

    return <dd>{displayValue}&nbsp;</dd>;
  }

  const renderElements = () => {
    if (data === undefined) {
      return [];
    }

    return Object.entries(data).map(keyValue => {
      const [key, value] = keyValue;

      return (
        <div className={'bb-raw-data-key-value'} key={key}>
          <dt>{key}</dt>
          {renderDataElement(key, value)}
        </div>
      );
    });
  }

  return (
    <dl className="dl-horizontal">
      {renderElements()}
    </dl>
  );
}
