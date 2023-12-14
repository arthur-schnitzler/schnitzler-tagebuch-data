<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:tei="http://www.tei-c.org/ns/1.0"
    exclude-result-prefixes="xs" version="3.0">
    <xsl:mode on-no-match="shallow-copy"/>
    <xsl:output indent="yes"/>
    <xsl:param name="konkordanz" select="document('../listplace-komplett.xml')"/>
    <xsl:key name="konkordanz" match="tei:place" use="@xml:id"/>
    <xsl:key name="konkordanz-neu" match="tei:place" use="tei:idno[@subtype='schnitzler-tagebuch']"></xsl:key>
    
    
    <xsl:template match="tei:rs[@type='place']/@ref">
        <xsl:variable name="id" select="replace(., '#', '')"/>
        <xsl:attribute name="ref">
        <xsl:choose>
            <xsl:when test="key('konkordanz', $id, $konkordanz)/@xml:id">
                <xsl:value-of select="."/>
            </xsl:when>
            <xsl:when test="key('konkordanz-neu', concat('https://schnitzler-tagebuch.acdh.oeaw.ac.at/', $id, '.html'), $konkordanz)/@xml:id">
                    <xsl:value-of select="concat('#', key('konkordanz-neu', concat('https://schnitzler-tagebuch.acdh.oeaw.ac.at/', $id, '.html'), $konkordanz)/@xml:id)"/>
            </xsl:when>
        </xsl:choose>
        </xsl:attribute>
    </xsl:template>
</xsl:stylesheet>
