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
import {useState} from "react";
import _ from "underscore";
import {isObservableArray, isObservableObject} from "mobx";
import ArrowExpander from "../ArrowExpander/ArrowExpander";

const isArrayRaw = (v: any) => {
  return _.isArray(v) || isObservableArray(v);
}
const isObjectRaw = (v: any) => {
  return (_.isObject(v) || isObservableObject(v)) && !isArrayRaw(v);
}

const isArrayOfObjectsRaw = (v: any) => {
  return isArrayRaw(v) && v.length > 0 && isObjectRaw(v[0]);
}

type RawDataProps = {
  data: {[key: string]: any};
}

const RawData = ({data}: RawDataProps) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const renderArrayElements = (value: any[]) => {
    return (
      <ul>
        {value.map((v, index) => (
          <li key={index}>
            <RawData data={v}/>
          </li>
        ))}
      </ul>
    );
  }

  const renderDataElement = (value: any) => {
    if (!isObjectRaw(value) && !isArrayOfObjectsRaw(value)) {
      return <dd>{value === null ? "null" : value.toString()}&nbsp;</dd>;
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
          {isExpanded ? <div><RawData data={value}/></div> : <></>}
        </dd>
      )
    }
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
          {renderDataElement(value)}
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

export default RawData;
