<?xml version="1.0" encoding="UTF-8"?>

<!--
   This XSL File is based on the NUnitSummary.xsl
   template created by Tomas Restrepo fot NAnt's NUnitReport.
   
   Modified by Gilles Bayon (gilles.bayon@laposte.net) for use
   with NUnit2Report.

-->

<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform" >
   <xsl:output method="html" indent="yes"/>
   <xsl:include href="/toolkit.xsl"/>
   <xsl:preserve-space elements='a root'/>

<!--
	====================================================
		Create the page structure
    ====================================================
-->
<xsl:template match="test-results">

	<HTML>
		<HEAD>
			<title>Katana test results</title>

			<link href='http://fonts.googleapis.com/css?family=Pacifico&amp;subset=latin' rel='stylesheet' type='text/css' />	
		    <link href='http://fonts.googleapis.com/css?family=Leckerli+One&amp;subset=latin' rel='stylesheet' type='text/css' />
			<link rel="stylesheet" href="/css/default.css" type="text/css" />
			<link rel="stylesheet" href="/css/log.css" type="text/css" />
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
			<footer class="footer">
      <div class="container-inner">
        <h3 class="buildbot-version">
        	Produced by <a href="/">Katana</a>
        </h3>
      </div>
    </footer>
    <script type="text/javascript" src="/script/libs/jQuery-2-0-3.js"></script>
	<script type="text/javascript" src="/script/plugins/jquery-datatables.js"></script>
    <script type="text/javascript" src="/script/log.js"></script>
		</body>
	</HTML>
</xsl:template>
	
	<xsl:template name="testsuites">   
		<xsl:for-each select="//test-suite[(child::results/test-case)]">
			<xsl:sort select="@name"/>
			<!-- create an anchor to this class name 
			<a name="#{generate-id(@name)}"></a>
			-->
				<xsl:variable name="lcletters">abcdefghijklmnopqrstuvwxyz</xsl:variable>
				<xsl:variable name="ucletters">ABCDEFGHIJKLMNOPQRSTUVWXYZ</xsl:variable>
				
			
				<xsl:variable name="testCount" select="count(child::results/test-case)"/>
				<xsl:variable name="passCount" select="count(child::results/test-case[translate(@success,$ucletters,$lcletters)='true'])"/>
				<xsl:variable name="ignoredCount" select="count(child::results/test-case[translate(@executed,$ucletters,$lcletters)='false'])"/>
				<xsl:variable name="failureCount" select="count(child::results/test-case[translate(@success,$ucletters,$lcletters) ='false'])"/>
				<xsl:variable name="timeCount" select="translate(@time,',','.')"/>
		<div class="table-holder">
			<ul class="summary-list">
				<li>
					<span id=":i18n:Tests">Tests </span>
					<xsl:value-of select="$testCount"/>
				</li>
				<li>
					<span id=":i18n:Passed">Passed </span>
					<xsl:value-of select="$passCount"/>
				</li>
				<li>
					<span id=":i18n:Failures">Failures </span>
					<xsl:value-of select="$failureCount"/>
				</li>
				<li>
					<span id=":i18n:Error">Ignored </span>
					<xsl:value-of select="$ignoredCount"/>
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
			<table class="table-1 tablesorter tablesorter-log-js">
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
</div>
		</xsl:for-each>
	</xsl:template>
	
  <xsl:template name="dot-replace">
	  <xsl:param name="package"/>
	  <xsl:choose>
		  <xsl:when test="contains($package,'.')"><xsl:value-of select="substring-before($package,'.')"/>_<xsl:call-template name="dot-replace"><xsl:with-param name="package" select="substring-after($package,'.')"/></xsl:call-template></xsl:when>
		  <xsl:otherwise><xsl:value-of select="$package"/></xsl:otherwise>
	  </xsl:choose>
  </xsl:template>

 <xsl:template name="GetLastSegment">
    <xsl:param name="value" />
    <xsl:param name="separator" select="'.'" />

    <xsl:choose>
      <xsl:when test="contains($value, $separator)">
        <xsl:call-template name="GetLastSegment">
          <xsl:with-param name="value" select="substring-after($value, $separator)" />
          <xsl:with-param name="separator" select="$separator" />
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="$value" />
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>



</xsl:stylesheet>
