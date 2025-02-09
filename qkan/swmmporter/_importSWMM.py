# -*- coding: utf-8 -*-

__author__ = "Joerg Hoettges"
__date__ = "März 2020"
__copyright__ = "(C) 2020, Joerg Hoettges"

import os
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, cast
from lxml import etree
from qgis.core import QgsCoordinateReferenceSystem, QgsProject
from qgis.utils import pluginDirectory
from qkan import QKan, enums
from qkan.config import ClassObject
from qkan.database.dbfunc import DBConnection
from qkan.database.qkan_utils import fehlermeldung
from qkan.tools.k_qgsadapt import qgsadapt
from qgis.core import Qgis
from qgis.utils import iface

logger = logging.getLogger("QKan.importswmm")

# Hilfsfunktionen, werden wenn Sie in QKan integriert sind importiert
# from qkan.database.qkan_utils import eval_node_types, fehlermeldung, fzahl


def fzahl(text: str, n: float = 0.0, default: float = 0.0) -> float:
    """Ersetzt während der Entwicklungszeit die QKan-Funktion"""
    """Wandelt einen Text in eine Zahl um. Falls kein Dezimalzeichen
       enthalten ist, werden n Nachkommastellen angenommen"""
    zahl = text.strip()
    if zahl == "":
        return default
    elif "." in zahl:
        try:
            return float(zahl)
        except BaseException as err:
            logger.error("10: {}".format(err))
            return default
    else:
        return float(zahl) / 10.0 ** n


def kstFromKs(ks: float) -> float:
    """Umrechnung des Wertes für die äquivalente Sandrauheit k in die Rauheit nach Manning-Strickler"""
    c_chezy = 25.68
    erg = c_chezy / ks ** (1 / 6)
    return erg


def ksFromKst(kst: float) -> float:
    """Umrechnung des Wertes für die äquivalente Sandrauheit k in die Rauheit nach Manning-Strickler"""
    c_chezy = 25.68
    erg = (c_chezy / kst) ** 6
    return erg


class ImportTask:
    def __init__(
        self,
        inpfile: str,
        db_qkan: DBConnection,
        projectfile: str,
        #offset: List[float],
        epsg: int = 25832,
        dbtyp: str = "SpatiaLite",
    ):
        self.epsg = epsg
        self.dbtyp = dbtyp
        self.inpobject = Path(inpfile)
        self.data: Dict[str, List[str]] = {}
        self.db_qkan = db_qkan
        self.projectfile = projectfile
        #self.xoffset, self.yoffset = offset
        self.xoffset, self.yoffset = [0.0,0.0]

        self.connected = self.db_qkan.connected

        if not self.db_qkan.connected:
            fehlermeldung(
                "Fehler in import_from_swmm:\n",
                "QKan-Datenbank {:s} wurde nicht gefunden oder war nicht aktuell!\nAbbruch!".format(
                    db_qkan
                ),
            )

    def __del__(self) -> None:
        self.db_qkan.sql("SELECT RecoverSpatialIndex()")

    def read(self) -> None:
        with self.inpobject.open("r") as inp:
            position = inp.tell()
            block = ""

            while True:
                zeile = inp.readline().strip()

                # Break at end of file
                if position == inp.tell():
                    break
                position = inp.tell()

                # Skip comments and empty lines
                if zeile.startswith(";") or len(zeile) < 1:
                    continue

                # Block starts
                if zeile.startswith("["):
                    block = zeile.replace("[", "").replace("]", "").lower()

                # Block data
                if not zeile.startswith("[") and block != "":
                    data = self.data.get(block, [])
                    data.append(zeile)
                    self.data[block] = data

    def run(self) -> bool:
        #self._init_mappers()
        self.read()
        self._junctions()
        self._outfalls()
        self._dividers()
        self._storage()
        self._coordinates()
        self._conduits()
        self._pumps()
        self._outlets()
        self._weirs()
        self._orifices()
        self._xsections()
        self._subcatchments()
        self._polygons()
        self._vertices()

        return True

    @property
    def title(self) -> str:
        title = cast(List[str], self.data.get("title", ["Unknown"]))
        return title[0]

    @property
    def options(self) -> dict:
        # Könnte auch direkt gesetzt werden, um Rechenzeit zu sparen
        opts = self.data.get("options", [])
        ret = {}
        for line in opts:
            opt = line.split()
            ret[opt[0]] = opt[1]
        return ret

    def _junctions(self) -> bool:
        """Liest einen Teil der Schachtdaten ein. Rest siehe coordinates"""
        data = self.data.get("junctions", [])
        for line in data:
            line_tokens = line.split()
            name = line_tokens[0]  # schnam
            elevation = line_tokens[1]  # sohlhoehe
            maxdepth = line_tokens[2]  # = deckelhoehe - sohlhoehe
            initdepth = line_tokens[3]  # entfällt
            surDepth = line_tokens[4]  # entfällt
            areaPonded = line_tokens[5]  # ueberstauflaeche

            params = {'schnam': name,
                      'sohlhoehe': elevation, 'deckelhoehe': float(elevation) + float(maxdepth),
                       'schachttyp': 'Schacht'}

            logger.debug(f'swmm.import - insertdata:\ntabnam: schaechte\n'
                         f'params: {params}')

            if not self.db_qkan.insertdata(
                    tabnam="schaechte",
                    mute_logger=False,
                    **params
            ):
                return False

        self.db_qkan.commit()


    def _outfalls(self) -> bool:
        """Liest die Ausläufe ein. Rest siehe coordinates"""

        outtypes = {
            "FREE": "frei",
            "NORMAL": "normal",
            "FIXED": "konstant",
            "TIDAL": "Tide",
            "TIMESERIES": "Zeitreihe",
        }

        data = self.data.get("outfalls", [])
        for line in data:
            line_tokens = line.split()
            name = line_tokens[0] # schnam
            elevation = line_tokens[1]  # sohlhoehe
            outtype = line_tokens[2]   # Auslasstyp
            if outtype not in outtypes.keys():
                auslasstyp = outtypes[outtype]
            else:
                auslasstyp = "frei"

            params = {'schnam': name,
                      'sohlhoehe': elevation, 'schachttyp': 'Auslass'}

            logger.debug(f'swmmporter.import - insertdata:\ntabnam: schaechte\n'
                         f'params: {params}')

            if not self.db_qkan.insertdata(
                    tabnam="schaechte",
                    mute_logger=False,
                    **params
            ):
                return

        self.db_qkan.commit()
    def _dividers(self):
        #speicherschächte

        data = self.data.get("dividers", [])
        for line in data:
            line_tokens = line.split()
            name = line_tokens[0] # schnam
            elevation = line_tokens[1]  # sohlhoehe
            maxdepth = 'NULL'   # ToDo!
            #initdepth = line_tokens[3]   # entfällt

            params = {'schnam': name,
                      'sohlhoehe': elevation, 'deckelhoehe': 'NULL',
                      'schachttyp': 'Speicher'}

            logger.debug(f'mswmmporter.import - insertdata:\ntabnam: schaechte\n'
                         f'params: {params}')

            if not self.db_qkan.insertdata(
                    tabnam="schaechte",
                    mute_logger=False,
                    **params
            ):
                return

        self.db_qkan.commit()

    def _storage(self):
        #speicherschächte

        data = self.data.get("storage", [])
        for line in data:
            line_tokens = line.split()
            name = line_tokens[0] # schnam
            elevation = line_tokens[1]  # sohlhoehe
            maxdepth = line_tokens[2]   # = deckelhoehe - sohlhoehe
            #initdepth = line_tokens[3]   # entfällt


            params = {'schnam': name,
                      'sohlhoehe': elevation, 'deckelhoehe': elevation + maxdepth,
                      'schachttyp': 'Speicher'}

            logger.debug(f'mswmmporter.import - insertdata:\ntabnam: schaechte\n'
                         f'params: {params}')

            if not self.db_qkan.insertdata(
                    tabnam="schaechte",
                    mute_logger=False,
                    **params
            ):
                return

        self.db_qkan.commit()


    def _coordinates(self) -> bool:
        """Liest die Koordinaten zu den bereits angelegten Schaechten ein"""
        data = self.data.get("coordinates", [])
        for line in data:
            linen = line.strip()
            line_tokens = linen.split()
            name = line_tokens[0]
            xsch = fzahl(line_tokens[1], 3, self.xoffset) + self.xoffset  # xsch
            ysch = fzahl(line_tokens[2], 3, self.yoffset) + self.yoffset  # ysch
            du = 1.0

            sql = f"""
                UPDATE schaechte SET (xsch, ysch, geop ,geom) =
                (?, ?, MakePoint(?, ?, ?), 
                     CastToMultiPolygon(MakePolygon(MakeCircle(?, ?, ?, ?))
                 ))
                WHERE schnam = ?
                """
            if not self.db_qkan.sql(sql, parameters=(xsch, ysch,
                                                     xsch, ysch, QKan.config.epsg,
                                                     xsch, ysch, du, QKan.config.epsg,
                                                     name)):
                return False

        self.db_qkan.commit()


    def _subcatchments(self) -> bool:
        """Liest einen Teil der Daten zu tezg-Flächen ein"""
        data = self.data.get("subcatchments", [])
        for line in data:
            # Attribute bitte aus qkan.database.qkan_database.py entnehmen
            line_tokens = line.split()
            name = line_tokens[0]
            regenschreiber = line_tokens[1]
            schnam = line_tokens[2]
            befgrad = fzahl(line_tokens[4])
            neigung = fzahl(line_tokens[6])
            abnam = '$Default_Unbef'

            params = {'flnam': name, 'regenschreiber': regenschreiber, 'schnam': schnam,
                       'befgrad': befgrad, 'neigung': int(neigung), 'abflussparameter': abnam}

            logger.debug(f'mswmmporter.import - insertdata:\ntabnam: tezg\n'
                          f'params: {params}')

            if not self.db_qkan.insertdata(
                     tabnam="tezg",
                     mute_logger=False,
                     **params
            ):
                return False

        self.db_qkan.commit()


    def _polygons(self) -> bool:
        """Liest die Polygone zu den bereits angelegten tezg-Flächen ein"""

        data = self.data.get("polygons", [])
        data.append("ende")  # Trick, damit am Ende das letzte Polygon geschrieben wird

        nampoly = ""  # Solange der Name gleich bleibt, gehören
        # die Eckpunkte zum selben Polygon (tezg-Fläche)

        xlis: List[float] = []  # x-Koordinaten zum Polygon
        ylis: List[float] = []  # y-Koordinaten zum Polygon
        for line in data:
            line_tokens = line.split()
            name = line_tokens[0]
            if name != "ende":
                xsch = fzahl(line_tokens[1], 3, self.xoffset) + self.xoffset  # xsch
                ysch = fzahl(line_tokens[2], 3, self.yoffset) + self.yoffset  # ysch

            if nampoly != name:
                if nampoly != "":
                    # Koordinaten des ersten Punkte am Ende nochmal anhängen
                    xlis.append(xlis[0])
                    ylis.append(ylis[0])

                    # Polygon schreiben
                    coords = ", ".join([f"{x} {y}" for x, y in zip(xlis, ylis)])

                    #iface.messageBar().pushMessage("Error", str(coords),
                    #                               level=Qgis.Critical)


                    sql = "UPDATE tezg SET geom = GeomFromText('MULTIPOLYGON((("+str(coords)+")))',?) WHERE flnam = ? "

                    if not self.db_qkan.sql(
                            sql, parameters=(QKan.config.epsg, nampoly)
                    ):
                        return False

                nampoly = name

                # Listen zurücksetzen
                xlis = []
                ylis = []
            if name == "ende":
                continue  # Letzte Zeile ist nur ein dummy

            # Koordinaten des Eckpunktes übernehmen
            xlis.append(xsch)
            ylis.append(ysch)

        self.db_qkan.commit()


    def _conduits(self) -> bool:
        """Liest einen Teil der Haltungsdaten ein"""

        data = self.data.get("conduits", [])
        for line in data:
            # Attribute bitte aus qkan.database.qkan_database.py entnehmen
            line_tokens = line.split()
            haltnam = line_tokens[0]
            schoben = line_tokens[1]
            schunten = line_tokens[2]
            laenge = line_tokens[3]

            # Rauheitsbeiwerte
            mannings_n = fzahl(line_tokens[4])
            # kst = 1/mannings_n                      # interessant: die Einheit von mannings_n ist s/m**(1/3)!
            # ks = ksFromKst(kst)

            params = {'haltnam': haltnam, 'schoben': schoben, 'schunten': schunten,
                      'laenge': laenge, 'ks': mannings_n, 'entwart': 'Regenwasser', 'haltungstyp': 'Haltung',
                      'simstatus': 'vorhanden'}

            logger.debug(f'isyporter.import - insertdata:\ntabnam: haltungen\n'
                         f'params: {params}')

            if not self.db_qkan.insertdata(
                    tabnam="haltungen",
                    mute_logger=False,
                    **params
            ):
                return

        self.db_qkan.commit()

        # Haltungsobjekte mithilfe der Schachtkoordinaten erzeugen
        sql = f"""
        UPDATE haltungen
         SET geom = (
         SELECT
         MakeLine(schob.geop, schun.geop)
         FROM
         schaechte AS schob,
         schaechte AS schun
         WHERE schob.schnam = haltungen.schoben AND schun.schnam = haltungen.schunten
         )
         """
        if not self.db_qkan.sql(sql):
            return False

        self.db_qkan.commit()

    def _pumps(self):

        data = self.data.get("pumps", [])
        for line in data:
            # Attribute bitte aus qkan.database.qkan_database.py entnehmen
            line_tokens = line.split()
            haltnam = line_tokens[0]
            schoben = line_tokens[1]
            schunten = line_tokens[2]

            params = {'haltnam': haltnam, 'schoben': schoben, 'schunten': schunten,
                       'entwart': 'Regenwasser', 'haltungstyp': 'Pumpe',
                      'simstatus': 'vorhanden'}

            logger.debug(f'isyporter.import - insertdata:\ntabnam: haltungen\n'
                         f'params: {params}')

            if not self.db_qkan.insertdata(
                    tabnam="haltungen",
                    mute_logger=False,
                    **params
            ):
                return

        self.db_qkan.commit()

        # Haltungsobjekte mithilfe der Schachtkoordinaten erzeugen
        sql = f"""
                UPDATE haltungen
                 SET geom = (
                 SELECT
                 MakeLine(schob.geop, schun.geop)
                 FROM
                 schaechte AS schob,
                 schaechte AS schun
                 WHERE schob.schnam = haltungen.schoben AND schun.schnam = haltungen.schunten
                 )
                 """
        if not self.db_qkan.sql(sql):
            return False

    def _orifices(self):
        data = self.data.get("orifices", [])
        for line in data:
            # Attribute bitte aus qkan.database.qkan_database.py entnehmen
            line_tokens = line.split()
            haltnam = line_tokens[0]
            schoben = line_tokens[1]
            schunten = line_tokens[2]

            params = {'haltnam': haltnam, 'schoben': schoben, 'schunten': schunten,
                      'entwart': 'Regenwasser', 'haltungstyp': 'Drosselbauwerk',
                      'simstatus': '?'} # ToDo!

            logger.debug(f'isyporter.import - insertdata:\ntabnam: haltungen\n'
                         f'params: {params}')

            if not self.db_qkan.insertdata(
                    tabnam="haltungen",
                    mute_logger=False,
                    **params
            ):
                return

        self.db_qkan.commit()
        
    def _outlets(self):
        data = self.data.get("outlets", [])
        for line in data:
            # Attribute bitte aus qkan.database.qkan_database.py entnehmen
            line_tokens = line.split()
            haltnam = line_tokens[0]
            schoben = line_tokens[1]
            schunten = line_tokens[2]

            params = {'haltnam': haltnam, 'schoben': schoben, 'schunten': schunten,
                      'entwart': 'Regenwasser', 'haltungstyp': 'Haltung mit Oeffnung',
                      'simstatus': '?'} # ToDo!

            logger.debug(f'isyporter.import - insertdata:\ntabnam: haltungen\n'
                         f'params: {params}')

            if not self.db_qkan.insertdata(
                    tabnam="haltungen",
                    mute_logger=False,
                    **params
            ):
                return

        self.db_qkan.commit()
        
        
    def _weirs(self):

        data = self.data.get("weirs", [])
        for line in data:
            # Attribute bitte aus qkan.database.qkan_database.py entnehmen
            line_tokens = line.split()
            haltnam = line_tokens[0]
            schoben = line_tokens[1]
            schunten = line_tokens[2]

            params = {'haltnam': haltnam, 'schoben': schoben, 'schunten': schunten,
                      'entwart': 'Regenwasser', 'haltungstyp': 'Wehr',
                      'simstatus': 'vorhanden'}

            logger.debug(f'isyporter.import - insertdata:\ntabnam: haltungen\n'
                         f'params: {params}')

            if not self.db_qkan.insertdata(
                    tabnam="haltungen",
                    mute_logger=False,
                    **params
            ):
                return

        self.db_qkan.commit()

        # Haltungsobjekte mithilfe der Schachtkoordinaten erzeugen
        sql = f"""
                        UPDATE haltungen
                         SET geom = (
                         SELECT
                         MakeLine(schob.geop, schun.geop)
                         FROM
                         schaechte AS schob,
                         schaechte AS schun
                         WHERE schob.schnam = haltungen.schoben AND schun.schnam = haltungen.schunten
                         )
                         """
        if not self.db_qkan.sql(sql):
            return False

    def _vertices(self) -> bool:
        data = self.data.get("vertices", [])
        data.append("ende")  # Trick, damit am Ende das letzte Polygon geschrieben wird

        namvor = ""  # Solange der Name gleich bleibt, gehören
        # die Eckpunkte zur selben Haltung
        # npt = 2  # Punkt, der eingefügt werden muss
        npt = 1
        x_start=0
        y_start=0
        x_end=0
        y_end=0

        list = []

        for line in data:
            line_tokens = line.split()
            name = line_tokens[0]
            if name != "ende":
                xsch = fzahl(line_tokens[1], 3, self.xoffset) + self.xoffset  # xsch
                ysch = fzahl(line_tokens[2], 3, self.yoffset) + self.yoffset  # ysch

            if name == namvor:
                npt += 1

            else:
                npt = 1

            if npt == 1:
                # Start und Endpunkt der Haltung ausgeben
                sql = f"""Select 
                        ST_X(StartPoint(geom)) AS xanf,
                        ST_Y(StartPoint(geom)) AS yanf,
                        ST_X(EndPoint(geom))   AS xend,
                        ST_Y(EndPoint(geom))   AS yend
                    FROM haltungen
                    WHERE haltnam =?"""

                self.db_qkan.sql(sql, parameters=(name,))
                for attr in self.db_qkan.fetchall():
                    x_start, y_start, x_end, y_end = attr

                # altes haltungsobjekt löschen, da AddPoint ansonsten nicht richtig funktioniert
                sql = f"""
                                         UPDATE haltungen SET geom = NULL
                                         WHERE haltnam = ?
                                         """

                if not self.db_qkan.sql(
                        sql, parameters=(name,)
                ):
                    return False

                sql = f"""
                            UPDATE haltungen SET geom = AddPoint(MakeLine(MakePoint(?, ?, ?), MakePoint(?, ?, ?)),
                                            MakePoint(?, ?, ?), ?)
                            WHERE haltnam = ?
                         """

                paralist = [x_start, y_start, QKan.config.epsg, x_end, y_end, QKan.config.epsg, xsch, ysch,
                            QKan.config.epsg, npt, name]

                if not self.db_qkan.sql(
                        sql, parameters=paralist
                ):
                    return False

            if npt > 1:
                # weitere punkte ergänzen
                sql = f"""
                                UPDATE haltungen SET geom = AddPoint(geom,MakePoint(?, ?, ?), ?)
                                WHERE haltnam = ?
                             """

                paralist = [xsch, ysch, QKan.config.epsg, npt, name]

                if not self.db_qkan.sql(
                        sql, parameters=paralist
                ):
                    return False

            namvor = name

        self.db_qkan.commit()


    def _xsections(self) -> bool:
        """Liest die Profildaten zu den Haltungen ein. Dabei werden sowohl Haltungsdaten ergänzt
        als auch Profildaten erfasst"""
        #TODO nochmal prüfen

        profiltypes = {"CIRCULAR": "Kreisquerschnitt"}

        data = self.data.get("xsections", [])
        for line in data:
            # Attribute bitte aus qkan.database.qkan_database.py entnehmen
            line_tokens = line.split()
            haltnam = line_tokens[0]
            xsection = line_tokens[1]  # shape
            if xsection == "IRREGULAR":
                hoehe = "NULL"
                breite = "NULL"
            elif xsection == "CUSTOM":
                hoehe = "NULL"
                breite = "NULL"
            elif xsection == "STREET":
                hoehe = "NULL"
                breite = "NULL"
            else: # der Normalfall
                hoehe = line_tokens[2]  # Geom1
                breite = line_tokens[3]  # Geom2   

            if xsection in profiltypes:
                profilnam = profiltypes[xsection]
            else:
                profilnam = "Kreisquerschnitt"

            sql = f"""
                UPDATE haltungen SET (profilnam, hoehe, breite) = (?, ?, ?)
                WHERE haltnam = ?
                """
            if not self.db_qkan.sql(sql, parameters=(profilnam, hoehe, breite, haltnam)):
                return False

        self.db_qkan.commit()


        # todo: SQL-Anweisung wie oben ergänzen

    def _writeProjektfile(self) -> bool:
        # --------------------------------------------------------------------------
        # Zoom-Bereich für die Projektdatei vorbereiten
        sql = """SELECT min(x(geop)) AS xmin, 
                        max(x(geop)) AS xmax, 
                        min(y(geop)) AS ymin, 
                        max(y(geop)) AS ymax
                 FROM schaechte"""
        try:
            if not self.db_qkan.sql(sql, "importkanaldaten_swmm (17)"):
                return False

        except BaseException as e:
            fehlermeldung("SQL-Fehler", str(e))
            fehlermeldung(
                "Fehler in QKan_Import_from_KP",
                "\nFehler in sql_zoom: \n" + sql + "\n\n",
            )

        try:
            zoom = self.db_qkan.fetchone()
        except BaseException as e:
            fehlermeldung("SQL-Fehler", str(e))
            fehlermeldung(
                "Fehler in QKan_Import_from_KP",
                "\nFehler in sql_zoom;\n",
            )
            zoom = [0.0, 100.0, 0.0, 100.0]

        # --------------------------------------------------------------------------
        # Projektionssystem für die Projektdatei vorbereiten
        sql = """SELECT srid
                FROM geom_cols_ref_sys
                WHERE Lower(f_table_name) = Lower('schaechte')
                AND Lower(f_geometry_column) = Lower('geom')"""
        if not self.db_qkan.sql(sql, "importkanaldaten_swmm (37)"):
            return False

        srid = self.db_qkan.fetchone()[0]
        try:
            crs = QgsCoordinateReferenceSystem.fromEpsgId(srid)
            srsid = crs.srsid()
            proj4text = crs.toProj()
            description = crs.description()
            projectionacronym = crs.projectionAcronym()
            if "ellipsoidAcronym" in dir(crs):
                ellipsoidacronym = crs.ellipsoidAcronym()
            else:
                ellipsoidacronym = None
        except BaseException as e:
            srid, srsid, proj4text, description, projectionacronym, ellipsoidacronym = (
                "dummy",
                "dummy",
                "dummy",
                "dummy",
                "dummy",
                "dummy",
            )

            fehlermeldung('\nFehler in "daten"', str(e))
            fehlermeldung(
                "Fehler in QKan_Import_from_KP",
                "\nFehler bei der Ermittlung der srid: \n",
            )

        # --------------------------------------------------------------------------
        # Projektdatei schreiben, falls ausgewählt

        if self.projectfile is not None and self.projectfile != "":
            templatepath = os.path.join(pluginDirectory("qkan"), "templates")
            projecttemplate = os.path.join(templatepath, "projekt.qgs")
            projectpath = os.path.dirname(self.projectfile)
            if os.path.dirname(self.db_qkan) == projectpath:
                datasource = self.db_qkan.replace(
                    os.path.dirname(self.db_qkan), "."
                )
            else:
                datasource = self.db_qkan

            # Lesen der Projektdatei ------------------------------------------------------------------
            qgsxml = ET.parse(projecttemplate)
            root = qgsxml.getroot()

            # Projektionssystem anpassen --------------------------------------------------------------

            for tag_maplayer in root.findall(".//projectlayers/maplayer"):
                tag_datasource = tag_maplayer.find("./datasource")
                if not tag_datasource:
                    continue

                tex = tag_datasource.text
                if not tex:
                    continue

                # Nur QKan-Tabellen bearbeiten
                if tex[tex.index('table="') + 7 :].split('" ')[0] in QKAN_TABLES:

                    # <extend> löschen
                    for tag_extent in tag_maplayer.findall("./extent"):
                        tag_maplayer.remove(tag_extent)

                    for tag_spatialrefsys in tag_maplayer.findall(
                        "./srs/spatialrefsys"
                    ):
                        tag_spatialrefsys.clear()

                        elem = ET.SubElement(tag_spatialrefsys, "proj4")
                        elem.text = proj4text
                        elem = ET.SubElement(tag_spatialrefsys, "srsid")
                        elem.text = "{}".format(srsid)
                        elem = ET.SubElement(tag_spatialrefsys, "srid")
                        elem.text = "{}".format(srid)
                        elem = ET.SubElement(tag_spatialrefsys, "authid")
                        elem.text = "EPSG: {}".format(srid)
                        elem = ET.SubElement(tag_spatialrefsys, "description")
                        elem.text = description
                        elem = ET.SubElement(tag_spatialrefsys, "projectionacronym")
                        elem.text = projectionacronym
                        if ellipsoidacronym is not None:
                            elem = ET.SubElement(tag_spatialrefsys, "ellipsoidacronym")
                            elem.text = ellipsoidacronym

            # Pfad zu Formularen auf plugin-Verzeichnis setzen -----------------------------------------

            formspath = os.path.join(pluginDirectory("qkan"), "forms")
            for tag_maplayer in root.findall(".//projectlayers/maplayer"):
                tag_editform = tag_maplayer.find("./editform")
                if tag_editform and tag_editform.text:
                    dateiname = os.path.basename(tag_editform.text)
                    #if dateiname in QKAN_FORMS:
                        # Nur QKan-Tabellen bearbeiten
                    #    tag_editform.text = os.path.join(formspath, dateiname)

            # Zoom für Kartenfenster einstellen -------------------------------------------------------
            if len(zoom) == 0 or any([x is None for x in zoom]):
                zoom = [0.0, 100.0, 0.0, 100.0]

            for extent in root.findall(".//mapcanvas/extent"):
                for idx, name in enumerate(["xmin", "ymin", "xmax", "ymax"]):
                    element = extent.find(f"./{name}")
                    if element is not None:
                        element.text = "{:.3f}".format(zoom[idx])

            # Projektionssystem anpassen --------------------------------------------------------------

            for tag_spatialrefsys in root.findall(".//projectCrs/spatialrefsys"):
                tag_spatialrefsys.clear()

                elem = ET.SubElement(tag_spatialrefsys, "proj4")
                elem.text = proj4text
                elem = ET.SubElement(tag_spatialrefsys, "srid")
                elem.text = "{}".format(srid)
                elem = ET.SubElement(tag_spatialrefsys, "authid")
                elem.text = "EPSG: {}".format(srid)
                elem = ET.SubElement(tag_spatialrefsys, "description")
                elem.text = description
                elem = ET.SubElement(tag_spatialrefsys, "projectionacronym")
                elem.text = projectionacronym
                if ellipsoidacronym is not None:
                    elem = ET.SubElement(tag_spatialrefsys, "ellipsoidacronym")
                    elem.text = ellipsoidacronym

            # Pfad zur QKan-Datenbank anpassen

            for tag_datasource in root.findall(".//projectlayers/maplayer/datasource"):
                text = tag_datasource.text

                if not text:
                    continue

                tag_datasource.text = (
                    "dbname='" + datasource + "' " + text[text.find("table=") :]
                )

            qgsxml.write(self.projectfile)  # writing modified project file
            logger.debug("Projektdatei: {}".format(self.projectfile))
            # logger.debug(u'encoded string: {}'.format(tex))
        return True

    def subareas(self) -> None:
        pass  # in QKan nicht verwaltet

    def symbols(self) -> None:
        pass  # in QKan nicht verwaltet

    def coverages(self) -> None:
        pass  # in QKan nicht verwaltet

    def evaporation(self) -> None:
        pass  # in QKan nicht verwaltet

    def raingages(self) -> None:
        pass  # in QKan nicht verwaltet

    def infiltration(self) -> None:
        pass  # in QKan nicht verwaltet

    def pollutants(self) -> None:
        pass  # in QKan nicht verwaltet

    def landuses(self) -> None:
        pass  # in QKan nicht verwaltet

    def loadings(self) -> None:
        pass  # in QKan nicht verwaltet

    def buildup(self) -> None:
        pass  # in QKan nicht verwaltet

    def washoff(self) -> None:
        pass  # in QKan nicht verwaltet

    def timeseries(self) -> None:
        pass  # in QKan nicht verwaltet

    def report(self) -> None:
        pass  # in QKan nicht verwaltet

    def tags(self) -> None:
        pass  # in QKan nicht verwaltet

    def map(self) -> None:
        pass  # in QKan nicht verwaltet


#def importKanaldaten(
#    inpfile: str, database_qkan: str, projectfile: str, epsg: int = 25832
#) -> bool:
#    """Ruft die Klasse SWMM zur Verarbeitung der Daten auf"""

 #   if not os.path.exists(inpfile):
  #      return False

   # swmm = SWMM(
    #    inpfile,
     #   database_qkan,
   #     projectfile,
   #     offset=[0.0, 0.0],
   #     epsg=epsg,
   #     dbtyp="SpatiaLite",
   # )

    #if not swmm.connected:
    #    return False

    #swmm.read()

   # print(swmm.title)
    # print(swmm.options)        # wird nicht benötigt

    # from pprint import pprint

    # pprint(swmm.data)

    # --------------------------------------------------------------------------
    # Datenbankverbindungen schliessen

  #  template_project = Path(pluginDirectory("qkan")) / "templates" / "Projekt.qgs"
  #  qgsadapt(database_qkan, swmm.db_qkan, projectfile, str(template_project), epsg)

    # noinspection PyArgumentList
   # project = QgsProject.instance()
   # project.read(projectfile)
   # project.reloadAllLayers()

    # swmm.writeProjektfile()

   # del swmm

   # return True


if __name__ == "__main__" or __name__ == "console":
    # importKanaldaten("tutorial.inp", "sqlcommands.sql")
    pass
