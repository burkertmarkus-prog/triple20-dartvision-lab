# Triple20 DartVision Labor

Eigenständige Testumgebung für die spätere automatische Dart-Erkennung.

## Sicherheitsgrenze

- keine Verbindung zur produktiven Triple20-App
- kein Supabase und keine Zugangsdaten
- keine Pushnachrichten
- kein Service Worker oder App-Cache
- Testdaten bleiben im lokalen Browser
- dieses Verzeichnis wird in ein eigenes GitHub-Repository hochgeladen

## Aktueller Stand

- vier virtuelle Boards
- 301 oder 501
- Best of 1, 3 oder 5
- getrennte Spielernamen, Restpunkte und Legs
- Dart-für-Dart-Eingabe mit Feld und Ring
- automatische Berechnung der laufenden Aufnahme
- Double-Out, Bust und automatischer Wechsel nach drei Darts
- einzelne Darts der laufenden Aufnahme antippen und ersetzen
- letzte abgeschlossene Aufnahme bis zum nächsten Dart korrigieren
- definierte Raspberry-Ereignisschnittstelle für vier Boards
- integrierter Simulator für Kameraereignisse und doppelte Signalfilterung
- Bust-Regel für Restwert unter 0 oder genau 1
- Rückgängig-Funktion
- lokale Wiederherstellung nach dem Neuladen
- Export der Testdaten als JSON

Die einzelnen Darts werden momentan bewusst manuell simuliert. Genau dieses Ereignisformat soll später vom Raspberry geliefert werden. Kamera- und Raspberry-Daten werden erst in einer späteren, separat getesteten Stufe angeschlossen.

## Testbilder von einem Autodarts-Board

Das Werkzeug `tools/capture_board.py` liest aus den drei lokalen Autodarts-Kamerastreams gleichzeitig je ein Bild. Es verändert weder Autodarts noch die Kameraeinstellungen.

```bash
python3 tools/capture_board.py --host dcapi4.local:3180 --board board4
```

Die Aufnahmen werden lokal unter `captures/` gespeichert. Dieser Ordner wird nicht zu GitHub hochgeladen.

Zwei Aufnahmen können anschließend verglichen werden. Dafür wird der gebündelte Codex-Python-Runtime verwendet, damit keine zusätzlichen Pakete installiert werden müssen:

```bash
/Users/markusburkert/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  tools/compare_captures.py captures/board4/REFERENZ captures/board4/NACH_WURF
```

Der Vergleich legt pro Kamera ein markiertes Kontrollbild und einen JSON-Bericht im Ordner `comparison/` der zweiten Aufnahme ab.

Wenn zur Aufnahme auch eine gespeicherte Board-Kalibrierung vorliegt, kann die
Eintrittsstelle der Dartspitze innerhalb der Scheibe geschätzt werden:

```bash
/Users/markusburkert/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  tools/analyze_dart.py captures/board4/REFERENZ captures/board4/NACH_WURF
```

Die grüne Markierung in `dart-analysis/` zeigt die geschätzte Eintrittsstelle;
die türkise Markierung zeigt den kalibrierten Mittelpunkt. Die Auswertung läuft
ausschließlich mit bereits lokal gespeicherten Bildern.

Die Auswertung verwendet inzwischen alle drei Kameras gemeinsam:

- Kamerapixel werden über die Autodarts-Kalibrierung auf eine gemeinsame
  virtuelle Dartscheibe abgebildet.
- Aus mehreren Bildveränderungen wird die Kandidatenkombination gewählt, die
  in allen Kameras denselben realen Einschlag beschreibt.
- Bei teilweise verdeckten Darts kann eine eindeutige Zwei-von-drei-Mehrheit
  den Treffer mit reduzierter Sicherheit bestätigen. Unterschiedliche Felder
  ohne Mehrheit werden weiterhin verworfen.
- Mit `--max-darts 3` kann ein Vergleich zwischen leerer Scheibe und einer
  vollständigen Aufnahme bis zu drei Treffer liefern. Ein Drei-Kamera-Treffer
  hat Vorrang; weitere eng gruppierte Treffer dürfen durch zwei passende
  Kameras mit reduzierter Sicherheit ergänzt werden.
- Sektor und Ring werden automatisch aus der gemeinsamen Position bestimmt.
- Treffer innerhalb von ungefähr einem Millimeter zu einer Drahtkante werden
  als `nearWire` gekennzeichnet. Sie können später in der Bedienoberfläche zur
  Bestätigung angeboten werden, anstatt stillschweigend falsch zu zählen.

Die lokalen Einzelwurf-Referenzen T5, S16, S7, D20, Bull, T19 und S6 sowie eine
vollständige Drei-Dart-Folge D18, S6, S20 werden derzeit korrekt erkannt. D18
war ein dokumentierter Drahtfall, bei dem die Sichtprüfung und die eigene
Erkennung D18 ergaben, Autodarts jedoch S18 meldete. Diese kleine Stichprobe
enthält außerdem eine enge Gruppierung, die ohne Zwischenbilder korrekt als
S14, S5 und S1 getrennt wurde. Sie belegt noch keine allgemeine Zuverlässigkeit;
weitere Tests müssen insbesondere stärkere Verdeckungen und Bouncer abdecken.

## Lokal starten

Die Datei `index.html` kann zum ersten Ansehen direkt geöffnet werden. Für Tests auf einem zweiten Gerät wird später ein kleiner lokaler Webserver oder eine eigene GitHub-Pages-Testadresse verwendet.

## Vorgesehenes GitHub-Repository

Name: `triple20-dartvision-lab`

Nur die Dateien aus diesem Ordner hochladen. Niemals Dateien aus dem produktiven Ordner `Triple20` mit diesem Repository vermischen.
