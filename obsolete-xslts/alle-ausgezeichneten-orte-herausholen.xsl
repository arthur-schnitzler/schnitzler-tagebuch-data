<?xml version="1.0" encoding="UTF-8"?>
<xsl:transform xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="3.0"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:tei="http://www.tei-c.org/ns/1.0"
    exclude-result-prefixes="xs">
    
    <xsl:mode on-no-match="shallow-skip"/>
    <xsl:output indent="true" method="xml"/>
    
    <xsl:param name="aufenthaltsorte-bekannt" select="document('aufenthaltsorte-von-schnitzler.xml')"/>
    <xsl:key name="kennmascho" match="tei:event" use="@when"/>
    
    <!-- Root Template -->
    <xsl:template match="/">
        <xsl:result-document method="xml" href="all-days-and-all-of-the-nights.xml">
           <xsl:element name="listEvent" namespace="http://www.tei-c.org/ns/1.0">
            <!-- Iterate through each XML document in the collection -->
            <xsl:for-each select="collection('../editions/?select=entry__*.xml')">
                <xsl:sort select="child::tei:TEI[1]/tei:teiHeader[1]/tei:fileDesc[1]/tei:titleStmt[1]/tei:title[@type='iso-date']"/>
                <xsl:if test="descendant::tei:text/tei:body/descendant::tei:rs[@type='place'][1]">
                <xsl:variable name="date" select="child::tei:TEI[1]/tei:teiHeader[1]/tei:fileDesc[1]/tei:titleStmt[1]/tei:title[@type='iso-date']"/>
                <xsl:element name="event" namespace="http://www.tei-c.org/ns/1.0">
                <xsl:attribute name="when">
                    <xsl:value-of select="$date"/>
                </xsl:attribute>
                <!-- Iterate through each matching 'rs' element -->
                <xsl:for-each select="descendant::tei:text/tei:body/descendant::tei:rs[@type='place']">
                    <xsl:variable name="refref" select="@ref"/>
                    <xsl:choose>
                        <xsl:when test="key('kennmascho', $date, $aufenthaltsorte-bekannt)">
                            <xsl:choose>
                                <xsl:when test="key('kennmascho', $date, $aufenthaltsorte-bekannt)/descendant::tei:place/@corresp = $refref"/>
                                <xsl:otherwise>
                                    <xsl:copy-of select="."/>
                                </xsl:otherwise>
                            </xsl:choose>
                        </xsl:when>
                        <xsl:otherwise>
                            <!--<xsl:copy-of select="."></xsl:copy-of>-->
                        </xsl:otherwise>
                    </xsl:choose>
                    
                </xsl:for-each>
                </xsl:element>
                </xsl:if>
            </xsl:for-each>
           </xsl:element>
        </xsl:result-document>
    </xsl:template>
</xsl:transform>
