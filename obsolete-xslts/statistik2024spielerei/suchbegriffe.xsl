<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:tei="http://www.tei-c.org/ns/1.0"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    version="3.0">
    
    <xsl:output method="xml" indent="true"/>
    
    <!-- Liste der Suchwörter -->
    <xsl:variable name="search-words" as="xs:string*" select="('Kaffeehaus', 'Kfh', 'Cfh', 'Griensteidl', 'Grstdl', 'Pfob', 'Kremser', 'Arkaden', 'Arkd', 'Stukart', 'Scheidl', 'Pucher', 'Central', 'Auböck')" />
    
    <!-- Start des Transformationsprozesses -->
    <xsl:template match="/">
        <listEvent>
            <!-- Durchsuche alle TEI-Dokumente im aktuellen Ordner -->
            <xsl:for-each select="collection('../../editions/?select=*.xml;recurse=yes')//tei:TEI/tei:text[1]/tei:body[1]/tei:div[1]">
                <xsl:sort select="@xml:id"/>
                <xsl:variable name="tei-id" select="@xml:id" />
                <xsl:variable name="currentnode" select="." as="node()"/>
                <!-- Durchsuche den Inhalt des aktuellen TEI-Dokuments nach den Suchwörtern -->
                <xsl:for-each select="$search-words">
                    <xsl:variable name="word" select="." />
                    <!-- Kontextwechsel: Sicherstellen, dass das Suchwort im Text des Dokuments gefunden wird -->
                    <xsl:if test="$currentnode/descendant::text()[contains(., $word)][1]">
                        <xsl:variable name="dateString" select="substring-after($tei-id, 'entry__')" />
                        <xsl:variable name="date" select="xs:date($dateString)" />
                        <xsl:variable name="weekday" select="format-date($date, '[FNn]')" />
                        <event id="{$tei-id}" ana="{$weekday}">
                            <xsl:value-of select="$word" />
                        </event>
                    </xsl:if>
                </xsl:for-each>
            </xsl:for-each>
        </listEvent>
    </xsl:template>
</xsl:stylesheet>
