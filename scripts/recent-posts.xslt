<?xml version="1.0"?>
<xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="text"/>
  <xsl:strip-space elements="*"/>

  <xsl:template match="/rss/channel">
    <xsl:text>### banast.as/blog&#10;&#10;</xsl:text>
    <xsl:for-each select="item[position() &gt; last() - 5]">
      <xsl:sort select="position()" data-type="number" order="descending"/>
      <xsl:text>  * [</xsl:text>
      <xsl:value-of select="title"/>
      <xsl:text>](</xsl:text>
      <xsl:value-of select="link"/>
      <xsl:text>)&#10;</xsl:text>
    </xsl:for-each>
  </xsl:template>

  <xsl:template match="text()"/>
</xsl:stylesheet>
