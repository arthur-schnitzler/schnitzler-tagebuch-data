<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:tei="http://www.tei-c.org/ns/1.0"
    xmlns=""
    xmlns:foo="frufru"
    exclude-result-prefixes="xs" version="3.0">
    <xsl:mode on-no-match="shallow-copy"/>
    <xsl:output method="xml" indent="yes"/>
    
    <xsl:param name="werke" select="document('works.xml')"/>
    <xsl:key name="werk-lookup" match="row" use="Werk_Titel"/>
    
    <xsl:template match="tei:title[ancestor::tei:body]">
        <xsl:choose>
            <xsl:when test="key('werk-lookup', text(), $werke) and not(key('werk-lookup', text(), $werke)[2])">
                <xsl:element name="tei:title" namespace="http://www.tei-c.org/ns/1.0">
                    <xsl:attribute name="tei:key">
                        <xsl:value-of select="key('werk-lookup', text(), $werke)/Werk"/>
                    </xsl:attribute>
                    <xsl:apply-templates/>
                </xsl:element>
            </xsl:when>
            <xsl:otherwise>
                <xsl:copy copy-namespaces="no">
                    <xsl:apply-templates/>
                </xsl:copy>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    
    
  
    
    
</xsl:stylesheet>