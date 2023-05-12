<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns="http://www.tei-c.org/ns/1.0"
    xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:fn="http://www.w3.org/2005/xpath-functions" version="3.0">
    <xsl:mode on-no-match="shallow-copy"/>
    <xsl:output method="xml" indent="yes"/>
    
    <xsl:template match="*[namespace-uri()='']">
        <xsl:element name="{local-name()}" namespace="http://www.tei-c.org/ns/1.0">
            <xsl:apply-templates select="@* | node()"/>
        </xsl:element>
    </xsl:template>
    
    
    <xsl:template match="@xml:id[contains(.,'__')]">
        <xsl:attribute name="xml:id">
            <xsl:value-of select="concat('pmb', substring-after(., '__'))"/>
        </xsl:attribute>
    </xsl:template>
    
    <xsl:template match="@key[contains(.,'__')]|@ref[contains(.,'__')]">
        <xsl:attribute name="ref">
            <xsl:value-of select="concat('pmb', substring-after(., '__'))"/>
        </xsl:attribute>
    </xsl:template>
    
    
    
</xsl:stylesheet>
