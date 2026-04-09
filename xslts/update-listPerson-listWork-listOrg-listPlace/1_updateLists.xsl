<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns="http://www.tei-c.org/ns/1.0"
    xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:fn="http://www.w3.org/2005/xpath-functions" version="3.0">
    <xsl:mode on-no-match="shallow-copy"/>
    <xsl:output method="xml" indent="yes"/>

    <!-- URIs der lokal heruntergeladenen PMB-Bulk-Listen, vom Workflow als
         absolute file://-URIs übergeben. Pro Lauf wird nur die Liste gebraucht,
         die zum gerade verarbeiteten Index-File passt. -->
    <xsl:param name="listperson-uri" as="xs:string" select="''"/>
    <xsl:param name="listplace-uri" as="xs:string" select="''"/>
    <xsl:param name="listbibl-uri" as="xs:string" select="''"/>

    <xsl:variable name="listperson-doc"
        select="if ($listperson-uri != '' and doc-available($listperson-uri)) then document($listperson-uri) else ()"/>
    <xsl:variable name="listplace-doc"
        select="if ($listplace-uri != '' and doc-available($listplace-uri)) then document($listplace-uri) else ()"/>
    <xsl:variable name="listbibl-doc"
        select="if ($listbibl-uri != '' and doc-available($listbibl-uri)) then document($listbibl-uri) else ()"/>

    <!-- Hilfsfunktion: Aus der schnitzler-tagebuch-Idno-URL die neue xml:id
         ableiten, z.B.
           https://schnitzler-tagebuch.acdh.oeaw.ac.at/person_17277.html -> person_17277
           https://schnitzler-tagebuch.acdh.oeaw.ac.at/pmb92368.html      -> pmb92368 -->
    <xsl:function name="tei:new-id" as="xs:string">
        <xsl:param name="entry" as="element()"/>
        <xsl:variable name="url"
            select="normalize-space($entry/tei:idno[@subtype='schnitzler-tagebuch'][1])"/>
        <xsl:value-of select="replace(replace($url, 'https://schnitzler-tagebuch\.acdh\.oeaw\.ac\.at/', ''), '\.html$', '')"/>
    </xsl:function>

    <!-- Top-Level-Container der Personenliste komplett neu befüllen -->
    <xsl:template match="tei:listPerson[@xml:id='listperson']">
        <xsl:copy>
            <xsl:apply-templates select="@*"/>
            <xsl:choose>
                <xsl:when test="exists($listperson-doc)">
                    <xsl:for-each select="$listperson-doc//tei:person[tei:idno[@subtype='schnitzler-tagebuch'] and not(contains(tei:idno[@subtype='schnitzler-tagebuch'][1], '#'))]">
                        <xsl:sort select="tei:new-id(.)"/>
                        <xsl:element name="person" namespace="http://www.tei-c.org/ns/1.0">
                            <xsl:attribute name="xml:id" select="tei:new-id(.)"/>
                            <xsl:copy-of select="@* except @xml:id" copy-namespaces="no"/>
                            <xsl:copy-of select="node()" copy-namespaces="no"/>
                        </xsl:element>
                    </xsl:for-each>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:apply-templates select="node()"/>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:copy>
    </xsl:template>

    <!-- Top-Level-Container der Ortsliste komplett neu befüllen -->
    <xsl:template match="tei:body/tei:listPlace">
        <xsl:copy>
            <xsl:apply-templates select="@*"/>
            <xsl:choose>
                <xsl:when test="exists($listplace-doc)">
                    <xsl:for-each select="$listplace-doc//tei:place[tei:idno[@subtype='schnitzler-tagebuch'] and not(contains(tei:idno[@subtype='schnitzler-tagebuch'][1], '#'))]">
                        <xsl:sort select="tei:new-id(.)"/>
                        <xsl:element name="place" namespace="http://www.tei-c.org/ns/1.0">
                            <xsl:attribute name="xml:id" select="tei:new-id(.)"/>
                            <xsl:copy-of select="@* except @xml:id" copy-namespaces="no"/>
                            <xsl:copy-of select="node()" copy-namespaces="no"/>
                        </xsl:element>
                    </xsl:for-each>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:apply-templates select="node()"/>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:copy>
    </xsl:template>

    <!-- Top-Level-Container der Werkliste komplett neu befüllen -->
    <xsl:template match="tei:listBibl[@xml:id='listwork']">
        <xsl:copy>
            <xsl:apply-templates select="@*"/>
            <xsl:choose>
                <xsl:when test="exists($listbibl-doc)">
                    <xsl:for-each select="$listbibl-doc//tei:bibl[tei:idno[@subtype='schnitzler-tagebuch'] and not(contains(tei:idno[@subtype='schnitzler-tagebuch'][1], '#'))]">
                        <xsl:sort select="tei:new-id(.)"/>
                        <xsl:element name="bibl" namespace="http://www.tei-c.org/ns/1.0">
                            <xsl:attribute name="xml:id" select="tei:new-id(.)"/>
                            <xsl:copy-of select="@* except @xml:id" copy-namespaces="no"/>
                            <xsl:copy-of select="node()" copy-namespaces="no"/>
                        </xsl:element>
                    </xsl:for-each>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:apply-templates select="node()"/>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:copy>
    </xsl:template>

</xsl:stylesheet>
