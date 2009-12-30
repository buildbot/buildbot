from string import Template



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

''')

main_line_comments = Template('''

''')

