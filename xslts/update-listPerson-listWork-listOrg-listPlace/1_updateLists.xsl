<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns="http://www.tei-c.org/ns/1.0"
    xmlns:tei="http://www.tei-c.org/ns/1.0"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    exclude-result-prefixes="tei xs"
    version="3.0">
    <xsl:mode on-no-match="shallow-copy"/>
    <xsl:output method="xml" indent="yes"/>

    <!-- Input: eine PMB-Bulk-Liste (listperson.xml / listplace.xml / listbibl.xml).
         Output: eine geschnittene Index-Datei mit dem handgepflegten teiHeader
         und dem projektspezifischen Wrapper. Pro Lauf greift genau eines der
         drei root-Templates. -->

    <xsl:function name="tei:new-id" as="xs:string">
        <xsl:param name="entry" as="element()"/>
        <xsl:variable name="url"
            select="normalize-space($entry/tei:idno[@subtype='schnitzler-tagebuch'][1])"/>
        <xsl:value-of select="replace(replace($url, 'https://schnitzler-tagebuch\.acdh\.oeaw\.ac\.at/', ''), '\.html$', '')"/>
    </xsl:function>

    <!-- ============================================================= -->
    <!-- listperson.xml                                                  -->
    <!-- ============================================================= -->
    <xsl:template match="/tei:TEI[tei:text/tei:body/tei:listPerson]">
        <TEI xmlns="http://www.tei-c.org/ns/1.0">
            <teiHeader>
                <fileDesc>
                    <titleStmt>
                        <title level="s">Arthur Schnitzler: Briefwechsel mit Autorinnen und Autoren</title>
                        <title level="a">Liste der Personen</title>
                        <respStmt>
                            <resp>providing the content</resp>
                            <name>Peter Michael Braunwarth</name>
                            <name>PMB – Personen der Moderne Basis</name>
                        </respStmt>
                        <respStmt>
                            <resp>converted to XML encoding</resp>
                            <name>Martin Anton Müller</name>
                        </respStmt>
                    </titleStmt>
                    <publicationStmt>
                        <publisher>ACDH-CH</publisher>
                        <date>2022-11-07</date>
                        <idno type="URI">https://id.acdh.oeaw.ac.at/arthur-schnitzler-briefe/v1/indices/listperson.xml</idno>
                    </publicationStmt>
                    <sourceDesc>
                        <p>Personenverzeichnis des Schnitzler-Tagebuchs.</p>
                    </sourceDesc>
                </fileDesc>
            </teiHeader>
            <text>
                <body>
                    <div type="index_persons">
                        <listPerson xml:id="listperson">
                            <xsl:for-each select="tei:text/tei:body/tei:listPerson/tei:person[tei:idno[@subtype='schnitzler-tagebuch'] and not(contains(tei:idno[@subtype='schnitzler-tagebuch'][1], '#'))]">
                                <xsl:sort select="tei:new-id(.)"/>
                                <xsl:apply-templates select="."/>
                            </xsl:for-each>
                        </listPerson>
                    </div>
                </body>
            </text>
        </TEI>
    </xsl:template>

    <!-- ============================================================= -->
    <!-- listplace.xml                                                   -->
    <!-- ============================================================= -->
    <xsl:template match="/tei:TEI[tei:text/tei:body/tei:listPlace]">
        <TEI xmlns="http://www.tei-c.org/ns/1.0">
            <teiHeader>
                <fileDesc>
                    <titleStmt>
                        <title>Index of places mentioned in the Digital Edition of Schnitzler’s Diaries</title>
                        <respStmt>
                            <resp>Data creation by</resp>
                            <persName>
                                <forename>Peter Michael</forename>
                                <surname>Braunwarth</surname>
                            </persName>
                        </respStmt>
                        <respStmt>
                            <resp>Data transformation to TEI by</resp>
                            <persName>
                                <forename>Peter</forename>
                                <surname>Andorfer</surname>
                            </persName>
                        </respStmt>
                        <respStmt>
                            <resp>Places georeferenced by</resp>
                            <persName>
                                <forename>Ulrike</forename>
                                <surname>Czeitschner</surname>
                            </persName>
                        </respStmt>
                    </titleStmt>
                    <publicationStmt>
                        <publisher>
                            <orgName>Austrian Centre for Digital Humanities, Austrian Academy of Sciences </orgName>
                            <address>
                                <addrLine>Sonnenfelsgasse 19</addrLine>
                                <addrLine>1010 Vienna</addrLine>
                            </address>
                        </publisher>
                        <pubPlace ref="http://d-nb.info/gnd/4066009-6">Vienna</pubPlace>
                        <date>2022-11-07+01:00</date>
                        <availability>
                            <licence target="https://creativecommons.org/licenses/by/4.0/">
                                <p>The Creative Commons Attribution 4.0 International (CC BY 4.0) License applies
                                    to this text.</p>
                                <p>The CC BY 4.0 License also applies to this TEI XML file.</p>
                            </licence>
                        </availability>
                        <idno type="URI">http://hdl.handle.net/21.11115/0000-000C-1CDF-B</idno>
                    </publicationStmt>
                    <sourceDesc>
                        <p>Born Digital</p>
                    </sourceDesc>
                </fileDesc>
                <revisionDesc>
                    <change>
                        <p>The entities were automatically georeferenced against <ref target="http://www.geonames.org/">geonames.org</ref> with the help of the <ref target="../process/enrich-places.xql">enrich-places.xql</ref> but without any
                            further manual processing</p>
                    </change>
                </revisionDesc>
            </teiHeader>
            <text>
                <body>
                    <listPlace>
                        <xsl:for-each select="tei:text/tei:body/tei:listPlace/tei:place[tei:idno[@subtype='schnitzler-tagebuch'] and not(contains(tei:idno[@subtype='schnitzler-tagebuch'][1], '#'))]">
                            <xsl:sort select="tei:new-id(.)"/>
                            <xsl:apply-templates select="."/>
                        </xsl:for-each>
                    </listPlace>
                </body>
            </text>
        </TEI>
    </xsl:template>

    <!-- ============================================================= -->
    <!-- listwork.xml (aus listbibl.xml gekürzt)                         -->
    <!-- ============================================================= -->
    <xsl:template match="/tei:TEI[tei:text/tei:body/tei:listBibl]">
        <TEI xmlns="http://www.tei-c.org/ns/1.0">
            <teiHeader>
                <fileDesc>
                    <titleStmt>
                        <title level="s">Arthur Schnitzler: Tagebuch</title>
                        <title level="a">Liste der Werke</title>
                        <respStmt>
                            <resp>providing the content</resp>
                            <name>PMB</name>
                        </respStmt>
                        <respStmt>
                            <resp>converted to XML encoding</resp>
                            <name>Peter Michael Braunwarth</name>
                            <name>Martin Anton Müller</name>
                            <name>Unknown members of ACDH</name>
                        </respStmt>
                    </titleStmt>
                    <publicationStmt>
                        <publisher>
                            <orgName full="yes">Austrian Centre for Digital Humanities,
                                Austrian Academy of Sciences</orgName>
                            <address>
                                <addrLine>Sonnenfelsgasse 19</addrLine>
                                <addrLine>1010 Vienna</addrLine>
                            </address>
                        </publisher>
                        <publisher>
                            <orgName full="yes">Verlag der Österreichischen Akademie der
                                Wissenschaften</orgName>
                        </publisher>
                        <pubPlace ref="http://d-nb.info/gnd/4066009-6">Vienna</pubPlace>
                        <date>2022-11-07+01:00</date>
                        <availability>
                            <licence target="https://creativecommons.org/licenses/by/4.0/">
                                <p part="N">The Creative Commons Attribution 4.0 International (CC BY 4.0)
                                    License applies to this text.</p>
                                <p part="N">The CC BY 4.0 License also applies to this TEI XML file.</p>
                            </licence>
                        </availability>
                        <idno type="URI">http://hdl.handle.net/21.11115/0000-000C-1CD9-1</idno>
                    </publicationStmt>
                    <sourceDesc>
                        <biblStruct>
                            <monogr>
                                <title level="m">Tagebuch 1931 / Gesamtverzeichnisse 1879-1931</title>
                                <idno type="ISBN">978-3-7001-2121-3</idno>
                                <author>
                                    <persName full="yes">
                                        <forename full="yes">Arthur</forename>
                                        <surname full="yes">Schnitzler</surname>
                                    </persName>
                                </author>
                                <editor>
                                    <persName full="yes">
                                        <forename full="yes">Werner</forename>
                                        <surname full="yes">Welzig</surname>
                                    </persName>
                                    <affiliation>Obmann der <orgName full="yes">Kommission für literarische Gebrauchsformen der
                                        Österreichischen Akademie der Wissenschaften</orgName>
                                    </affiliation>
                                </editor>
                                <respStmt>
                                    <resp>Unter Mitwirkung von</resp>
                                    <persName full="yes">
                                        <forename full="yes">Peter Michael</forename>
                                        <surname full="yes">Braunwarth</surname>
                                    </persName>
                                    <persName full="yes">
                                        <forename full="yes">Susanne</forename>
                                        <surname full="yes">Pertlik</surname>
                                    </persName>
                                    <persName full="yes">
                                        <forename full="yes">Reinhard</forename>
                                        <surname full="yes">Urbach</surname>
                                    </persName>
                                </respStmt>
                                <imprint>
                                    <publisher>
                                        <orgName full="yes">Verlag der Österreichischen
                                            Akademie der Wissenschaften</orgName>
                                        <orgName full="yes">Kommission für literarische
                                            Gebrauchsformen der Österreichischen Akademie der
                                            Wissenschaften</orgName>
                                    </publisher>
                                    <pubPlace>
                                        <placeName full="yes">Wien</placeName>
                                    </pubPlace>
                                    <date when="2000">2000</date>
                                </imprint>
                                <biblScope unit="volume">1931</biblScope>
                                <biblScope unit="page">109–137</biblScope>
                                <extent>
                                    <measure type="pages">637</measure>
                                </extent>
                            </monogr>
                            <series>
                                <title level="s">Tagebuch 1879-1931 - Gesamtausgabe</title>
                                <idno type="ISBN">978-3-7001-0395-0</idno>
                                <editor>
                                    <orgName full="yes">Verlag der Österreichischen Akademie
                                        der Wissenschaften</orgName>
                                    <orgName full="yes">Kommission für literarische
                                        Gebrauchsformen der Österreichischen Akademie der
                                        Wissenschaften</orgName>, Obmann: <persName full="yes">Werner Welzig</persName>. Unter Mitwirkung von <persName full="yes">Peter Michael Braunwarth</persName>,
                                    <persName full="yes">Susanne Pertlik</persName> und
                                    <persName full="yes">Reinhard Urbach</persName>
                                </editor>
                                <biblScope unit="volume">Band 1-10</biblScope>
                            </series>
                        </biblStruct>
                    </sourceDesc>
                </fileDesc>
            </teiHeader>
            <text>
                <body>
                    <p>
                        <listBibl xml:id="listwork">
                            <xsl:for-each select="tei:text/tei:body/tei:listBibl/tei:bibl[tei:idno[@subtype='schnitzler-tagebuch'] and not(contains(tei:idno[@subtype='schnitzler-tagebuch'][1], '#'))]">
                                <xsl:sort select="tei:new-id(.)"/>
                                <xsl:apply-templates select="."/>
                            </xsl:for-each>
                        </listBibl>
                    </p>
                </body>
            </text>
        </TEI>
    </xsl:template>

    <!-- xml:id der gebliebenen Top-Level-Einträge auf die neue Form umschreiben -->
    <xsl:template match="tei:person/@xml:id | tei:place/@xml:id | tei:bibl/@xml:id">
        <xsl:attribute name="xml:id" select="tei:new-id(..)"/>
    </xsl:template>
</xsl:stylesheet>
