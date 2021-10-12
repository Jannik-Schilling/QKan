<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis hasScaleBasedVisibilityFlag="0" maxScale="0" styleCategories="AllStyleCategories" version="3.20.1-Odense" minScale="0" readOnly="0">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
    <Private>0</Private>
  </flags>
  <temporal endField="" endExpression="" mode="0" startExpression="" durationUnit="min" enabled="0" fixedDuration="0" durationField="" accumulate="0" startField="">
    <fixedRange>
      <start></start>
      <end></end>
    </fixedRange>
  </temporal>
  <customproperties>
    <Option type="Map">
      <Option value="0" type="int" name="embeddedWidgets/count"/>
      <Option name="variableNames"/>
      <Option name="variableValues"/>
    </Option>
  </customproperties>
  <geometryOptions geometryPrecision="0" removeDuplicateNodes="0">
    <activeChecks/>
    <checkConfiguration/>
  </geometryOptions>
  <legend showLabelLegend="0" type="default-vector"/>
  <referencedLayers/>
  <fieldConfiguration>
    <field name="pk" configurationFlags="None">
      <editWidget type="TextEdit">
        <config>
          <Option type="Map">
            <Option value="0" type="QString" name="IsMultiline"/>
            <Option value="0" type="QString" name="UseHtml"/>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="abflusstyp" configurationFlags="None">
      <editWidget type="TextEdit">
        <config>
          <Option type="Map">
            <Option value="0" type="QString" name="IsMultiline"/>
            <Option value="0" type="QString" name="UseHtml"/>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="he_nr" configurationFlags="None">
      <editWidget type="TextEdit">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
    <field name="kp_nr" configurationFlags="None">
      <editWidget type="TextEdit">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
  </fieldConfiguration>
  <aliases>
    <alias index="0" field="pk" name=""/>
    <alias index="1" field="abflusstyp" name=""/>
    <alias index="2" field="he_nr" name=""/>
    <alias index="3" field="kp_nr" name=""/>
  </aliases>
  <defaults>
    <default applyOnUpdate="0" field="pk" expression=""/>
    <default applyOnUpdate="0" field="abflusstyp" expression=""/>
    <default applyOnUpdate="0" field="he_nr" expression=""/>
    <default applyOnUpdate="0" field="kp_nr" expression=""/>
  </defaults>
  <constraints>
    <constraint notnull_strength="1" unique_strength="1" exp_strength="0" field="pk" constraints="3"/>
    <constraint notnull_strength="0" unique_strength="0" exp_strength="0" field="abflusstyp" constraints="0"/>
    <constraint notnull_strength="0" unique_strength="0" exp_strength="0" field="he_nr" constraints="0"/>
    <constraint notnull_strength="0" unique_strength="0" exp_strength="0" field="kp_nr" constraints="0"/>
  </constraints>
  <constraintExpressions>
    <constraint exp="" desc="" field="pk"/>
    <constraint exp="" desc="" field="abflusstyp"/>
    <constraint exp="" desc="" field="he_nr"/>
    <constraint exp="" desc="" field="kp_nr"/>
  </constraintExpressions>
  <expressionfields/>
  <attributeactions>
    <defaultAction value="{00000000-0000-0000-0000-000000000000}" key="Canvas"/>
  </attributeactions>
  <attributetableconfig sortExpression="" sortOrder="0" actionWidgetStyle="dropDown">
    <columns>
      <column type="field" hidden="0" name="pk" width="-1"/>
      <column type="field" hidden="0" name="abflusstyp" width="-1"/>
      <column type="field" hidden="0" name="he_nr" width="-1"/>
      <column type="field" hidden="0" name="kp_nr" width="-1"/>
      <column type="actions" hidden="1" width="-1"/>
    </columns>
  </attributetableconfig>
  <conditionalstyles>
    <rowstyles/>
    <fieldstyles/>
  </conditionalstyles>
  <storedexpressions/>
  <editform tolerant="1">../../Users/hoettges/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/qkan/forms/forms</editform>
  <editforminit/>
  <editforminitcodesource>0</editforminitcodesource>
  <editforminitfilepath></editforminitfilepath>
  <editforminitcode><![CDATA[# -*- coding: utf-8 -*-
"""
QGIS forms can have a Python function that is called when the form is
opened.

Use this function to add extra logic to your forms.

Enter the name of the function in the "Python Init function"
field.
An example follows:
"""
from qgis.PyQt.QtWidgets import QWidget

def my_form_open(dialog, layer, feature):
	geom = feature.geometry()
	control = dialog.findChild(QWidget, "MyLineEdit")
]]></editforminitcode>
  <featformsuppress>0</featformsuppress>
  <editorlayout>uifilelayout</editorlayout>
  <editable>
    <field editable="1" name="abflusstyp"/>
    <field editable="1" name="he_nr"/>
    <field editable="1" name="kp_nr"/>
    <field editable="1" name="pk"/>
  </editable>
  <labelOnTop>
    <field labelOnTop="0" name="abflusstyp"/>
    <field labelOnTop="0" name="he_nr"/>
    <field labelOnTop="0" name="kp_nr"/>
    <field labelOnTop="0" name="pk"/>
  </labelOnTop>
  <reuseLastValue>
    <field name="abflusstyp" reuseLastValue="0"/>
    <field name="he_nr" reuseLastValue="0"/>
    <field name="kp_nr" reuseLastValue="0"/>
    <field name="pk" reuseLastValue="0"/>
  </reuseLastValue>
  <dataDefinedFieldProperties/>
  <widgets/>
  <previewExpression>"abflusstyp"</previewExpression>
  <mapTip></mapTip>
  <layerGeometryType>4</layerGeometryType>
</qgis>
