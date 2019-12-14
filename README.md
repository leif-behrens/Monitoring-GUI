# Monitoring für Windows

Dies ist ein GUI-Monitoring, geschrieben mit PyQt5. 
Geschrieben in Python 3.7.3

## Requirements

```
pip install -r requirements.txt
```

## Funktionsweise

Das Monitoring hat unterschiedliche Funktionen, bestehend aus 5 Tabs. 

### Tab 1

- Interface zum Starten der unterschiedlichen Monitorings
    - Überwachung CPU-Auslastung
    - Überwachung Arbeitsspeicher-Auslastungen
    - Festplattenmonitoring für jedes seperate Laufwerk (z. B. Laufwerk C, D, E etc.)
- Starten der unterschiedlichen Monitorings, wenn zuvor die entsprechenden **Schwellenwerte** (Soft- und Hardlimit) konfiguriert wurden
- Die Laufenden Monitorings werden auf diesem Interface angezeigt

### Tab 2

- Interface, wo gewisse Computerinformationen einzusehen sind, z. B.:
    - Angemeldeter Benutzer, Hostname, IP-Adresse, MAC-Adresse, Betriebssystem etc.
    - Man hat die Möglichkeit, diese Informationen als XML-Datei oder JSON-Datei abzuspeichern

### Tab 3

- Dieses Interface zeigt die unterschiedlichen Logs an
    - In drei weitere Tabs eingeteilt
        - Tab 1: System-Logs
        - Tab 2: Monitoring-Logs
        - Tab 3: Schwelle überschritten-Logs

### Tab 4

- Hier konfiguriert man die unterschiedlichen Einstellungen
- Unterteilt in nicht-optionale und optionale Eingaben
- Es gibt die Möglichkeit, die Einstellungen als laufende Konfiguration und/oder als Startup Konfiguration zu speichern
    - die laufende Konfiguration wird nach Beendung des Programms wieder gelöscht
    - die startup Konfiguration 

#### Nicht-optionale Eingaben

- Pfad der (Schwellenwert-Überschreitung)-Logs
- Empfänger-Mailadresse(n)
- Mail-Zugangsdaten
    - Email-Adresse
    - Passwort
    - Mailserver
    - Port des Mailservers
- Die Mail-Zugangsdaten müssen zunächst validiert werden, bevor die Konfiguration gespeichert werden kann

#### Optionale Eingaben

- Die unterschiedlichen Soft- und Hardlimits
    - Diese Limits müssen jedoch konfiguriert werden, wenn das entsprechende Monitoring gestartet werden soll


### Tab 5

- In zwei Tabs aufgeteilt
    - CPU
    - Arbeitsspeicher
- Graphische Übersicht der aktuellen Auslastungen
    - Live-Graph
- Die Auslastungen werden ebenfalls nicht-graphisch angezeigt
- Die Anzahl der laufenden Prozesse werden angezeigt
- Die Systemzeit, wie lange das Programm bereits läuft wird angezeigt

#### Created by Leif Behrens
Bei Fragen oder Verbesserungsvorschläge:

Mailto: [Leif Behrens](mailto:info@leifbehrens.de?subject=[GitHub]%20Monitoring)
