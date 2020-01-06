# -*- coding: utf-8 -*-

"""

  QGIS-Plugin
  ===========

  Definition der Formularklasse

  | Dateiname            : application.py
  | Date                 : Februar 2017
  | Copyright            : (C) 2016 by Joerg Hoettges
  | Email                : hoettges@fh-aachen.de
  | git sha              : $Format:%H$

  This program is free software; you can redistribute it and/or modify  
  it under the terms of the GNU General Public License as published by  
  the Free Software Foundation; either version 2 of the License, or     
  (at your option) any later version.                                  

"""
import json
import logging
import os.path
import site

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QFileDialog, QListWidgetItem
from qgis.core import QgsProject
from qgis.utils import iface, pluginDirectory

from qkan import QKan
from qkan.database.dbfunc import DBConnection
from qkan.database.qkan_utils import fehlermeldung, get_database_QKan, get_editable_layers
# noinspection PyUnresolvedReferences
from . import resources
# Initialize Qt resources from file resources.py
# Import the code for the dialog
from .application_dialog import ExportToKPDialog
from .k_qkkp import exportKanaldaten

# Anbindung an Logging-System (Initialisierung in __init__)
logger = logging.getLogger('QKan.exportdyna.application')

progress_bar = None


class ExportToKP:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """

        self.templatepath = os.path.join(pluginDirectory('qkan'), u"templates")

        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # Create the dialog (after translation) and keep reference
        self.dlg = ExportToKPDialog()

        # Anfang Eigene Funktionen -------------------------------------------------
        # (jh, 08.02.2017)

        logger.info('QKan_ExportKP initialisiert...')

        # Standard für Suchverzeichnis festlegen
        project = QgsProject.instance()
        self.default_dir = os.path.dirname(project.fileName())

        # Formularereignisse anbinden ----------------------------------------------

        self.dlg.pb_select_KP_dest.clicked.connect(self.selectFile_kpDB_dest)
        self.dlg.pb_select_KP_template.clicked.connect(self.selectFile_kpDB_template)
        self.dlg.lw_teilgebiete.itemClicked.connect(self.lw_teilgebieteClick)
        self.dlg.cb_selActive.stateChanged.connect(self.selActiveClick)
        self.dlg.button_box.helpRequested.connect(self.helpClick)
        self.dlg.pb_selectQKanDB.clicked.connect(self.selectFile_QKanDB)

        # Ende Eigene Funktionen ---------------------------------------------------

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('ExportToKP', message)

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/qkan/exportdyna/res/icon_qk2kp.png'
        QKan.instance.add_action(icon_path,
                                  text=self.tr('Export in DYNA-Datei...'),
                                  callback=self.run,
                                  parent=self.iface.mainWindow())

    def unload(self):
        pass

    # Anfang Eigene Funktionen -------------------------------------------------
    # (jh, 08.02.2017)

    def selectFile_kpDB_dest(self):
        """Zu erstellende DYNA-Datei eingeben"""

        filename, __ = QFileDialog.getSaveFileName(self.dlg, "Dateinamen der zu schreibenden DYNA-Datei eingeben",
                                                   self.default_dir, "*.ein")
        # if os.path.dirname(filename) != '':
        # os.chdir(os.path.dirname(filename))
        self.dlg.tf_KP_dest.setText(filename)

    def selectFile_kpDB_template(self):
        """Vorlage-DYNA-Datei auswaehlen."""

        filename, __ = QFileDialog.getOpenFileName(self.dlg, u"Vorlage-DYNA-Datei auswählen",
                                                   self.default_dir, "*.ein")
        # if os.path.dirname(filename) != '':
        # os.chdir(os.path.dirname(filename))
        self.dlg.tf_KP_template.setText(filename)

    def selectFile_QKanDB(self):
        """Datenbankverbindung zur QKan-Datenbank (SpatiLite) auswaehlen."""

        filename, __ = QFileDialog.getOpenFileName(self.dlg, u"QKan-Datenbank auswählen",
                                                   self.default_dir, "*.sqlite")
        # if os.path.dirname(filename) != '':
        # os.chdir(os.path.dirname(filename))
        self.dlg.tf_QKanDB.setText(filename)

    # -------------------------------------------------------------------------
    # Formularfunktionen

    def helpClick(self):
        """Reaktion auf Klick auf Help-Schaltfläche"""
        helpfile = os.path.join(self.plugin_dir, '..\doc', 'exportdyna.html')
        os.startfile(helpfile)

    def lw_teilgebieteClick(self):
        """Reaktion auf Klick in Tabelle"""

        self.dlg.cb_selActive.setChecked(True)
        self.countselection()

    def selActiveClick(self):
        """Reagiert auf Checkbox zur Aktivierung der Auswahl"""

        # Checkbox hat den Status nach dem Klick
        if self.dlg.cb_selActive.isChecked():
            # Nix tun ...
            logger.debug('\nChecked = True')
        else:
            # Auswahl deaktivieren und Liste zurücksetzen
            anz = self.dlg.lw_teilgebiete.count()
            for i in range(anz):
                item = self.dlg.lw_teilgebiete.item(i)
                item.setSelected(False)
                # self.dlg.lw_teilgebiete.setItemSelected(item, False)

            # Anzahl in der Anzeige aktualisieren
            self.countselection()

    def countselection(self):
        """Zählt nach Änderung der Auswahlen in den Listen im Formular die Anzahl
        der betroffenen Flächen und Haltungen"""
        logger.debug(u'arg: {}'.format(self.dlg.lw_teilgebiete))
        liste_teilgebiete = self.listselecteditems(self.dlg.lw_teilgebiete)

        # Zu berücksichtigende Flächen zählen
        auswahl = ''
        if len(liste_teilgebiete) != 0:
            auswahl = u" WHERE flaechen.teilgebiet in ('{}')".format("', '".join(liste_teilgebiete))

        sql = u"""SELECT count(*) AS anzahl FROM flaechen{auswahl}""".format(auswahl=auswahl)

        if not self.dbQK.sql(sql, u"QKan_ExportDYNA.application.countselection (1)"):
            return False
        daten = self.dbQK.fetchone()
        if not (daten is None):
            self.dlg.lf_anzahl_flaechen.setText(str(daten[0]))
        else:
            self.dlg.lf_anzahl_flaechen.setText('0')

        # Zu berücksichtigende Schächte zählen
        auswahl = ''
        if len(liste_teilgebiete) != 0:
            auswahl = u" WHERE schaechte.teilgebiet in ('{}')".format("', '".join(liste_teilgebiete))

        sql = u"""SELECT count(*) AS anzahl FROM schaechte{auswahl}""".format(auswahl=auswahl)
        if not self.dbQK.sql(sql, u"QKan_ExportDYNA.application.countselection (2) "):
            return False
        daten = self.dbQK.fetchone()
        if not (daten is None):
            self.dlg.lf_anzahl_schaechte.setText(str(daten[0]))
        else:
            self.dlg.lf_anzahl_schaechte.setText('0')

        # Zu berücksichtigende Haltungen zählen
        auswahl = ''
        if len(liste_teilgebiete) != 0:
            auswahl = u" WHERE haltungen.teilgebiet in ('{}')".format("', '".join(liste_teilgebiete))

        sql = u"""SELECT count(*) AS anzahl FROM haltungen{auswahl}""".format(auswahl=auswahl)
        if not self.dbQK.sql(sql, u"QKan_ExportDYNA.application.countselection (3) "):
            return False
        daten = self.dbQK.fetchone()
        if not (daten is None):
            self.dlg.lf_anzahl_haltungen.setText(str(daten[0]))
        else:
            self.dlg.lf_anzahl_haltungen.setText('0')

    # @staticmethod
    def listselecteditems(self, listWidget):
        """Erstellt eine Liste aus den in einem Auswahllisten-Widget angeklickten Objektnamen

        :param listWidget: String for translation.
        :type listWidget: QListWidgetItem

        :returns: Tuple containing selected teilgebiete
        :rtype: tuple
        """
        items = listWidget.selectedItems()
        liste = []
        for elem in items:
            liste.append(elem.text())
        return liste

    # Ende Eigene Funktionen ---------------------------------------------------

    def run(self):
        """Run method that performs all the real work"""
        # show the dialog

        # Check, ob die relevanten Layer nicht editable sind.
        if len({'flaechen', 'haltungen', 'linkfl', 'tezg', 'schaechte'} & get_editable_layers()) > 0:
            iface.messageBar().pushMessage(u"Bedienerfehler: ",
                                           u'Die zu verarbeitenden Layer dürfen nicht im Status "bearbeitbar" sein. Abbruch!',
                                           level=Qgis.Critical)
            return False

        if 'dynafile' in QKan.config:
            dynafile = QKan.config['dynafile']
        else:
            dynafile = ''
        self.dlg.tf_KP_dest.setText(dynafile)

        if 'template_dyna' in QKan.config:
            template_dyna = QKan.config['template_dyna']
        else:
            template_dyna = ''
        self.dlg.tf_KP_template.setText(template_dyna)

        if 'datenbanktyp' in QKan.config:
            datenbanktyp = QKan.config['datenbanktyp']
        else:
            datenbanktyp = 'spatialite'
            pass  # Es gibt noch keine Wahlmöglichkeit

        # Übernahme der Quelldatenbank:
        # Wenn ein Projekt geladen ist, wird die Quelldatenbank daraus übernommen.
        # Wenn dies nicht der Fall ist, wird die Quelldatenbank aus der
        # json-Datei übernommen.

        database_QKan = ''

        database_QKan, epsg = get_database_QKan()
        if not database_QKan:
            logger.error(
                u"exportdyna.application: database_QKan konnte nicht aus den Layern ermittelt werden. Abbruch!")
            return False
        self.dlg.tf_QKanDB.setText(database_QKan)

        # Datenbankverbindung für Abfragen
        if database_QKan != '':
            # Nur wenn schon eine Projekt geladen oder eine QKan-Datenbank ausgewählt
            self.dbQK = DBConnection(dbname=database_QKan)  # Datenbankobjekt der QKan-Datenbank zum Lesen
            if not self.dbQK.connected:
                fehlermeldung(u"Fehler in exportdyna.application:\n",
                             u'QKan-Datenbank {:s} wurde nicht gefunden oder war nicht aktuell!\nAbbruch!'.format(
                                 database_QKan))
                return None

            # Check, ob alle Teilgebiete in Flächen, Schächten und Haltungen auch in Tabelle "teilgebiete" enthalten

            sql = u"""INSERT INTO teilgebiete (tgnam)
                    SELECT teilgebiet FROM flaechen 
                    WHERE teilgebiet IS NOT NULL AND
                    teilgebiet NOT IN (SELECT tgnam FROM teilgebiete)
                    GROUP BY teilgebiet"""
            if not self.dbQK.sql(sql, u"QKan_ExportDYNA.application.run (1) "):
                return False

            sql = u"""INSERT INTO teilgebiete (tgnam)
                    SELECT teilgebiet FROM haltungen 
                    WHERE teilgebiet IS NOT NULL AND
                    teilgebiet NOT IN (SELECT tgnam FROM teilgebiete)
                    GROUP BY teilgebiet"""
            if not self.dbQK.sql(sql, u"QKan_ExportDYNA.application.run (2) "):
                return False

            sql = u"""INSERT INTO teilgebiete (tgnam)
                    SELECT teilgebiet FROM schaechte 
                    WHERE teilgebiet IS NOT NULL AND
                    teilgebiet NOT IN (SELECT tgnam FROM teilgebiete)
                    GROUP BY teilgebiet"""
            if not self.dbQK.sql(sql, u"QKan_ExportDYNA.application.run (3) "):
                return False

            self.dbQK.commit()

            # Anlegen der Tabelle zur Auswahl der Teilgebiete

            # Zunächst wird die Liste der beim letzten Mal gewählten Teilgebiete aus config gelesen
            liste_teilgebiete = []
            if 'liste_teilgebiete' in QKan.config:
                liste_teilgebiete = QKan.config['liste_teilgebiete']

            # Abfragen der Tabelle teilgebiete nach Teilgebieten
            sql = 'SELECT "tgnam" FROM "teilgebiete" GROUP BY "tgnam"'
            if not self.dbQK.sql(sql, u"QKan_ExportDYNA.application.run (4) "):
                return False
            daten = self.dbQK.fetchall()
            self.dlg.lw_teilgebiete.clear()

            for ielem, elem in enumerate(daten):
                self.dlg.lw_teilgebiete.addItem(QListWidgetItem(elem[0]))
                try:
                    if elem[0] in liste_teilgebiete:
                        self.dlg.lw_teilgebiete.setCurrentRow(ielem)
                except BaseException as err:
                    fehlermeldung(u'QKan_ExportDYNA (6), Fehler in elem = {}\n'.format(elem), repr(err))
                    # if len(daten) == 1:
                    # self.dlg.lw_teilgebiete.setCurrentRow(0)

            # Ereignis bei Auswahländerung in Liste Teilgebiete

        self.countselection()

        # Autokorrektur

        if 'profile_ergaenzen' in QKan.config:
            profile_ergaenzen = QKan.config['profile_ergaenzen']
        else:
            profile_ergaenzen = True
        self.dlg.cb_profile_ergaenzen.setChecked(profile_ergaenzen)

        if 'autonummerierung_dyna' in QKan.config:
            autonummerierung_dyna = QKan.config['autonummerierung_dyna']
        else:
            autonummerierung_dyna = False
        self.dlg.cb_autonummerierung_dyna.setChecked(autonummerierung_dyna)

        # Festlegung des Fangradius
        # Kann über Menü "Optionen" eingegeben werden
        if 'fangradius' in QKan.config:
            fangradius = QKan.config['fangradius']
        else:
            fangradius = u'0.1'

        # Haltungsflächen (tezg) berücksichtigen
        if 'mit_verschneidung' in QKan.config:
            mit_verschneidung = QKan.config['mit_verschneidung']
        else:
            mit_verschneidung = True
        self.dlg.cb_regardTezg.setChecked(mit_verschneidung)

        # Mindestflächengröße
        # Kann über Menü "Optionen" eingegeben werden
        if 'mindestflaeche' in QKan.config:
            mindestflaeche = QKan.config['mindestflaeche']
        else:
            mindestflaeche = u'0.5'

        # Maximalzahl Schleifendurchläufe
        if 'max_loops' in QKan.config:
            max_loops = QKan.config['max_loops']
        else:
            max_loops = 1000

        # Optionen zur Berechnung der befestigten Flächen
        if 'dynabef_choice' in QKan.config:
            dynabef_choice = QKan.config['dynabef_choice']
        else:
            dynabef_choice = u'flaechen'

        if dynabef_choice == u'flaechen':
            self.dlg.rb_flaechen.setChecked(True)
        elif dynabef_choice == u'tezg':
            self.dlg.rb_tezg.setChecked(True)

        # Optionen zur Zuordnung des Profilschlüssels
        if 'dynaprof_choice' in QKan.config:
            dynaprof_choice = QKan.config['dynaprof_choice']
        else:
            dynaprof_choice = u'profilname'

        if dynaprof_choice == u'profilname':
            self.dlg.rb_profnam.setChecked(True)
        elif dynaprof_choice == u'profilkey':
            self.dlg.rb_profkey.setChecked(True)

        # Formular anzeigen

        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:

            # Abrufen der ausgewählten Elemente in beiden Listen
            liste_teilgebiete = self.listselecteditems(self.dlg.lw_teilgebiete)

            # Eingaben aus Formular übernehmen
            database_QKan = self.dlg.tf_QKanDB.text()
            dynafile = self.dlg.tf_KP_dest.text()
            template_dyna = self.dlg.tf_KP_template.text()
            profile_ergaenzen = self.dlg.cb_profile_ergaenzen.isChecked()
            autonummerierung_dyna = self.dlg.cb_autonummerierung_dyna.isChecked()
            mit_verschneidung = self.dlg.cb_regardTezg.isChecked()
            if self.dlg.rb_flaechen.isChecked():
                dynabef_choice = u'flaechen'
            elif self.dlg.rb_tezg.isChecked():
                dynabef_choice = u'tezg'
            else:
                fehlermeldung(u"exportdyna.application.run",
                              u"Fehlerhafte Option: \ndynabef_choice = {}".format(repr(dynabef_choice)))
            if self.dlg.rb_profnam.isChecked():
                dynaprof_choice = u'profilname'
            elif self.dlg.rb_profkey.isChecked():
                dynaprof_choice = u'profilkey'
            else:
                fehlermeldung(u"exportdyna.application.run",
                              u"Fehlerhafte Option: \ndynaprof_choice = {}".format(repr(dynaprof_choice)))

            # Konfigurationsdaten schreiben
            QKan.config['dynafile'] = dynafile
            QKan.config['template_dyna'] = template_dyna
            QKan.config['database_QKan'] = database_QKan
            QKan.config['liste_teilgebiete'] = liste_teilgebiete
            QKan.config['profile_ergaenzen'] = profile_ergaenzen
            QKan.config['autonummerierung_dyna'] = autonummerierung_dyna
            QKan.config['fangradius'] = fangradius
            QKan.config['mindestflaeche'] = mindestflaeche
            QKan.config['mit_verschneidung'] = mit_verschneidung
            QKan.config['max_loops'] = max_loops
            QKan.config['dynabef_choice'] = dynabef_choice
            QKan.config['dynaprof_choice'] = dynaprof_choice

            QKan.save_config()

            # Start der Verarbeitung
            
            # Modulaufruf in Logdatei schreiben
            logger.info('''qkan-Modul:\n        exportKanaldaten(
                iface, 
                dynafile='{dynafile}', 
                template_dyna='{template_dyna}', 
                dbQK=qbQK, 
                dynabef_choice='{dynabef_choice}', 
                dynaprof_choice='{dynaprof_choice}',
                liste_teilgebiete='{liste_teilgebiete}', 
                profile_ergaenzen={profile_ergaenzen}, 
                autonum_dyna={autonummerierung_dyna}, 
                mit_verschneidung={mit_verschneidung}, 
                fangradius={fangradius}, 
                mindestflaeche={mindestflaeche}, 
                max_loops={max_loops}, 
                datenbanktyp='{datenbanktyp}')'''.format(
                dynafile=dynafile, 
                template_dyna=template_dyna, 
                dynabef_choice=dynabef_choice, 
                dynaprof_choice=dynaprof_choice, 
                liste_teilgebiete=liste_teilgebiete, 
                profile_ergaenzen=profile_ergaenzen, 
                autonummerierung_dyna=autonummerierung_dyna, 
                mit_verschneidung=mit_verschneidung, 
                fangradius=fangradius, 
                mindestflaeche=mindestflaeche, 
                max_loops=max_loops, 
                datenbanktyp = 'SpatiaLite'))

            exportKanaldaten(iface, dynafile, template_dyna, self.dbQK, dynabef_choice, dynaprof_choice,
                             liste_teilgebiete, profile_ergaenzen, autonummerierung_dyna, mit_verschneidung,
                             fangradius, mindestflaeche, max_loops, datenbanktyp)
