<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:fn="http://www.w3.org/2005/xpath-functions"
    xmlns:tei="http://www.tei-c.org/ns/1.0"
    version="3.0"
    exclude-result-prefixes="tei">
    <xsl:output method="xml" omit-xml-declaration="no" indent="true"/>
    <xsl:mode on-no-match="shallow-skip"/>
    
    <!-- Dieses XSLT auf eine beliebige Datei des Projekts angewandt,
    erstellt eine Liste aller vorkommenden Orte am jeweiligen
    Tag. Das ganze ist unsortiert, da mache ich schnell ein eigenes XSLT -->
    
    <xsl:template match="/">
        <xsl:apply-templates mode="rootcopy"/>
    </xsl:template>
    
    <xsl:template match="node()" mode="rootcopy">
        <xsl:element name="list">
            <xsl:variable name="folderURI" select="resolve-uri('.',base-uri())"/>
            <xsl:for-each select="collection('../editions/?select=entry__*.xml;recurse=yes')/node()">
                <xsl:element name="item">
                    <xsl:attribute name="target">
                        <xsl:value-of select="descendant::tei:title[@type='iso-date']"/>
                    </xsl:attribute>
                    <xsl:variable name="orte"
                     as="node()">
                        <xsl:element name="places">
                            <xsl:for-each select="descendant::tei:rs[@type='place' and not(@ana='#exclude')]">
                                <xsl:copy-of select="."/>
                            </xsl:for-each>
                        </xsl:element>
                    </xsl:variable>
                    <xsl:for-each select="distinct-values(descendant::tei:rs[@type='place' and not(@ana='#exclude')]/@ref)">
                        <xsl:variable name="current" select="."/>
                            <xsl:element name="placeName">
                                <xsl:attribute name="ref">
                                    <xsl:value-of select="replace(.,'#','')"/>
                                </xsl:attribute>
                                <xsl:copy-of select="$orte/descendant::tei:rs[$current =@ref][1]/text()"/>
                            </xsl:element>
                    </xsl:for-each>
                </xsl:element>
            </xsl:for-each>
        </xsl:element>
        
        
    </xsl:template>
    
    
    
  <!--  <!-\- Deep copy template -\->
    <xsl:template match="node()|@*" mode="copy">
        <xsl:copy>
            <xsl:apply-templates mode="copy" select="@*"/>
            <xsl:apply-templates mode="copy"/>
        </xsl:copy>
    </xsl:template>
    -->
    
    <!-- Handle default matching -->
    
    
    <xsl:template match="/*">
        <xsl:element name="TEI">
            <xsl:copy-of select="@*"/>
            <xsl:attribute name="noNamespaceSchemaLocation"
                namespace="http://www.w3.org/2001/XMLSchema-instance">your-value</xsl:attribute>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
</xsl:stylesheet>
