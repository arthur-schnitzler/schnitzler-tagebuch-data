<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns="http://www.tei-c.org/ns/1.0"
    xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:fn="http://www.w3.org/2005/xpath-functions" version="3.0">
    <xsl:mode on-no-match="shallow-copy"/>
    <xsl:output method="xml" indent="yes"/>
    <xsl:param name="places"
        select="document('/Users/oldfiche/Documents/git/schnitzler-orte/editions/schnitzler_places.xml')"/>
    <xsl:key name="place-lookup" match="tei:event" use="@when"/>
    <xsl:param name="date-of-diary-entry" select="descendant::tei:title[@type = 'iso-date']"
        as="xs:string"/>
    <xsl:template match="tei:profileDesc">
        <xsl:element name="profileDesc" namespace="http://www.tei-c.org/ns/1.0">
            <xsl:element name="settingDesc" namespace="http://www.tei-c.org/ns/1.0">
                <xsl:variable name="settinglistPlace"
                    select="key('place-lookup', $date-of-diary-entry, $places)/descendant::tei:listPlace"/>
                <xsl:if test="$settinglistPlace/*">
                    <xsl:element name="listPlace" namespace="http://www.tei-c.org/ns/1.0">
                        <xsl:for-each select="$settinglistPlace/tei:place">
                            <xsl:element name="place" namespace="http://www.tei-c.org/ns/1.0">
                                <xsl:variable name="pmb-nummer" as="xs:string">
                                    <xsl:value-of
                                        select="substring-before(substring-after(descendant::tei:idno[@type = 'pmb'][1], 'https://pmb.acdh.oeaw.ac.at/apis/entities/entity/place/'), '/detail')"
                                    />
                                </xsl:variable>
                                <xsl:element name="placeName" namespace="http://www.tei-c.org/ns/1.0">
                                    <xsl:attribute name="ref">
                                        <xsl:value-of select="concat('#', $pmb-nummer)"/>
                                    </xsl:attribute>
                                    <xsl:copy-of select="descendant::tei:placeName[1]/text()"/>
                                </xsl:element>
                            </xsl:element>
                        </xsl:for-each>
                    </xsl:element>
                </xsl:if>
            </xsl:element>
        </xsl:element>
    </xsl:template>
</xsl:stylesheet>
