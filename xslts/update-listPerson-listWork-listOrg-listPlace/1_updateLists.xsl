<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns="http://www.tei-c.org/ns/1.0"
    xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:fn="http://www.w3.org/2005/xpath-functions" version="3.0">
    <xsl:mode on-no-match="shallow-copy"/>
    <xsl:output method="xml" indent="yes"/>

    <!-- Pfade (URIs) zu den lokal heruntergeladenen PMB-Listen.
         Werden vom Workflow als absolute file://-URIs übergeben. -->
    <xsl:param name="listperson-uri" as="xs:string" select="''"/>
    <xsl:param name="listplace-uri" as="xs:string" select="''"/>
    <xsl:param name="listorg-uri" as="xs:string" select="''"/>
    <xsl:param name="listbibl-uri" as="xs:string" select="''"/>

    <xsl:variable name="listperson-doc"
        select="if ($listperson-uri != '' and doc-available($listperson-uri)) then document($listperson-uri) else ()"/>
    <xsl:variable name="listplace-doc"
        select="if ($listplace-uri != '' and doc-available($listplace-uri)) then document($listplace-uri) else ()"/>
    <xsl:variable name="listorg-doc"
        select="if ($listorg-uri != '' and doc-available($listorg-uri)) then document($listorg-uri) else ()"/>
    <xsl:variable name="listbibl-doc"
        select="if ($listbibl-uri != '' and doc-available($listbibl-uri)) then document($listbibl-uri) else ()"/>

    <!-- angewandt auf bestehende listperson.xml etc. -->
    <xsl:template match="tei:listPlace/tei:place[starts-with(@xml:id, 'pmb')]">
        <xsl:variable name="nummer" select="replace(@xml:id, 'pmb', '')"/>
        <xsl:variable name="entry"
            select="$listplace-doc//tei:place[@xml:id = concat('place__', $nummer)][1]"/>
        <xsl:choose>
            <xsl:when test="$entry">
                <xsl:copy-of select="$entry" copy-namespaces="no"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:element name="error">
                    <xsl:attribute name="type">
                        <xsl:text>place</xsl:text>
                    </xsl:attribute>
                    <xsl:value-of select="."/>
                </xsl:element>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    <xsl:template match="tei:listOrg/tei:org[tei:idno[@subtype='pmb']]">
        <xsl:variable name="nummer" select="replace(replace(tei:idno[@subtype='pmb']/text(), 'https://pmb.acdh.oeaw.ac.at/entity/', ''), '/', '')"/>
        <xsl:variable name="entry"
            select="$listorg-doc//tei:org[@xml:id = concat('org__', $nummer)][1]"/>
        <xsl:choose>
            <xsl:when test="$entry">
                <xsl:copy-of select="$entry" copy-namespaces="no"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:element name="error">
                    <xsl:attribute name="type">
                        <xsl:text>org</xsl:text>
                    </xsl:attribute>
                    <xsl:value-of select="$nummer"/>
                </xsl:element>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    <xsl:template match="tei:listBibl/tei:bibl[starts-with(@xml:id, 'pmb')]">
        <xsl:variable name="nummer" select="replace(@xml:id, 'pmb', '')"/>
        <xsl:variable name="entry"
            select="$listbibl-doc//tei:bibl[@xml:id = concat('work__', $nummer)][1]"/>
        <xsl:choose>
            <xsl:when test="$entry">
                <xsl:copy-of select="$entry" copy-namespaces="no"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:element name="error">
                    <xsl:attribute name="type">
                        <xsl:text>bibl</xsl:text>
                    </xsl:attribute>
                    <xsl:value-of select="$nummer"/>
                </xsl:element>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    <xsl:template match="tei:listPerson/tei:person[tei:idno[@subtype='pmb']]">
        <xsl:variable name="nummer" select="replace(replace(tei:idno[@subtype='pmb'][1]/text(), 'https://pmb.acdh.oeaw.ac.at/entity/', ''), '/', '')"/>
        <xsl:variable name="entry"
            select="$listperson-doc//tei:person[@xml:id = concat('person__', $nummer)][1]"/>
        <xsl:choose>
            <xsl:when test="$entry">
                <xsl:element name="person" namespace="http://www.tei-c.org/ns/1.0">
                    <xsl:attribute name="xml:id">
                        <xsl:value-of select="$entry//tei:idno[@subtype='schnitzler-tagebuch'][1]/replace(replace(text(), 'https://schnitzler-tagebuch.acdh.oeaw.ac.at/', ''), '.html', '')"/>
                    </xsl:attribute>
                <xsl:copy-of select="$entry/*" copy-namespaces="no"/>
                </xsl:element>
            </xsl:when>
            <xsl:otherwise>
                <xsl:element name="error" namespace="http://www.tei-c.org/ns/1.0">
                    <xsl:attribute name="type">
                        <xsl:text>person</xsl:text>
                    </xsl:attribute>
                    <xsl:value-of select="$nummer"/>
                </xsl:element>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

</xsl:stylesheet>
