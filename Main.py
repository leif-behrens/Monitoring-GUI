# Python standard libraries
import sys
import multiprocessing
import json
import smtplib
import base64
import shutil
import pickle
import glob
import uuid
import re
import datetime
from xml.dom.minidom import parseString
import argparse
import textwrap
import subprocess
from pathlib import Path

# 3rd party libraries
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import style
from matplotlib.ticker import MaxNLocator
import psutil
import dicttoxml

# local library
from functions import *


class Monitoring(QMainWindow):
    """
    Namenskonvention der Labels:
    tab_* -> QTabWidget
    lb_* -> QLabel
    btn_* -> QPushButton
    le_* -> QLineEdit
    lw_* -> QListWidget
    cb_* -> QComboBox
    tb_* -> QTextBrowser
    """
    def __init__(self):
        # Temp und Logs-Directory erstellen, falls es nicht existiert
        Path("./Temp").mkdir(parents=True, exist_ok=True)
        Path("./Logs").mkdir(parents=True, exist_ok=True)
        
        log("Logs/system.log", "info", "Programm gestartet")

        super().__init__()
        # Titel des Programms
        self.title = "Monitoring"
        self.icon = "Images/Icon.png"
        
        self.width = 1000
        self.height = 600

        # Standard Labelgröße
        self.lb_x_default = 200
        self.lb_y_default = 25

        # Timestamp, sobald das Programm aufgerufen wird
        self.start_system_time = time.time()

        # Listen für die Werte, die die Graphen benötigen
        self.cpu_values = []
        self.ram_values = []
        self.systemtime_values = []

        # {<Name des Monitoring>: <PID>}
        self.processes = {}

        # (sichtbare) Namen der Laufenden Monitorings. Werden im Monitoring-Tab für das QListWidget benötigt
        self.monitoring = []

        # Eine Liste mit allen vorhandenen Laufwerken)
        self.drives = get_pc_information()["drives"]

        # Dictionary, wo bereits alle Laufwerke mit Soft- und Hardlimit vorkonfiguriert sind
        self.drive_chosen = {}  
        for drive in self.drives:
            self.drive_chosen[drive] = {"soft": "", "hard": ""}

        # Timestamp, der zum clearen der Status- und Errorlabels zuständig ist
        self.lb_timer = time.time()

        # Boolean zum checken, ob der Mailaccount validiert ist
        self.mail_access = False     

        # Initialisierung des QTimers, der sich sekündlich aktualisiert und dafür sorgt, dass die Graphen aktualisiert werden
        self.timer_refresh_current_utilization = QTimer(self)
        self.timer_refresh_current_utilization.timeout.connect(self.refresh_current_utilization)
        self.timer_refresh_current_utilization.start(1000)
        
        # Mainwindows sowie alle Tab-Widgets werden in der self.initWindow()-Methode initialisiert
        self.initWindow()

        # Es wird geschaut, ob die Datai startup_config.ini im Ordner existiert. Wenn ja, wird versucht die aktuelle Konfiguration zu laden
        if os.path.isfile("startup_config.ini"):
            self.lb_timer = time.time()
            
            # Hier wird mit Try-Except gearbeitet, da der User eventuell die Config-Datei manuell anpassen könnte, die ggf. zum Programmabsturz führen
            try:
                self.current_config = {"username": "",
                                       "password": "",
                                       "server": "",
                                       "port": "",
                                       "mail_receiver": "",
                                       "attachment": None,
                                       "limits": {}}
                
                """
                Es wird nun durch das Konfigfile geparsed
                Es werden alle Sections durchgangen und die Werte der Datei werden dem self.current_config-dictionary zugeordnet sowie
                die QLineEdits und QComboBoxen werden mit den Werten gefüllt
                """
                parser = ConfigParser()
                parser.read("startup_config.ini")

                # Section "Access_to_mail"
                self.current_config["username"] = parser["Access_to_mail"]["user"]
                self.current_config["password"] = parser["Access_to_mail"]["password"]
                self.current_config["server"] = parser["Access_to_mail"]["server"]
                self.current_config["port"] = int(parser["Access_to_mail"]["port"])

                self.le_mail_sender.setText(self.current_config["username"])
                self.le_mail_password.setText(base64.b64decode(self.current_config["password"]).decode("utf-8"))
                self.le_mail_server.setText(self.current_config["server"])
                self.le_mail_server_port.setText(str(self.current_config["port"]))

                self.mail_access = True


                # Section "DEFAULT"               
                self.current_config["mail_receiver"] = parser["DEFAULT"]["mailadressen"]
                self.current_config["attachment"] = eval(parser["DEFAULT"]["attach_logs"])
                
                self.le_mail_receiver.setText(self.current_config["mail_receiver"])
                
                if self.current_config["attachment"]:
                    self.cb_attachment_sent.setCurrentText("Ja")
                else:
                    self.cb_attachment_sent.setCurrentText("Nein")
                
                # Section "limits*""
                for limit in parser.sections():
                    if "limits" in limit:
                        if "limits_cpu" == limit:
                            self.current_config["limits"]["cpu"] = {"soft": int(parser[limit]["soft"]), "hard": int(parser[limit]["hard"])}
                            self.cb_cpu_softlimit.setCurrentText(str(self.current_config["limits"]["cpu"]["soft"]))
                            self.cb_cpu_hardlimit.setCurrentText(str(self.current_config["limits"]["cpu"]["hard"]))
                        elif "limits_ram" == limit:
                            self.current_config["limits"]["ram"] = {"soft": int(parser[limit]["soft"]), "hard": int(parser[limit]["hard"])}
                            self.cb_ram_softlimit.setCurrentText(str(self.current_config["limits"]["ram"]["soft"]))
                            self.cb_ram_hardlimit.setCurrentText(str(self.current_config["limits"]["ram"]["hard"]))
                        else:
                            self.current_config["limits"][limit[-2:]] = {"soft": int(parser[limit]["soft"]), "hard": int(parser[limit]["hard"])}
                            self.drive_chosen[limit[-2:]]["soft"] = self.current_config["limits"][limit[-2:]]["soft"]
                            self.drive_chosen[limit[-2:]]["hard"] = self.current_config["limits"][limit[-2:]]["hard"]
                self.cb_drives_limits_refresh()

                shutil.copy("startup_config.ini", "Temp/running_config.ini")
            
            # Sollten irgendwelche Werte/Sections nicht gefunden werden, so wird die Fehlermeldung in rot auf das Warnlabel geschrieben, ein Logeintrag
            # erstellt, self.current_config auf None gesetzt und die alle Widgets gecleared
            except Exception as e:
                self.lb_config_warnings.setStyleSheet("color: red")
                self.lb_config_warnings.setText(f"{e}")
                self.current_config = None
                
                self.le_mail_sender.clear()
                self.le_mail_password.clear()
                self.le_mail_server.clear()
                self.le_mail_server_port.clear()
                self.le_mail_receiver.clear()
                self.cb_cpu_softlimit.clear()
                self.cb_ram_softlimit.clear()
                self.drive_chosen.clear()
                log("Logs/system.log", "error", f"Initialisierung Temp/running_config schlug fehl: {e}")
        
        # Sollte die startup_config.ini nicht existieren, wird self.current_config auf None gesetzt und ein Info-Log geschrieben
        else:
            self.current_config = None
            log("Logs/system.log", "info", f"current_config.ini existiert nicht")

    def closeEvent(self, event):
        """
        Geerbte Methode vom QMainWindow, die hier überschrieben wird
        Sobald der User das Fenster schließt, werden alle temporären Dateien gelöscht, existierende Monitoringprozesse gekillt
        und ein Logeinträge geschrieben
        """

        try:
            # Lösche running_config.ini Datei
            if os.path.isfile("Temp/running_config.ini"):
                os.remove("Temp/running_config.ini")
                log("Logs/system.log", "info", "Temp/running_config.ini-Datei wurde gelöscht")

            # Kill alle Monitoring-Prozesse
            for mon, pid in self.processes.items():
                try:
                    psutil.Process(pid).terminate()
                    log("Logs/monitoring.log", "info", f"{mon}-Monitoring wurde beendet. Prozess-ID: {pid}")
                except:
                    log("Logs/monitoring.log", "error", f"{mon}-Monitoring mit der Prozess-ID {pid} war bereits beendet")
            
            # Lösche alle *.pickle Files (die die Werte für die Live-Graphen in Listen gespeichert haben)
            for f in glob.glob("Temp/*.pickle"):
                if f == "Temp\processes.pickle":
                    continue
                os.remove(f)
                log("Logs/system.log", "info", f"{f}-Datei wurde gelöscht")
            
        except Exception as e:
            log("Logs/system.log", "debug", f"Programm beenden - Folgender Fehler ist aufgetreten: {e}")
        
        finally:
            log("Logs/system.log", "info", f"Programm nach {round(time.time()-self.start_system_time, 2)} Sekunden beendet")
            
    def initWindow(self):
        """
        Initialisierung des Mainwindows sowie die unterschiedlichen Tabs. Zuletzt wird die GUI angezeigt (show)
        """
        
        # Mainwindow Einstellungen
        self.setWindowTitle(self.title)
        self.setWindowIcon(QIcon(self.icon))
        self.setFixedSize(self.width, self.height)

        # Tabwidget erstellt
        self.tabWidget = QTabWidget(self)
        self.tabWidget.setGeometry(QRect(0, 0, self.width, self.height))
        
        # Tabs werden initialisiert
        self.initMonitoring()    
        self.initComputerinformation()
        self.initLogs()        
        self.initConfig()        
        self.initGraph()
        
        # Anzeige der GUI
        self.show()

    def initMonitoring(self):
        """
        Methode zum initialisierung des Layouts für das Monitoring-Tab
        Alle Widgets werden initialisiert und die Buttons mit einer Methode gebinded        
        """
        
        # Ein neuer Tab wird dem tabWidget hinzugefügt
        self.tab_monitoring = QWidget()
        self.tabWidget.addTab(self.tab_monitoring, "Monitoring")
        
        # y ist nur ein Zähler, um die Widgets an einer bestimmten Position zu setzen (mit setGeometry)
        y = 15
        
        self.lb_cpu_start_stop = QLabel(self.tab_monitoring)
        self.lb_cpu_start_stop.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_cpu_start_stop.setText("CPU-Monitoring")

        self.btn_cpu_start_stop = QPushButton(self.tab_monitoring)
        self.btn_cpu_start_stop.setGeometry(QRect(200, y, 130, self.lb_y_default))
        self.btn_cpu_start_stop.setText("Start")
        y += 35
        

        self.lb_ram_start_stop = QLabel(self.tab_monitoring)
        self.lb_ram_start_stop.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_ram_start_stop.setText("Arbeitsspeicher-Monitoring")

        self.btn_ram_start_stop = QPushButton(self.tab_monitoring)
        self.btn_ram_start_stop.setGeometry(QRect(200, y, 130, self.lb_y_default))
        self.btn_ram_start_stop.setText("Start")
        y += 35
        

        self.lb_disk_start_stop = QLabel(self.tab_monitoring)
        self.lb_disk_start_stop.setGeometry(QRect(15, y, self.lb_x_default-50, self.lb_y_default))
        self.lb_disk_start_stop.setText("Festplatten-Monitoring")

        self.cb_disk_mon = QComboBox(self.tab_monitoring)
        self.cb_disk_mon.setGeometry(QRect(150, y, 40, self.lb_y_default))
        
        # Alle Laufwerke werden der QComboBox hinzugefügt
        for drive in self.drives:
            self.cb_disk_mon.addItem(drive)
    
        self.btn_disk_start_stop = QPushButton(self.tab_monitoring)
        self.btn_disk_start_stop.setGeometry(QRect(200, y, 130, self.lb_y_default))
        self.btn_disk_start_stop.setText("Start")

        self.lb_monitoring_description = QLabel(self.tab_monitoring)
        self.lb_monitoring_description.setGeometry(QRect(15, 130, self.lb_x_default-50, self.lb_y_default))
        self.lb_monitoring_description.setText("Laufende Monitorings:")

        self.lw_processes = QListWidget(self.tab_monitoring)
        self.lw_processes.setGeometry(QRect(15, 165, 125, 200))
        
        self.lb_error = QLabel(self.tab_monitoring)
        self.lb_error.setGeometry(QRect(15, self.height-50, self.width-30, self.lb_y_default))
        self.lb_error.setStyleSheet("color: red")

        self.lb_status = QLabel(self.tab_monitoring)
        self.lb_status.setGeometry(QRect(15, self.height-100, self.width-30, self.lb_y_default))
        self.lb_status.setStyleSheet("color: green")

        # Buttons bekommen jeweils eine Methode zugewiesen. Sobald man auf die Buttons klickt, wird diese Methode aufgerufen
        # Da den Methoden Argumente übergeben werden, musste ich hier mit der lambda-Funktion arbeiten
        self.btn_cpu_start_stop.clicked.connect(lambda: self.start("cpu", "CPU", self.btn_cpu_start_stop, mon_cpu))
        self.btn_ram_start_stop.clicked.connect(lambda: self.start("ram", "Arbeitsspeicher", self.btn_ram_start_stop, mon_memory))
        self.btn_disk_start_stop.clicked.connect(lambda: self.start_disk(self.cb_disk_mon.currentText()))
        
        # ComboBox wird ebenfalls einer Methode zugewiesen. Sobald sich dort der Text ändert, wird diese Methode aufgerufen
        self.cb_disk_mon.currentTextChanged.connect(lambda: self.cb_disk_mon_change(self.cb_disk_mon.currentText()))

    def start_disk(self, disk):
        """
        :param disk: String -> Festplatte, für das das Monitoring gestartet werden soll
        """
        
        self.lb_timer = time.time()

        # Erst wird geschaut, ob self.current_config nicht None ist. Monitorings können nur gestartet werden, wenn eine Konfiguration
        # vorhanden ist
        if self.current_config is not None:
            """
            In dem Try-Except-Block wird versucht, die aktuelle Konfigurations zu laden und in Variablen zu speichern.
            Es wird versucht, die Soft- und Hardlimits in einen Integer zu konvertieren. Sollten die Limits für diese 
            Festplatte nicht konfiguriert sein, wird eine KeyError Exception geraised und die Funktion wird mit return beendet.
            Um ein Monitoring zu starten müssen vorher die entsprechenden Limits konfiguriert sein.
            """
            try:
                username = self.current_config["username"]
                pwd = base64.b64decode(self.current_config["password"]).decode("utf-8")
                server = self.current_config["server"]
                port = self.current_config["port"]

                attachment = self.current_config["attachment"]
                mail_receiver = self.current_config["mail_receiver"]

                soft = int(self.current_config["limits"][disk]["soft"])
                hard = int(self.current_config["limits"][disk]["hard"])
                
            except KeyError:
                self.lb_error.setText(f"{disk}-Limits sind nicht konfiguriert.")
                log("Logs/system.log", "error", f"Starten Laufwerk {disk}-Monitorings schlug fehl. Limits sind nicht konfiguriert")
                return

            except Exception as e:
                self.lb_error.setText(f"Fehler: {e}")
                log("Logs/system.log", "error", f"Aktuelle Konfiguration konnte nicht initiiert werden. Fehler: {e}")
                return
            
            # Wenn es zu keinem Error kam, wird zunächst das Listwidget, wo alle Monitoring-Beschreibungen enthalten sind, 
            # gecleared
            self.lw_processes.clear()

            """
            In der folgenden Routine wird überprüft, ob das Monitoring für diese Festplatte bereits läuft.
            Wenn ja, wird das Monitoring gestoppt und der Buttontext ändert sich zu "Start", der Text des Statuslabels
            ändert sich, das Item wird von der self.monitoring-Liste entfernt. Anschließend wird über die self.monitoring-Liste
            iteriert und das Listwidget erhält alle Items (also alle Monitorings, die gerade laufen). Anschließend wird returnt,
            sodass der Rest der Methode nicht mehr ausgeführt wird
            """           
            for d, p in self.processes.items():
                if disk == d:
                    try:
                        psutil.Process(pid=p).terminate()
                        del self.processes[d]
                        self.monitoring.remove(f"{disk}-Laufwerk")
                        self.lb_status.setText(f"Beende Festplatten-Monitoring für Laufwerk: {disk}")
                        self.btn_disk_start_stop.setText("Start")
                        log("Logs/monitoring.log", "info", f"Laufwerk {disk}-Monitoring wurde beendet. Prozess-ID: {p}")

                    except Exception as e:
                        log("Logs/monitoring.log", "error", f"Laufwerk {disk}-Monitoring beenden schlug fehl. Fehler: {e}")

                    for mon in self.monitoring:
                        self.lw_processes.addItem(mon)
                    return
                else:
                    continue
            
            """
            Wenn kein Prozess für dieses Monitoring läuft, wird zunächst versucht, ob ein Zugriff auf das Laufwerk möglich ist.
            Falls es sich beispielsweise um ein Netzlaufwerk handelt, dass nicht erreichbar oder um ein CD-Laufwerk, wo keine
            DVD enthalten ist, würde es an dieser Stelle zu einem Prozessabbruch kommen und das Programm wird mit einem Error 
            beendet (habe ich beides ausgetestet)
            """
            try:
                psutil.disk_usage(disk)
            except Exception as e:
                for mon in self.monitoring:
                    self.lw_processes.addItem(mon)
                self.lb_error.setStyleSheet("color: red")
                self.lb_error.setText(str(e))
                log("Logs/monitoring.log", "error", f"Laufwerk {disk} konnten nicht gestartet werden. Fehler: {e}")
                return

            """           
            Wenn das Monitoring für das Laufwerk nicht läuft und es auch erreichbar ist, wird versucht, das Monitoring
            für das Laufwerk zu starten. Der Buttonname wird wird auf "Stopp" gesetzt, self.monitoring ergänzt, das Listwidget 
            gefüllt und ein Logeintrag geschrieben
            """
            try:
                process = multiprocessing.Process(target=mon_disk, 
                                                args=(disk, [mail_receiver], attachment, soft, 
                                                        hard, username, pwd, server, port))
                process.start()
                self.processes[disk] = process.pid

                self.lb_status.setText(f"Starte Festplatten-Monitoring für Laufwerk: {disk}")
                self.btn_disk_start_stop.setText("Stopp")
                self.monitoring.append(f"{disk}-Laufwerk")

                for mon in self.monitoring:
                    self.lw_processes.addItem(mon)

                log("Logs/monitoring.log", "info", f"Laufwerk {disk}-Monitoring wurde gestartet. Prozess-ID: {process.pid}")

            except Exception as e:
                log("Logs/monitoring.log", "error", f"Laufwerk {disk}-Monitoring konnte nicht gestartet werden. Fehler: {e}")

        # Falls keine Konfiguration vorhanden ist, wird das Errorlabel mit einer Meldung versehen und ein Logeintrag geschrieben
        else:
            self.lb_error.setText("Keine Konfiguration vorhanden")
            log("Logs/monitoring.log", "info", f"Laufwerk {disk}-Monitoring konnte nicht gestartet werden - keine Konifguration vorhanden")

    def cb_disk_mon_change(self, disk):
        """
        Methode die aufgerufen wird, sobald ein User im Monitoring-Tab den Wert der Combobox mit den Laufwerken ändert.
        Es wird überprüft, ob das Monitoring für das Laufwerk läuft oder nicht. Wenn ja, wird der Text des Buttons zum Starten des
        Monitorings auf "Stopp" gesetzt, anderenfalls auf "Start"
        """
        if self.current_config is not None:

            for d in self.processes.keys():
                if disk == d:
                    self.btn_disk_start_stop.setText("Stopp")
                    return

            self.btn_disk_start_stop.setText("Start")

    def start(self, typ, description, btn, function):
        """
        :param typ: String -> "cpu" oder "ram" wird erwartet (kommt drauf an, welcher Button gedrückt wurde)
        :param description: String -> Beschreibung des Prozesses für das ListWidget
        :param btn: QPushButton-Objekt, um den Text des Buttons zu ändern (Start oder Stopp)
        :param function: Function-Objekt, das zum Aufruf des Monitorings ist
        """

        # Initialieren des Error- und Statuslabels
        self.lb_error.clear()
        self.lb_status.clear()
        self.lb_timer = time.time()
        
        # Erst wird geschaut, ob self.current_config nicht None ist. Monitorings können nur gestartet werden, wenn eine Konfiguration
        # vorhanden ist
        if self.current_config is not None:
            """
            In dem Try-Except-Block wird versucht, die aktuelle Konfigurations zu laden und in Variablen zu speichern.
            Es wird versucht, die Soft- und Hardlimits in einen Integer zu konvertieren. Sollten die Limits nicht konfiguriert 
            sein, wird eine KeyError Exception geraised und die Funktion wird mit return beendet. Um ein Monitoring zu starten 
            müssen vorher die entsprechenden Limits konfiguriert sein.
            """
            try:
                username = self.current_config["username"]
                pwd = base64.b64decode(self.current_config["password"]).decode("utf-8")
                server = self.current_config["server"]
                port = self.current_config["port"]

                attachment = self.current_config["attachment"]
                mail_receiver = self.current_config["mail_receiver"]

                soft = int(self.current_config["limits"][typ]["soft"])
                hard = int(self.current_config["limits"][typ]["hard"])

            except KeyError:
                self.lb_error.setText(f"{description}-Limits sind nicht konfiguriert.")
                log("Logs/system.log", "error", f"Starten {typ.upper()}-Monitorings schlug fehl. Limits sind nicht konfiguriert")
                return

            except Exception as e:
                self.lb_error.setText(f"Fehler: {e}")
                log("Logs/system.log", "error", f"Aktuelle Konfiguration konnte nicht initiiert werden. Fehler: {e}")
                return
            
            self.lw_processes.clear()
            
            """
            In der folgenden Routine wird überprüft, ob das Monitoring bereits läuft.
            Wenn ja, wird das Monitoring gestoppt und der Buttontext ändert sich zu "Start", der Text des Statuslabels
            ändert sich, das Item wird von der self.monitoring-Liste entfernt. Anschließend wird über die self.monitoring-Liste
            iteriert und das Listwidget erhält alle Items (also alle Monitorings, die gerade laufen). Anschließend wird returnt,
            sodass der Rest der Methode nicht mehr ausgeführt wird
            """
            for d, p in self.processes.items():
                if typ == d:
                    
                    psutil.Process(pid=p).terminate()
                    del self.processes[d]
                    self.monitoring.remove(description)
                    self.lb_status.setText(f"Beende {description}-Monitoring")
                    btn.setText("Start")
                    log("Logs/monitoring.log", "info", f"{typ.upper()}-Monitoring wurde beendet. Prozess-ID: {p}")

                    for mon in self.monitoring:
                        self.lw_processes.addItem(mon)
                    
                    return
                else:
                    continue

            """           
            Wenn das Monitoring nicht läuft, wird versucht, das Monitoring für das Laufwerk zu starten. Der Buttonname wird auf 
            "Stopp" gesetzt, self.monitoring ergänzt, das Listwidget gefüllt und ein Logeintrag geschrieben            
            """
            try:
                self.lb_status.setText(f"Starte {description}-Monitoring")
                btn.setText("Stopp")
                self.monitoring.append(description)

                process = multiprocessing.Process(target=function, 
                                                args=([mail_receiver], attachment, soft, hard, 
                                                        username, pwd, server, port))
                process.start()
                self.processes[typ] = process.pid

                for mon in self.monitoring:
                    self.lw_processes.addItem(mon)                
                
                log("Logs/monitoring.log", "info", f"{typ.upper()}-Monitoring wurde gestartet. Prozess-ID: {process.pid}")

            except Exception as e:
                log("Logs/monitoring.log", "error", f"{typ.upper()}-Monitoring konnte nicht gestartet werden. Fehler: {e}")

        else:
            self.lb_error.setText("Wähle zuerst eine Konfiguration.")
            log("Logs/monitoring.log", "info", f"{typ.upper()}-Monitoring konnte nicht gestartet werden - keine Konifguration vorhanden")

    def initComputerinformation(self):
        """
        Initialisierung des "Computerinformationen"-Tabs
        Alle Werte werden den Labels hinzugefügt
        """

        self.pc_info = get_pc_information()
        self.lb_x_value = 400
        
        # Computerinformationen in Variablen schreiben
        self.current_user = self.pc_info["current_user"]
        self.hostname = self.pc_info["hostname"]
        self.boot_time = datetime.datetime.fromtimestamp(psutil.boot_time()).strftime("%d.%m.%Y %H:%M:%S")
        self.ip = self.pc_info["ip_address"]
        self.mac = ":".join(re.findall("..", "%x" % uuid.getnode()))
        self.os = self.pc_info["os"]
        self.os_version = platform.version()
        self.processor = self.pc_info["processor"]
        self.cpu_p = self.pc_info["cpu_p"]
        self.cpu_l = self.pc_info["cpu_l"]
        self.memory = self.pc_info["memory"]
        self.drives = self.pc_info["drives"] 

        # Informationen in ein Dictionary schreiben, da die Informationen ggf. benötigt werden, sobald ein User
        # die Informationen als XML oder JSON Datei abspeichern möchte
        self.computerinfo = {"timestamp": time.strftime('%d.%m.%y %H:%M:%S'),
                             "current_user": self.current_user, 
                             "hostname": self.hostname,
                             "boottime": self.boot_time,
                             "ip": self.ip,
                             "os": self.os,
                             "os_version": self.os_version,
                             "processor": self.processor,
                             "cpu_physical": self.cpu_p,
                             "cpu_logical": self.cpu_l,
                             "memory_GiB": self.memory,
                             "drives": {}}
        
        for drive in self.drives:
            try:
                self.computerinfo["drives"][drive] = {"total_GiB": get_disk_usage(drive)["total"],
                                                      "used_GiB": get_disk_usage(drive)["used"],
                                                      "free_GiB": get_disk_usage(drive)["free"]}
            except:
                continue
        
        # Variable für y-Positionierung
        y = 15
                        
        self.tab_computerinformation = QWidget()
        self.tabWidget.addTab(self.tab_computerinformation, "Computerinformationen")

        self.lb_user_description = QLabel(self.tab_computerinformation)
        self.lb_user_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_user_description.setText("Angemeldeter Benutzer")

        self.lb_user_value = QLabel(self.tab_computerinformation)
        self.lb_user_value.setGeometry(QRect(225, y, self.lb_x_default, self.lb_y_default))
        self.lb_user_value.setText(self.current_user)
        y += 25


        self.lb_hostname_description = QLabel(self.tab_computerinformation)
        self.lb_hostname_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_hostname_description.setText("Hostname")

        self.lb_hostname_value = QLabel(self.tab_computerinformation)
        self.lb_hostname_value.setGeometry(QRect(225, y, self.lb_x_default, self.lb_y_default))
        self.lb_hostname_value.setText(self.hostname)
        y += 25


        self.lb_boot_time_description = QLabel(self.tab_computerinformation)
        self.lb_boot_time_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_boot_time_description.setText("Letzte Boottime")

        self.lb_boot_time_value = QLabel(self.tab_computerinformation)
        self.lb_boot_time_value.setGeometry(QRect(225, y, self.lb_x_default, self.lb_y_default))
        self.lb_boot_time_value.setText(self.boot_time)
        y += 25


        self.lb_ip_description = QLabel(self.tab_computerinformation)
        self.lb_ip_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_ip_description.setText("IP-Adresse")

        self.lb_ip_value = QLabel(self.tab_computerinformation)
        self.lb_ip_value.setGeometry(QRect(225, y, self.lb_x_default, self.lb_y_default))
        self.lb_ip_value.setText(self.ip)
        y += 25


        self.lb_mac_description = QLabel(self.tab_computerinformation)
        self.lb_mac_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_mac_description.setText("MAC-Adresse")

        self.lb_mac_value = QLabel(self.tab_computerinformation)
        self.lb_mac_value.setGeometry(QRect(225, y, self.lb_x_default, self.lb_y_default))
        self.lb_mac_value.setText(self.mac)
        y += 25


        self.lb_os_description = QLabel(self.tab_computerinformation)
        self.lb_os_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_os_description.setText("Betriebssystem")

        self.lb_os_value = QLabel(self.tab_computerinformation)
        self.lb_os_value.setGeometry(QRect(225, y, self.lb_x_default, self.lb_y_default))
        self.lb_os_value.setText(self.os)
        y += 25


        self.lb_os_version_description = QLabel(self.tab_computerinformation)
        self.lb_os_version_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_os_version_description.setText("Betriebssystem Release Version")

        self.lb_os_version_value = QLabel(self.tab_computerinformation)
        self.lb_os_version_value.setGeometry(QRect(225, y, self.lb_x_default, self.lb_y_default))
        self.lb_os_version_value.setText(self.os_version)
        y += 25


        self.lb_processor_description = QLabel(self.tab_computerinformation)
        self.lb_processor_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_processor_description.setText("Verbauter Prozessor")

        self.lb_processor_value = QLabel(self.tab_computerinformation)
        self.lb_processor_value.setGeometry(QRect(225, y, self.lb_x_default+100, self.lb_y_default))
        self.lb_processor_value.setText(self.processor)
        y += 25


        self.lb_count_physical_cores_description = QLabel(self.tab_computerinformation)
        self.lb_count_physical_cores_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_count_physical_cores_description.setText("Anzahl physischer Kerne")

        self.lb_count_physical_cores_value = QLabel(self.tab_computerinformation)
        self.lb_count_physical_cores_value.setGeometry(QRect(225, y, self.lb_x_default, self.lb_y_default))
        self.lb_count_physical_cores_value.setText(str(self.cpu_p))
        y += 25


        self.lb_count_logical_cores_description = QLabel(self.tab_computerinformation)
        self.lb_count_logical_cores_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_count_logical_cores_description.setText("Anzahl logischer Kerne")

        self.lb_count_logical_cores_value = QLabel(self.tab_computerinformation)
        self.lb_count_logical_cores_value.setGeometry(QRect(225, y, self.lb_x_default, self.lb_y_default))
        self.lb_count_logical_cores_value.setText(str(self.cpu_l))
        y += 25


        self.lb_ram_description = QLabel(self.tab_computerinformation)
        self.lb_ram_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_ram_description.setText("Verbauter Arbeitsspeicher")

        self.lb_ram_value = QLabel(self.tab_computerinformation)
        self.lb_ram_value.setGeometry(QRect(225, y, self.lb_x_default, self.lb_y_default))
        self.lb_ram_value.setText(str(self.memory) + " GiB")
        y += 25


        self.lb_drives_description = QLabel(self.tab_computerinformation)
        self.lb_drives_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_drives_description.setText("Laufwerke")

        self.lb_drives_value = QLabel(self.tab_computerinformation)
        self.lb_drives_value.setGeometry(QRect(225, y, self.lb_x_default, self.lb_y_default))
        self.lb_drives_value.setText(", ".join(self.drives))
        y += 40


        self.lb_drive_description = QLabel(self.tab_computerinformation)
        self.lb_drive_description.setGeometry(QRect(70, y, self.lb_x_default, self.lb_y_default))
        self.lb_drive_description.setText("Laufwerk")

        self.cb_drive = QComboBox(self.tab_computerinformation)
        self.cb_drive.setGeometry(QRect(125, y, 40, 25))
        
        for drive in self.drives:
            self.cb_drive.addItem(drive)

        self.lb_total_description = QLabel(self.tab_computerinformation)
        self.lb_total_description.setGeometry(QRect(225, y, 100, self.lb_y_default))
        self.lb_total_description.setText("Gesamt")

        self.lb_total_value = QLabel(self.tab_computerinformation)
        self.lb_total_value.setGeometry(QRect(275, y, 100, self.lb_y_default))
        y += 25


        self.lb_used_description = QLabel(self.tab_computerinformation)
        self.lb_used_description.setGeometry(QRect(225, y, 100, self.lb_y_default))
        self.lb_used_description.setText("Genutzt")

        self.lb_used_value = QLabel(self.tab_computerinformation)
        self.lb_used_value.setGeometry(QRect(275, y, 100, self.lb_y_default))
        y += 25


        self.lb_free_description = QLabel(self.tab_computerinformation)
        self.lb_free_description.setGeometry(QRect(225, y, 100, self.lb_y_default))
        self.lb_free_description.setText("Frei")

        self.lb_free_value = QLabel(self.tab_computerinformation)
        self.lb_free_value.setGeometry(QRect(275, y, 100, self.lb_y_default))
        y += 25

        
        self.lb_info_saved = QLabel(self.tab_computerinformation)
        self.lb_info_saved.setGeometry(QRect(15, self.height-100, self.width-30, self.lb_y_default))
        self.lb_info_saved.setStyleSheet("color: green")

        self.btn_save_xml = QPushButton(self.tab_computerinformation)
        self.btn_save_xml.setGeometry(QRect(15, self.height-75, 130, self.lb_y_default))
        self.btn_save_xml.setText("XML-Datei speichern")

        self.btn_save_json = QPushButton(self.tab_computerinformation)
        self.btn_save_json.setGeometry(QRect(150, self.height-75, 130, self.lb_y_default))
        self.btn_save_json.setText("JSON-Datei speichern")


        self.btn_save_xml.clicked.connect(self.save_xml)
        self.btn_save_json.clicked.connect(self.save_json)
        self.cb_drive.currentTextChanged.connect(self.cb_drive_change)

        # Initialize Labels
        self.cb_drive_change()

    def cb_drive_change(self):
        """
        Methode wird aufgerufen, wenn sich der Text der Combobox im Computerinformationen-Tab wechselt
        """
        try:
            self.lb_total_value.setText(str(self.computerinfo["drives"][self.cb_drive.currentText()]["total_GiB"]) + " GiB")
            self.lb_used_value.setText(str(self.computerinfo["drives"][self.cb_drive.currentText()]["used_GiB"]) + " GiB")
            self.lb_free_value.setText(str(self.computerinfo["drives"][self.cb_drive.currentText()]["free_GiB"]) + " GiB")
        except:
            self.lb_total_value.setText("")
            self.lb_used_value.setText("")
            self.lb_free_value.setText("")
    
    def save_xml(self):
        """
        Methode wird aufgerufen, sobald ein User den self.btn_save_xml-Button im Computerinformationen-Tab
        klickt. Es öffnet sich ein QFileDialog, wo der User die Möglichkeit hat, den und Namen auszuwählen, 
        wo die Datei gespeichert werden soll
        """
        
        data = QFileDialog.getSaveFileName(self, "Speichern", "", "XML (*.xml)")

        xml = dicttoxml.dicttoxml(self.computerinfo)
        dom = parseString(xml)
        self.lb_timer = time.time()

        try:
            if data[0]:
                with open(data[0], "w") as x:
                    x.write(dom.toprettyxml())
                
                self.lb_info_saved.setText(f"Gespeichert unter {data[0]}")
                log("Logs/system.log", "info", f"Computerinformationen als json unter {data[0]} gespeichert")
        
        except Exception as e:
            log("Logs/system.log", "error", f"Computerinformationen konnte nicht als json unter {data[0]} gespeichert werden. Fehler: {e}")
        
        
    def save_json(self):
        """
        Methode wird aufgerufen, sobald ein User den self.btn_save_json-Button im Computerinformationen-Tab
        klickt. Es öffnet sich ein QFileDialog, wo der User die Möglichkeit hat, den und Namen auszuwählen, 
        wo die Datei gespeichert werden soll
        """
        data = QFileDialog.getSaveFileName(self, "Speichern", "", "JSON (*.json)")
        
        self.lb_timer = time.time()
        try:
            if data[0]:                    
                with open(data[0], "w") as j:
                    json.dump(self.computerinfo, j, indent=4)

                self.lb_info_saved.setText(f"Gespeichert unter {data[0]}")
                log("Logs/system.log", "info", f"Computerinformationen als xml unter {data[0]} gespeichert")

        except Exception as e:
            log("Logs/system.log", "error", f"Computerinformationen konnte nicht als xml unter {data[0]} gespeichert werden. Fehler: {e}")

    def initLogs(self):
        """
        Initialisierung des Log-Tabs
        """
        self.tab_logs = QWidget()
        self.tabWidget.addTab(self.tab_logs, "Logs")
        self.tabWidget.currentChanged.connect(self.push_logs)

        self.tab_logs_all = QTabWidget(self.tab_logs)
        self.tab_logs_all.setGeometry(QRect(0, 0, self.width, self.height))
        
        self.tab_logs_system_logs = QWidget()
        self.tab_logs_all.addTab(self.tab_logs_system_logs, "System-Logs")

        self.tb_logs_system_logs = QTextBrowser(self.tab_logs_system_logs)
        self.tb_logs_system_logs.setGeometry(QRect(15, 15, self.width-40, self.height-80))
        self.tb_logs_system_logs.moveCursor(QTextCursor.End)


        self.tab_logs_monitoring_logs = QWidget()
        self.tab_logs_all.addTab(self.tab_logs_monitoring_logs, "Monitoring-Logs")

        self.tb_logs_monitoring_logs = QTextBrowser(self.tab_logs_monitoring_logs)
        self.tb_logs_monitoring_logs.setGeometry(QRect(15, 15, self.width-40, self.height-80))
        self.tb_logs_monitoring_logs.moveCursor(QTextCursor.End)

        
        self.tab_logs_threshold_limits = QWidget(self.tab_logs_all)
        self.tab_logs_all.addTab(self.tab_logs_threshold_limits, "Schwelle überschritten-Logs")
        
        self.tb_logs_threshold_limits = QTextBrowser(self.tab_logs_threshold_limits)
        self.tb_logs_threshold_limits.setGeometry(QRect(15, 15, self.width-40, self.height-80))
        self.tb_logs_threshold_limits.moveCursor(QTextCursor.End)
        
        # Sobald man den Tab wechselt, wird die Methode self.push_logs aufgerufen
        self.tab_logs_all.currentChanged.connect(self.push_logs)

    def push_logs(self):
        """
        Hier werden die Logs in die unterschiedlichen TextBrowser gepusht
        """
        try:
            logs_path = "Logs/system.log"
            if os.path.isfile(logs_path):
                with open(logs_path) as f:
                    logs = f.read()
                    self.tb_logs_system_logs.setText(logs)
                    self.tb_logs_system_logs.moveCursor(QTextCursor.End)
            
            logs_path = "Logs/monitoring.log"
            if os.path.isfile(logs_path):
                with open(logs_path) as f:
                    logs = f.read()
                    self.tb_logs_monitoring_logs.setText(logs)
                    self.tb_logs_monitoring_logs.moveCursor(QTextCursor.End)

            
            logs_path = "Logs/limits.log"
            if os.path.isfile(logs_path):
                with open(logs_path) as f:
                    logs = f.read()
                    self.tb_logs_threshold_limits.setText(logs)
                    self.tb_logs_threshold_limits.moveCursor(QTextCursor.End)
                                                
        except:
            pass
    
    def initConfig(self):
        """
        Konfigurationstab wird initialisiert
        """
        self.tab_config = QWidget()
        self.tabWidget.addTab(self.tab_config, "Konfigurieren")
        
        # Label zur Positionierung der Widgets
        y = 15

        self.lb_mail_sender = QLabel(self.tab_config)
        self.lb_mail_sender.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_mail_sender.setText("Sender-Mailadresse")

        self.le_mail_sender = QLineEdit(self.tab_config)
        self.le_mail_sender.setGeometry(QRect(150, y, self.lb_x_default, self.lb_y_default))
        y += 35

        self.lb_mail_password = QLabel(self.tab_config)
        self.lb_mail_password.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_mail_password.setText("Passwort")

        self.le_mail_password = QLineEdit(self.tab_config)
        self.le_mail_password.setGeometry(QRect(150, y, self.lb_x_default, self.lb_y_default))
        self.le_mail_password.setEchoMode(QLineEdit.Password)
        y += 35

        self.lb_mail_server = QLabel(self.tab_config)
        self.lb_mail_server.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_mail_server.setText("Mailserver")
        
        self.le_mail_server = QLineEdit(self.tab_config)
        self.le_mail_server.setGeometry(QRect(150, y, self.lb_x_default, self.lb_y_default))
        y += 35

        self.lb_mail_server_port = QLabel(self.tab_config)
        self.lb_mail_server_port.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_mail_server_port.setText("Port")
        
        self.le_mail_server_port = QLineEdit(self.tab_config)
        self.le_mail_server_port.setGeometry(QRect(150, y, 40, self.lb_y_default))

        
        self.btn_validate_login = QPushButton(self.tab_config)
        self.btn_validate_login.setGeometry(QRect(195, y, 155, self.lb_y_default))
        self.btn_validate_login.setText("Validiere Zugangsdaten")
        y += 100

        self.lb_mail_receiver = QLabel(self.tab_config)
        self.lb_mail_receiver.setGeometry(QRect(15, y, 330, self.lb_y_default))
        self.lb_mail_receiver.setText("Empfänger-Mailadresse")

        self.le_mail_receiver = QLineEdit(self.tab_config)
        self.le_mail_receiver.setGeometry(QRect(150, y, self.lb_x_default, self.lb_y_default))
        y += 45

        self.lb_attachment_sent = QLabel(self.tab_config)
        self.lb_attachment_sent.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_attachment_sent.setText("Logs-Anhang")

        self.cb_attachment_sent = QComboBox(self.tab_config)
        self.cb_attachment_sent.setGeometry(QRect(150, y, 60, self.lb_y_default))
        self.cb_attachment_sent.addItem("Nein")
        self.cb_attachment_sent.addItem("Ja")
        y += 45

        self.lb_softlimit_description = QLabel(self.tab_config)
        self.lb_softlimit_description.setGeometry(QRect(150, y, 100, self.lb_y_default))
        self.lb_softlimit_description.setText("Softlimit %")

        self.lb_hardlimit_description = QLabel(self.tab_config)
        self.lb_hardlimit_description.setGeometry(QRect(235, y, 100, self.lb_y_default))
        self.lb_hardlimit_description.setText("Hardlimit %")
        y += 25

        self.lb_cpu_description = QLabel(self.tab_config)
        self.lb_cpu_description.setGeometry(QRect(15, y, 200, self.lb_y_default))
        self.lb_cpu_description.setText("CPU")

        self.cb_cpu_softlimit = QComboBox(self.tab_config)
        self.cb_cpu_softlimit.setGeometry(QRect(150, y, 60, self.lb_y_default))

        self.cb_cpu_hardlimit = QComboBox(self.tab_config)
        self.cb_cpu_hardlimit.setGeometry(QRect(235, y, 60, self.lb_y_default))

        self.lb_cpu_limit_status = QLabel(self.tab_config)
        self.lb_cpu_limit_status.setGeometry(QRect(250, y, self.lb_x_default, self.lb_y_default))
        y += 35

        self.lb_ram_description = QLabel(self.tab_config)
        self.lb_ram_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_ram_description.setText("Arbeitsspeicher")
        
        self.cb_ram_softlimit = QComboBox(self.tab_config)
        self.cb_ram_softlimit.setGeometry(QRect(150, y, 60, self.lb_y_default))

        self.cb_ram_hardlimit = QComboBox(self.tab_config)
        self.cb_ram_hardlimit.setGeometry(QRect(235, y, 60, self.lb_y_default))

        self.lb_ram_limit_status = QLabel(self.tab_config)
        self.lb_ram_limit_status.setGeometry(QRect(250, y, self.lb_x_default, self.lb_y_default))
        y += 35

        
        self.lb_drives_description = QLabel(self.tab_config)
        self.lb_drives_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_drives_description.setText("Laufwerk")

        self.cb_drives_limits = QComboBox(self.tab_config)
        self.cb_drives_limits.setGeometry(QRect(70, y, 40, self.lb_y_default))

        for drive in self.drives:
            self.cb_drives_limits.addItem(drive)

        self.cb_drives_softlimit = QComboBox(self.tab_config)
        self.cb_drives_softlimit.setGeometry(QRect(150, y, 60, self.lb_y_default))
        
        self.cb_drives_hardlimit = QComboBox(self.tab_config)
        self.cb_drives_hardlimit.setGeometry(QRect(235, y, 60, self.lb_y_default))

        self.lb_drives_limit_status = QLabel(self.tab_config)
        self.lb_drives_limit_status.setGeometry(QRect(250, y, self.lb_x_default, self.lb_y_default))

        # Blanks werden eingefügt und sind auch Standardmäßig eingestellt
        self.cb_cpu_softlimit.addItem("")
        self.cb_ram_softlimit.addItem("")
        self.cb_cpu_hardlimit.addItem("")
        self.cb_ram_hardlimit.addItem("")
        self.cb_drives_softlimit.addItem("")
        self.cb_drives_hardlimit.addItem("")

        # ComboBoxen werden gefüllt mit Werten von 100 bis 1
        for percent in range(100, 0, -1):
            self.cb_cpu_softlimit.addItem(str(percent))
            self.cb_ram_softlimit.addItem(str(percent))
            self.cb_cpu_hardlimit.addItem(str(percent))
            self.cb_ram_hardlimit.addItem(str(percent))
            self.cb_drives_softlimit.addItem(str(percent))
            self.cb_drives_hardlimit.addItem(str(percent))    



        self.lb_config_info = QLabel(self.tab_config)
        self.lb_config_info.setGeometry(QRect(15, self.height-125, self.width-30, self.lb_y_default))
        self.lb_config_info.setStyleSheet("color: green")

        self.lb_config_warnings = QLabel(self.tab_config)
        self.lb_config_warnings.setGeometry(QRect(15, self.height-100, self.width-30, self.lb_y_default))
        self.lb_config_warnings.setStyleSheet("color: red")

        self.btn_running_config = QPushButton(self.tab_config)
        self.btn_running_config.setGeometry(QRect(15, self.height-70, 200, self.lb_y_default))
        self.btn_running_config.setText("Laufende Konfiguration speichern")
        
        self.btn_startup_config = QPushButton(self.tab_config)
        self.btn_startup_config.setGeometry(QRect(220, self.height-70, 200, self.lb_y_default))
        self.btn_startup_config.setText("Startup Konfiguration speichern")
        
        # Bindings der Buttons und Comboboxen
        self.btn_running_config.clicked.connect(self.running_config)
        self.btn_startup_config.clicked.connect(self.startup_config)
        self.cb_drives_limits.currentTextChanged.connect(self.cb_drives_limits_refresh)
        self.cb_drives_softlimit.currentTextChanged.connect(self.cb_drive_soft_commit)
        self.cb_drives_hardlimit.currentTextChanged.connect(self.cb_drive_hard_commit)
        self.btn_validate_login.clicked.connect(self.validate_login)

    def running_config(self):
        """
        Methode die aufgerufen wird, sobald der User auf den Button self.btn_running_config in dem Konfigurationstab klickt
        Wenn alle Werte korrekt eingegeben sind, wird zum einen die current_config.ini geschrieben/überschrieben und anschließend
        auch das self.current_config-Dictionary neu geschrieben
        """
        
        # Zunächst wird die Methode check_config aufgerufen. Diese checkt, ob alle Eingaben in dem Konfigurationstab
        # in Ordnung sind oder nicht. 
        # Diese Methode returnt entweder False oder ein Dictionary mit der neuen Konfiguration
        check_config = self.check_config()
        self.lb_timer = time.time()

        if check_config:
            # Wenn check_config True ist (also das Dictionary returnt), wird self.current_config ebenfalls auf das 
            # Dictionary referenziert.
            self.current_config = check_config
            
            # Anschließend wird die current_config.ini-Datei geschrieben
            parser = ConfigParser()

            parser["DEFAULT"] = {"Mailadressen": self.current_config["mail_receiver"],
                                "Attach_Logs": self.current_config["attachment"]}

            parser["Access_to_mail"] = {"user": self.le_mail_sender.text(),
                                        "password": base64.b64encode(self.le_mail_password.text().encode("utf-8")).decode("utf-8"),
                                        "server": self.le_mail_server.text(),
                                        "port":self.le_mail_server_port.text()}
            
            if self.current_config["limits"]["cpu"]:
                parser["limits_cpu"] = {"soft": self.current_config["limits"]["cpu"]["soft"],
                                        "hard": self.current_config["limits"]["cpu"]["hard"]}

            if self.current_config["limits"]["ram"]:
                parser["limits_ram"] = {"soft": self.current_config["limits"]["ram"]["soft"],
                                        "hard": self.current_config["limits"]["ram"]["hard"]}

            
            for k, v in self.current_config["limits"]["drives"].items():
                if self.current_config["limits"]["drives"][k]:
                    parser[f"limits_{k}"] = {"soft": v["soft"],
                                             "hard": v["hard"]}

            with open("Temp/running_config.ini", "w") as c:
                parser.write(c)

            self.lb_config_info.setStyleSheet("color: green")
            self.lb_config_info.setText("Laufende Konfiguration gespeichert")
            
            log("Logs/system.log", "info", "Temp/running_config.ini wurde geschrieben")
            
            """
            # Anschließend wird die ini-Datei geparsed und in die self.current_config-Variable geschrieben
            # Der Grund, warum dasgemacht wird ist, ist, weil zu diesem Zeitpunkt self.current_config noch für jede
            # Monitoring-Möglichkeit (CPU-Monitoring, RAM-Monitoring und alle Laufwerke-Monitorings), die nicht konfiguriert sind,
            # ein leeres Dictionary enthält
            """
            try:
                self.current_config = {"username": "",
                                       "password": "",
                                       "server": "",
                                       "port": "",
                                       "mail_receiver": "",
                                       "attachment": None,
                                       "limits": {}}

                parser = ConfigParser()
                parser.read("Temp/running_config.ini")

                # Section "Access_to_mail"
                self.current_config["username"] = parser["Access_to_mail"]["user"]
                self.current_config["password"] = parser["Access_to_mail"]["password"]
                self.current_config["server"] = parser["Access_to_mail"]["server"]
                self.current_config["port"] = int(parser["Access_to_mail"]["port"])
                
                # Section "DEFAULT"
                self.current_config["mail_receiver"] = parser["DEFAULT"]["mailadressen"]
                self.current_config["attachment"] = eval(parser["DEFAULT"]["attach_logs"])

                # Section "limits*""
                for limit in parser.sections():
                    if "limits" in limit:
                        if "limits_cpu" == limit:
                            self.current_config["limits"]["cpu"] = {"soft": int(parser[limit]["soft"]), "hard": int(parser[limit]["hard"])}
                        elif "limits_ram" == limit:
                            self.current_config["limits"]["ram"] = {"soft": int(parser[limit]["soft"]), "hard": int(parser[limit]["hard"])}
                        else:
                            self.current_config["limits"][limit[-2:]] = {"soft": int(parser[limit]["soft"]), "hard": int(parser[limit]["hard"])}

                log("Logs/system.log", "info", f"Temp/running_config.ini-Datei erfolgreich geparsed")
                return True
                
            except Exception as e:
                log("Logs/system.log", "error", f"Temp/running_config.ini-Datei konnte nicht erfolgreich geparsed werden. Fehler: {e}")
                return False
        else:
            return False
        
    def startup_config(self):
        """
        Ini-Datei dauerhaft speichern und beim erneuten Aufruf des Programms automatisch parsen.
        Im Prinzip wird nur die running_config.ini erstellt und anschließend kopiert
        """
        
        self.lb_timer = time.time()
        
        # current_config wird vorher in einer Variablen gespeichert, falls self.running_config False returnt. Wenn False 
        # returnt wird, ist self.current_config None (wird beim Aufruf der Funktion check_config auf None gesetzt). Somit 
        # kann man dies wieder rückgängig machen
        current_config = self.current_config
        
        # Erstellung der running_config. Falls eine Eingabe des Users fehlerhaft ist oder fehlt, wird False returnt. 
        if not self.running_config():
            self.current_config = current_config
            return
        
        # Es wird die running_config.ini kopiert und als startup_config.ini gespeichert
        try:
            shutil.copy("Temp/running_config.ini", "startup_config.ini")            
            self.lb_config_info.setStyleSheet("color: green")
            self.lb_config_info.setText("Startup Konfiguration gespeichert")
            log("Logs/system.log", "info", "startup_config.ini erfolgreich erstellt")

        except Exception as e:
            self.lb_config_info.setStyleSheet("color: red")
            self.lb_config_info.setText(f"Startup Konfiguration konnte nicht gespeichert werden. Fehler: {e}")
            log("Logs/system.log", "error", f"startup_config.ini konnte nicht erstellt werden. Fehler: {e}")
 
    def check_config(self):
        """
        Methode wird aufgerufen, wenn man die Konfiguration speichern möchte. Hier wird geprüft, ob die Eingaben,
        die der User gemacht hat, korrekt sind.
        :return: Entweder False oder ein Dictionary
        """
        
        self.lb_config_warnings.clear()
        self.lb_config_warnings.setStyleSheet("color: red")
        self.lb_config_info.clear()
        self.lb_timer = time.time()

        log("Logs/system.log", "info", "Starte Überprüfung der Konfiguration")
        
        # Sollten irgendwelche Prozesse am laufen sein, müssen diese zunächst beendet werden. False wird returnt
        if self.processes:
            self.lb_config_warnings.setText("Beende zunächst alle Monitorings.")
            log("Logs/system.log", "error", "current_config.ini konnte nicht geschrieben werden - alle Monitorings müssen beendet sein")
            return False
        
        # Mailaccount muss zunächst validiert sein. False wird returnt
        if not self.mail_access:
            self.lb_config_warnings.setText("Validiere zunächst den Mailzugang.")
            log("Logs/system.log", "info", "current_config.ini konnte nicht geschrieben werden - Mailzugang muss zunächst validiert werden")
            return False
        
        # must_have_inputs sind die inputs, die benötigt werden, sodass die Konfiguration gespeichert werden kann.
        # Dazu zählen die Mailzugangsdaten sowie der Mailempfänger
        must_have_inputs = []
        warn_msg_lb = "|"
        drive_chosen = {}

        # Es wird zunächst ein Dictionary mit allen möglichen Einstellungen erstellt
        config = {"mail_receiver": "",
                  "attachment": None,
                  "limits": {"cpu": {},
                             "ram": {},
                             "drives": {}}}

        # Alle Laufwerke werden dem dictionary hinzugefügt
        for drive in self.drives:
            config["limits"]["drives"][drive] = {}
            drive_chosen[drive] = {"soft": "", "hard": ""}
        
        # Der aktuelle Text des LineEdits für die Empfänger-Mailadresse wird ausgelesen
        # Wenn nichts eingegeben wurde oder nur Whitespaces, dann wird False der Liste must_have_inputs
        # hinzugefügt 
        if self.le_mail_receiver.text().strip():
            config["mail_receiver"] = self.le_mail_receiver.text()
        else:
            must_have_inputs.append(False)
            warn_msg_lb += " Keine Mailadresse angegeben* |"
            log("Logs/system.log", "info", "Keine Mailadressen angegeben")
        

        if self.cb_attachment_sent.currentText() == "Nein":
            config["attachment"] = False
        else:
            config["attachment"] = True


        # Die Konfiguration der Schwellenwerte ist optional, jedoch muss der User die entsprechenden 
        # Schwellenwerte konfiguriert haben (z. B. für die CPU), um das Monitoring dafür zu starten

        # Überprüfung der CPU-Schwellenwerte

        if (self.cb_cpu_softlimit.currentText() == "") and (not self.cb_cpu_hardlimit.currentText() == ""):
            warn_msg_lb += " CPU - Wert wurde nicht eingegeben |"
        
        elif (self.cb_cpu_hardlimit.currentText() == "") and (not self.cb_cpu_softlimit.currentText() == ""):
            warn_msg_lb += " CPU - Wert wurde nicht eingegeben |"
        
        elif self.cb_cpu_softlimit.currentText() == "" and self.cb_cpu_softlimit.currentText() == "":
            pass

        elif int(self.cb_cpu_softlimit.currentText() ) >= int(self.cb_cpu_hardlimit.currentText() ):
            warn_msg_lb += " CPU - Hardlimit muss größer als Softlimit sein |"
        
        else:
            config["limits"]["cpu"]["soft"] = int(self.cb_cpu_softlimit.currentText())
            config["limits"]["cpu"]["hard"] = int(self.cb_cpu_hardlimit.currentText())


        # Überprüfung der RAM-Schwellenwerte
                
        if (self.cb_ram_softlimit.currentText()  == "" and not self.cb_ram_hardlimit.currentText()  == ""):
            warn_msg_lb += " Arbeitsspeicher - Ein Wert wurde nicht eingegeben |"

        elif (self.cb_ram_hardlimit.currentText()  == "" and not self.cb_ram_softlimit.currentText()  == ""):
            warn_msg_lb += " Arbeitsspeicher - Ein Wert wurde nicht eingegeben |"

        elif self.cb_ram_softlimit.currentText() == "" and self.cb_ram_softlimit.currentText()  == "":
            pass
        
        elif int(self.cb_ram_softlimit.currentText() ) >= int(self.cb_ram_hardlimit.currentText()):
            warn_msg_lb += " Arbeitsspeicher - Hardlimit muss größer als Softlimit sein |"
        
        else:
            config["limits"]["ram"]["soft"] = int(self.cb_ram_softlimit.currentText())
            config["limits"]["ram"]["hard"] = int(self.cb_ram_hardlimit.currentText())


        # Überprüfung der Laufwerk-Schwellenwerte
        for k in self.drive_chosen.keys():

            if self.drive_chosen[k]["soft"] == "" and self.drive_chosen[k]["hard"] == "":
                pass

            elif (self.drive_chosen[k]["soft"] == "" and not self.drive_chosen[k]["hard"] == "") or (self.drive_chosen[k]["hard"] == "" and not self.drive_chosen[k]["soft"] == ""):
                warn_msg_lb += f" {k} - Ein Wert wurde nicht eingegeben |"

            elif int(self.drive_chosen[k]["soft"]) >= int(self.drive_chosen[k]["hard"]):
                warn_msg_lb += f" {k} - Hardlimit muss größer als Softlimit sein |"
            
            else:
                config["limits"]["drives"][k]["soft"] = int(self.drive_chosen[k]["soft"])
                config["limits"]["drives"][k]["hard"] = int(self.drive_chosen[k]["hard"])
                
        
        # Falls bei der Konfiguration der Schwellenwerte nicht alle Eingaben korrekt sind, wird eine Warn-Message 
        # in ein Label geschrieben, jedoch wird die Konfiguration trotzdem gespeichert (nur ohne die fehlerhafte 
        # Konfiguration)
        if len(warn_msg_lb) != 1:
            self.lb_config_warnings.setText(warn_msg_lb)
        
        # Nur wenn alle must_have_inputs True sind, wird das config-Dictionary returnt. Anderenfalls False
        if all(must_have_inputs):
            log("Logs/system.log", "info", "Beende Überprüfung Konfigurationsdateien. Alle essentiellen Eingaben sind gültig.")
            return config
        else:
            log("Logs/system.log", "info", "Beende Überprüfung Konfigurationsdateien. Mind. eine ungültige essentielle Eingabe")
            return False

    def cb_drives_limits_refresh(self):
        """
        Die ComboBoxen im Konfigurationstab der Limits werden angepasst, sobald sich der Text der ComboBox ändert.
        """
        for k in self.drive_chosen.keys():
            if k == self.cb_drives_limits.currentText():
                self.cb_drives_softlimit.setCurrentText(str(self.drive_chosen[k]["soft"]))
                self.cb_drives_hardlimit.setCurrentText(str(self.drive_chosen[k]["hard"]))

    def cb_drive_soft_commit(self):
        """
        Der Wert des Softlimits des aktuell ausgewählten Laufwerks wird ins self.drive_chosen-Dictionary geschrieben
        """
        for k in self.drive_chosen.keys():
            if k == self.cb_drives_limits.currentText():
                self.drive_chosen[k]["soft"] = self.cb_drives_softlimit.currentText()

    def cb_drive_hard_commit(self):
        """
        Der Wert des Hardlimits des aktuell ausgewählten Laufwerks wird ins self.drive_chosen-Dictionary geschrieben
        """
        for k in self.drive_chosen.keys():
            if k == self.cb_drives_limits.currentText():
                self.drive_chosen[k]["hard"] = self.cb_drives_hardlimit.currentText()

    def validate_login(self):
        """
        Validierung der Logindaten
        """

        self.lb_timer = time.time()
        self.lb_config_info.clear()
        self.lb_config_warnings.clear()

        try:
            if not self.le_mail_sender.text() or not self.le_mail_password.text() or not self.le_mail_server.text() or not self.le_mail_server_port.text():
                self.lb_config_warnings.setStyleSheet("color: red")
                self.lb_config_warnings.setText("Es müssen alle Felder ausgefüllt werden")
                log("Logs/system.log", "info", "Mailkonto-Validierung - nicht alle Felder sind ausgefüllt")
                return

            # Es wird nur versucht, sich mit den Logindaten an dem ausgewählten Mailserver anzumelden. Wenn das klappt, 
            # ist das Mailkonto validiert und wird zu Eingabe disabled
            mailserver = smtplib.SMTP(self.le_mail_server.text(), int(self.le_mail_server_port.text()))
            mailserver.ehlo()
            mailserver.starttls()
            mailserver.ehlo()
            mailserver.login(self.le_mail_sender.text(), self.le_mail_password.text())
            
            self.mail_access = True
            self.lb_config_info.setStyleSheet("color: green")
            self.lb_config_info.setText("Validierung erfolgreich")
            log("Logs/system.log", "info", f"Mailkonto-Validierung mit Konto '{self.le_mail_sender.text()}' erfolgreich")

        except ValueError:
            self.lb_config_info.setStyleSheet("color: red")
            self.lb_config_info.setText("Port muss eine Zahl sein")
            log("Logs/system.log", "info", f"Mailkonto-Validierung - Port '{self.le_mail_server_port.text()}' ist keine Zahl")
        except smtplib.SMTPAuthenticationError:
            self.lb_config_info.setStyleSheet("color: red")
            self.lb_config_info.setText("Logindaten nicht korrekt")
            log("Logs/system.log", "info", f"Mailkonto-Validierung - Credentials sind nicht korrekt")
        except Exception as e:
            self.lb_config_info.setStyleSheet("color: red")
            self.lb_config_info.setText(f"Folgender Fehler: {e}")
            log("Logs/system.log", "info", f"Mailkonto-Validierung - Folgender Fehler ist aufgetreten: {e} ")
        
    def initGraph(self):
        """
        Initialisierung des Graphen-Tabs
        """
        
        self.tab_graph = QWidget()
        self.tabWidget.addTab(self.tab_graph, "Graph")


        self.tab_graph_mon = QTabWidget(self.tab_graph)
        self.tab_graph_mon.setGeometry(QRect(0, 0, self.width, self.height))
        

        self.tab_graph_mon_cpu = QWidget()
        self.tab_graph_mon.addTab(self.tab_graph_mon_cpu, "CPU")
        # Mit PlotCanvas wird ein neues Objekt erstellt und auf den self.tab_graph_mon_cpu embedded
        # Die Werte für den Live-Graphen erhält der Graph über die cpu.pickle-Datei
        PlotCanvas(self.tab_graph_mon_cpu, width=10, height=4, pickle_file="Temp/cpu.pickle").move(0, 100)


        self.tab_graph_mon_ram = QWidget()
        self.tab_graph_mon.addTab(self.tab_graph_mon_ram, "Arbeitsspeicher")
        PlotCanvas(self.tab_graph_mon_ram, width=10, height=4, pickle_file="Temp/ram.pickle").move(0, 100)
        
        # Variable zur Positionierung der Widgets
        y = 40
        

        self.lb_graph_mon_cpu_description = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_cpu_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_graph_mon_cpu_description.setText("CPU:")

        self.lb_graph_mon_cpu_value = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_cpu_value.setGeometry(QRect(115, y, 50, self.lb_y_default))
        
        self.lb_graph_mon_cpu_avg_description = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_cpu_avg_description.setGeometry(QRect(165, y, self.lb_x_default, self.lb_y_default))
        self.lb_graph_mon_cpu_avg_description.setText("CPU-Durchschnitt (60s):")

        self.lb_graph_mon_cpu_avg_value = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_cpu_avg_value.setGeometry(QRect(380, y, 50, self.lb_y_default))
        y += 25


        self.lb_graph_mon_ram_description = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_ram_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_graph_mon_ram_description.setText("Arbeitsspeicher:")

        self.lb_graph_mon_ram_value = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_ram_value.setGeometry(QRect(115, y, 50, self.lb_y_default))

        self.lb_graph_mon_ram_avg_description = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_ram_avg_description.setGeometry(QRect(165, y, self.lb_x_default, self.lb_y_default))
        self.lb_graph_mon_ram_avg_description.setText("Arbeitsspeicher-Durchschnitt (60s):")

        self.lb_graph_mon_ram_avg_value = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_ram_avg_value.setGeometry(QRect(380, y, 50, self.lb_y_default))
        y += 25


        self.lb_graph_mon_processes_description = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_processes_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_graph_mon_processes_description.setText("Anzahl Prozesse:")

        self.lb_graph_mon_processes_value = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_processes_value.setGeometry(QRect(115, y, 50, self.lb_y_default))
        y += 25


        self.lb_graph_mon_system_time_description = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_system_time_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_graph_mon_system_time_description.setText("Systemzeit:")

        self.lb_graph_mon_system_time_value = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_system_time_value.setGeometry(QRect(115, y, 50, self.lb_y_default))

    def refresh_current_utilization(self):
        """
        Diese Methode wird sekündlich vom QTimer aufgerufen. Somit wird der Graph sekündlich aktualisiert
        """
        
        # Einlesen der aktuellen Hardwareinformationen sowie die Anzahl der Prozesse und die aktuelle 
        # Laufzeit des Programms
        cpu = psutil.cpu_percent()
        ram = round(get_virtual_memory()["percent"], 2)
        processes = len(psutil.pids())
        system_time = round(time.time() - self.start_system_time)

        
        # Die eingelesenen Werte werden den Listen angehängt
        self.cpu_values.append(cpu)
        self.ram_values.append(ram)
        self.systemtime_values.append(system_time)
        
        # Sollten die Werte > 60 sein, wird der erste Wert gelöscht. Somit zeigt der Graph immer
        # nur die letzten 60 Sekunden an
        if len(self.cpu_values) > 60:
            del self.cpu_values[0]
            del self.ram_values[0]
            del self.systemtime_values[0]
        
        # Durchschnittswerte der Auslastungen werden berechnet, da diese in Labels als Klartext
        # angezeigt werden
        cpu_avg = round(sum(self.cpu_values)/len(self.cpu_values), 2)
        ram_avg = round(sum(self.ram_values)/len(self.ram_values), 2)
        
        # Liste der Werte werden mit dem pickle-Modul in eine Datei geschrieben, die vom Graphen 
        # eingelesen wird und kann somit die Werte graphisch darstellen
        with open("Temp/cpu.pickle", "wb") as p:
            pickle.dump([self.systemtime_values, self.cpu_values], p)

        with open("Temp/ram.pickle", "wb") as p:
            pickle.dump([self.systemtime_values, self.ram_values], p)
        
        # Lables werden mit den neuen Werten beschriftet
        self.lb_graph_mon_cpu_value.setText(str(cpu) + " %")
        self.lb_graph_mon_ram_value.setText(str(ram) + " %")
        self.lb_graph_mon_processes_value.setText(str(processes))
        self.lb_graph_mon_system_time_value.setText(str(system_time) + " s")
        self.lb_graph_mon_cpu_avg_value.setText(str(cpu_avg) + " %")
        self.lb_graph_mon_ram_avg_value.setText(str(ram_avg) + " %")
        
        # Alle Status-, Error und Warninglabels werden nach 3 Sekunden gecleared
        if time.time() - self.lb_timer >= 3:
            self.lb_config_warnings.clear()
            self.lb_error.clear()
            self.lb_config_info.clear()
            self.lb_status.clear()
            self.lb_info_saved.clear()
        
        """
        Kleines Feature zur Visualisierung. Sollte ein Monitoring laufen (z. B. für die CPU),
        wird die Schriftfarbe der Labels entsprechend gefärbt 
        rot=Hardlimit überschritten
        orange=Softlimit überschritten
        grün=kein Limit überschritten
        schwarz=Monitoring läuft nicht
        """
        try:
            if "CPU" in self.monitoring:
                soft = int(self.current_config["limits"]["cpu"]["soft"])
                hard = int(self.current_config["limits"]["cpu"]["hard"])

                if soft <= cpu < hard:
                    self.lb_graph_mon_cpu_value.setStyleSheet("color: orange")
                elif cpu >= hard:
                    self.lb_graph_mon_cpu_value.setStyleSheet("color: red")
                else:
                    self.lb_graph_mon_cpu_value.setStyleSheet("color: green")
            else:
                self.lb_graph_mon_cpu_value.setStyleSheet("color: black")

            if "Arbeitsspeicher" in self.monitoring:
                soft = int(self.current_config["limits"]["ram"]["soft"])
                hard = int(self.current_config["limits"]["ram"]["hard"])

                if soft <= ram < hard:
                    self.lb_graph_mon_ram_value.setStyleSheet("color: orange")
                elif ram >= hard:
                    self.lb_graph_mon_ram_value.setStyleSheet("color: red")
                else:
                    self.lb_graph_mon_ram_value.setStyleSheet("color: green")
            else:
                self.lb_graph_mon_ram_value.setStyleSheet("color: black")
        except:
            pass

class PlotCanvas(FigureCanvas):
    """
    Das matploblob-Canvas, was den Live-Graphen in der GUI anzeigt
    """
    def __init__(self, parent, width, height, pickle_file):
        """
        :param parent: QWidget -> wo das Canvas embedded wird
        :param width: Integer -> Breite des Graphen
        :param height: Integer -> Höhe des Graphen
        :param pickle_file: String -> Pfad der pickle-Datei mit den Werten für den Graphen
        :return: None
        """
        
        self.file = pickle_file

        self.fig = Figure(figsize=(width, height))
        self.axis = self.fig.add_subplot(1, 1, 1)
        self.axis.set_ylabel("Auslastung in %")
        self.axis.set_xlabel("Zeit in s")

        self.axis.set_ylim(ymin=0, ymax=105)
        
        # Der Konstruktor der geerbten Klasse FigureCanvas wird aufgerufen
        FigureCanvas.__init__(self, self.fig)
        
        self.setParent(parent)
        
        # Animationsmethode wird gestartet
        self.ani = animation.FuncAnimation(self.fig, self.animate, interval=1000)

    def animate(self, i):
        # Überprüfung ob die Datei existiert
        if os.path.isfile(self.file):
            try:
                # Die pickle-Datei wird gelesen/geladen
                # xs und ys sind jeweils eine Liste
                with open(self.file, "rb") as p:
                    xs, ys = pickle.load(p)
                
                # Durchschnittswerte
                y_mean = [sum(ys)/len(ys)] * len(ys)

                # Skalierung der Achsen sind Integer und keine Floats
                self.axis.yaxis.set_major_locator(MaxNLocator(integer=True))
                self.axis.xaxis.set_major_locator(MaxNLocator(integer=True))
                
                # Achsen werden gecleared, da sonst jede Sekunde ein neuer Graph erstellt wird
                self.axis.clear()
                # Skalierung der y-Achse
                self.axis.set_ylim(ymin=0, ymax=105)
                
                # Beschriftung der Labels
                self.axis.set_ylabel("Auslastung in %")
                self.axis.set_xlabel("Zeit in s")
                
                # Achsen werden geplotted udnd erhalten ein Label, sodass man sieht, welche Achse was ist
                self.axis.plot(xs, ys, label="Auslastung letzte 60 s")
                self.axis.plot(xs, y_mean, label="Durchschnitt Auslastung letzte 60 s", linestyle="--")
                
                # Legende ist oben links lokalisiert
                self.axis.legend(loc='upper left')
            except Exception as e:
                log("Logs/monitoring.log", "error", f"Graph-Animation nicht möglich. Fehler: {e}")


if __name__ == "__main__":
    if platform.system() == "Windows":
        app = QApplication(sys.argv)
        window = Monitoring()
        sys.exit(app.exec_())
    else:
        print("Monitoring kann nur unter Windows gestartet werden")
