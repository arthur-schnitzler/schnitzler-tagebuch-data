<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns="https://www.tei-c.org/ns/1.0"
    xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:fn="http://www.w3.org/2005/xpath-functions" version="3.0">
    <xsl:mode on-no-match="shallow-copy"/>
    <xsl:output method="xml" indent="yes"/>
    
    <xsl:param name="pmb-uri-varianten" select="document('utils/multiple-pmb-uris.xml')"/>
    <xsl:key name="pmb-varianten-lookup" match="item" use="idno"/>
    
    <xsl:template match="tei:publicationStmt/tei:date">
        <xsl:element name="date" namespace="http://www.tei-c.org/ns/1.0">
        <xsl:value-of select="fn:current-date()"/>
        </xsl:element>
    </xsl:template>
    
    <!-- Das holt die Person neu aus der PMB -->
    <xsl:template match="tei:listPerson/tei:person">
     <xsl:element name="person" namespace="http://www.tei-c.org/ns/1.0">
         <xsl:copy-of select="@*"/>
         <xsl:variable name="nummer">
             <xsl:choose>
                 <xsl:when test="child::tei:idno[@type='pmb' or @subtype='pmb'][2]">
                     <xsl:for-each select="child::tei:idno[@type='pmb' or @subtype='pmb']">
                         <xsl:variable name="nummeri" select="replace(replace(., 'https://pmb.acdh.oeaw.ac.at/entity/', ''), '/', '')"/>
                         <xsl:variable name="eintragi"
                             select="fn:escape-html-uri(concat('https://pmb.acdh.oeaw.ac.at/apis/entities/tei/person/', $nummeri))"
                             as="xs:string"/>
                         <xsl:if test="doc-available($eintragi)">
                             <xsl:value-of select="$nummeri"/>
                         </xsl:if>
                     </xsl:for-each>
                 </xsl:when>
                 <xsl:otherwise>
                     <xsl:value-of select="replace(replace(child::tei:idno[@type='pmb' or @subtype='pmb'][1], 'https://pmb.acdh.oeaw.ac.at/entity/', ''), '/', '')"/>
                 </xsl:otherwise>
             </xsl:choose>
         </xsl:variable>
         <xsl:variable name="nummer-check">
             <xsl:choose>
                 <xsl:when test="key('pmb-varianten-lookup', concat('https://pmb.acdh.oeaw.ac.at/entity/', $nummer), $pmb-uri-varianten)">
                     <xsl:variable name="nummer-lookup" select="key('pmb-varianten-lookup', concat('https://pmb.acdh.oeaw.ac.at/entity/', $nummer), $pmb-uri-varianten)/@xml:id"/>
                     <xsl:value-of select="replace($nummer-lookup, 'pmb', '')"/>
                 </xsl:when>
                 <xsl:otherwise>
                     <xsl:value-of select="$nummer"/>
                 </xsl:otherwise>
             </xsl:choose>
         </xsl:variable>
         <xsl:variable name="eintrag"
             select="fn:escape-html-uri(concat('https://pmb.acdh.oeaw.ac.at/apis/entities/tei/person/', $nummer-check))"
             as="xs:string"/>
         <xsl:choose>
             <xsl:when test="doc-available($eintrag)">
                 <xsl:copy-of select="document($eintrag)/child::person/*" copy-namespaces="no"/>
             </xsl:when>
             <xsl:otherwise>
                 <xsl:element name="error">
                     <xsl:attribute name="type">
                         <xsl:text>person</xsl:text>
                     </xsl:attribute>
                     <xsl:value-of select="$nummer-check"/>
                 </xsl:element>
             </xsl:otherwise>
         </xsl:choose>
     </xsl:element>
 </xsl:template>
    
    <!-- Das holt die Orts-Idnos neu aus der PMB -->
    
    <xsl:template match="tei:listPlace/tei:place">
        <xsl:element name="place" namespace="http://www.tei-c.org/ns/1.0">
            <xsl:copy-of select="@*"/>
            <xsl:variable name="nummer" select="replace(@xml:id, 'pmb', '')"/>
            <xsl:variable name="nummer-check">
                <xsl:choose>
                    <xsl:when test="key('pmb-varianten-lookup', concat('https://pmb.acdh.oeaw.ac.at/entity/', $nummer), $pmb-uri-varianten)">
                        <xsl:variable name="nummer-lookup" select="key('pmb-varianten-lookup', concat('https://pmb.acdh.oeaw.ac.at/entity/', $nummer), $pmb-uri-varianten)/@xml:id"/>
                        <xsl:value-of select="replace($nummer-lookup, 'pmb', '')"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:value-of select="$nummer"/>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:variable>
            <xsl:variable name="eintrag"
                select="fn:escape-html-uri(concat('https://pmb.acdh.oeaw.ac.at/apis/entities/tei/place/', $nummer-check))"
                as="xs:string"/>
            <xsl:choose>
                <xsl:when test="doc-available($eintrag)">
                    <xsl:copy-of select="document($eintrag)/child::place/*" copy-namespaces="no"/>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:element name="error">
                        <xsl:attribute name="type">
                            <xsl:text>place</xsl:text>
                        </xsl:attribute>
                        <xsl:value-of select="$nummer-check"/>
                    </xsl:element>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:element>
    </xsl:template>
    
    
    
 
 <!-- holt werke neu. pubPlace, notes werden kopiert 
 
 aus faulheit habe ich noch dieses suchen und ersetzen
 auf das ergebnis gemacht, als das mit einem xslt zu korrigieren:
 
 "person__" zu "pmb"
 
 -->
    
    <xsl:template match="tei:listBibl/tei:bibl">
        <xsl:element name="bibl" namespace="http://www.tei-c.org/ns/1.0">
            <xsl:copy-of select="@*"/>
            <xsl:variable name="nummer" select="replace(@xml:id, 'pmb', '')"/>
            <xsl:variable name="nummer-check">
                <xsl:choose>
                    <xsl:when test="key('pmb-varianten-lookup', concat('https://pmb.acdh.oeaw.ac.at/entity/', $nummer), $pmb-uri-varianten)">
                        <xsl:variable name="nummer-lookup" select="key('pmb-varianten-lookup', concat('https://pmb.acdh.oeaw.ac.at/entity/', $nummer), $pmb-uri-varianten)/@xml:id"/>
                        <xsl:value-of select="replace($nummer-lookup, 'pmb', '')"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:value-of select="$nummer"/>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:variable>
        <xsl:variable name="eintrag"
            select="fn:escape-html-uri(concat('https://pmb.acdh.oeaw.ac.at/apis/entities/tei/work/', $nummer-check))"
            as="xs:string"/>
            <xsl:choose>
                <xsl:when test="doc-available($eintrag)">
                    <xsl:copy-of select="document($eintrag)/child::bibl/*" copy-namespaces="no"/>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:element name="error">
                        <xsl:attribute name="type">
                            <xsl:text>bibl</xsl:text>
                        </xsl:attribute>
                        <xsl:value-of select="$nummer-check"/>
                    </xsl:element>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:element>
    </xsl:template>
    
    
    
    
    
</xsl:stylesheet>
