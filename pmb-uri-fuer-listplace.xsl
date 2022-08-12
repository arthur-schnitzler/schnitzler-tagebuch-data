<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:tei="http://www.tei-c.org/ns/1.0"
    exclude-result-prefixes="xs" version="3.0">
    <xsl:mode on-no-match="shallow-copy"/>
    <xsl:output indent="yes"/>
    <xsl:param name="konkordanz" select="document('listplace-pmb.xml')"/>
    <xsl:key name="konkordanz" match="tei:place" use="tei:idno[@type = 'geonames']"/>
    <xsl:key name="konkordanz-will-never-work" match="tei:place" use="tei:idno[@type='this-will-never-work/']"/>
    
  <!--  <xsl:template match="tei:place[tei:idno[@type='geonames']]">
        <xsl:variable name="geoname-nummer" select="normalize-space(replace(substring-after(., 'geonames.org/'), '/', ''))"/>
        <xsl:variable name="pmb-nummer">
            <xsl:choose>
                <xsl:when test="key('konkordanz', $geoname-nummer, $konkordanz)[1]">
                    <xsl:value-of select="replace(key('konkordanz', $geoname-nummer, $konkordanz)[1]/@xml:id, 'place__', '')"/>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:text>ERROR</xsl:text>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:variable> 
        <xsl:variable name="obsolete-id" select="@xml:id"/>
        <xsl:element name="place" namespace="http://www.tei-c.org/ns/1.0">
        <xsl:choose>
            <xsl:when test="not($pmb-nummer='ERROR')">
                <xsl:attribute name="xml:id">
                   <xsl:value-of select="concat('pmb', $pmb-nummer)"/>
                </xsl:attribute>
                <xsl:copy-of select="child::*"/>
                <xsl:element name="idno" namespace="http://www.tei-c.org/ns/1.0">
                    <xsl:attribute name="type">
                        <xsl:text>obsolete-schnitzler-diary</xsl:text>
                    </xsl:attribute>
                    <xsl:value-of select="@xml:id"/>
                </xsl:element>
                <xsl:element name="idno" namespace="http://www.tei-c.org/ns/1.0">
                    <xsl:attribute name="type">
                        <xsl:text>pmb</xsl:text>
                    </xsl:attribute>
                    <xsl:value-of select="concat('https://pmb.acdh.oeaw.ac.at/entity/', $pmb-nummer)"/>
                </xsl:element>
            </xsl:when>
            <xsl:otherwise>
                <xsl:copy select="@*"/>
                <xsl:copy-of select="child::*"/>
            </xsl:otherwise>
        </xsl:choose>
        </xsl:element>
    </xsl:template>-->
    
    <xsl:template match="tei:place[not(starts-with(@xml:id, 'pmb'))]">
        <xsl:variable name="treffer" select="key('konkordanz-will-never-work', @xml:id, $konkordanz)"/>
        <xsl:choose>
            <xsl:when test="empty($treffer)">
                <xsl:copy-of select="."/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:element name="place" namespace="http://www.tei-c.org/ns/1.0">
                    <xsl:attribute name="xml:id">
                        <xsl:value-of select="replace($treffer/@xml:id, 'place__', 'pmb')"/>
                    </xsl:attribute>  
                    <xsl:copy-of select="child::*"/>
                    <xsl:element name="idno" namespace="http://www.tei-c.org/ns/1.0">
                        <xsl:attribute name="type">
                            <xsl:text>obsolete-schnitzler-diary</xsl:text>
                        </xsl:attribute>
                        <xsl:value-of select="@xml:id"/>
                    </xsl:element>
                    <xsl:element name="idno" namespace="http://www.tei-c.org/ns/1.0">
                        <xsl:attribute name="type">
                            <xsl:text>pmb</xsl:text>
                        </xsl:attribute>
                        <xsl:value-of select="concat('https://pmb.acdh.oeaw.ac.at/entity/', replace($treffer/@xml:id, 'place__', ''))"/>
                    </xsl:element>
                </xsl:element>
            </xsl:otherwise>
        </xsl:choose>
        
    </xsl:template>
    
</xsl:stylesheet>
