import logging
import sys
import re
from typing import Dict, Iterator, Tuple, Union
from qgis.utils import iface
from qgis.core import Qgis
import csv
import os
import codecs
import array
import math
import numpy as np
from pathlib import Path

import win32com.client
import pythoncom
from win32com.client import VARIANT
import pywintypes

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from qkan import QKan
from qkan.database.dbfunc import DBConnection
from qkan.database.qkan_utils import fehlermeldung
from qkan.database.qkan_utils import get_qkanlayer_attributes
from .dijkstra import find_route


logger = logging.getLogger("QKan.laengs.import")


#TODO: mit einpflegen, dass die Geländehöhe von meheren DGM Layern angezeigt wird


class LaengsTask:
    def __init__(self, db_qkan: DBConnection, file: str, fig: plt.figure, canv:FigureCanvas):
        self.db_qkan = db_qkan
        self.fig = fig
        self.canv = canv

        self.file = file


    def run(self) -> bool:
        self.zeichnen()

    def zeichnen(self):
        #hier wird der Längsschnitt in das Fenster gezeichnet
        figure = self.fig
        figure.clear()
        new_plot = figure.add_subplot(111)

        #aktuellen layer auswählen
        layer = iface.activeLayer()
        x = layer.source()

        #mit dbfunk layer namen anzeigen lassen (für die information ob haltungen oder schächte ausgewählt wurden)
        dbname, table, geom, sql = get_qkanlayer_attributes(x)


        #selektierte elemente anzeigen
        selected = layer.selectedFeatures()
        liste=[]

        if table not in ['schaechte', 'haltungen']:
            iface.messageBar().pushMessage("Fehler", 'Bitte Haltungen oder Schächte wählen', level=Qgis.Critical)
            return

        if table == 'schaechte':
            for f in selected:
                x = f['schnam']
                liste.append(x)

        if table == 'haltungen':
            for f in selected:
                x = f['schoben']
                x2 = f['schunten']
                if x not in liste:
                    liste.append(x)
                if x2 not in liste:
                    liste.append(x2)

        route = find_route(self.file, liste)
        # route = (['2747.1J55', '2747.1J56', '2747.1J57'], ['M2747.1J55', 'M2747.1J56'])
        x_sohle = []
        y_sohle = []
        x_sohle2 = []
        y_sohle2 = []
        x_deckel = []
        y_deckel = []
        y_label = []
        name = []
        haltnam_l = []
        schoben_l = []
        schunten_l = []
        laenge_l = []
        entwart_l = []
        hoehe_l = []
        breite_l = []
        material_l = []
        strasse_l = []
        haltungstyp_l = []
        laenge1 = 0
        laenge2 = 0

        if route is None:
            iface.messageBar().pushMessage("Fehler", 'Es wurden keine Elemente Ausgewählt', level=Qgis.Critical)
            x = 'nicht erstellt'
            return x

        for i in route[1]:

            sql = """
                    SELECT
                        h.schoben,
                        h.hoehe,
                        h.schunten,
                        h.laenge,
                        schob.deckelhoehe,
                        schob.sohlhoehe,
                        schun.deckelhoehe,
                        schun.sohlhoehe,
                        h.entwart,
                        h.haltnam,
                        h.breite,
                        h.material,
                        h.strasse,
                        h.haltungstyp,
                        h.sohleoben,
                        h.sohleunten
                    FROM haltungen AS h,
                        schaechte AS schob,
                        schaechte AS schun
                    WHERE schob.schnam = h.schoben AND schun.schnam = h.schunten AND haltnam = {}
                    """.format("'"+str(i)+"'")

            if not self.db_qkan.sql(sql, "laengsschnitt: Datenbankzugriff nicht möoeglich"):
                x = 'nicht erstellt'
                return x

            for attr in self.db_qkan.fetchall():
                schoben = attr[0]
                hoehe = attr[1]
                schunten = attr[2]
                laenge = attr[3]
                deckeloben = attr[4]
                sohleoben = attr[14]
                deckelunten = attr[6]
                sohleunten = attr[15]
                entwart = attr[8]
                haltnam = attr[9]
                breite = attr[10]
                material = attr[11]
                strasse = attr[12]
                haltungstyp = attr[13]

                laenge2 += laenge

                y_sohle.append(sohleoben)
                y_sohle.append(sohleunten)
                x_sohle.append(laenge1)
                x_sohle.append(laenge2)

                y_sohle2.append(sohleoben + hoehe)
                y_sohle2.append(sohleunten + hoehe)
                x_sohle2.append(laenge1)
                x_sohle2.append(laenge2)

                y_deckel.append(deckeloben)
                y_deckel.append(deckelunten)
                x_deckel.append(laenge1)
                x_deckel.append(laenge2)

                y_label.append((deckeloben+sohleoben-hoehe)/2)
                y_label.append((deckelunten+sohleunten-hoehe)/2)

                laenge1 += laenge
                name.append(schoben)
                name.append(schunten)
                haltnam_l.append(haltnam)
                schoben_l.append(schoben)
                schunten_l.append(schunten)
                laenge_l.append(laenge)
                entwart_l.append(entwart)
                hoehe_l.append(hoehe)
                breite_l.append(breite)
                material_l.append(material)
                strasse_l.append(strasse)
                haltungstyp_l.append(haltungstyp)

        farbe = 'black'
        if entwart == 'MW' or 'KM' or 'Mischwasser':
            farbe = 'pink'

        elif entwart == 'RW' or 'KR' or 'Regenwasser':
            farbe = 'blue'

        elif entwart == 'SW' or 'KS' or 'Schmutzwasser':
            farbe = 'red'

        data = [schoben_l, schunten_l, laenge_l, entwart_l, hoehe_l, breite_l, material_l, strasse_l, haltungstyp_l]

        columns = tuple(haltnam_l)
        rows = ('Schacht oben', 'Schacht unten', 'Länge [m]', 'Entwässerungsart', 'Höhe [m]', 'Breite [m]', 'Material', 'Strasse', 'Typ')

        new_plot.plot(x_deckel, y_deckel, color="black", label='Deckel')
        new_plot.plot(x_sohle, y_sohle, color=farbe, label='Kanalsohle')
        new_plot.plot(x_sohle2, y_sohle2, color=farbe, label='Kanalscheitel')

        x_deckel_neu = []
        name_neu = []
        y_label_neu = []

        for i in x_deckel:
            if i not in x_deckel_neu:
                x_deckel_neu.append(i)

        for i in name:
            if i not in name_neu:
                name_neu.append(i)
        #iface.messageBar().pushMessage("Fehler", str(y_label), level=Qgis.Critical)

        for i in y_label:
            if i not in y_label_neu:
                y_label_neu.append(i)

        #iface.messageBar().pushMessage("Fehler", str(y_label_neu), level=Qgis.Critical)

        for x, y, nam in zip(x_deckel_neu, y_label_neu, name_neu):
            plt.annotate(nam, (x, y),
                         textcoords="offset points",
                         xytext=(-10, 0),
                         rotation=90,
                         ha='center')

        plt.vlines(x_deckel, y_sohle, y_deckel, color="red", linestyles='solid', label='Schacht', linewidth=5)
        plt.xlabel('Länge [m]')
        plt.ylabel('Höhe [m NHN]')
        new_plot.legend()
        plt.table(cellText=data, rowLabels=rows, colLabels=columns, loc='bottom', bbox=[0.0, -0.65, 1, 0.45], cellLoc='center')
        plt.subplots_adjust(top=0.98,
                            bottom=0.4,
                            left=0.13,
                            right=0.99,
                            hspace=0.2,
                            wspace=0.2)


    def cad(self):

        layer = iface.activeLayer()
        x = layer.source()

        # mit dbfunk layer namen anzeigen lassen (für die information ob haltungen oder schächte ausgewählt wurden)
        dbname, table, geom, sql = get_qkanlayer_attributes(x)

        # selektierte elemente anzeigen
        selected = layer.selectedFeatures()
        liste = []

        if table not in ['schaechte', 'haltungen']:
            iface.messageBar().pushMessage("Fehler", 'Bitte Haltungen oder Schächte wählen', level=Qgis.Critical)
            return

        if table == 'schaechte':
            for f in selected:
                x = f['schnam']
                liste.append(x)

        if table == 'haltungen':
            for f in selected:
                x = f['schoben']
                x2 = f['schunten']
                if x not in liste:
                    liste.append(x)
                if x2 not in liste:
                    liste.append(x2)

        route = find_route(self.file, liste)

        x_sohle = []
        y_sohle = []
        x_sohle2 = []
        y_sohle2 = []
        x_deckel = []
        y_deckel = []
        y_label = []
        name = []
        z_deckel = []
        z_sohle =[]

        haltnam_l = ['Haltungsname']
        schoben_l = ['Schacht oben']
        schunten_l = ['Schacht unten']
        laenge_l = ['Laenge [m]']
        entwart_l = ['Entwaesserungsart']
        hoehe_l = ['Hoehe [m]']
        breite_l = ['Breite [m]']
        material_l = ['Material']
        strasse_l = ['Strasse']
        haltungstyp_l = ['Typ']
        laenge1 = 0
        laenge2 = 0


        if route is None:
            iface.messageBar().pushMessage("Fehler", 'Es wurden keine Elemente Ausgewählt', level=Qgis.Critical)
            return

        for i in route[1]:

            sql = """
                            SELECT
                                h.schoben,
                                h.hoehe,
                                h.schunten,
                                h.laenge,
                                schob.deckelhoehe,
                                schob.sohlhoehe,
                                schun.deckelhoehe,
                                schun.sohlhoehe,
                                h.entwart,
                                h.haltnam,
                                h.breite,
                                h.material,
                                h.strasse,
                                h.haltungstyp,
                                h.sohleoben,
                                h.sohleunten
                            FROM haltungen AS h,
                                schaechte AS schob,
                                schaechte AS schun
                            WHERE schob.schnam = h.schoben AND schun.schnam = h.schunten AND haltnam = {}
                            """.format("'" + str(i) + "'")

            if not self.db_qkan.sql(sql, "laengsschnitt: Datenbankzugriff nicht möglich"):
                return

            for attr in self.db_qkan.fetchall():
                schoben = attr[0]
                hoehe = attr[1]
                schunten = attr[2]
                laenge = attr[3]
                deckeloben = attr[4]
                sohleoben = attr[14]
                deckelunten = attr[6]
                sohleunten = attr[15]
                entwart = attr[8]
                haltnam = attr[9]
                breite = attr[10]
                material = attr[11]
                strasse = attr[12]
                haltungstyp = attr[13]

                laenge2 += laenge

                y_sohle.append(sohleoben)
                y_sohle.append(sohleunten)
                x_sohle.append(laenge1)
                x_sohle.append(laenge2)

                y_sohle2.append(sohleoben + hoehe)
                y_sohle2.append(sohleunten + hoehe)
                x_sohle2.append(laenge1)
                x_sohle2.append(laenge2)

                y_deckel.append(deckeloben)
                y_deckel.append(deckelunten)
                x_deckel.append(laenge1)
                x_deckel.append(laenge2)

                y_label.append((deckeloben + sohleoben) / 2)
                y_label.append((deckelunten + sohleunten) / 2)

                laenge1 += laenge
                name.append(schoben)
                name.append(schunten)
                z_deckel.append(deckeloben)
                z_deckel.append(deckelunten)
                z_sohle.append(sohleoben)
                z_sohle.append(sohleunten)

                haltnam_l.append(haltnam)
                schoben_l.append(schoben)
                schunten_l.append(schunten)
                laenge_l.append(laenge)
                entwart_l.append(entwart)
                hoehe_l.append(hoehe)
                breite_l.append(breite)
                material_l.append(material)
                strasse_l.append(strasse)
                haltungstyp_l.append(haltungstyp)

        farbe = "-FARBE" +"\n"+ "7\n" "\n"
        if entwart == 'MW' or 'KM' or 'Mischwasser':
            farbe = "-FARBE" +"\n"+ "6\n" "\n"

        elif entwart == 'RW' or 'KR' or 'Regenwasser':
            farbe = "-FARBE" +"\n"+ "5\n" "\n"

        elif entwart == 'SW' or 'KS' or 'Schmutzwasser':
            farbe = "-FARBE" +"\n"+ "1\n" "\n"

        # autocad benötigt andere daten als matplotlib (Koordinatenpaare erwartet!)
        deckel = "LINIE"
        scheitel = "LINIE"
        sohle = "LINIE"

        #deckelkoordinaten
        for i, j in zip(x_deckel, y_deckel):
            deckel += " " + str(i) + "," + str(j)

        deckel += "\n" "\n"

        #scheitelkoordinaten
        for i, j in zip(x_sohle2, y_sohle2):
            scheitel += " " + str(i) + "," + str(j)

        scheitel += "\n" "\n"

        #sohlenkoordinaten
        for i, j in zip(x_sohle, y_sohle):
            sohle += " " + str(i) + "," + str(j)

        sohle += "\n" "\n"


        #CSV-Tabelle erstellen
        path = Path(__file__).parent.absolute()
        path = str(path)+'/some.csv'
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            rows = tuple(haltnam_l)
            writer.writerow(rows)

            data = [schoben_l, schunten_l, laenge_l, entwart_l, hoehe_l, breite_l, material_l, strasse_l, haltungstyp_l]
            for i in data:
                writer.writerow(i)

        #cad anbindung starten
        acad = None
        doc = None

        try:
            acad = win32com.client.Dispatch('AutoCAD.Application')
            acad.Visible = True
        except WindowsError:
            print('Autocad wird gestartet. Das kann ca. eine halbe Minute dauern...')
            acad = win32com.client.CreateObject('AutoCAD.Application')
            acad = win32com.client.GetActiveObject('AutoCAD.Application')  # scheint zwar doppelt,
            # aber sonst erscheint ein Fehler
            acad.Visible = True
        except pywintypes.error as e:
            print(e)
        except BaseException as e:
            print(e)

        # Prüfen, ob schon eine Datei offen ist. Falls nicht, wird eine neue Datei angelegt.
        if acad is None:
            iface.messageBar().pushMessage("Error", "Autocad ist nicht installiert!", level=Qgis.Critical)
        elif acad.Documents.Count > 0:
            doc = acad.ActiveDocument
            print("Eine Datei ist bereits offen")
        else:
            print("Eine neue Datei wird angelegt")
            doc = acad.Documents.Add()

        if doc is not None:
            #print("Bitte klicken Sie in der AutoCAD-Datei auf einen Punkt!")
            #x0, y0, z0 = doc.Utility.GetPoint()  # z0 wird nicht benötigt
            #print('Geklickt: ({},{})'.format(x0, y0))

            #längssschnitt in cad erstellen

            #doc.SendCommand("LINIE " "1,1 " "3,5\n" "5,-2\n" "\n")
            # mit "FARBE" die Farbe der zu zeichnenden Linie ändern
            doc.SendCommand("-FARBE" +"\n"+ "7\n" "\n")
            doc.SendCommand(deckel)
            doc.SendCommand(farbe)
            doc.SendCommand(scheitel)
            doc.SendCommand(farbe)
            doc.SendCommand(sohle)

            # schacht linien einzeichnen
            for i, j, z in zip(x_deckel, y_sohle, y_deckel):
                schacht = "LINIE"
                schacht += " " + str(i) + "," + str(j)
                schacht += " " + str(i) + "," + str(z)
                schacht += "\n" "\n"
                doc.SendCommand("-FARBE" +"\n"+ "1\n" "\n")
                doc.SendCommand(schacht)


            #Graphen zeichnen lassen
            doc.SendCommand("-FARBE" + "\n" + "7\n" "\n")
            x_min = -5
            y_min = float(min(y_sohle)) - 5
            y_max = float(max(y_deckel)) + 5
            x_max = laenge2 + 5
            x_linie = "LINIE " + str(x_min) + "," + str(y_min) + " " + str(x_max) + "," + str(y_min) + "\n" + "\n"
            #iface.messageBar().pushMessage("Error", str(x_linie), level=Qgis.Critical)
            doc.SendCommand(x_linie)
            #y_linie = "LINIE " + str(x_min) + "," + str(y_min) +  " " + str(x_min) + "," + str(y_max) + "\n" + "\n"
            #iface.messageBar().pushMessage("Error", str(y_linie), level=Qgis.Critical)
            #doc.SendCommand(y_linie)
            x_linie2 = "LINIE " + str(x_min) + "," + str(y_min-3.5) + " " + str(x_max) + "," + str(y_min-3.5) + "\n" + "\n"
            doc.SendCommand(x_linie2)
            x_linie3 = "LINIE " + str(x_min) + "," + str(y_min - 7.5) + " " + str(x_max) + "," + str(y_min - 7.5) + "\n" + "\n"
            doc.SendCommand(x_linie3)

            #zu den eingefügten Daten zoomen
            doc.SendCommand("ZOOM"+ "\n"+"A"+ "\n")


            #regelmäßige Striche für die Beschriftung der Graphen erzeugen

            x_deckel_neu = []
            name_neu = []

            for i in x_deckel:
                if i not in x_deckel_neu:
                    x_deckel_neu.append(i)

            for i in name:
                if i not in name_neu:
                    name_neu.append(i)

            for i,j,x,y in zip(x_deckel_neu,name_neu,z_deckel,z_sohle):
                linien = "LINIE"
                linien += " " + str(i) + "," + str(y_min)
                linien += " " + str(i) + "," + str(y_min-9)
                linien += "\n" "\n"
                doc.SendCommand(linien)

                text1 = "-TEXT" +"\n"+str(i-1.5) + "," + str(y_min-3)+"\n"+"0.7"+"\n"+"90"+"\n"+str(x)+"\n" "\n"
                doc.SendCommand(text1)
                text2 = "-TEXT" + "\n" + str(i - 1.5) + "," + str(y_min - 7) + "\n" + "0.7" + "\n" + "90" + "\n" + str(y) + "\n" "\n"
                doc.SendCommand(text2)
                text3 = "-TEXT" + "\n" + str(i - 2) + "," + str(y_min - 11) + "\n" + "1" + "\n" + "0" + "\n" + str(j) + "\n" "\n"
                doc.SendCommand(text3)


