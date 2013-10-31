<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:param name="nant.filename" />
<xsl:param name="nant.version" />
<xsl:param name="nant.project.name" />
<xsl:param name="nant.project.buildfile" />
<xsl:param name="nant.project.basedir" />
<xsl:param name="nant.project.default" />
<xsl:param name="sys.os" />
<xsl:param name="sys.os.platform" />
<xsl:param name="sys.os.version" />
<xsl:param name="sys.clr.version" />

<!--
    TO DO
	Corriger les alignement sur error
	Couleur http://nanning.sourceforge.net/junit-report.html
-->


<!--
    format a number in to display its value in percent
    @param value the number to format
-->
<xsl:template name="display-time">
	<xsl:param name="value"/>
	<xsl:value-of select="format-number($value,'0.000')"/>
</xsl:template>

<!--
    format a number in to display its value in percent
    @param value the number to format
-->
<xsl:template name="display-percent">
	<xsl:param name="value"/>
	<xsl:value-of select="format-number($value,'0.00 %')"/>
</xsl:template>

<!--
    transform string like a.b.c to ../../../
    @param path the path to transform into a descending directory path
-->
<xsl:template name="path">
	<xsl:param name="path"/>
	<xsl:if test="contains($path,'.')">
		<xsl:text>../</xsl:text>	
		<xsl:call-template name="path">
			<xsl:with-param name="path"><xsl:value-of select="substring-after($path,'.')"/></xsl:with-param>
		</xsl:call-template>	
	</xsl:if>
	<xsl:if test="not(contains($path,'.')) and not($path = '')">
		<xsl:text>../</xsl:text>	
	</xsl:if>	
</xsl:template>

<!--
	template that will convert a carriage return into a br tag
	@param word the text from which to convert CR to BR tag
-->
<xsl:template name="br-replace">
	<xsl:param name="word"/>
	<xsl:choose>
		<xsl:when test="contains($word,'&#xA;')">
			<xsl:value-of select="substring-before($word,'&#xA;')"/>
			<br/>
			<xsl:call-template name="br-replace">
				<xsl:with-param name="word" select="substring-after($word,'&#xA;')"/>
			</xsl:call-template>
		</xsl:when>
		<xsl:otherwise>
			<xsl:value-of select="$word"/>
		</xsl:otherwise>
	</xsl:choose>
</xsl:template>

<!-- 
		=====================================================================
		classes summary header
		=====================================================================
-->
<xsl:template name="header">
	<xsl:param name="path"/>

<nav class="sub-menu-container">
<div class="container-inner">
	
		
	<div class="dataTables_filter">
		
		<label class="input-label">
			<input type="text" placeholder="Free text filter" id="filterinput" />
		</label>
			<button class="grey-btn" id="submitFilter">Filter</button>
			<button class="grey-btn" id="clearFilter">Clear</button>

		<div class="check-boxes-list">
			<label for="passinput">Passed</label>
			<input type="checkbox" value="Pass" id="passinput"/>
			<label for="ignoreinput">ignored</label>
			<input type="checkbox" value="Ignored" id="ignoreinput"/>
			<label for="failedinput">Failed</label>
			<input type="checkbox" value="Failed" id="failedinput"/>
		</div>

	</div>
	<h1 class="logo">
      <a href="/">
        <span>K</span>atana
      </a>
    </h1>

</div>
</nav>

</xsl:template>

<xsl:template name="summaryHeader">
	<tr>
		<th class="txt-align-left first-child" id=":i18n:Tests">All tests</th>
		<th class="txt-align-left first-child" id=":i18n:Passed">Passed</th>
		<th class="txt-align-left" id=":i18n:Failures">Failures</th>
		<th class="txt-align-left" id=":i18n:Errors">Ignored</th>
		<th class="txt-align-left" id=":i18n:SuccessRate" colspan="2">Success Rate</th>
		<th class="txt-align-left" id=":i18n:Time" nowrap="nowrap">Time(s)</th>
	</tr>
</xsl:template>


<!-- 
		=====================================================================
		classes summary header
		=====================================================================
-->
<xsl:template name="classesSummaryHeader">
	<tr>
		<th class="txt-align-left first-child" id=":i18n:Name">Name</th>
		<th id=":i18n:Status">Status</th>
		<th id=":i18n:Time">Time(s)</th>
	</tr>
</xsl:template>

<!-- 
		=====================================================================
		Write the summary report
		It creates a table with computed values from the document:
		User | Date | Environment | Tests | Failures | Errors | Rate | Time
		Note : this template must call at the testsuites level
		=====================================================================
-->

	<xsl:template name="summary">
		<a id="btd" href="#" class="back-to-detail"></a>
		<h1 class="main-head" id=":i18n:Summary">Summary</h1>
		
		<xsl:variable name="lcletters">abcdefghijklmnopqrstuvwxyz</xsl:variable>
		<xsl:variable name="ucletters">ABCDEFGHIJKLMNOPQRSTUVWXYZ</xsl:variable>

		<xsl:variable name="runCount" select="count(//test-case)"/>

		<!-- new test counting -->
		<xsl:variable name="passCount" select="count(//test-case[translate(@success,$ucletters,$lcletters)='true'])"/>

		<xsl:variable name="failureCount" select="count(//test-case[translate(@success,$ucletters,$lcletters)='false'])"/>

		<xsl:variable name="ignoreCount" select="count(//test-case[translate(@executed,$ucletters,$lcletters)='false'])"/>

		<xsl:variable name="total" select="$runCount + $ignoreCount + $failureCount"/>

		<xsl:variable name="timeCount" select="format-number(sum(//test-case/@time),'#.000')"/>
	
		<xsl:variable name="successRate" select="$runCount div $total"/>		

		<table class="table-1" id="summaryTable">
		<thead>
			<xsl:call-template name="summaryHeader"/>
		</thead>
		<tbody>
		<tr>
			<xsl:attribute name="class">
    			<xsl:choose>
    			    <xsl:when test="$failureCount &gt; 0">Failure</xsl:when>
    				<xsl:when test="$ignoreCount &gt; 0">Error</xsl:when>
    				<xsl:otherwise>Pass</xsl:otherwise>
    			</xsl:choose>			
			</xsl:attribute>		
			<td class="txt-align-left first-child">
				<xsl:value-of select="$runCount"/>
			</td>
			<td class="txt-align-left">
				<xsl:value-of select="$passCount"/>
			</td>
			<td class="txt-align-left">
				<xsl:value-of select="$failureCount"/>
			</td>
			<td class="txt-align-left">
				<xsl:value-of select="$ignoreCount"/>
			</td>
			<td class="txt-align-left">
			    <xsl:call-template name="display-percent">
			        <xsl:with-param name="value" select="$successRate"/>
			    </xsl:call-template>
			</td>
			<td class="txt-align-left">
				<xsl:if test="round($runCount * 200 div $total )!=0">
					<span class="covered">
						<xsl:attribute name="style">width:<xsl:value-of select="round($runCount * 200 div $total )"/>px</xsl:attribute>
					</span>
				</xsl:if>
				<xsl:if test="round($ignoreCount * 200 div $total )!=0">
				<span class="ignored">
					<xsl:attribute name="style">width:<xsl:value-of select="round($ignoreCount * 200 div $total )"/>px</xsl:attribute>
				</span>
				</xsl:if>
				<xsl:if test="round($failureCount * 200 div $total )!=0">
					<span class="uncovered">
						<xsl:attribute name="style">width:<xsl:value-of select="round($failureCount * 200 div $total )"/>px</xsl:attribute>
					</span>
				</xsl:if>
			</td>
			<td class="txt-align-left">
				<xsl:value-of select="$timeCount"/>
			
			</td>
		</tr>
		</tbody>
		</table>
		<!--
			<span id=":i18n:Note">Note</span>: <i id=":i18n:failures">failures</i>&#160;<span id=":i18n:anticipated">are anticipated and checked for with assertions while</span>&#160;<i id=":i18n:errors">errors</i>&#160;<span id=":i18n:unanticipated">are unanticipated.</span>
		-->
	</xsl:template>

<!-- 
		=====================================================================
		testcase report
		=====================================================================
-->
<xsl:template match="test-case">
	
	<xsl:param name="open.description"/>

	<xsl:variable name="Mname" select="concat('M:',./@name)" />

   <xsl:variable name="result">
			<xsl:choose>
				<xsl:when test="./failure"><span id=":i18n:Failure">Failure</span></xsl:when>
				<xsl:when test="./error"><span id=":i18n:Error">Error</span></xsl:when>
				<xsl:when test="@executed='False'"><span id=":i18n:Ignored">Ignored</span></xsl:when>
				<xsl:otherwise><span id=":i18n:Pass">Pass</span></xsl:otherwise>
			</xsl:choose>
   </xsl:variable>

   <xsl:variable name="newid" select="generate-id(@name)" />
	<tr>
		<td class="txt-align-left first-child">
			
				<!-- If failure, add click on the test method name and color red -->
				<xsl:choose>
					<xsl:when test="$result = 'Failure' or $result = 'Error'">
						<span>
						
						<xsl:attribute name="class">error case-names</xsl:attribute>
						<xsl:call-template name="GetLastSegment">
							<xsl:with-param name="value" select="./@name" />
						</xsl:call-template>
						</span>
					</xsl:when>
					<xsl:when test="$result = 'Ignored'">
						<xsl:call-template name="GetLastSegment">
							<xsl:with-param name="value" select="./@name" />
						</xsl:call-template>
						
					</xsl:when>
					<xsl:otherwise>
						<xsl:attribute name="class">method txt-align-left case-names first-child</xsl:attribute>
						<xsl:call-template name="GetLastSegment">
							<xsl:with-param name="value" select="./@name" />
						</xsl:call-template>
					</xsl:otherwise>
				</xsl:choose>
			
		</td>
		<!--
		<td>
			<xsl:choose>
				<xsl:when test="$result = 'Pass'">
					<span class="covered" ></span>
				</xsl:when>
				<xsl:when test="$result = 'Ignored'">
					<span class="ignored" ></span>
				</xsl:when>			
				<xsl:when test="$result = 'Failure' or $result = 'Error'">
					<span class="uncovered" ></span>
				</xsl:when>			
			</xsl:choose>
			 The test method description
				
		</td>
		-->
		<td>
			<xsl:attribute name="class"><xsl:value-of select="$result"/></xsl:attribute>
			<xsl:attribute name="id">:i18n:<xsl:value-of select="$result"/></xsl:attribute><xsl:value-of select="$result"/>
		</td>
		
		<td>
		    <xsl:call-template name="display-time">
		        <xsl:with-param name="value" select="@time"/>
		    </xsl:call-template>				
		</td>
	</tr>

	<xsl:if test="$result != &quot;Pass&quot;">
	   <tr>
	      <xsl:attribute name="id">
	         <xsl:value-of select="$newid"/>
	      </xsl:attribute>
	      <td class="txt-align-left failure-detail-cont colspan-js" colspan="3">
	      	
	      	<div class="failure-detail-txt">
	      		<xsl:apply-templates select="./failure"/>
	      		<xsl:apply-templates select="./error"/>
	      		<xsl:apply-templates select="./reason"/>
	      	</div>
         </td>
         <td>&#160;</td>
         <td>
         	&#160;
         </td>
      </tr>
	</xsl:if>
</xsl:template>

<!-- Note : the below template error and failure are the same style
            so just call the same style store in the toolkit template -->
<!-- <xsl:template match="failure">
	<xsl:call-template name="display-failures"/>
</xsl:template>

<xsl:template match="error">
	<xsl:call-template name="display-failures"/>
</xsl:template> -->

<!-- Style for the error and failure in the tescase template -->
<!-- <xsl:template name="display-failures">
	<xsl:choose>
		<xsl:when test="not(@message)">N/A</xsl:when>
		<xsl:otherwise>
			<xsl:value-of select="@message"/>
		</xsl:otherwise>
	</xsl:choose> -->
	<!-- display the stacktrace -->
<!-- 	<code>
		<p/>
		<xsl:call-template name="br-replace">
			<xsl:with-param name="word" select="."/>
		</xsl:call-template>
	</code> -->
	<!-- the later is better but might be problematic for non-21" monitors... -->
	<!--pre><xsl:value-of select="."/></pre-->
<!-- </xsl:template>
 -->


<!-- I am sure that all nodes are called -->
<xsl:template match="*">
	<xsl:apply-templates/>
</xsl:template>

</xsl:stylesheet>