<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:fn="http://www.w3.org/2005/xpath-functions"
    xmlns:foo="whatever" xmlns:tei="http://www.tei-c.org/ns/1.0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="3.0">
    <xsl:output method="xml" indent="true"/>
    <xsl:mode on-no-match="shallow-copy"/>
    <!-- dieses XSLT schreibt die pmb-nummern in person-day 
   -->
    
    <xsl:param name="listperson" select="document('https://raw.githubusercontent.com/arthur-schnitzler/schnitzler-tagebuch-data/master/indices/listperson.xml')" as="node()"/>
    <xsl:key name="listperson-treffer" match="tei:listPerson/tei:person" use="@xml:id"/>
    
    <xsl:template match="*:ref">
        <xsl:element name="ref">
            <xsl:attribute name="corresp">
            <xsl:value-of select="concat('pmb', replace(substring-after(key('listperson-treffer', ., $listperson)/tei:idno[@subtype='pmb'][1], 'https://pmb.acdh.oeaw.ac.at/entity/'), '/', ''))"/>
            </xsl:attribute>
            <xsl:value-of select="."/>
        </xsl:element>
    </xsl:template>
</xsl:stylesheet>
