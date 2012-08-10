<!-- -*- Mode: nXML; tab-width: 2; indent-tabs-mode: nil; -*- -->
<!-- vim: set tabstop=2 expandtab shiftwidth=2 textwidth=80:  -->
<!--
    Copyright 2012 Design Science, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  
  <xsl:strip-space elements="*"/>

  <xsl:template match="*">
    <xsl:apply-templates select="*"/>
  </xsl:template>

  <xsl:template match="body">
    <xsl:comment>This file is automatically generated. Do not edit</xsl:comment>
    <root><xsl:apply-templates select="*"/></root>
  </xsl:template>

  <xsl:template match="div[@class='formatted-content']/div">
    <xsl:for-each select="*">
      <xsl:choose>
        <!-- XXXfred: The XSLT language/implementation does not seem really
             powerful... Do more filters on the Python side. -->
        <xsl:when test="contains(., '.html')">
          <paragraph>
            <xsl:value-of select="."/>
          </paragraph>
        </xsl:when>
        <xsl:otherwise>
          <xsl:apply-templates select="*"/>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:for-each>
  </xsl:template>

</xsl:stylesheet>