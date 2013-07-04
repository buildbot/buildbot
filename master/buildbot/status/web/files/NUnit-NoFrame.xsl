<?xml version="1.0" encoding="ISO-8859-1"?>

<!--
   This XSL File is based on the NUnitSummary.xsl
   template created by Tomas Restrepo fot NAnt's NUnitReport.
   
   Modified by Gilles Bayon (gilles.bayon@laposte.net) for use
   with NUnit2Report.

-->




<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">


   <xsl:output method="html" indent="yes"/>
   <xsl:include href="toolkit.xsl"/>
   <xsl:preserve-space elements='a root'/>


<!--
	====================================================
		Create the page structure
    ====================================================
-->
<xsl:template match="test-results">

	<HTML>
		<HEAD>
		<style type="text/css">
			

			span.covered {
				background: #00df00; 
				
			}
			span.uncovered {
				background: #df0000; 
				border-top:#9c9c9c 1px solid;
				border-bottom:#9c9c9c 1px solid;
				border-right:#9c9c9c 1px solid;
				}
			span.ignored {
				background: #ffff00;
				
			}
				
			.Error {
				font-weight:bold; 
			}
			.Failure {
				  background-color: #EFCFCF;
    				border-top: 1px solid #FFFFFF;
			}
			.Ignored {
				font-weight:bold; 
			}
			.table-1.first-child tr td.FailureDetail:first-child {
				
				padding-left: 40px;
				
			}
			.Pass {
				 border-top: 1px solid #FFFFFF;
				  background-color: #DDE6D6;
			}
			.TableHeader {
				background: #efefef;
				color: #000;
				font-weight: bold;
				horizontal-align: center;
			}
			
			a.summarie {
				color:#000;
				text-decoration: none;
			}
			a.summarie:active {
				color:#000;
				text-decoration: none;
			}
			a.summarie:visited {
				color:#000;
				text-decoration: none;
			}
			.description {
				margin-top:1px;
				padding:3px;
				background-color:#dcdcdc;
				color:#000;
				font-weight:normal;
			}
			.method{
				color:#000;
				font-weight:normal;
				padding-left:5px;
			}
			a.method{
				text-decoration: none;
				color:#000;
				font-weight:normal;
				padding-left:5px;
			}
			a.Failure {
				font-weight:bold; 
				color:red;
				text-decoration: none;
			}
			a.Failure:visited {
				font-weight:bold; 
				color:red;
				text-decoration: none;
			}
			a.Failure:active {
				font-weight:bold; 
				color:red;
				text-decoration: none;
			}
			a.error {
				font-weight:bold; 
				color:red;
			}
			a.error:visited {
				font-weight:bold; 
				color:red;
			}
			a.error:active {
				font-weight:bold; 
				color:red;
				/*text-decoration: none;
				padding-left:5px;*/
			}
			a.ignored {
				font-weight:bold; 
				text-decoration: none;
				
			}
			a.ignored:visited {
				font-weight:bold; 
				text-decoration: none;
				
			}
			a.ignored:active {
				font-weight:bold; 
				text-decoration: none;
							}
	  </style>


		<link href='http://fonts.googleapis.com/css?family=Pacifico' rel='stylesheet' type='text/css' />	
	    <link href='http://fonts.googleapis.com/css?family=Leckerli+One' rel='stylesheet' type='text/css' />
		<link rel="stylesheet" href="/css/default.css" type="text/css" />
	    <script type="text/javascript" src="/script/jQuery.2.0.2.js"></script>
	    <script type="text/javascript" src="/script/jquery.dataTables.js"></script>
	    <script type="text/javascript" src="/script/default.js"></script>
		<script language="JavaScript"><![CDATA[   
	  function Toggle(id) {
	  var element = document.getElementById(id);

		 if ( element.style.display == "none" )
			element.style.display = "block";
		 else 
			element.style.display = "none";
	  }

	  function ToggleImage(id) {
	  var element = document.getElementById(id);

		 if ( element.innerText   == "-" )
			element.innerText   = "+";
		 else 
			element.innerText = "-";
	  }
	  /*
	  $(document).ready(function() {
	  	$('.case-names').each(function(){
		var myArray = $(this).text().split(/[\s.]+/);
		$(this).text(myArray[myArray.length-1])
		}).show();
	});*/
	]]></script>
		</HEAD>
		<body class="interface log-main">
			
			
				<xsl:call-template name="header"/>
			<div class="container-inner">	
				<!-- Summary part -->
				<xsl:call-template name="summary"/>
				
				
				<!-- Package List part 
					<xsl:call-template name="packagelist"/>
				-->
				
				<!-- For each testsuite create the part -->
				<xsl:call-template name="testsuites"/>
				
				
				<!-- Environment info part 
	 			
				<xsl:call-template name="envinfo"/>
				-->
			</div>
		</body>
	</HTML>
</xsl:template>
	
	
	
	<!-- ================================================================== -->
	<!-- Write a list of all packages with an hyperlink to the anchor of    -->
	<!-- of the package name.                                               -->
	<!-- ================================================================== -->
	<xsl:template name="packagelist">	
		<h2 id=":i18n:TestSuiteSummary">TestSuite Summary</h2>
		<table border="0" cellpadding="2" cellspacing="0" width="95%">
			<xsl:call-template name="packageSummaryHeader"/>
			<!-- list all packages recursively -->
			<xsl:for-each select="//test-suite[(child::results/test-case)]">
				<xsl:sort select="@name"/>
				<xsl:variable name="testCount" select="count(child::results/test-case)"/>
				<xsl:variable name="errorCount" select="count(child::results/test-case[@executed='False'])"/>
				<xsl:variable name="failureCount" select="count(child::results/test-case[@success='False'])"/>
				<xsl:variable name="runCount" select="$testCount - $errorCount - $failureCount"/>
				<xsl:variable name="timeCount" select="translate(@time,',','.')"/>
		
				<!-- write a summary for the package -->
				<tr valign="top">
					<!-- set a nice color depending if there is an error/failure -->
					<xsl:attribute name="class">
						<xsl:choose>
						    <xsl:when test="$failureCount &gt; 0">Failure</xsl:when>
							<xsl:when test="$errorCount &gt; 0"> Error</xsl:when>
							<xsl:otherwise>Pass</xsl:otherwise>
						</xsl:choose>
					</xsl:attribute> 	
					<td width="25%">
						<a href="#{generate-id(@name)}">
						<xsl:attribute name="class">
							<xsl:choose>
								<xsl:when test="$failureCount &gt; 0">Failure</xsl:when>
							</xsl:choose>
						</xsl:attribute> 	
						<xsl:value-of select="@name"/>
						</a>
					</td>
					<td nowrap="nowrap" width="6%" align="right">
						<xsl:variable name="successRate" select="$runCount div $testCount"/>
						<b>
						<xsl:call-template name="display-percent">
							<xsl:with-param name="value" select="$successRate"/>
						</xsl:call-template>
						</b>
					</td>
					<td width="20%" height="9px">
						<xsl:if test="round($runCount * 200 div $testCount )!=0">
							<span class="covered">
								<xsl:attribute name="style">width:<xsl:value-of select="round($runCount * 200 div $testCount )"/>px</xsl:attribute>
							</span>
						</xsl:if>
						<xsl:if test="round($errorCount * 200 div $testCount )!=0">
						<span class="ignored">
							<xsl:attribute name="style">width:<xsl:value-of select="round($errorCount * 200 div $testCount )"/>px</xsl:attribute>
						</span>
						</xsl:if>
						<xsl:if test="round($failureCount * 200 div $testCount )!=0">
							<span class="uncovered">
								<xsl:attribute name="style">width:<xsl:value-of select="round($failureCount * 200 div $testCount )"/>px</xsl:attribute>
							</span>
						</xsl:if>
					</td>
					<td><xsl:value-of select="$runCount"/></td>
					<td><xsl:value-of select="$errorCount"/></td>
					<td><xsl:value-of select="$failureCount"/></td>
					<td>
                       <xsl:call-template name="display-time">
                        	<xsl:with-param name="value" select="$timeCount"/>
                        </xsl:call-template>				
					</td>					
				</tr>
			</xsl:for-each>
		</table>		
	</xsl:template>
	
	<xsl:template name="testsuites">   
		<xsl:for-each select="//test-suite[(child::results/test-case)]">
			<xsl:sort select="@name"/>
			<!-- create an anchor to this class name 
			<a name="#{generate-id(@name)}"></a>
			-->
			
				<xsl:variable name="testCount" select="count(child::results/test-case)"/>
				<xsl:variable name="errorCount" select="count(child::results/test-case[@executed='False'])"/>
				<xsl:variable name="failureCount" select="count(child::results/test-case[@success='False'])"/>
				<xsl:variable name="runCount" select="$testCount - $errorCount - $failureCount"/>
				<xsl:variable name="timeCount" select="translate(@time,',','.')"/>

			<ul class="summary-list">
				<li>
					<span id=":i18n:Tests">Tests </span>
					<xsl:value-of select="$runCount"/>
				</li>
				<li>
					<span id=":i18n:Errors">Errors </span>
					<xsl:value-of select="$errorCount"/>
				</li>
				<li>
					<span id=":i18n:Failures">Failures </span>
					<xsl:value-of select="$failureCount"/>
				</li>
				<li>
					<span id=":i18n:Time">Time(s) </span>
					<xsl:call-template name="display-time">
                        	<xsl:with-param name="value" select="$timeCount"/>
                    </xsl:call-template>				
				</li>
			</ul>

			<h1 class="main-head">
				<xsl:value-of select="@name"/>
			</h1>
			<table class="table-1 first-child tablesorter tablesorter-log-js">
				<!-- Header -->
				<thead>
					<xsl:call-template name="classesSummaryHeader"/>
				</thead>
				<!-- match the testcases of this package -->
				<tbody>
					<xsl:apply-templates select="results/test-case">
					   <xsl:sort select="@name" /> 
					</xsl:apply-templates>
				</tbody>
			</table>
			<a class="back-top-top" href="#top" id=":i18n:Backtotop">Back to top</a>
		</xsl:for-each>
	</xsl:template>
	

  <xsl:template name="dot-replace">
	  <xsl:param name="package"/>
	  <xsl:choose>
		  <xsl:when test="contains($package,'.')"><xsl:value-of select="substring-before($package,'.')"/>_<xsl:call-template name="dot-replace"><xsl:with-param name="package" select="substring-after($package,'.')"/></xsl:call-template></xsl:when>
		  <xsl:otherwise><xsl:value-of select="$package"/></xsl:otherwise>
	  </xsl:choose>
  </xsl:template>

</xsl:stylesheet>
