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

type PropertiesTableProps = {
  properties: Map<string, any>;
}

const PropertiesTable = observer(({properties}: PropertiesTableProps) => {
  const propertyRows = Array.from(properties.entries()).map(([key, valueSource]: [string, any]) => {
    const [value, source] = valueSource;
    const valueString = JSON.stringify(value);
    return (
      <tr key={key}>
        <td className="text-left">{key}</td>
        <td className="text-left">
          <pre className="bb-properties-value">{valueString}</pre>
          <CopyToClipboard text={valueString}>
            <i className="bb-properties-copy fa fa-copy clickable"></i>
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

export default PropertiesTable;
