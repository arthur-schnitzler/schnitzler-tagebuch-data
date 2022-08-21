<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:tei="http://www.tei-c.org/ns/1.0"
    exclude-result-prefixes="xs" version="3.0">
    <xsl:mode on-no-match="shallow-copy"/>
    <xsl:output indent="yes"/>
    <xsl:param name="konkordanz" select="document('indices/listplace-geonamesundpmb.xml')"/>
    <xsl:key name="konkordanz" match="tei:place" use="tei:idno[@type = 'obsolete-schnitzler-diary']"/>
    
 <xsl:template match="tei:rs[@type='place' and not(starts-with(@ref,'#pmb'))]/@ref">
     <xsl:attribute name="ref">
         <xsl:variable name="lookup" select="key('konkordanz', substring-after(.,'#'), $konkordanz)" as="node()?"/>
         <xsl:choose>
             <xsl:when test="$lookup/child::*[1]">
                 <xsl:value-of select="concat('#',$lookup/@xml:id)"/>
             </xsl:when>
             <xsl:otherwise>
                 <xsl:value-of select="."/>
             </xsl:otherwise>
         </xsl:choose>
     </xsl:attribute>
 </xsl:template>
    
</xsl:stylesheet>
