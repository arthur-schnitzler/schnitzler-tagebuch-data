<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns="http://www.tei-c.org/ns/1.0"
    xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:fn="http://www.w3.org/2005/xpath-functions" version="3.0">
    <xsl:mode on-no-match="shallow-copy"/>
    <xsl:output method="xml" indent="yes"/>
    
    <xsl:param name="neue-werte">
        <root>
            <row>
                <falsch>92136</falsch>
                <name>Albulapass</name>
                <neu>90063</neu>
            </row>
            <row>
                <falsch>90235</falsch>
                <name>Altmoabit</name>
                <neu>52918</neu>
            </row>
            <row>
                <falsch>90392</falsch>
                <name>Breslau</name>
                <neu>677</neu>
            </row>
            <row>
                <falsch>40202</falsch>
                <name>Brunn</name>
                <neu>40201</neu>
            </row>
            <row>
                <falsch>90476</falsch>
                <name>Christiania</name>
                <neu>36296</neu>
            </row>
            <row>
                <falsch>92219</falsch>
                <name>Dreikirchen</name>
                <neu>90151</neu>
            </row>
            <row>
                <falsch>90556</falsch>
                <name>Durazzo</name>
                <neu>65558</neu>
            </row>
            <row>
                <falsch>92234</falsch>
                <name>Fedaja</name>
                <neu>90084</neu>
            </row>
            <row>
                <falsch>90717</falsch>
                <name>Gibraltar</name>
                <neu>51646</neu>
            </row>
            <row>
                <falsch>90759</falsch>
                <name>Graz</name>
                <neu>860</neu>
            </row>
            <row>
                <falsch>92262</falsch>
                <name>Gumpendorferstraße</name>
                <neu>45602</neu>
            </row>
            <row>
                <falsch>92270</falsch>
                <name>Hammerand</name>
                <neu>585</neu>
            </row>
            <row>
                <falsch>90909</falsch>
                <name>Hottingen</name>
                <neu>17142</neu>
            </row>
            <row>
                <falsch>90931</falsch>
                <name>Innsbruck</name>
                <neu>867</neu>
            </row>
            <row>
                <falsch>90954</falsch>
                <name>Jena</name>
                <neu>876</neu>
            </row>
            <row>
                <falsch>90989</falsch>
                <name>Kammer</name>
                <neu>63056</neu>
            </row>
            <row>
                <falsch>92327</falsch>
                <name>Kammersee</name>
                <neu>90072</neu>
            </row>
            <row>
                <falsch>91050</falsch>
                <name>Köln</name>
                <neu>145</neu>
            </row>
            <row>
                <falsch>92347</falsch>
                <name>Kremser</name>
                <neu>46</neu>
            </row>
            <row>
                <falsch>92357</falsch>
                <name>Landstraße</name>
                <neu>50530</neu>
            </row>
            <row>
                <falsch>91211</falsch>
                <name>Marienbad</name>
                <neu>772</neu>
            </row>
            <row>
                <falsch>91247</falsch>
                <name>Millstättersee</name>
                <neu>39637</neu>
            </row>
            <row>
                <falsch>91259</falsch>
                <name>Moabit</name>
                <neu>36809</neu>
            </row>
            <row>
                <falsch>92416</falsch>
                <name>Naifthal</name>
                <neu>90162</neu>
            </row>
            <row>
                <falsch>91336</falsch>
                <name>Neuchâtel</name>
                <neu>34057</neu>
            </row>
            <row>
                <falsch>92727</falsch>
                <name>Hollabrunn</name>
                <neu>36639</neu>
            </row>
            <row>
                <falsch>92426</falsch>
                <name>Odde</name>
                <neu>90138</neu>
            </row>
            <row>
                <falsch>91478</falsch>
                <name>Pieve di Cadore</name>
                <neu>34112</neu>
            </row>
            <row>
                <falsch>91602</falsch>
                <name>Riva</name>
                <neu>465</neu>
            </row>
            <row>
                <falsch>91649</falsch>
                <name>Salzburg</name>
                <neu>30</neu>
            </row>
            <row>
                <falsch>91651</falsch>
                <name>Salzkammergut</name>
                <neu>429</neu>
            </row>
            <row>
                <falsch>91691</falsch>
                <name>Schneeberg</name>
                <neu>5836</neu>
            </row>
            <row>
                <falsch>91717</falsch>
                <name>Seeboden</name>
                <neu>34824</neu>
            </row>
            <row>
                <falsch>91836</falsch>
                <name>Steindorf</name>
                <neu>34860</neu>
            </row>
            <row>
                <falsch>91881</falsch>
                <name>Teneriffa</name>
                <neu>16330</neu>
            </row>
            <row>
                <falsch>91907</falsch>
                <name>Toblach</name>
                <neu>987</neu>
            </row>
            <row>
                <falsch>92578</falsch>
                <name>Val Ampola</name>
                <neu>90152</neu>
            </row>
            <row>
                <falsch>92001</falsch>
                <name>Velden</name>
                <neu>909</neu>
            </row>
            <row>
                <falsch>92063</falsch>
                <name>Weimar</name>
                <neu>197</neu>
            </row>
            <row>
                <falsch>92065</falsch>
                <name>Weissenbach</name>
                <neu>34344</neu>
            </row>
            <row>
                <falsch>92127</falsch>
                <name>Zirndorf</name>
                <neu>40867</neu>
            </row>
        </root>
    </xsl:param>
    
    <xsl:key name="nachschlagen" match="tei:row" use="tei:falsch"/>
    
    
    <!--<xsl:template match="tei:place[tei:error]/@xml:id">
        <xsl:attribute name="xml:id">
            <xsl:choose>
                <xsl:when test="key('nachschlagen', replace(., 'pmb', ''), $neue-werte)">
                    <xsl:value-of select="concat('pmb', key('nachschlagen', replace(., 'pmb', ''), $neue-werte)/tei:neu)"/>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:value-of select="@xml:id"/><xsl:text>falsch</xsl:text>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:attribute>
    </xsl:template>-->
    
    <xsl:template match="tei:rs[@type='place']/@ref">
        <xsl:attribute name="ref">
            <xsl:choose>
                <xsl:when test="key('nachschlagen', replace(., '#pmb', ''), $neue-werte)">
                    <xsl:value-of select="concat('pmb', key('nachschlagen', replace(., '#pmb', ''), $neue-werte)/tei:neu)"/>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:value-of select="."/>
                </xsl:otherwise>
            </xsl:choose>
            
        </xsl:attribute>
        
    </xsl:template>
    
    <xsl:template match="placeName/@ref">
        <xsl:attribute name="ref">
            <xsl:choose>
                <xsl:when test="key('nachschlagen', replace(., 'pmb', ''), $neue-werte)">
                    <xsl:value-of select="concat('pmb', key('nachschlagen', replace(., 'pmb', ''), $neue-werte)/tei:neu)"/>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:value-of select="."/><xsl:text>falsch</xsl:text>
                </xsl:otherwise>
            </xsl:choose>
            
        </xsl:attribute>
        
    </xsl:template>


</xsl:stylesheet>