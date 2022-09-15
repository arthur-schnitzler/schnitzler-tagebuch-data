<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:fn="http://www.w3.org/2005/xpath-functions"
    version="3.0"
    >
    <xsl:output method="xml" omit-xml-declaration="no" indent="true"/>
    <xsl:mode on-no-match="shallow-copy"/>
    
    <!-- Sortiert die Tage, die vorher aus
    dem Tagebuch gezogen wurdne-->
    
    <xsl:template match="list">
        <list>
        <xsl:apply-templates select="item">
            <xsl:sort select="@target"/>
        </xsl:apply-templates>
        </list>
        
    </xsl:template>
    
    
</xsl:stylesheet>
