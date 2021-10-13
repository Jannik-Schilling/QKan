import logging

from qkan.database.dbfunc import DBConnection

VERSION = "3.2.16"

logger = logging.getLogger("QKan.database.migrations")


def run(dbcon: DBConnection) -> bool:
    """Ergänze Tabellen für XML Import"""

    # Tabelle mit SQL-Abfragen

    sql = """CREATE TABLE IF NOT EXISTS haltungen_untersucht(
             pk INTEGER PRIMARY KEY,
             haltnam TEXT,
             schoben TEXT,
             schunten TEXT,
             hoehe REAL,
             breite REAL,
             laenge REAL,
             kommentar TEXT,
             createdat TEXT DEFAULT (strftime('%d.%m.%Y %H:%M:%S','now','localtime')),
             baujahr INTEGER,
             untersuchtag TEXT,
             untersucher TEXT,
             wetter INTEGER DEFAULT 0,
             bewertungsart INTEGER DEFAULT 0,
             bewertungstag TEXT,
             xschob REAL,
             yschob REAL,
             xschun REAL,
             yschun REAL)"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = f"""CREATE VIEW IF NOT EXISTS haltungen_untersucht_data AS
                  SELECT 
                    haltnam, schoben, schunten, 
                    hoehe, breite, laenge,
                    kommentar, createdat, baujahr, untersuchtag, untersucher, wetter, bewertungsart, bewertungstag,
                    xschob, yschob, xschun, yschun
                  FROM haltungen_untersucht;"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = f"""CREATE TRIGGER IF NOT EXISTS haltungen_untersucht_insert_clipboard
                    INSTEAD OF INSERT ON haltungen_untersucht_data FOR EACH ROW
                  BEGIN
                    INSERT INTO haltungen_untersucht
                      (haltnam, schoben, schunten,
                       hoehe, breite, laenge,
                       kommentar, createdat, baujahr,  
                       geom, untersuchtag, untersucher, wetter, bewertungsart, bewertungstag)
                    SELECT 
                      new.haltnam, new.schoben, new.schunten, 
                      CASE WHEN new.hoehe > 20 THEN new.hoehe/1000 ELSE new.hoehe END, 
                      CASE WHEN new.breite > 20 THEN new.breite/1000 ELSE new.breite END,
                      new.laenge, new.kommentar, 
                      coalesce(new.createdat, strftime('%d.%m.%Y %H:%M:%S','now','localtime')), new.baujahr,
                      MakeLine(
                        coalesce(
                          MakePoint(new.xschob, new.yschob, {epsg}),
                          schob.geop
                        ), 
                        coalesce(
                          MakePoint(new.xschun, new.yschun, {epsg}),
                          schun.geop
                        )
                      ), new.untersuchtag, new.untersucher, new.wetter, new.bewertungsart, new.bewertungstag
                    FROM
                      schaechte AS schob,
                      schaechte AS schun
                    WHERE schob.schnam = new.schoben AND schun.schnam = new.schunten;
                  END;"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = """CREATE TABLE IF NOT EXISTS Untersuchdat_haltung (
            pk INTEGER PRIMARY KEY,
            untersuchhal TEXT,
            untersuchrichtung TEXT,
            schoben TEXT, 
            schunten TEXT,
            id INTEGER,
            videozaehler INTEGER,
            inspektionslaenge REAL,
            station REAL,
            timecode INTEGER,
            video_offset REAL,
            kuerzel TEXT,
            charakt1 TEXT,
            charakt2 TEXT,
            quantnr1 REAL, 
            quantnr2 REAL, 
            streckenschaden TEXT,
            streckenschaden_lfdnr INTEGER,
            pos_von INTEGER, 
            pos_bis INTEGER,
            foto_dateiname TEXT,
            film_dateiname TEXT,
            ordner_bild TEXT,
            ordner_video TEXT,
            richtung TEXT,
            createdat TEXT DEFAULT (strftime('%d.%m.%Y %H:%M:%S','now','localtime'))
        )"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = f"""CREATE VIEW IF NOT EXISTS untersuchdat_haltung_data AS 
                      SELECT
                        untersuchhal, untersuchrichtung, schoben, schunten, id, videozaehler, inspektionslaenge, station, timecode, video_offset, kuerzel, 
                            charakt1, charakt2, quantnr1, quantnr2, streckenschaden, streckenschaden_lfdnr, pos_von, pos_bis, foto_dateiname, film_dateiname, ordner_bild, ordner_video, richtung, createdat
                      FROM Untersuchdat_haltung;"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = f"""CREATE TRIGGER IF NOT EXISTS Untersuchdat_haltung_insert_clipboard
                        INSTEAD OF INSERT ON untersuchdat_haltung_data FOR EACH ROW
                      BEGIN
                        INSERT INTO untersuchdat_haltung
                          (untersuchhal, untersuchrichtung, schoben, schunten, id, videozaehler, inspektionslaenge, station, timecode, video_offset, kuerzel, 
                            charakt1, charakt2, quantnr1, quantnr2, streckenschaden, streckenschaden_lfdnr, pos_von, pos_bis, foto_dateiname, film_dateiname, ordner_bild, ordner_video, richtung, createdat, geom)
                        SELECT
                          new.untersuchhal, new.untersuchrichtung, new.schoben, new.schunten, 
                            new.id, new.videozaehler, new.inspektionslaenge , new.station, new.timecode, new.video_offset, new.kuerzel, 
                            new.charakt1, new.charakt2, new.quantnr1, new.quantnr2, new.streckenschaden, new.streckenschaden_lfdnr, new.pos_von, new.pos_bis, new.foto_dateiname, new.film_dateiname, new.ordner_bild, new.ordner_video, new.richtung,
                            coalesce(new.createdat, strftime('%d.%m.%Y %H:%M:%S','now','localtime')),
                            CASE
                            WHEN (new.untersuchrichtung = "in Fließrichtung" AND ST_X(schun.geop)-ST_X(schob.geop) >=0 AND ST_Y(schun.geop)-ST_Y(schob.geop) >= 0 AND new.richtung = "fließrichtung" AND new.schoben <> haltung.schoben AND new.schunten <> haltung.schunten) OR
                                    (new.untersuchrichtung = "in Fließrichtung" AND ST_X(schun.geop)-ST_X(schob.geop) < 0 AND ST_Y(schun.geop)-ST_Y(schob.geop) >= 0 AND new.richtung = "fließrichtung" AND new.schoben <> haltung.schoben AND new.schunten <> haltung.schunten) OR
                                    (new.untersuchrichtung = "in Fließrichtung" AND ST_X(schun.geop)-ST_X(schob.geop) >=0 AND ST_Y(schun.geop)-ST_Y(schob.geop) >= 0 AND new.richtung = "untersuchungsrichtung" AND new.schoben <> haltung.schoben AND new.schunten <> haltung.schunten) OR
                                    (new.untersuchrichtung = "in Fließrichtung" AND ST_X(schun.geop)-ST_X(schob.geop) < 0 AND ST_Y(schun.geop)-ST_Y(schob.geop) >= 0 AND new.richtung = "untersuchungsrichtung" AND new.schoben <> haltung.schoben AND new.schunten <> haltung.schunten) OR
                                    (new.untersuchrichtung = "in Fließrichtung" AND ST_X(schun.geop)-ST_X(schob.geop) >=0 AND ST_Y(schun.geop)-ST_Y(schob.geop) < 0 AND new.richtung = "fließrichtung" AND new.schoben = haltung.schoben AND new.schunten = haltung.schunten) OR
                                    (new.untersuchrichtung = "in Fließrichtung" AND ST_X(schun.geop)-ST_X(schob.geop) < 0 AND ST_Y(schun.geop)-ST_Y(schob.geop) < 0 AND new.richtung = "fließrichtung" AND new.schoben = haltung.schoben AND new.schunten = haltung.schunten) OR
                                    (new.untersuchrichtung = "in Fließrichtung" AND ST_X(schun.geop)-ST_X(schob.geop) >=0 AND ST_Y(schun.geop)-ST_Y(schob.geop) < 0 AND new.richtung = "untersuchungsrichtung" AND new.schoben = haltung.schoben AND new.schunten = haltung.schunten) OR
                                    (new.untersuchrichtung = "in Fließrichtung" AND ST_X(schun.geop)-ST_X(schob.geop) < 0 AND ST_Y(schun.geop)-ST_Y(schob.geop) < 0 AND new.richtung = "untersuchungsrichtung" AND new.schoben = haltung.schoben AND new.schunten = haltung.schunten)

                            THEN 
                            MakeLine(
                                coalesce(
                                MakePoint((ST_X(schob.geop)+(new.station*MAX(haltung.laenge/new.inspektionslaenge,1)*(ST_X(schun.geop)-ST_X(schob.geop))/haltung.laenge)),(ST_Y(schob.geop)+(new.station*MAX(haltung.laenge/new.inspektionslaenge,1)*(ST_Y(schun.geop)-ST_Y(schob.geop))/haltung.laenge)), {epsg}),
                                    schob.geop
                                ), 
                                coalesce(
                                MakePoint((ST_X(schob.geop)+(new.station*MAX(haltung.laenge/new.inspektionslaenge,1)*(ST_X(schun.geop)-ST_X(schob.geop))/haltung.laenge))+2*((-1)/sqrt(1+(((ST_X(schun.geop)-ST_X(schob.geop))/(ST_Y(schun.geop)-ST_Y(schob.geop))))*((ST_X(schun.geop)-ST_X(schob.geop))/(ST_Y(schun.geop)-ST_Y(schob.geop))))), (ST_Y(schob.geop)+(new.station*MAX(haltung.laenge/new.inspektionslaenge,1)*(ST_Y(schun.geop)-ST_Y(schob.geop))/haltung.laenge))+2*(((ST_X(schun.geop)-ST_X(schob.geop))/(ST_Y(schun.geop)-ST_Y(schob.geop)))/sqrt(1+(((ST_X(schun.geop)-ST_X(schob.geop))/(ST_Y(schun.geop)-ST_Y(schob.geop))))*((ST_X(schun.geop)-ST_X(schob.geop))/(ST_Y(schun.geop)-ST_Y(schob.geop))))), {epsg}),
                                    schun.geop
                                )
                            )
                            WHEN (new.untersuchrichtung = "in Fließrichtung" AND ST_X(schun.geop)-ST_X(schob.geop) >=0 AND ST_Y(schun.geop)-ST_Y(schob.geop) < 0 AND new.richtung = "fließrichtung" AND new.schoben <> haltung.schoben AND new.schunten <> haltung.schunten) OR
                                    (new.untersuchrichtung = "in Fließrichtung" AND ST_X(schun.geop)-ST_X(schob.geop) < 0 AND ST_Y(schun.geop)-ST_Y(schob.geop) < 0 AND new.richtung = "fließrichtung" AND new.schoben <> haltung.schoben AND new.schunten <> haltung.schunten) OR
                                    (new.untersuchrichtung = "in Fließrichtung" AND ST_X(schun.geop)-ST_X(schob.geop) >=0 AND ST_Y(schun.geop)-ST_Y(schob.geop) < 0 AND new.richtung = "untersuchungsrichtung" AND new.schoben <> haltung.schoben AND new.schunten <> haltung.schunten) OR
                                    (new.untersuchrichtung = "in Fließrichtung" AND ST_X(schun.geop)-ST_X(schob.geop) < 0 AND ST_Y(schun.geop)-ST_Y(schob.geop) < 0 AND new.richtung = "untersuchungsrichtung" AND new.schoben <> haltung.schoben AND new.schunten <> haltung.schunten) OR
                                    (new.untersuchrichtung = "in Fließrichtung" AND ST_X(schun.geop)-ST_X(schob.geop) >=0 AND ST_Y(schun.geop)-ST_Y(schob.geop) >= 0 AND new.richtung = "fließrichtung" AND new.schoben = haltung.schoben AND new.schunten = haltung.schunten) OR
                                    (new.untersuchrichtung = "in Fließrichtung" AND ST_X(schun.geop)-ST_X(schob.geop) < 0 AND ST_Y(schun.geop)-ST_Y(schob.geop) >= 0 AND new.richtung = "fließrichtung" AND new.schoben = haltung.schoben AND new.schunten = haltung.schunten) OR
                                    (new.untersuchrichtung = "in Fließrichtung" AND ST_X(schun.geop)-ST_X(schob.geop) >=0 AND ST_Y(schun.geop)-ST_Y(schob.geop) >= 0 AND new.richtung = "untersuchungsrichtung" AND new.schoben = haltung.schoben AND new.schunten = haltung.schunten) OR
                                    (new.untersuchrichtung = "in Fließrichtung" AND ST_X(schun.geop)-ST_X(schob.geop) < 0 AND ST_Y(schun.geop)-ST_Y(schob.geop) >= 0 AND new.richtung = "untersuchungsrichtung" AND new.schoben = haltung.schoben AND new.schunten = haltung.schunten)

                            THEN 
                            MakeLine(
                                coalesce(
                                MakePoint((ST_X(schob.geop)+(new.station*MAX(haltung.laenge/new.inspektionslaenge,1)*(ST_X(schun.geop)-ST_X(schob.geop))/haltung.laenge)),(ST_Y(schob.geop)+(new.station*MAX(haltung.laenge/new.inspektionslaenge,1)*(ST_Y(schun.geop)-ST_Y(schob.geop))/haltung.laenge)), {epsg}),
                                    schob.geop
                                ), 
                                coalesce(
                                MakePoint((ST_X(schob.geop)+(new.station*MAX(haltung.laenge/new.inspektionslaenge,1)*(ST_X(schun.geop)-ST_X(schob.geop))/haltung.laenge))-2*((-1)/sqrt(1+(((ST_X(schun.geop)-ST_X(schob.geop))/(ST_Y(schun.geop)-ST_Y(schob.geop))))*((ST_X(schun.geop)-ST_X(schob.geop))/(ST_Y(schun.geop)-ST_Y(schob.geop))))), (ST_Y(schob.geop)+(new.station*MAX(haltung.laenge/new.inspektionslaenge,1)*(ST_Y(schun.geop)-ST_Y(schob.geop))/haltung.laenge))-2*(((ST_X(schun.geop)-ST_X(schob.geop))/(ST_Y(schun.geop)-ST_Y(schob.geop)))/sqrt(1+(((ST_X(schun.geop)-ST_X(schob.geop))/(ST_Y(schun.geop)-ST_Y(schob.geop))))*((ST_X(schun.geop)-ST_X(schob.geop))/(ST_Y(schun.geop)-ST_Y(schob.geop))))), {epsg}),
                                    schun.geop
                                )
                            )
                            WHEN (new.untersuchrichtung = "gegen Fließrichtung" AND ST_X(schob.geop)-ST_X(schun.geop)  >=0 AND ST_Y(schob.geop)-ST_Y(schun.geop) >= 0 AND new.richtung = "fließrichtung" AND new.schoben <> haltung.schoben AND new.schunten <> haltung.schunten) OR
                                    (new.untersuchrichtung = "gegen Fließrichtung" AND ST_X(schob.geop)-ST_X(schun.geop) <0 AND ST_Y(schob.geop)-ST_Y(schun.geop) >= 0 AND new.richtung = "fließrichtung" AND new.schoben <> haltung.schoben AND new.schunten <> haltung.schunten) OR
                                    (new.untersuchrichtung = "gegen Fließrichtung" AND ST_X(schob.geop)-ST_X(schun.geop) < 0 AND ST_Y(schob.geop)-ST_Y(schun.geop) < 0 AND new.richtung = "untersuchungsrichtung" AND new.schoben <> haltung.schoben AND new.schunten <> haltung.schunten) OR
                                    (new.untersuchrichtung = "gegen Fließrichtung" AND ST_X(schob.geop)-ST_X(schun.geop) >=0 AND ST_Y(schob.geop)-ST_Y(schun.geop) < 0 AND new.richtung = "untersuchungsrichtung" AND new.schoben <> haltung.schoben AND new.schunten <> haltung.schunten) OR
                                    (new.untersuchrichtung = "gegen Fließrichtung" AND ST_X(schob.geop)-ST_X(schun.geop)  >=0 AND ST_Y(schob.geop)-ST_Y(schun.geop) >= 0 AND new.richtung = "fließrichtung" AND new.schoben = haltung.schoben AND new.schunten = haltung.schunten) OR
                                    (new.untersuchrichtung = "gegen Fließrichtung" AND ST_X(schob.geop)-ST_X(schun.geop) <0 AND ST_Y(schob.geop)-ST_Y(schun.geop) >= 0 AND new.richtung = "fließrichtung" AND new.schoben = haltung.schoben AND new.schunten = haltung.schunten) OR
                                    (new.untersuchrichtung = "gegen Fließrichtung" AND ST_X(schob.geop)-ST_X(schun.geop) < 0 AND ST_Y(schob.geop)-ST_Y(schun.geop) < 0 AND new.richtung = "untersuchungsrichtung" AND new.schoben = haltung.schoben AND new.schunten = haltung.schunten) OR
                                    (new.untersuchrichtung = "gegen Fließrichtung" AND ST_X(schob.geop)-ST_X(schun.geop) >=0 AND ST_Y(schob.geop)-ST_Y(schun.geop) < 0 AND new.richtung = "untersuchungsrichtung" AND new.schoben = haltung.schoben AND new.schunten = haltung.schunten)

                            THEN 
                            MakeLine(
                                coalesce(
                                MakePoint((ST_X(schun.geop)+(new.station*MAX(haltung.laenge/new.inspektionslaenge,1)*(ST_X(schob.geop)-ST_X(schun.geop))/haltung.laenge)), (ST_Y(schun.geop)+(new.station*MAX(haltung.laenge/new.inspektionslaenge,1)*(ST_Y(schob.geop)-ST_Y(schun.geop))/haltung.laenge)), {epsg}),
                                    schob.geop
                                ), 
                                coalesce(
                                MakePoint((ST_X(schun.geop)+(new.station*MAX(haltung.laenge/new.inspektionslaenge,1)*(ST_X(schob.geop)-ST_X(schun.geop))/haltung.laenge))-2*((-1)/sqrt(1+(((ST_X(schob.geop)-ST_X(schun.geop))/(ST_Y(schob.geop)-ST_Y(schun.geop))))*((ST_X(schob.geop)-ST_X(schun.geop))/(ST_Y(schob.geop)-ST_Y(schun.geop))))), (ST_Y(schun.geop)+(new.station*MAX(haltung.laenge/new.inspektionslaenge,1)*(ST_Y(schob.geop)-ST_Y(schun.geop))/haltung.laenge))-2*(((ST_X(schob.geop)-ST_X(schun.geop))/(ST_Y(schob.geop)-ST_Y(schun.geop)))/sqrt(1+(((ST_X(schob.geop)-ST_X(schun.geop))/(ST_Y(schob.geop)-ST_Y(schun.geop))))*((ST_X(schob.geop)-ST_X(schun.geop))/(ST_Y(schob.geop)-ST_Y(schun.geop))))), {epsg}),
                                    schun.geop
                                )
                            )
                            WHEN (new.untersuchrichtung = "gegen Fließrichtung" AND ST_X(schob.geop)-ST_X(schun.geop) < 0 AND ST_Y(schob.geop)-ST_Y(schun.geop) < 0 AND new.richtung = "fließrichtung" AND new.schoben <> haltung.schoben AND new.schunten <> haltung.schunten) OR 
                                    (new.untersuchrichtung = "gegen Fließrichtung" AND ST_X(schob.geop)-ST_X(schun.geop) >=0 AND ST_Y(schob.geop)-ST_Y(schun.geop) < 0 AND new.richtung = "fließrichtung" AND new.schoben <> haltung.schoben AND new.schunten <> haltung.schunten) OR
                                    (new.untersuchrichtung = "gegen Fließrichtung" AND ST_X(schob.geop)-ST_X(schun.geop)  >=0 AND ST_Y(schob.geop)-ST_Y(schun.geop) >= 0 AND new.richtung = "untersuchungsrichtung" AND new.schoben <> haltung.schoben AND new.schunten <> haltung.schunten) OR
                                    (new.untersuchrichtung = "gegen Fließrichtung" AND ST_X(schob.geop)-ST_X(schun.geop) <0 AND ST_Y(schob.geop)-ST_Y(schun.geop) >= 0 AND new.richtung = "untersuchungsrichtung" AND new.schoben <> haltung.schoben AND new.schunten <> haltung.schunten) OR
                                    (new.untersuchrichtung = "gegen Fließrichtung" AND ST_X(schob.geop)-ST_X(schun.geop) < 0 AND ST_Y(schob.geop)-ST_Y(schun.geop) < 0 AND new.richtung = "fließrichtung" AND new.schoben = haltung.schoben AND new.schunten = haltung.schunten) OR 
                                    (new.untersuchrichtung = "gegen Fließrichtung" AND ST_X(schob.geop)-ST_X(schun.geop) >=0 AND ST_Y(schob.geop)-ST_Y(schun.geop) < 0 AND new.richtung = "fließrichtung" AND new.schoben = haltung.schoben AND new.schunten = haltung.schunten) OR
                                    (new.untersuchrichtung = "gegen Fließrichtung" AND ST_X(schob.geop)-ST_X(schun.geop)  >=0 AND ST_Y(schob.geop)-ST_Y(schun.geop) >= 0 AND new.richtung = "untersuchungsrichtung" AND new.schoben = haltung.schoben AND new.schunten = haltung.schunten) OR
                                    (new.untersuchrichtung = "gegen Fließrichtung" AND ST_X(schob.geop)-ST_X(schun.geop) <0 AND ST_Y(schob.geop)-ST_Y(schun.geop) >= 0 AND new.richtung = "untersuchungsrichtung" AND new.schoben = haltung.schoben AND new.schunten = haltung.schunten)

                            THEN 
                            MakeLine(
                                coalesce(
                                MakePoint((ST_X(schun.geop)+(new.station*MAX(haltung.laenge/new.inspektionslaenge,1)*(ST_X(schob.geop)-ST_X(schun.geop))/haltung.laenge)), (ST_Y(schun.geop)+(new.station*MAX(haltung.laenge/new.inspektionslaenge,1)*(ST_Y(schob.geop)-ST_Y(schun.geop))/haltung.laenge)), {epsg}),
                                    schob.geop
                                ), 
                                coalesce(
                                MakePoint((ST_X(schun.geop)+(new.station*MAX(haltung.laenge/new.inspektionslaenge,1)*(ST_X(schob.geop)-ST_X(schun.geop))/haltung.laenge))+2*((-1)/sqrt(1+(((ST_X(schob.geop)-ST_X(schun.geop))/(ST_Y(schob.geop)-ST_Y(schun.geop))))*((ST_X(schob.geop)-ST_X(schun.geop))/(ST_Y(schob.geop)-ST_Y(schun.geop))))), (ST_Y(schun.geop)+(new.station*MAX(haltung.laenge/new.inspektionslaenge,1)*(ST_Y(schob.geop)-ST_Y(schun.geop))/haltung.laenge))+2*(((ST_X(schob.geop)-ST_X(schun.geop))/(ST_Y(schob.geop)-ST_Y(schun.geop)))/sqrt(1+(((ST_X(schob.geop)-ST_X(schun.geop))/(ST_Y(schob.geop)-ST_Y(schun.geop))))*((ST_X(schob.geop)-ST_X(schun.geop))/(ST_Y(schob.geop)-ST_Y(schun.geop))))), {epsg}),
                                    schun.geop
                                )
                            )
                            ELSE NULL
                            END
                        FROM
                        schaechte AS schob,
                        schaechte AS schun,
                        haltungen AS haltung
                        WHERE schob.schnam = new.schoben AND schun.schnam = new.schunten AND haltung.haltnam = new.untersuchhal;
                      END"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = f"""CREATE VIEW IF NOT EXISTS untersuchdat_haltung_data AS 
                          SELECT
                            untersuchhal, untersuchrichtung, schoben, schunten, id, videozaehler, station, timecode, video_offset, kuerzel, 
                            charakt1, charakt2, quantnr1, quantnr2, streckenschaden, streckenschaden_lfdnr, pos_von, pos_bis, foto_dateiname, film_dateiname, ordner_bild, ordner_video, richtung, createdat
                          FROM untersuchdat_haltung;"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = f"""CREATE TRIGGER IF NOT EXISTS untersuchdat_haltung_insert_clipboard
                            INSTEAD OF INSERT ON untersuchdat_haltung_data FOR EACH ROW
                          BEGIN
                            INSERT INTO untersuchdat_haltung
                              (untersuchhal, untersuchrichtung, schoben, schunten, id, videozaehler, inspektionslaenge, station, timecode, video_offset, kuerzel, 
                            charakt1, charakt2, quantnr1, quantnr2, streckenschaden, streckenschaden_lfdnr, pos_von, pos_bis, foto_dateiname, film_dateiname, ordner_bild, ordner_video, richtung, createdat)
                            VALUES (
                              new.untersuchhal, new.untersuchrichtung, new.schoben, new.schunten, new.id, new.videozaehler, new.inspektionslaenge, new.station, new.timecode, new.video_offset, new.kuerzel, 
                            new.charakt1, new.charakt2, new.quantnr1, new.quantnr2, new.streckenschaden, new.streckenschaden_lfdnr, new.pos_von, new.pos_bis, new.foto_dateiname, new.film_dateiname, new.ordner_bild, new.ordner_video, new.richtung, new.createdat
                            );
                          END"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = """CREATE TABLE IF NOT EXISTS anschlussleitungen (
            pk INTEGER PRIMARY KEY,
            leitnam TEXT,
            schoben TEXT,
            schunten TEXT,
            hoehe REAL,
            breite REAL,
            laenge REAL,
            sohleoben REAL,
            sohleunten REAL,
            deckeloben REAL,
            deckelunten REAL,
            teilgebiet TEXT,
            qzu REAL,
            profilnam TEXT DEFAULT 'Kreisquerschnitt',
            entwart TEXT DEFAULT 'Regenwasser',
            rohrtyp TEXT,
            ks REAL DEFAULT 1.5,
            simstatus TEXT DEFAULT 'vorhanden',
            kommentar TEXT,
            createdat TEXT DEFAULT (strftime('%d.%m.%Y %H:%M:%S','now','localtime')),
            xschob REAL,
            yschob REAL,
            xschun REAL,
            yschun REAL)"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = f"""CREATE VIEW IF NOT EXISTS anschlussleitungen_data AS
                  SELECT 
                    leitnam, schoben, schunten, 
                    hoehe, breite, laenge, 
                    sohleoben, sohleunten, 
                    deckeloben, deckelunten, 
                    teilgebiet, qzu, profilnam, 
                    entwart, rohrtyp, ks,
                    simstatus, kommentar, createdat, 
                    xschob, yschob, xschun, yschun
                  FROM anschlussleitungen;"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = f"""CREATE TRIGGER IF NOT EXISTS anschlussleitungen_insert_clipboard
                    INSTEAD OF INSERT ON anschlussleitungen_data FOR EACH ROW
                  BEGIN
                    INSERT INTO anschlussleitungen
                      (leitnam, schoben, schunten,
                       hoehe, breite, laenge,
                       sohleoben, sohleunten,
                       deckeloben, deckelunten, 
                       teilgebiet, qzu, profilnam, 
                       entwart, rohrtyp, ks,
                       simstatus, kommentar, createdat,  
                       geom)
                    VALUES( 
                      new.leitnam, new.schoben, new.schunten, 
                      CASE WHEN new.hoehe > 20 THEN new.hoehe/1000 ELSE new.hoehe END, 
                      CASE WHEN new.breite > 20 THEN new.breite/1000 ELSE new.breite END,
                      new.laenge, 
                      new.sohleoben, new.sohleunten, 
                      new.deckeloben, new.deckelunten, 
                      new.teilgebiet, new.qzu, coalesce(new.profilnam, 'Kreisquerschnitt'), 
                      coalesce(new.entwart, 'Regenwasser'), new.rohrtyp, coalesce(new.ks, 1.5), 
                      coalesce(new.simstatus, 'vorhanden'), new.kommentar, 
                      coalesce(new.createdat, strftime('%d.%m.%Y %H:%M:%S','now','localtime')), 
                      MakeLine(
                          MakePoint(new.xschob, new.yschob, {epsg})
                          , 
                          MakePoint(new.xschun, new.yschun, {epsg})
                      ))
                    ;
                  END;"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = """CREATE TABLE IF NOT EXISTS schaechte_untersucht (
                pk INTEGER PRIMARY KEY,
                schnam TEXT, 
                durchm REAL,
                kommentar TEXT,
                createdat TEXT DEFAULT (strftime('%d.%m.%Y %H:%M:%S','now','localtime')),
                baujahr INTEGER,
                untersuchtag TEXT, 
                untersucher TEXT, 
                wetter INTEGER DEFAULT 0, 
                bewertungsart INTEGER DEFAULT 0, 
                bewertungstag TEXT
                )"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = f"""CREATE VIEW IF NOT EXISTS schaechte_untersucht_data AS 
                      SELECT
                        schnam, durchm, 
                        kommentar, createdat, baujahr, untersuchtag, untersucher, wetter, bewertungsart, bewertungstag
                      FROM schaechte_untersucht;"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = f"""CREATE TRIGGER IF NOT EXISTS schaechte_untersucht_insert_clipboard
                        INSTEAD OF INSERT ON schaechte_untersucht_data FOR EACH ROW
                      BEGIN
                        INSERT INTO schaechte_untersucht
                          (schnam, durchm,  
                           kommentar, createdat, baujahr,
                           geop, untersuchtag, untersucher, wetter, bewertungsart, bewertungstag)
                        SELECT
                          new.schnam,
                          CASE WHEN new.durchm > 200 THEN new.durchm/1000 ELSE new.durchm END, 
                          new.kommentar, coalesce(new.createdat, strftime('%d.%m.%Y %H:%M:%S','now','localtime')), new.baujahr,
                          sch.geop,
                          new.untersuchtag, new.untersucher, new.wetter, new.bewertungsart, new.bewertungstag
                        FROM
                          schaechte AS sch
                          WHERE sch.schnam = new.schnam;
                      END"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = """CREATE TABLE IF NOT EXISTS Untersuchdat_schacht (
            pk INTEGER PRIMARY KEY,
            untersuchsch TEXT,
            id INTEGER,
            videozaehler INTEGER,
            timecode INTEGER,
            kuerzel TEXT,
            charakt1 TEXT,
            charakt2 TEXT,
            quantnr1 REAL,
            quantnr2 REAL,
            streckenschaden TEXT,
            streckenschaden_lfdnr INTEGER,
            pos_von INTEGER,
            pos_bis INTEGER,
            vertikale_lage INTEGER,
            inspektionslaenge INTEGER,
            bereich TEXT,
            foto_dateiname TEXT,
            ordner TEXT,
            createdat TEXT DEFAULT (strftime('%d.%m.%Y %H:%M:%S','now','localtime'))
            )"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = f"""CREATE VIEW IF NOT EXISTS untersuchdat_schacht_data AS 
                  SELECT
                    untersuchsch, id, videozaehler, timecode, kuerzel, 
                        charakt1, charakt2, quantnr1, quantnr2, streckenschaden,streckenschaden_lfdnr, pos_von, pos_bis, vertikale_lage, inspektionslaenge, bereich, foto_dateiname, ordner, createdat 
                  FROM Untersuchdat_schacht;"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = f"""CREATE TRIGGER IF NOT EXISTS Untersuchdat_schacht_insert_clipboard
                    INSTEAD OF INSERT ON untersuchdat_schacht_data FOR EACH ROW
                  BEGIN
                    INSERT INTO Untersuchdat_schacht
                      (untersuchsch, id, videozaehler, timecode, kuerzel, 
                        charakt1, charakt2, quantnr1, quantnr2, streckenschaden, streckenschaden_lfdnr, pos_von, pos_bis, vertikale_lage, inspektionslaenge, bereich, foto_dateiname, ordner, createdat, geop)
                    SELECT 
                      new.untersuchsch, new.id, new.videozaehler, new.timecode, new.kuerzel, 
                        new.charakt1, new.charakt2, new.quantnr1, new.quantnr2, new.streckenschaden, new.streckenschaden_lfdnr, new.pos_von, new.pos_bis, new.vertikale_lage, new.inspektionslaenge,
                        new.bereich, new.foto_dateiname, new.ordner, coalesce(new.createdat, strftime('%d.%m.%Y %H:%M:%S','now','localtime')), sch.geop
                    FROM
                        schaechte AS sch
                        WHERE sch.schnam = new.untersuchsch;
                  END"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = f"""CREATE VIEW IF NOT EXISTS untersuchdat_schacht_data AS 
                      SELECT
                        untersuchsch, id, videozaehler, timecode, kuerzel, 
                        charakt1, charakt2, streckenschaden, streckenschaden_lfdnr, pos_von, pos_bis, vertikale_lage, inspektionslaenge, bereich, foto_dateiname, ordner, createdat
                      FROM untersuchdat_schacht;"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    sql = f"""CREATE TRIGGER IF NOT EXISTS untersuchdat_schacht_insert_clipboard
                        INSTEAD OF INSERT ON untersuchdat_schacht_data FOR EACH ROW
                      BEGIN
                        INSERT INTO untersuchdat_schacht
                          (untersuchsch, id, videozaehler, timecode, kuerzel, 
                        charakt1, charakt2, quantnr1, quantnr2, streckenschaden, streckenschaden_lfdnr, pos_von, pos_bis, vertikale_lage, inspektionslaenge, bereich, foto_dateiname, ordner, createdat)
                        VALUES (
                          new.untersuchsch, new.id, new.videozaehler, new.timecode, new.kuerzel, 
                        new.charakt1, new.charakt2, new.quantnr1, new.quantnr2, new.streckenschaden, new.streckenschaden_lfdnr, new.pos_von, new.pos_bis, new.vertikale_lage, new.inspektionslaenge,
                        new.bereich, new.foto_dateiname, new.ordner, coalesce(new.createdat, strftime('%d.%m.%Y %H:%M:%S','now','localtime'))
                        );
                      END"""

    if not dbcon.sql(sql):
        logger.debug(f"Fehler bei Migration zu Version {VERSION}")
        return False

    dbcon.commit()
    return True
