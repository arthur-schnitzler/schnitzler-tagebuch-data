<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema" exclude-result-prefixes="xs" version="2.0">
    <xsl:mode on-no-match="shallow-copy"/>

    <xsl:template match="strich">
        <xsl:variable name="begin" select="day-from-date(./preceding-sibling::date[1]/@when)"/>
        <xsl:variable name="end" select="day-from-date(./following-sibling::date[1]/@when)"/>
        <xsl:variable name="month" select="month-from-date(./preceding-sibling::date[1]/@when)"/>
        <xsl:variable name="year" select="year-from-date(./preceding-sibling::date[1]/@when)"/>
        <xsl:variable name="counter" select="$end - $begin - 1"/>
        <xsl:for-each select="1 to $counter">
            <xsl:element name="date">
                <xsl:attribute name="when">
                    <xsl:value-of select="$year"/>
                    <xsl:text>-</xsl:text>

                    <xsl:if test="$month &lt; 10">
                        <xsl:text>0</xsl:text>
                    </xsl:if>

                    <xsl:value-of select="$month"/>
                    <xsl:text>-</xsl:text>
                    <xsl:if test="$begin + . &lt; 10">
                        <xsl:text>0</xsl:text>
                    </xsl:if>
                    <xsl:value-of select="$begin + ."/>
                </xsl:attribute>
                <xsl:value-of select="$begin + ."/>
                <xsl:text>.</xsl:text>
                <xsl:value-of select="$month"/>
                <xsl:text>.</xsl:text>
                <xsl:value-of select="$year"/>
            </xsl:element>
        </xsl:for-each>
        <xsl:apply-templates/>
    </xsl:template>


</xsl:stylesheet>
