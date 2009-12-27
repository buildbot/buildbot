from string import Template


main_line_category_header = Template('''
    <tr>
      <td width="1%">
      </td>
      <td width="1%">
      </td>
''')

main_line_category_name = Template('''
      <td class='DevStatus $alt $first $last' width=$size%>
      $category
      </td>
''')

main_line_category_footer = Template('''
    </tr>
    <tr class='DevStatusSpacing'>
    </tr>
''')

main_line_info = Template('''
    <tr>
      <td class='DevRev $alt' width="1%">
        $revision_link
      </td>
      <td class='DevName $alt' width="1%">
        $who
      </td>
''')

main_line_slave_header = Template('''
    <tr>
      <td width="1%">
      </td>
      <td width="1%">
      </td>
      <td class='DevSlave $alt'>
        <table width="100%">
          <tr>
''')

main_line_slave_section = Template('''
          </tr>
        </table>
      </td>
      <td class='DevSlave $alt'>
        <table width="100%">
          <tr>
''')
                                          
main_line_slave_status = Template('''
            <td class='DevSlaveBox'>
              <a href='$url' title='$title' class='DevSlaveBox $color' target=_blank>
              </a>
            </td>
''')

main_line_slave_footer = Template('''
           </tr>
        </table>
      </td>
    </tr>
''')

main_line_status_header = Template('''
      <td class='DevStatus $alt $last'>
        <table width="100%">
          <tr>
''')

main_line_status_section = Template('''
          </tr>
        </table>
      </td>
      <td class='DevStatus $alt $last'>
        <table width="100%">
          <tr>
''')
                                          
main_line_status_box = Template('''
            <td class='DevStatusBox'>
              <a href='#' onClick='showBuildBox("$url", event); return false;' title='$title' class='DevStatusBox $color $tag' target=_blank></a>
            </td>
''')

main_line_status_footer = Template('''
           </tr>
        </table>
      </td>
    </tr>
''')

main_line_details = Template('''
    <tr>
      <td colspan=$span class='DevDetails $alt'>
        <ul style='margin: 0px; padding: 1em;'>
          $details
        </ul>
      </td>
    </tr>
''')

main_line_comments = Template('''
    <tr>
      <td colspan=$span class='DevComment $alt'> $comments </td>
    </tr>
    <tr class='DevStatusSpacing'>
      <td>
      </td>
    </tr>
''')

