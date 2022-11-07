<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns="https://www.tei-c.org/ns/1.0"
    xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:fn="http://www.w3.org/2005/xpath-functions" version="3.0">
    <xsl:mode on-no-match="shallow-skip"/>
    <xsl:output method="xml" indent="yes"/>
    
    <!-- aus dem pmb-dump alle pmb-uris nehmen -->
    
    
    <xsl:template match="tei:body/tei:listPerson|tei:body/tei:listBibl|tei:body/tei:listPlace">
        <xsl:element name="list" namespace="">
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="tei:person[tei:idno[@type='pmb' or @subtype='pmb'][2]]">
        <xsl:element name="item" namespace="">
            <xsl:copy-of select="@*"/>
            <xsl:copy-of select="tei:idno[@type='pmb' or @subtype='pmb']" />
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="tei:bibl[tei:idno[@type='pmb' or @subtype='pmb'][2]]">
        <xsl:element name="item" namespace="">
            <xsl:copy-of select="@*"/>
            <xsl:copy-of select="tei:idno[@type='pmb' or @subtype='pmb']" />
        </xsl:element>
    </xsl:template>
    
    
    <xsl:template match="tei:place[tei:idno[@type='pmb' or @subtype='pmb'][2]]">
        <xsl:element name="item" namespace="">
            <xsl:copy-of select="@*"/>
            <xsl:copy-of select="tei:idno[@type='pmb' or @subtype='pmb']" />
        </xsl:element>
    </xsl:template>
    
    
</xsl:stylesheet>