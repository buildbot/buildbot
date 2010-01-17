try:
    from string import Template
except ImportError:
    from buildbot.stringTemplate import Template


top_header = Template('''
<div align="center">
  <table width=95% class="Grid" border="0" cellspacing="0">
''')

top_info_name = Template('''
    <tr>
      <td width=33% align=left class=left_align><a href="$projectUrl">$projectName</a>
''')

top_info_categories = Template('''
        <br><b>Categories:</b> $categories
''')

top_info_branch = Template('''
        <br /><b>Branch:</b> $branch
''')

top_info_name_end = Template('''
      </td>
''')

top_legend = Template('''
<td width=33% align=center class=center_align>
  <div align="center">
    <table>
      <tr>
        <td>Legend:&nbsp;&nbsp;</td>
        <td><div class='legend success' title='All tests passed'>Passed</div></td>
        <td><div class='legend failure' title='There is a new failure. Take a look!'>Failed</div></td>
        <td><div class='legend warnings' title='It was failing before, and it is still failing. Make sure you did not introduce new regressions'>Failed Again</div></td>
        <td><div class='legend running' title='The tests are still running'>Running</div></td>
        <td><div class='legend exception' title='Something went wrong with the test, there is no result'>Exception</div></td>
        <td><div class='legend notstarted' title='No result yet.'>No data</div></td>
      </tr>
    </table>
  </div>
</td>
''')

top_personalize = Template('''
<td width=33% align=right class=right_align>
  <script>
    function reload_page() {
      name_value = document.getElementById('namebox').value
      if (document.location.href.lastIndexOf('?') == -1)
        document.location.href = document.location.href+ '?name=' + name_value;
      else
        document.location.href = document.location.href+ '&name=' + name_value;
    }
  </script>
  <input id='namebox' name='name' type='text' style='color:#999;'
      onblur='this.value = this.value || this.defaultValue; this.style.color = "#999";'
      onfocus='this.value=""; this.style.color = "#000";'
      value='Personalized for...'>
      
  <input type=submit value='Go' onclick='reload_page()'>
</td>
''')

top_footer = Template('''
    </tr>
  </table>
</div>
''')

main_header = Template('''
<br>
<div align="center">
  <table width=96%>
''')

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

main_footer = Template('''
  </table>
</div>
''')


bottom = Template('''
<hr />

<div class="footer">
  [ <a href="$welcomeUrl">welcome</a> ] 
  <br />
  <a href="http://buildbot.sourceforge.net/">Buildbot - $version</a> working for the <a href="$projectUrl"> $projectName </a> project.
  <br />
  Page built: $time
  <br />
  Debug Info: $debugInfo
</div>

<div id="divBox" OnMouseOut="if (checkMouseLeave(this, event)) this.style.display = 'None'" class="BuildWaterfall"> 
</div>
<iframe id="frameBox" style="display: none;" onload="updateDiv(event);"></iframe>
''')

