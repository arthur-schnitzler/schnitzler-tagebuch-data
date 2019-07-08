<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    exclude-result-prefixes="xs"
    version="2.0">
    <xsl:mode on-no-match="shallow-copy" />
    
    <xsl:template match="day">
        <xsl:element name="date">
            <xsl:attribute name="when">
                <xsl:value-of select="preceding-sibling::year[1]"/>
                <xsl:text>-</xsl:text>
                <xsl:value-of select="preceding-sibling::month[1]"/>
                <xsl:text>-</xsl:text>
                <xsl:if test="string-length(.)=1">
                    <xsl:text>0</xsl:text>
                </xsl:if>
               <xsl:value-of select="."/>
            </xsl:attribute>
            
            <xsl:value-of select="."/>
            <xsl:text>.</xsl:text>
            <xsl:choose>
                <xsl:when test="starts-with(preceding-sibling::month[1],'0')">
                     <xsl:value-of select="substring(preceding-sibling::month[1],2)"/>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:value-of select="preceding-sibling::month[1]"/>
                </xsl:otherwise>
            </xsl:choose>
            
           
            <xsl:text>.</xsl:text>
            <xsl:value-of select="preceding-sibling::year[1]"/>
        </xsl:element>
        

        
    </xsl:template>
    <xsl:template match="year|month"></xsl:template>
    
    <xsl:template match="date">
        <xsl:copy>
        <xsl:if test="contains(@when,'?')">
            
            <xsl:attribute name="cert">
                <xsl:text>low</xsl:text>
            </xsl:attribute>
        </xsl:if>
            <xsl:attribute name="when">
                <xsl:value-of select="replace(@when,'\?','')"/>
               
            </xsl:attribute>
            <xsl:apply-templates></xsl:apply-templates>
        </xsl:copy>
    </xsl:template>
</xsl:stylesheet>