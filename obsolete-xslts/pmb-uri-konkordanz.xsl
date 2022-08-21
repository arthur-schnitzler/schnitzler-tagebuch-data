<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:tei="http://www.tei-c.org/ns/1.0"
    exclude-result-prefixes="xs" version="3.0">
    <xsl:output method="text" omit-xml-declaration="yes" indent="no"/>
    <xsl:mode on-no-match="shallow-skip"/>

<xsl:template match="tei:listPlace">
    
    <xsl:for-each select="tei:place/@xml:id">
        <xsl:value-of select="substring-after(., 'pmb')"/><xsl:text>,</xsl:text>
        <xsl:value-of select="concat('https://schnitzler-tagebuch.acdh.oeaw.ac.at/',.,'.html')"/>
        <xsl:text>&#xA;</xsl:text>
    </xsl:for-each>
    
    
</xsl:template>


</xsl:stylesheet>
