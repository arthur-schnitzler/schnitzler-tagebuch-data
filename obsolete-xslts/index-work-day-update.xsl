<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns="http://www.tei-c.org/ns/1.0"
    xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:fn="http://www.w3.org/2005/xpath-functions" version="3.0">
    <xsl:mode on-no-match="shallow-copy"/>
    <xsl:output method="xml" indent="yes"/>
    
    <!-- das hier passt die idnos von index_work_day.xml an, wenn durch
    merge in der PMB Fehler reingekommen sind-->
    
    <xsl:param name="listwork" select="document('../indices/listwork.xml')"/>
    <xsl:key name="lookupkey" match="tei:bibl" use="tei:idno[@subtype='pmb']"/>
    
    <xsl:template match="ref">
        <xsl:element name="ref" inherit-namespaces="true" namespace="">
            <xsl:variable name="wert" select="key('lookupkey', concat('https://pmb.acdh.oeaw.ac.at/entity/', replace(., 'pmb', ''), '/'), $listwork)"/>
           <xsl:choose>
               <xsl:when test="not($wert/@xml:id)">
                   <xsl:text>ERROR</xsl:text>
                   <xsl:value-of select="."/>
               </xsl:when>
               <xsl:otherwise>
                   <xsl:value-of select="$wert/@xml:id"/>
               </xsl:otherwise>
           </xsl:choose>
            
            
        </xsl:element>
        
        
    </xsl:template>
    
    
    
 


</xsl:stylesheet>