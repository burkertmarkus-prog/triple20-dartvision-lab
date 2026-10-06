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
- Bust-Regel für Restwert unter 0 oder genau 1
- Rückgängig-Funktion
- lokale Wiederherstellung nach dem Neuladen
- Export der Testdaten als JSON

Die Eingaben sind momentan bewusst manuell. Kamera- und Raspberry-Daten werden erst in einer späteren, separat getesteten Stufe angeschlossen.

## Lokal starten

Die Datei `index.html` kann zum ersten Ansehen direkt geöffnet werden. Für Tests auf einem zweiten Gerät wird später ein kleiner lokaler Webserver oder eine eigene GitHub-Pages-Testadresse verwendet.

## Vorgesehenes GitHub-Repository

Name: `triple20-dartvision-lab`

Nur die Dateien aus diesem Ordner hochladen. Niemals Dateien aus dem produktiven Ordner `Triple20` mit diesem Repository vermischen.
