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

import './PropertiesTable.scss';
import {Table} from "react-bootstrap";
import CopyToClipboard from 'react-copy-to-clipboard';
import {observer} from "mobx-react";
import {FaCopy} from "react-icons/fa";

type PropertiesTableProps = {
  properties: Map<string, any>;
}

export const PropertiesTable = observer(({properties}: PropertiesTableProps) => {
  const propertyRows = Array.from(properties.entries()).map(([key, valueSource]: [string, any]) => {
    const [value, source] = valueSource;
    const valueString = JSON.stringify(value);
    return (
      <tr key={key}>
        <td className="text-left">{key}</td>
        <td className="text-left">
          <pre className="bb-properties-value">{valueString}</pre>
          {/* @ts-ignore CopyToClipboard is not understood as React component for some reason */}
          <CopyToClipboard text={valueString}>
            <FaCopy className="bb-properties-copy clickable"></FaCopy>
          </CopyToClipboard>
        </td>
        <td className="text-right">{source}</td>
      </tr>
    )
  });

  return (
    <Table hover striped size="sm">
      <thead>
        <tr>
          <th className="text-left">Name</th>
          <th className="text-center">Value</th>
          <th className="text-right">Source</th>
        </tr>
      </thead>
      <tbody>
        {propertyRows}
      </tbody>
    </Table>
  );
});
