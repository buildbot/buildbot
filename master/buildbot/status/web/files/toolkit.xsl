<?xml version="1.0" encoding="UTF-8"?>


<xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                >

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
		<xsl:call-template name="format-duration">
			<xsl:with-param name="value" select="format-number($value,'0.000')"/>
		</xsl:call-template>
</xsl:template>

	<!--
    	Format a number to hours minutes and seconds
	-->

<xsl:template name="format-duration">

    <xsl:param name="value" select="." />
     
	    <xsl:param name="alwaysIncludeHours" select="true()" />
	    <xsl:param name="includeSeconds" select="true()" />
	 <xsl:if test="$value != 'NaN'">   
	    	
	    (<xsl:if test="$value > 3600 or $alwaysIncludeHours">
	      <xsl:value-of select="concat(format-number($value div 3600, '00'), ':')"/>
	    </xsl:if>

	    <xsl:value-of select="format-number($value div 60 mod 60, '00')" />

	    <xsl:if test="$includeSeconds">
	      <xsl:value-of select="concat( ':', format-number($value mod 60, '00'))" />
	    </xsl:if>)
	    
    </xsl:if>
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
			<input type="checkbox" value="Failure" id="failedinput"/>
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
		<th class="txt-align-left first-child">All tests</th>
		<th class="txt-align-left first-child">Passed</th>
		<th class="txt-align-left">Failures</th>
		<th class="txt-align-left">Ignored</th>
		<th class="txt-align-left">Success Rate</th>
		<th class="txt-align-left">Time(s)</th>
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
		<xsl:variable name="passCount" select="count(//test-case[translate(@success,$ucletters,$lcletters)='true' and translate(@executed,$ucletters,$lcletters)='true'])"/>

		<xsl:variable name="failureCount" select="count(//test-case[translate(@success,$ucletters,$lcletters)='false' and translate(@executed,$ucletters,$lcletters)='true'])"/>

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
				<xsl:value-of select="$timeCount"/>
				
				<xsl:call-template name="format-duration">
					<xsl:with-param name="value" select="$timeCount"/>
				</xsl:call-template>
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

	<xsl:variable name="Mname" select="concat('M:',./@name)" />

	<xsl:variable name="lcletters">abcdefghijklmnopqrstuvwxyz</xsl:variable>
	<xsl:variable name="ucletters">ABCDEFGHIJKLMNOPQRSTUVWXYZ</xsl:variable>

   <xsl:variable name="result">
	<xsl:choose>
		<xsl:when test="translate(@executed, $ucletters, $lcletters)='true' and translate(@success, $ucletters, $lcletters)='false'">
			<span>Failure</span>
		</xsl:when>
		<xsl:when test="./error"><span>Error</span></xsl:when>
		<xsl:when test="translate(@executed, $ucletters, $lcletters)='false'">
			<span>Ignored</span>
		</xsl:when>
		<xsl:otherwise><span>Pass</span></xsl:otherwise>
	</xsl:choose>
   </xsl:variable>

   <xsl:variable name="newid" select="generate-id(@name)" />

	<tr>
		<td class="txt-align-left first-child">
				
			<span>
				<xsl:attribute name="class">case-names</xsl:attribute>
					<xsl:choose>
						<xsl:when test="translate($result, $ucletters, $lcletters) = 'failure'">
							<xsl:value-of select="@name"/>
						</xsl:when>
						<xsl:otherwise>
							<xsl:call-template name="GetLastSegment">
								<xsl:with-param name="value" select="./@name" />
							</xsl:call-template>
							<xsl:value-of select="translate($result, $ucletters, $lcletters)"/>
						</xsl:otherwise>
					</xsl:choose>
			</span>
				
		</td>
		
		<td>
			<xsl:attribute name="class"><xsl:value-of select="$result"/></xsl:attribute>
			<xsl:value-of select="$result"/>
		</td>
		
		<td>
		    <xsl:call-template name="display-time">
		        <xsl:with-param name="value" select="@time"/>
		    </xsl:call-template>	
		</td>
	</tr>

	<xsl:if test="$result = &quot;Failure&quot; and (./failure != '' or ./error != '' or ./reason != '')">
	   <tr>
	      <xsl:attribute name="id">
	         <xsl:value-of select="$newid"/>
	      </xsl:attribute>
	      <td class="txt-align-left failure-detail-cont colspan-js">
	      	<div class="pos-relative">
	      	<div class="failure-detail-txt">
	      		<xsl:apply-templates select="./failure"/>
	      		<xsl:apply-templates select="./error"/>
	      		<xsl:apply-templates select="./reason"/>
	      	</div>
	      </div>
         </td>
         <td class="hidden-result"><xsl:value-of select="$result"/></td>
         <td>
         	&#160;
         </td>
      </tr>
	</xsl:if>
</xsl:template>


<!-- I am sure that all nodes are called -->
<xsl:template match="*">
	<xsl:apply-templates/>
</xsl:template>

</xsl:stylesheet>