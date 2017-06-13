# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Laengsschnitt
                                 A QGIS plugin
 Plugin für einen animierten Laengsschnitt
                              -------------------
        begin                : 2017-02-16
        git sha              : $Format:%H$
        copyright            : (C) 2017 by Leon Ochsenfeld
        email                : Ochsenfeld@fh-aachen.de
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4.QtCore import *
from PyQt4.QtGui import *
# Initialize Qt resources from file resources.py
import resources_laengs
import resources_gangl

from QKan_Database.navigation import Navigator
import plotter
from application_dialog import LaengsschnittDialog
import random
import os.path
import slider as s
from Enums import SliderMode, Type, LayerType
import copy
from ganglinie import Ganglinie
import logging

main_logger = logging.getLogger("QKan_Laengsschnitt")
main_logger.setLevel(logging.INFO)
logging_file = os.path.join(os.path.dirname(__file__), "log_laengsschnitt.txt")
ch = logging.FileHandler(filename=logging_file, mode="a", encoding="utf8")
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
main_logger.addHandler(ch)
main_logger.info("Application started")


class Laengsschnitt:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        self.__log = logging.getLogger("QKan_Laengsschnitt.application.Laengsschnitt")
        self.__t = 2
        # Save reference to the QGIS interface
        self.__iface = iface

        # Declare instance attributes
        self.__actions = []
        self.__menu = u'&Laengsschnitt'
        self.__toolbar = self.__iface.addToolBar(u'Laengsschnitt')
        self.__toolbar.setObjectName(u'Laengsschnitt')
        self.__dlg = None
        self.__result_db = ""
        self.__spatialite = ""
        self.__route = {}
        self.__toolbar_widget = None
        self.__id = 0
        self.__maximizer = None
        self.__auto_update = False
        self.__animator = None
        self.__speed_controller = None
        self.__speed_label = None
        self.__default_function = None
        self.__ganglinie = Ganglinie(1)
        self.__dlg2 = self.__ganglinie.get_dialog()
        self.__navigator = None
        self.__workspace = ""

    def __add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag=True,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
            whats_this=None,
            parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.__actions list.
        :rtype: QAction
        """

        # Create the dialog (after translation) and keep reference
        self.__dlg = LaengsschnittDialog()

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.__toolbar.addAction(action)

        if add_to_menu:
            self.__iface.addPluginToMenu(
                self.__menu,
                action)

        self.__actions.append(action)

        return action

    def initGui(self):
        """
        Längsschnitt- und Ganglinie-Tool werden als unabhängige Werkzeuge dargestellt.
        Hier werden die GUI-Elemente mit bestimmten Event-Listenern verbunden.
        """
        icon_path_laengs = ':/plugins/QKan_Laengsschnitt/icon_laengs.png'
        icon_path_gangl = ':/plugins/QKan_Laengsschnitt/icon_gangl.png'

        self.__add_action(
            icon_path_laengs,
            text=u'Längsschnitt-Tool',
            callback=self.__run
        )
        self.__add_action(
            icon_path_gangl,
            text=u'Ganglinien-Tool',
            callback=self.__run_ganglinie
        )

        workspace = os.path.dirname(__file__)
        self.__dlg.btn_forward.setText("")
        self.__dlg.btn_forward.setIcon(QIcon(os.path.join(workspace, "forward.png")))
        self.__dlg.btn_backward.setText("")
        self.__dlg.btn_backward.setIcon(QIcon(os.path.join(workspace, "backward.png")))
        self.__dlg.finished.connect(self.__finished)
        self.__dlg.btn_path.clicked.connect(self.__select_db)
        self.__dlg.checkbox_maximum.stateChanged.connect(self.__switch_max_values)
        self.__dlg.btn_forward.clicked.connect(self.__step_forward)
        self.__dlg.btn_backward.clicked.connect(self.__step_backward)
        self.__dlg.btn_ganglinie.clicked.connect(self.__ganglinie.show)

    def __finished(self):
        """
        Schließt den Ganglinien-Dialog, falls geöffnet
        """
        self.__log.info("Ganglinien-Dialog wird geschlossen")
        self.__dlg2.close()

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.__actions:
            self.__iface.removePluginMenu(
                u'&Laengsschnitt',
                action)
            self.__iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.__toolbar

    def __step_forward(self):
        """
        Geht einen Datensatz nach rechts im Zeitstrahl, falls der Entpunkt nicht erreicht ist.
        Pausiert die Animation, falls diese läuft.
        """
        if self.__speed_controller.get_mode() != SliderMode.Pause:
            self.__log.info("Animation ist noch nicht pausiert")
            self.__speed_controller.set_paused()
            self.__animator.pause()
        value = self.__dlg.slider.value()
        maximum = self.__dlg.slider.maximum()
        if value < maximum:
            self.__log.info("Zeitstrahl-Slider wird ein Schritt weiter gesetzt")
            self.__log.debug("Zeitstrahl-Slider hat jetzt den Wert {}".format(value + 1))
            self.__dlg.slider.setValue(value + 1)

    def __step_backward(self):
        """
        Geht einen Datensatz nach links im Zeitstrahl, falls der Anfangspunkt nicht erreicht ist.
        Pausiert die Animation, falls diese läuft.
        """
        if self.__speed_controller.get_mode() != SliderMode.Pause:
            self.__log.info("Animation ist noch nicht pausiert")
            self.__speed_controller.set_paused()
            self.__animator.pause()
        value = self.__dlg.slider.value()
        minimum = self.__dlg.slider.minimum()
        if value > minimum:
            self.__log.info("Zeitstrahl-Slider wird ein Schritt zurueck gesetzt")
            self.__log.debug("Zeitstrahl-Slider hat jetzt den Wert {}".format(value - 1))
            self.__dlg.slider.setValue(value - 1)

    def __switch_max_values(self, activate):
        """
        Macht die Maximal-Linie sichtbar bzw unsichtbar, abhängig vom Zustand der Checkbox.
        Plottet die Maximal-Linie falls nicht vorhanden.

        :param activate: Zustand der Checkbox, nach dem anklicken.
        :type activate: int
        """
        if self.__maximizer is None or self.__maximizer.get_id() != self.__id:
            self.__maximizer = plotter.Maximizer(self.__id, copy.deepcopy(self.__route), self.__result_db)
            self.__maximizer.draw()
        if activate == 2:
            self.__maximizer.show()
        else:
            self.__maximizer.hide()

    @staticmethod
    def __show_message_box(title, _string, _type):
        """
        Generiert eine Messagebox.
        Abhängig vom _type werden unterschiedliche Optionen in den Dialog eingebunden.
        Es wird False zurückgegeben, wenn der User auf "Abbrechen" drückt.


        :param title: Der Titel der MessageBox
        :type title: str
        :param _string: Der Inhalt der MessageBox
        :type _string: str
        :param _type: Welche Buttons generiert werden sollen. Bzw die Art der MessageBox.
        :type _type: Type
        :return: Ob der User auf "Abbrechen" gedrückt hat
        :rtype: bool
        """
        if _type == Type.Error:

            standard_buttons = QMessageBox.Ok
            default_button = QMessageBox.Ok
        else:
            standard_buttons = (QMessageBox.Cancel | QMessageBox.Open)
            default_button = QMessageBox.Open
        title = title.decode("utf-8")
        _string = _string.decode("utf-8")
        msg = QMessageBox()
        msg.setStandardButtons(standard_buttons)
        msg.setDefaultButton(default_button)
        msg.setText(_string)
        msg.setWindowTitle(title)
        if default_button == QMessageBox.Open:
            return msg.exec_() != QMessageBox.Open
        else:
            msg.exec_()

    def __speed_control(self, value):
        """
        * Übergibt der Animation die neue Geschwindigkeit.
        * Updatet den Stil des Sliders
        Ist die Geschwindigkeit 0, wird die Animation pausiert.

        :param value: Geänderte Geschwindigkeit.
        :type value: int
        """
        if self.__speed_controller.get_mode() == SliderMode.Pause:
            if self.__speed_controller.get_last_mode() == SliderMode.Forward:
                self.__speed_label.setText("Geschwindigkeit: {}x".format(value))
                self.__speed_label.setStyleSheet(
                    "QLabel {color:qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #050DFF, stop:1 #757AFF);}")
            else:
                self.__speed_label.setText("Geschwindigkeit: -{}x".format(value))
                self.__speed_label.setStyleSheet(
                    "QLabel {color:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #000000, stop:1 #8f8f8f);}")
        elif self.__speed_controller.get_mode() == SliderMode.Forward:
            self.__speed_label.setText("Geschwindigkeit: {}x".format(value))
            self.__speed_label.setStyleSheet(
                "QLabel {color:qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #050DFF, stop:1 #757AFF);}")
        else:
            self.__speed_label.setText("Geschwindigkeit: -{}x".format(value))
            self.__speed_label.setStyleSheet(
                "QLabel {color:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #000000, stop:1 #8f8f8f);}")

        if self.__speed_controller.get_mode() == SliderMode.Pause:
            self.__log.info("Speed-Controller ist pausiert")
            self.__animator.pause()
            return
        if value == 0:
            self.__log.info("Neue Geschwindigkeit ist 0")
            self.__animator.pause()
        else:
            self.__log.info(u"Animation wird in gewünschte Konfiguration abgespielt")
            self.__animator.play(value, self.__speed_controller.get_mode())

    def __slider_click(self, event):
        """
        * Ist der Eventlistener des Zeitstrahl-Sliders bei einem Mausklick.
        * Definiert das Verhalten je nach gedrückter Taste.

        :param event: Entspricht dem Mausevent, wenn der Slider angeklickt wird
        :type event: QMouseEvent
        """
        self.__log.info("Der Zeitstrahl-Slider wurde angeklickt")
        ctrl = event.modifiers() == Qt.ControlModifier
        if event.button() == Qt.RightButton:
            if ctrl:
                self.__log.debug(u"STRG+RMT wurde gedrückt")
                self.__speed_controller.ctrl_click()
            else:
                self.__log.debug(u"RMT wurde gedrückt")
                self.__speed_controller.set_paused()
                if self.__speed_controller.get_mode() == SliderMode.Pause:
                    self.__animator.pause()
                else:
                    self.__log.info("Animation wird fortgesetzt")
        else:
            if self.__speed_controller.get_mode() != SliderMode.Pause:
                self.__speed_controller.set_paused()
                self.__animator.pause()
            self.__log.info("Zeitstrahl-Slider bekommt seinen Default-EventListener zugewiesen")
            self.__default_function(event)

    def __select_db(self):
        """
        Diese Funktion öffnet einen Datei-Dialog, welcher den User auffordert eine Ergebnis-Datenbank auszuwählen.
        """
        self.__animator.pause()
        filename = QFileDialog.getOpenFileName(self.__dlg, u"Wählen Sie eine Ergebnis-Datenbank",
                                               filter="IDBF (*.idbf);; Alle Dateien (*.*)")
        if filename != "":
            self.__result_db = filename
            self.__dlg.label_dbname.setText(filename)
            self.__run()

    def __layer_to_type(self, layer):
        """
        Wandelt layer in einen LayerType um. So wird unabhängig von der User-spezifischen Benennung der richtige Layer
        gewählt.
        
        :param layer: Ist der übergebene Layer, welcher in einen Typen geparst werden soll
        :type layer: QgsVectorLayer
        :return: Gibt einen LayerType zurück, der dem übergebenen QgsVectorLayer entspricht
        :rtype: LayerType
        """
        layer_source = layer.source()
        kvp = layer_source.split(" ")
        name = ""
        for kv in kvp:
            if kv.startswith("table"):
                name = kv.split("=")[1][1:-1]
            elif kv.startswith("dbname") and self.__spatialite == "":
                self.__spatialite = kv.split("=")[1][1:-1]
                self.__log.info("SpatiaLite-Datenbank wurde gesetzt")
                self.__log.debug(u"SpatiaLite-Datenbank liegt in \"{}\"".format(self.__spatialite))
                self.__workspace = os.path.dirname(self.__spatialite)
                self.__log.debug(u"Workspace wurde auf \"{}\" gesetzt".format(self.__workspace))
        types = dict(wehre=LayerType.Wehr, haltungen=LayerType.Haltung, schaechte=LayerType.Schacht,
                     pumpen=LayerType.Pumpe)
        try:
            return types[name]
        except KeyError:
            return -1

    def __run(self):
        """
        Wird aufgerufen, wenn der Längsschnitt angeklickt wird. 
        """
        self.__log.info(u"Längsschnitt-Tool gestartet!")

        def init_application():
            """
            Initialisiert den Längsschnitt und liest die gewählten Layer aus.
            Prüft außerdem auf Kompatibilität und Anzahl der Layer. 
            Bricht ggf. die Funktion ab, wenn der Datensatz fehlerhaft ist.
            
            :return: Gibt eine Liste der selektierten Layer zurück und einen LayerType
            :rtype: (list,LayerType)
            """
            if self.__animator is not None:
                self.__log.info("Animator bereits vorhanden!")
                self.__animator.pause()
            if self.__speed_controller is not None:
                self.__log.info("Speed-Controller bereits vorhanden!")
                self.__speed_controller.reset()
            if self.__ganglinie is not None:
                self.__dlg2.close()
                self.__log.info("Ganglinie wurde geschlossen.")
            self.__dlg.close()
            self.__id = random.random()
            self.__log.info("Neue ID wurde generiert")
            self.__log.debug("ID:\t{}".format(self.__id))
            selected_layers = self.__get_selected_layers()
            if len(selected_layers) == 0:
                self.__log.critical(u"Es wurde kein Layer ausgewählt!")
                self.__iface.messageBar().pushCritical("Fehler", u"Wählen Sie zunächst ein Layer!")
                return False
            layer_types = []
            for layer in selected_layers:
                layer_types.append(self.__layer_to_type(layer))
            layer_types = list(set(layer_types))
            if len(layer_types) != 1:
                for _l in layer_types:
                    if _l not in [LayerType.Haltung, LayerType.Wehr, LayerType.Pumpe]:
                        self.__log.critical(u"Gewählte Layer sind inkompatibel zueinander!")
                        self.__iface.messageBar().pushCritical("Fehler", "Inkompatible Layer-Kombination!")
                        return False
                _layer_type = LayerType.Haltung
            else:
                _layer_type = layer_types[0]
            if _layer_type in [LayerType.Wehr, LayerType.Pumpe]:
                _layer_type = LayerType.Haltung
            if _layer_type not in [LayerType.Haltung, LayerType.Schacht]:
                self.__log.critical(u"Ausgewählter Layer wird nicht unterstützt.")
                self.__iface.messageBar().pushCritical("Fehler", u"Ausgewählter Layer wird nicht unterstützt!")
                return False
            self.__log.info(u"Layer wurde ausgewählt")
            self.__log.debug(
                u"Gewählter Layer ist {}".format("Schacht" if _layer_type == LayerType.Schacht else "Haltung"))
            while self.__result_db == "":
                stop = self.__show_message_box("Ergebnis-Datenbank",
                                               "Bitte wählen Sie eine Ergebnis-Datenbank aus!",
                                               Type.Selection)
                if stop:
                    self.__log.info("Ergebnis-Datenbank-Auswahl wurde abgebrochen.")
                    return False
                self.__result_db = QFileDialog.getOpenFileName(self.__dlg,
                                                               u"Wählen Sie eine Simulations-Datenbank",
                                                               self.__workspace,
                                                               filter="IDBF (*.idbf);; Alle Dateien (*.*)")
            self.__dlg.label_dbname.setText(self.__result_db)
            self.__log.info(u"Ergebnis-Datenbank wurde ausgewählt")
            self.__log.debug("Ergebnis-Datenbank liegt in {}".format(self.__result_db))

            if self.__navigator is None or self.__navigator.get_id() != self.__id:
                self.__navigator = MyNavigator(self.__spatialite, self.__id)
            self.__log.info("Navigator wurde initiiert.")
            return selected_layers, _layer_type

        initialized = init_application()
        if initialized:
            self.__log.info(u"Längsschnitt wurde erfolgreich initiiert!")
            layers, layer_type = initialized
        else:
            self.__log.warning(u"Initiierung abgebrochen. Längsschnitt-Tool wird beendet.")
            return
        speed_controller_initialized = self.__speed_controller is None
        layout = QGridLayout()
        if speed_controller_initialized:
            self.__speed_controller = s.Slider()
            self.__speed_controller.setMaximumWidth(500)
            self.__speed_controller.setMinimumWidth(300)
            layout.addWidget(self.__speed_controller, 0, 0, 1, 1, Qt.AlignRight)
            self.__speed_label = QLabel("Geschwindigkeit: 0x")
            self.__speed_label.setStyleSheet(
                "QLabel {color:qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #050DFF, stop:1 #757AFF);}")
            self.__speed_controller.setToolTip(
                "Links: Geschwindigkeit einstellen\nRechts: Pause/Start\nStrg+Rechts: Geschwindigkeit umkehren")
            layout.addWidget(self.__speed_label, 1, 0, 1, 1, Qt.AlignCenter)
        self.__dlg.widget.setLayout(layout)
        self.__log.info("Speed-Controller wurde erfolgreich initiiert und in den Dialog eingebettet.")
        feature_count = 0
        for l in layers:
            feature_count += l.selectedFeatureCount()
        self.__log.debug("Es wurden {} Elemente selektiert.".format(feature_count))
        if feature_count < 2 and layer_type == LayerType.Schacht:
            self.__log.critical("Es wurde eine unzureichende Menge an Elementen selektiert!")
            self.__iface.messageBar().pushCritical("Fehler",
                                                   u"Bitte wählen Sie mindestens einen Start- und"
                                                   u" Endpunkt Ihrer gewünschten Route!")
            return
        elif feature_count < 1:
            self.__log.critical("Es wurde kein Element selektiert!")
            self.__iface.messageBar().pushCritical("Fehler",
                                                   u"Bitte wählen Sie mindestens einen Start- und Endpunkt"
                                                   u" Ihrer gewünschten Route!")
            return
        # run application
        features = []
        for l in layers:
            features += [f[1] for f in l.selectedFeatures()]
        features = list(set(features))
        self.__log.debug(u"{} wurde ausgewählt.".format(features))
        self.__iface.messageBar().pushMessage("Navigation", "Route wird berechnet...", self.__iface.messageBar().INFO,
                                              60)
        if layer_type == LayerType.Haltung:
            _route = self.__navigator.calculate_route_haltung(features)
        else:
            _route = self.__navigator.calculate_route_schacht(features)
        self.__iface.messageBar().clearWidgets()
        if _route:
            self.__log.info(u"Navigation wurde erfolgreich durchgeführt!")
            self.__route = _route
            self.__log.debug("Route:\t{}".format(self.__route))
        else:
            error_msg = self.__navigator.get_error_msg()
            self.__log.critical(u"Es trat ein Fehler in der Navigation auf:\t\"{}\"".format(error_msg))
            self.__iface.messageBar().pushCritical("Fehler", error_msg)
            return
        laengsschnitt = plotter.Laengsschnitt(copy.deepcopy(self.__route))
        laengsschnitt.draw()
        plotter.set_ax_labels("m", "m")
        widget, _toolbar = laengsschnitt.get_widget()
        if self.__toolbar_widget is not None:
            for i in reversed(range(self.__dlg.verticalLayout.count())):
                self.__dlg.verticalLayout.itemAt(i).widget().setParent(None)
        self.__toolbar_widget = _toolbar
        self.__dlg.verticalLayout.addWidget(self.__toolbar_widget)
        self.__dlg.stackedWidget.insertWidget(0, widget)
        self.__dlg.stackedWidget.setCurrentIndex(0)
        self.__log.info("Toolbar wurde eingebettet.")
        # init methods

        self.__dlg.checkbox_maximum.setChecked(True)
        self.__switch_max_values(2)
        if self.__animator is None or self.__animator.get_id() != self.__id:
            self.__animator = plotter.Animator(self.__id, copy.deepcopy(self.__route),
                                               self.__result_db, self.__dlg.slider, self.__dlg.btn_forward,
                                               self.__dlg.btn_backward)
        plotter.set_legend()
        if self.__ganglinie.get_id() != self.__id:
            self.__ganglinie.refresh(_id=self.__id, haltungen=self.__route.get("haltungen"),
                                     schaechte=self.__route.get("schaechte"), dbname=self.__result_db,
                                     laengsschnitt=laengsschnitt)
            self.__ganglinie.draw_at(self.__animator.get_timestamps()[self.__animator.get_last_index()])
        self.__animator.set_ganglinie(self.__ganglinie)
        self.__dlg2.auto_update.hide()
        self.__log.info("Auto-Update-Checkbox wurde versteckt")
        self.__speed_controller.valueChanged.connect(self.__speed_control)
        self.__dlg.slider.valueChanged.connect(self.__animator.go_step)
        self.__dlg.slider.setToolTip(
            "Links: Zeitpunkt einstellen\nRechts: Pause/Start\nStrg+Rechts: Geschwindigkeit umkehren")
        if self.__default_function is None:
            self.__default_function = self.__dlg.slider.mousePressEvent
            self.__log.info("MousePressEvent des Sliders wurde gespeichert")
        self.__dlg.slider.mousePressEvent = lambda event: self.__slider_click(event)
        self.__dlg.show()
        self.__log.info("Dialog wird angezeigt")

        # Längsschnitt starten
        self.__speed_controller.setValue(5)
        self.__animator.play(5, SliderMode.Forward)
        self.__speed_controller.set_paused()

        # Run the dialog event loop
        result = self.__dlg.exec_()
        # See if OK was pressed
        if result:
            # neustart
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass
            # else:
            # beenden
        self.__animator.pause()
        self.__speed_controller.reset()
        self.__log.info(u"Längsschnitt wurde geschlossen!")

    def __get_selected_layers(self):
        """
        Geht alle selektierten Layer durch und prüft, ob innerhalb dieser, Elemente ausgewählt wurden.
        
        :return: Gibt eine Liste der Layer zurück, welche angewählte Elemente beinhalten.
        :rtype:list 
        """
        layers = self.__iface.legendInterface().layers()
        selected_layers = []
        self.__log.debug(u"Verfügbare Layer:\t{}".format(layers))
        for l in layers:
            if l.selectedFeatureCount() > 0:
                selected_layers.append(l)
        self.__log.debug("Selektierte Layer:\t{}".format(selected_layers))
        return selected_layers

    def __run_ganglinie(self):
        """
        Wird aufgerufen, wenn das Ganglinien-Tool angeklickt wird.
        """
        tmp = Ganglinie(self.__t)
        self.__t += 1
        self.__log.info(u"Ganglinie hinzugefügt")

        def init_application():
            """
            Initialisiert die Ganglinie mit den nötigen Parametern. Fragt unter anderem die Datenbanken ab und 
            prüft auf Kompatibilität und Anzahl der Layer.
            Bricht ggf. die Funktion ab, wenn fehlerhafte Daten vorliegen.
            
            :return: Gibt eine Liste von den selektierten Layern und dem vorliegenden LayerType zurück.
            :rtype: (list,LayerType)
            """
            self.__log.info("Ganglinien-Tool wurde gestartet!")

            self.__id = random.random()
            self.__log.info("Neue ID wurde generiert")
            self.__log.debug("ID:\t{}".format(self.__id))
            while self.__result_db == "":
                stop = self.__show_message_box("Ergebnis-Datenbank",
                                               "Bitte wählen Sie eine Ergebnis-Datenbank aus!",
                                               Type.Selection)
                if stop:
                    self.__log.info("Ergebnis-Datenbank-Auswahl wurde abgebrochen.")
                    return False
                self.__result_db = QFileDialog.getOpenFileName(self.__dlg,
                                                               u"Wählen Sie eine Simulations-Datenbank",
                                                               filter="IDBF (*.idbf);; Alle Dateien (*.*)")
            self.__log.info(u"Ergebnis-Datenbank wurde ausgewählt")
            self.__log.debug(u"Ergebnis-Datenbank liegt in {}".format(self.__result_db))
            selected_layers = self.__get_selected_layers()
            if len(selected_layers) == 0:
                self.__log.critical(u"Es wurde kein Layer ausgewählt!")
                self.__iface.messageBar().pushCritical("Fehler", u"Wählen Sie zunächst ein Layer")
                return False
            layer_types = []
            for layer in selected_layers:
                layer_types.append(self.__layer_to_type(layer))
            layer_types = list(set(layer_types))
            if len(layer_types) != 1:
                _layer_type = LayerType.Haltung
            else:
                _layer_type = layer_types[0]
            if _layer_type in [LayerType.Wehr, LayerType.Pumpe]:
                _layer_type = LayerType.Haltung
            if _layer_type not in [LayerType.Haltung, LayerType.Schacht]:
                self.__log.critical(u"Ausgewählter Layer wird nicht unterstützt.")
                self.__iface.messageBar().pushCritical("Fehler", u"Ausgewählter Layer wird nicht unterstützt")
                return False
            self.__log.info(u"Layer wurde ausgewählt")
            self.__log.debug(
                u"Gewählter Layer ist {}".format("Schacht" if _layer_type == LayerType.Schacht else "Haltung"))
            return selected_layers, _layer_type

        def auto_update_changed(state):
            """
            Ist der Event-Listener der "Automatische Updates"-Checkbox.
            
            :param state: Ist der Zustand der Checkbox, nach dem Klicken 
            :type state: int
            """
            self.__log.info("Auto-Update wurde {}.".format("aktiviert" if state == 2 else "deaktiviert"))
            if state == 2:
                subscribe_auto_update()
                selection_changed([0])
            else:
                subscribe_auto_update(False)

        def subscribe_auto_update(subscribing=True):
            """
            Fügt die entsprechenden Event-Listener hinzu, falls subscribing True ist. Es werden ausschließlich die 
            wichtigen Layer subscribed, da nicht alle relevant sind.
            
            :param subscribing: Gibt an, ob dem automatischen Updates subscribed/unsubscribed werden soll.
            :type subscribing: bool
            """
            _layers = self.__iface.legendInterface().layers()
            important_layers = []
            for _l in _layers:
                if self.__layer_to_type(_l) != -1:
                    important_layers.append(_l)
            for layer in important_layers:
                if subscribing:
                    layer.selectionChanged.connect(selection_changed)
                    self.__log.info("Event-Listener gesetzt")
                else:
                    try:
                        layer.selectionChanged.disconnect(selection_changed)
                        self.__log.info("Event-Listener entfernt")
                    except TypeError as e:
                        self.__log.warning(u"Beim Entfernen eines Layers trat folgender Fehler auf: {}".format(e))
                        pass

        def selection_changed(selection):
            """
            Wird aufgerufen, wenn ein subscribter Layer eine Veränderung in seinen selektierten Elementen registriert.
            
            :param selection: Bekommt die geänderte Auswahl eines Layers übergeben
            :type selection: list
            """
            if len(selection) == 0:
                return
            _layers = self.__get_selected_layers()
            _schaechte = []
            _haltungen = []
            for _l in _layers:
                _layer_type = self.__layer_to_type(_l)
                if _layer_type == LayerType.Schacht:
                    _schaechte += [_f[1] for _f in _l.selectedFeatures()]
                elif _layer_type in [LayerType.Haltung, LayerType.Pumpe, LayerType.Wehr]:
                    _haltungen += [_f[1] for _f in _l.selectedFeatures()]
            _schaechte = list(set(_schaechte))
            _haltungen = list(set(_haltungen))
            _route = dict(haltungen=_haltungen, schaechte=_schaechte)
            self.__log.info(u"Selektierung wurde geändert")
            self.__log.debug(u"Selektierung:\t{}".format(_route))
            tmp.refresh(_id=self.__id, haltungen=_route.get("haltungen"),
                        schaechte=_route.get("schaechte"), dbname=self.__result_db)
            tmp.show()

        initialized = init_application()
        if initialized:
            self.__log.info("Ganglinien-Tool wurde erfolgreich initiiert!")
            layers, layer_type = initialized
        else:
            self.__log.warning("Initiierung abgebrochen. Ganglinien-Tool wird beendet.")
            return
        feature_count = 0
        for l in layers:
            feature_count += l.selectedFeatureCount()
        self.__log.debug("Es wurden {} Elemente selektiert.".format(feature_count))
        if feature_count < 1:
            self.__log.critical("Es wurde kein Element selektiert!")
            self.__iface.messageBar().pushCritical("Fehler", u"Bitte wählen Sie mindestens ein Element aus!")
            return

        layers = self.__get_selected_layers()
        schaechte = []
        haltungen = []
        for l in layers:
            layer_type = self.__layer_to_type(l)
            if layer_type == LayerType.Schacht:
                schaechte += [f[1] for f in l.selectedFeatures()]
            elif layer_type in [LayerType.Haltung, LayerType.Pumpe, LayerType.Wehr]:
                haltungen += [f[1] for f in l.selectedFeatures()]
        schaechte = list(set(schaechte))
        haltungen = list(set(haltungen))
        route = dict(haltungen=haltungen, schaechte=schaechte)
        self.__log.info("Route wurde erstellt")
        self.__log.debug(u"Route:\t{}".format(route))
        tmp.get_dialog().auto_update.show()
        self.__log.info("Auto-Update-Checkbox wird jetzt angezeigt.")
        subscribe_auto_update()
        tmp.get_dialog().auto_update.stateChanged.connect(auto_update_changed)
        tmp.refresh(_id=self.__id, haltungen=route.get("haltungen"),
                    schaechte=route.get("schaechte"), dbname=self.__result_db)
        tmp.draw()
        tmp.show()
        self.__log.info("Ganglinie wurde initiiert und geplottet.")
        subscribe_auto_update(False)
        self.__log.info("Event-Listener auf Layer wurden entfernt.")


class MyNavigator(Navigator):
    def get_info(self, route):
        """
                * Erstellt Dictionarys, welche folgende Informationen beinhalten.
                * Es wird je ein Dictionary für die Schächte und die Haltungen gemacht.
                * Schacht- bzw. Haltungs-Name entspricht dem Key.
                - Schacht:
                    +sohlhoehe:float
                    +deckelhoehe:float
                - Haltung:
                    +laenge:float
                    +schachtoben:str (Schacht-Name aus QGis)
                    +schachtunten:str (Schacht-Name aus QGis)
                    +sohlhoeheunten:float
                    +sohlhoeheoben:float
                    +querschnitt:float

                :param route: Beinhaltet getrennt von einander die Haltungs- und Schacht-Namen aus QGis.
                :type route: dict
                :return: Gibt ein Dictionary zurück mit allen Haltungs- und Schacht-Namen und den nötigen Informationen zu
                        diesen
                :rtype: dict
                """
        haltung_info = {}
        schacht_info = {}
        statement = u"""
                        SELECT * FROM (SELECT
                                 haltnam                            AS name,
                                 schoben,
                                 schunten,
                                 laenge,
                                 COALESCE(sohleoben, SO.sohlhoehe)  AS sohleoben,
                                 COALESCE(sohleunten, SU.sohlhoehe) AS sohleunten,
                                 hoehe
                               FROM haltungen
                                 LEFT JOIN
                                 (SELECT
                                    sohlhoehe,
                                    schnam
                                  FROM schaechte) AS SO ON haltungen.schoben = SO.schnam
                                 LEFT JOIN
                                 (SELECT
                                    sohlhoehe,
                                    schnam
                                  FROM schaechte) AS SU ON haltungen.schunten = SU.schnam
                               UNION
                               SELECT
                                 wnam         AS name,
                                 schoben,
                                 schunten,
                                 laenge,
                                 SO.sohlhoehe AS sohleoben,
                                 SU.sohlhoehe AS sohleunten,
                                 0.5          AS hoehe
                               FROM wehre
                                 LEFT JOIN
                                 (SELECT
                                    sohlhoehe,
                                    schnam
                                  FROM schaechte) AS SO ON wehre.schoben = SO.schnam
                                 LEFT JOIN
                                 (SELECT
                                    sohlhoehe,
                                    schnam
                                  FROM schaechte) AS SU ON wehre.schunten = SU.schnam
                               UNION
                               SELECT
                                 pnam        AS name,
                                 schoben,
                                 schunten,
                                 5            AS laenge,
                                 SO.sohlhoehe AS sohleoben,
                                 SU.sohlhoehe AS sohleunten,
                                 0.5          AS hoehe
                               FROM pumpen
                                 LEFT JOIN
                                 (SELECT
                                    sohlhoehe,
                                    schnam
                                  FROM schaechte) AS SO ON pumpen.schoben = SO.schnam
                                 LEFT JOIN
                                 (SELECT
                                    sohlhoehe,
                                    schnam
                                  FROM schaechte) AS SU ON pumpen.schunten = SU.schnam
                              )
                        WHERE name="{}"
                        """
        for haltung in route.get("haltungen"):
            self.db.sql(statement.format(haltung))
            name, schachtoben, schachtunten, laenge, sohlhoeheoben, sohlhoeheunten, querschnitt = self.db.fetchone()
            haltung_info[haltung] = dict(schachtoben=schachtoben, schachtunten=schachtunten, laenge=laenge,
                                         sohlhoeheoben=sohlhoeheoben, sohlhoeheunten=sohlhoeheunten,
                                         querschnitt=querschnitt)
        self.log.info(u"Haltunginfo wurde erstellt")
        statement = u"""
                SELECT sohlhoehe,deckelhoehe FROM schaechte WHERE schnam="{}"
                """
        for schacht in route.get("schaechte"):
            self.db.sql(statement.format(schacht))
            res = self.db.fetchone()
            schacht_info[schacht] = dict(deckelhoehe=res[1], sohlhoehe=res[0])

        self.log.info(u"Schachtinfo wurde erstellt")
        return schacht_info, haltung_info
