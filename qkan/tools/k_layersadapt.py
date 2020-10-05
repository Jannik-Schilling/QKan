# -*- coding: utf-8 -*-

"""

  Adapt QKan-Layers to QKan-Standard
  ==============

  Für ein bestehendes Projekt werden alle oder ausgewählte Layer auf den QKan-Standard
  (zurück-) gesetzt. Dabei können optional der Layerstil, die Werteanbindungen, die
  Formularverknüpfung sowie die Datenbankanbindung bearbeitet werden.

  | Dateiname            : k_layersadapt.py
  | Date                 : September 2018
  | Copyright            : (C) 2018 by Joerg Hoettges
  | Email                : hoettges@fh-aachen.de
  | git sha              : $Format:%H$

  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.

"""
import logging
import os
from xml.etree import ElementTree

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsDataSourceUri,
    QgsEditorWidgetSetup,
    QgsProject,
    QgsVectorLayer,
    QgsField,
)
from qgis.utils import iface, pluginDirectory

from PyQt5.QtCore import QVariant

from qkan import enums
from qkan.database.dbfunc import DBConnection
from qkan.database.qkan_database import qgsActualVersion, qgsVersion
from qkan.database.qkan_utils import (
    evalNodeTypes,
    fehlermeldung,
    get_qkanlayerAttributes,
    getLayerConfigFromQgsTemplate,
    listQkanLayers,
    meldung,
    warnung,
)

__author__ = "Joerg Hoettges"
__date__ = "September 2018"
__copyright__ = "(C) 2018, Joerg Hoettges"


logger = logging.getLogger("QKan.tools.k_layersadapt")

progress_bar = None


def layersadapt(
    database_QKan,
    projectTemplate,
    anpassen_ProjektMakros,
    anpassen_Datenbankanbindung,
    anpassen_Wertebeziehungen_in_Tabellen,
    anpassen_Formulare,
    anpassen_Projektionssystem,
    aktualisieren_Schachttypen,
    zoom_alles,
    fehlende_layer_ergaenzen,
    anpassen_auswahl: enums.SelectedLayers,
):
    """Anpassen von Projektlayern an den QKan-Standard
    Voraussetzungen: keine

    :database_QKan:                                 Ziel-Datenbank, auf die die Projektdatei angepasst werden soll
    :type database_QKan:                            String

    :projectTemplate:                               Vorlage-Projektdatei für die anzupassenden Layereigenschaften
    :type projectTemplate:                          String

    :anpassen_ProjektMakros:                        Projektmakros werden angepasst
    :type anpassen_ProjektMakros:                   Boolean

    :anpassen_Datenbankanbindung:                   Datenbankanbindungen werden angepasst
    :type anpassen_Datenbankanbindung:              Boolean

    :anpassen_Wertebeziehungen_in_Tabellen:         Wertebeziehungen werden angepasst
    :type anpassen_Wertebeziehungen_in_Tabellen:    Boolean

    :anpassen_Formulare:                            Formulare werden anpasst
    :type anpassen_Formulare:                       Boolean

    :anpassen_Projektionssystem:                    Projektionssystem wird angepasst
    :type anpassen_Projektionssystem:               Boolean

    :aktualisieren_Schachttypen:                    Knotentypen in schaechte.knotentyp setzen
    :type aktualisieren_Schachttypen                Boolean

    :zoom_alles:                                    Nach der Bearbeitung die Karte auf gesamte Gebiet zoomen
    :type zoom_alles:                               Boolean

    :fehlende_layer_ergaenzen:                      Fehlende QKan-Layer werden ergänzt
    :type fehlende_layer_ergaenzen:                 Boolean

    :anpassen_auswahl:                              Wahl der anzupassenden Layer
    :type anpassen_auswahl:                         enums.SelectedLayers

    :returns: void
    """

    # -----------------------------------------------------------------------------------------------------
    # Datenbankverbindungen

    dbQK = DBConnection(
        dbname=database_QKan
    )  # Datenbankobjekt der QKan-Datenbank

    if not dbQK.connected:
        fehlermeldung('Programmfehler in QKan.tools.k_layersadapt.layersadapt()',
                      'Datenbank konnte nicht verbunden werden'
        )
        return False

    actversion = dbQK.actversion
    logger.debug("actversion: {}".format(actversion))

    if not(anpassen_Formulare or
           anpassen_Projektionssystem or
           anpassen_Wertebeziehungen_in_Tabellen or
           aktualisieren_Schachttypen or
           fehlende_layer_ergaenzen
    ):
        del dbQK
        return True

    # -----------------------------------------------------------------------------------------------------
    # QKan-Projekt
    project = QgsProject.instance()

    if project.count() == 0:
        fehlermeldung("Benutzerfehler: ", "Es ist kein Projekt geladen.")
        del dbQK
        return

    # Projekt auf aktuelle Version setzen. Es werden keine Layer geändert.
    qgsActualVersion()

    # Vorlage-Projektdatei. Falls Standard oder keine Vorgabe, wird die Standard-Projektdatei verwendet

    templateDir = os.path.join(pluginDirectory("qkan"), "templates")
    if projectTemplate is None or projectTemplate == "":
        projectTemplate = os.path.join(templateDir, "Projekt.qgs")

    logger.debug("Projekttemplate: {}".format(projectTemplate))

    # Liste aller QKan-Layernamen aus gewählter QGS-Vorlage.
    # Dabei wird trotzdem geprüft, ob es sich um einen QKan-Layer handelt; es könnte sich ja um eine
    # vom Benutzer angepasste Vorlage handeln.

    qkanLayers = listQkanLayers(
        projectTemplate
    )  # Liste aller Layernamen aus gewählter QGS-Vorlage
    # logger.debug(u'qkanLayers: {}'.format(qkanLayers))

    # Fehlende Layer ergänzen. Unabhängig von der Auswahl werden die fehlenden Referenztabellen
    # auf jeden Fall ergänzt.

    layersRoot = project.layerTreeRoot()
    for layername in qkanLayers:
        if len(project.mapLayersByName(layername)) == 0:
            # layername fehlt in aktuellem Projekt
            isVector = (
                qkanLayers[layername][1] != ""
            )  # Test, ob Vorlage-Layer spatial ist
            if not isVector or fehlende_layer_ergaenzen:
                # Referenzlisten werden auf jeden Fall ergänzt.
                table, geom_column, sql, group = qkanLayers[layername]
                uri = QgsDataSourceUri()
                uri.setDatabase(database_QKan)
                uri.setDataSource(sql, table, geom_column)
                try:
                    layer = QgsVectorLayer(uri.uri(), layername, enums.QKanDBChoice.SPATIALITE.value)
                except BaseException as err:
                    fehlermeldung(
                        "Fehler in k_layersadapt (1): {}".format(err),
                        "layername: {}".format(layername),
                    )
                    del dbQK
                    return False
                project.addMapLayer(layer, False)
                atcGroup = layersRoot.findGroup(group)
                if atcGroup is None:
                    atcGroup = layersRoot.addGroup(group)
                atcGroup.addLayer(layer)

                # Stildatei laden, falls vorhanden
                qlsnam = os.path.join(templateDir, "Layer_{}.qml".format(layername))
                if os.path.exists(qlsnam):
                    layer.loadNamedStyle(qlsnam)
                    logger.debug("Layerstil geladen: {}".format(qlsnam))
                # layerList[layer.name()] = layer           --> in QGIS3 nicht nötig
                logger.debug("k_layersadapt: Layer ergänzt: {}".format(layername))
            else:
                logger.debug("k_layersadapt: Layer nicht ergänzt: {}".format(layername))
        # else:
        # logger.debug("k_layersadapt: Layer schon vorhanden: {}".format(layername))

    # Dictionary, das alle LayerIDs aus der Template-Projektdatei den entsprechenden (QKan-) LayerIDs
    # des aktuell geladenen Projekts zuordnet. Diese Liste wird bei der Korrektur der Wertelisten
    # benötigt.

    qgsxml = ElementTree.ElementTree()
    qgsxml.parse(projectTemplate)

    layerNotInProjektMeldung = False
    rltext = "projectlayers/maplayer"
    nodes_refLayerTemplate = qgsxml.findall(rltext)
    layerIdList = {}
    for node in nodes_refLayerTemplate:
        refLayerName = node.findtext("layername")
        refLayerId = node.findtext("id")
        layerobjects = project.mapLayersByName(refLayerName)
        if len(layerobjects) > 0:
            layer = layerobjects[0]  # Der Layername muss eindeutig sein.
            layerId = layer.id()
            logger.debug("layerId: {}".format(layerId))
            layerIdList[refLayerId] = layerId
            if len(layerobjects) > 1:
                warnung(
                    "Layername doppelt: {}",
                    "Es wird nur ein Layer bearbeitet.".format(refLayerName),
                )
        else:
            layerNotInProjektMeldung = (
                not fehlende_layer_ergaenzen
            )  # nur setzen, wenn keine Ergänzung gewählt
            logger.info(
                "k_layersadapt: QKan-Layer nicht in Projekt: {}".format(refLayerName)
            )
    logger.debug("Refliste Layer-Ids: \n{}".format(layerIdList))

    # Liste der zu bearbeitenden Layer
    if anpassen_auswahl == enums.SelectedLayers.SELECTED:
        # Im Formular wurde "nur ausgewählte Layer" angeklickt

        selectedLayers = iface.layerTreeCanvasBridge().rootGroup().checkedLayers()
        selectedLayerNames = [lay.name() for lay in selectedLayers]
    elif anpassen_auswahl == enums.SelectedLayers.ALL:
        legendLayers = iface.layerTreeCanvasBridge().rootGroup().findLayers()
        selectedLayerNames = [lay.name() for lay in legendLayers]
    elif anpassen_auswahl == enums.SelectedLayers.NONE:
        selectedLayerNames = []
    else:
        logger.error(f'Fehler in anpassen_auswahl: {anpassen_auswahl}\nWert ist nicht definiert (enums.py)')

    logger.debug("k_layersadapt (2), selectedLayerNames: {}".format(selectedLayerNames))

    layerNotQkanMeldung = (
        False
    )  # Am Schluss erscheint ggfs. eine Meldung, dass Nicht-QKan-Layer gefunden wurden.

    # Alle (ausgewählten) Layer werden jetzt anhand der entsprechenden Layer des Template-Projektes angepasst

    formsDir = os.path.join(pluginDirectory("qkan"), "forms")

    for layername in selectedLayerNames:
        # Nur Layer behandeln, die in der Vorlage-Projektdatei enthalten sind, d.h. QKan-Layer sind.
        if layername not in qkanLayers:
            continue

        layerobjects = project.mapLayersByName(layername)
        if len(layerobjects) == 0:
            logger.error(
                f"QKan-Fehler: Projektlayer {layername} konnte im Projekt nicht gefunden werden"
            )
            return False
        else:
            layer = layerobjects[0]

        tagLayer = "projectlayers/maplayer[layername='{}'][provider='spatialite']".format(
            layername
        )
        qgsLayers = qgsxml.findall(tagLayer)
        if len(qgsLayers) > 1:
            fehlermeldung(
                "DateifFehler!",
                "In der Vorlage-Projektdatei wurden mehrere Layer {} gefunden".format(
                    layername
                ),
            )
            del dbQK
            return False
        elif len(qgsLayers) == 0:
            layerNotQkanMeldung = True
            logger.info(
                "In der Vorlage-Projektdatei wurden kein Layer {} gefunden".format(
                    layername
                )
            )
            continue  # Layer ist in Projekt-Templatenicht vorhanden...

        if anpassen_ProjektMakros:
            nodes = qgsxml.findall('properties/Macros')
            for node in nodes:
                macros = node.findtext("pythonCode")
            project.writeEntry("Macros", "/pythonCode", macros)

        if anpassen_Datenbankanbindung:
            datasource = layer.source()
            dbname, table, geom, sql = get_qkanlayerAttributes(datasource)
            # logger.debug(f"datasource: {datasource}")
            # logger.debug(f"\nDatenbankanbindung\n  dbname: {dbname}\n  table: {table}\n  geom: {geom}\n  sql: {sql}")
            if geom != "":
                # Vektorlayer
                newdatasource = "dbname='{dbname}' table=\"{table}\" ({geom}) sql={sql}".format(
                    dbname=database_QKan, table=table, geom=geom, sql=sql
                )
            else:
                # Tabellenlayer
                newdatasource = "dbname='{dbname}' table=\"{table}\" sql={sql}".format(
                    dbname=database_QKan, table=table, geom=geom, sql=sql
                )
            layer.setDataSource(newdatasource, layername, enums.QKanDBChoice.SPATIALITE.value)
            logger.debug("\nAnbindung neue QKanDB: {}\n".format(newdatasource))

        if anpassen_Projektionssystem:
            # epsg-Code des Layers an angebundene Tabelle anpassen
            logger.debug("anpassen_Projektionssystem...")
            datasource = layer.source()
            dbname, table, geom, sql = get_qkanlayerAttributes(datasource)
            # logger.debug(f"datasource: {datasource}")
            # logger.debug(f"\nDatenbankanbindung\n  dbname: {dbname}\n  table: {table}\n  geom: {geom}\n  sql: {sql}")
            logger.debug("Prüfe KBS von Tabelle {}".format(table))
            if geom != "":
                # Nur für Vektorlayer
                sql = """SELECT srid
                        FROM geom_cols_ref_sys
                        WHERE Lower(f_table_name) = Lower('{table}')
                        AND Lower(f_geometry_column) = Lower('{geom}')""".format(
                    table=table, geom=geom
                )
                if not dbQK.sql(sql, "dbQK: k_layersadapt (3)"):
                    del dbQK
                    return False

                data = dbQK.fetchone()
                if data is not None:
                    epsg = data[0]
                else:
                    logger.debug("\nTabelle hat kein KBS: {}\n".format(datasource))

                crs = QgsCoordinateReferenceSystem(
                    epsg, QgsCoordinateReferenceSystem.EpsgCrsId
                )
                if crs.isValid():
                    layer.setCrs(crs)
                    logger.debug(
                        'KBS angepasst für Tabelle "{0:} auf {1:}"'.format(
                            table, crs.postgisSrid()
                        )
                    )
                else:
                    fehlermeldung(
                        "Fehler bei Festlegung des Koordinatensystems!",
                        "Layer {}".format(layername),
                    )

        if anpassen_Formulare:
            formpath = qgsLayers[0].findtext("./editform")
            form = os.path.basename(formpath)
            editFormConfig = layer.editFormConfig()
            editFormConfig.setUiForm(os.path.join(formsDir, form))
            layer.setEditFormConfig(editFormConfig)

        if anpassen_Wertebeziehungen_in_Tabellen:
            dictOfEditWidgets, displayExpression = getLayerConfigFromQgsTemplate(
                qgsxml, layername
            )

            # Anpassen der Wertebeziehungen
            # iterating over all fieldnames in template project
            for idx, field in enumerate(layer.fields()):
                fieldname = field.name()
                if fieldname in dictOfEditWidgets:
                    type, options = dictOfEditWidgets[fieldname]
                    if "Layer" in options:
                        # LayerId aus Template-Projektdatei muss durch den
                        # entsprechenden LayerId der Projektdatei ersetzt werden.
                        try:
                            templateLayerName = options["Layer"]
                            projectLayerName = layerIdList[templateLayerName]
                        except BaseException as err:
                            fehlermeldung(
                                f"Fehler in k_layersadapt (4) in layer {layername}: {err}",
                                "Möglicherweise ist der Template-Projektdatei fehlerhaft",
                            )
                            del dbQK
                            return False
                        options["Layer"] = projectLayerName
                    ews = QgsEditorWidgetSetup(type, options)
                    layer.setEditorWidgetSetup(idx, ews)

            # Anpassen des Anzeige-Ausdrucks, nur wenn nicht schon anderweitig sinnvoll gesetzt. 
            logger.debug(f'DisplayExpression zu Layer {layer.name()}: {layer.displayExpression()}\n')
            if layer.displayExpression() in ('pk', '"pk"', '', """COALESCE("pk", '<NULL>')"""):
                logger.debug(f'DisplayExpression zu Layer {layer.name()} gesetzt: {displayExpression}\n')
                layer.setDisplayExpression(displayExpression)

    # Koordinaten in einer eigenen Spalte, nur für Layer Schächte, Auslässe, Speicher
    for layername in ['Schächte', 'Auslässe', 'Speicher']:
        # Expressions aus Projektvorlage (xml) lesen
        tagLayer = f"projectlayers/maplayer[layername='{layername}']/expressionfields/field"
        qgsLayers = qgsxml.findall(tagLayer)
        exprList = {}                           # zur Vermeidung von Doppelungen
        for lay in qgsLayers:
            expression = lay.attrib['expression']
            name = lay.attrib['name']
            typeName = lay.attrib['typeName']
            comment = lay.attrib['comment']
            exprList[name] = [expression, typeName, comment]

        # Expressions in Attributtabelle einfügen
        project = QgsProject.instance()
        layer = project.mapLayersByName(layername)[0]
        for name in exprList.keys():
            expression, typeName, comment = exprList[name]
            if typeName == 'double precision':
                layer.addExpressionField(expression, QgsField(name=name, type=QVariant.Double, comment=comment))
            elif typeName == 'integer':
                layer.addExpressionField(expression, QgsField(name=name, type=QVariant.Integer, comment=comment))
            else:
                Fehlermeldung('Programmfehler', f'Datentyp noch nicht programmiert: {typeName}')
                return False

    if layerNotInProjektMeldung:
        meldung(
            "Information zu den Layern",
            "Es fehlten Layer, die zum QKan-Standard gehörten. Eine Liste steht in der LOG-Datei...",
        )
    # if layerNotQkanMeldung:
    # meldung(u'Information zu den Layern', u'Es wurden Layer gefunden, die nicht zum QKan-Standard gehörten. Eine Liste steht in der LOG-Datei...')

    # Projektmakros
    rltext = 'properties/Macros/pythonCode'
    macrotext = qgsxml.findtext(rltext)
    project.writeEntry("Macros", "/pythonCode", macrotext)

    if aktualisieren_Schachttypen:
        # Schachttypen auswerten
        evalNodeTypes(dbQK)  # in qkan.database.qkan_utils

    project.setTitle("QKan Version {}".format(qgsVersion()))

    # if status_neustart:
    # meldung("Achtung! Benutzerhinweis!", "Die Datenbank wurde geändert. Bitte QGIS-Projekt neu laden...")
    # return False

    # Zoom auf alles
    if zoom_alles:
        # Tabellenstatistik aktualisieren, damit Zoom alles richtig funktioniert ...
        sql = 'SELECT UpdateLayerStatistics()'
        if not dbQK.sql(sql, "dbQK: k_layersadapt (5)"):
            del dbQK
            return False

        canvas = iface.mapCanvas()
        canvas.zoomToFullExtent()

    del qgsxml
    del dbQK

    # Todo:
    #  - Sicherungskopie der Datenbank, falls Versionsupdate

    # ------------------------------------------------------------------------------
    # Abschluss: Ggfs. Protokoll schreiben und Datenbankverbindungen schliessen

    iface.mainWindow().statusBar().clearMessage()
    iface.messageBar().pushMessage(
        "Information",
        "Projektdatei ist angepasst und muss noch gespeichert werden!",
        level=Qgis.Info,
    )

    return True

#def dbAdapt(database_QKan):