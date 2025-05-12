<?xml version="1.0"?>
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="text"/>
  <xsl:strip-space elements="*"/>

  <xsl:template match="/rss/channel">
    <xsl:text>### banast.as/blog</xsl:text>
    <xsl:text>&#10;&#10;</xsl:text>
    <xsl:for-each select="item">
      <xsl:sort select="pubDate" order="descending" data-type="text"/>
      <xsl:if test="position() &lt;= 5">
        <xsl:text>  * [</xsl:text>
        <xsl:value-of select="title"/>
        <xsl:text>](</xsl:text>
        <xsl:value-of select="link"/>
        <xsl:text>&#10;</xsl:text>
      </xsl:if>
    </xsl:for-each>
  </xsl:template>

  <xsl:template match="text()"/>
</xsl:stylesheet>
