from PyQt5 import QtGui
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QRect, QTimer
from PyQt5.QtGui import QIcon, QTextCursor
import sys
from functions import *
import psutil
import multiprocessing
import json
import smtplib
import base64
import shutil
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import style
from matplotlib.ticker import MaxNLocator
import pickle
import glob
import uuid
import re
import datetime
import dicttoxml
from xml.dom.minidom import parseString


class Monitoring(QMainWindow):
    def __init__(self):
        super().__init__()
        self.title = "Monitoring"
        self.icon = "Images/Icon.png"
        
        self.width = 1000
        self.height = 600

        self.lb_x_default = 200
        self.lb_y_default = 25

        self.start_system_time = time.time()
        self.cpu_values = []
        self.ram_values = []
        self.systemtime_values = []

        self.processes = {}     # {<name of monitoring>: <PID>}
        self.monitoring = []    # List with the names of monitorings for the current running monitorings (QListWigdet)
        self.drives = get_pc_information()["drives"]    # List with all drives

        self.drive_chosen = {}  # dictionary for the soft- and hardlimits
        for drive in self.drives:
            self.drive_chosen[drive] = {"soft": "", "hard": ""}
        self.mail_access = False    # Bool for checking if the login credentials of the mailaccount are valid

        log("Logs/system.log", "info", "Programm gestartet")

        self.timer_refresh_current_utilization = QTimer(self)
        self.timer_refresh_current_utilization.timeout.connect(self.refresh_current_utilization)
        self.timer_refresh_current_utilization.start(1000)
        self.current_timer = 0
        
        
        self.initWindow()   # initialize Main Window
        
        # if the startup_config.ini - File exists the current_configuration initialiaze
        if os.path.isfile("startup_config.ini"):
            try:
                self.current_config = {"username": "",
                                       "password": "",
                                       "server": "",
                                       "port": "",
                                       "logs_path": "",
                                       "mail_receiver": [],
                                       "attachment": None,
                                       "limits": {}}

                # parsing through the config-file
                # parses through all sections of the config file, sets the values to the "self.current_config"-dictionary and fills the
                # line-edits and combo-boxes with the values, that are written in the config file.
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

                self.le_mail_server.setDisabled(True)
                self.le_mail_server_port.setDisabled(True)
                self.le_mail_sender.setDisabled(True)
                self.le_mail_password.setDisabled(True)
                self.mail_access = True


                # Section "DEFAULT"
                self.current_config["logs_path"] = parser["DEFAULT"]["pfad_logs"]
                mail_addresses = (parser["DEFAULT"]["mailadressen"]).split(";")
                for mail in mail_addresses:
                    self.current_config["mail_receiver"].append(mail)
                self.current_config["attachment"] = eval(parser["DEFAULT"]["attach_logs"])
                
                self.le_logs_destination_value.setText(self.current_config["logs_path"])
                self.le_mail_receiver.setText((";").join(self.current_config["mail_receiver"]))

                self.current_config["attachment"] = eval(parser["DEFAULT"]["attach_logs"])
                
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

            except Exception as e:
                self.lb_config_warnings.setStyleSheet("color: red")
                self.lb_config_warnings.setText(e)
                log("Logs/system.log", "error", f"Initialisierung Temp/running_config schlug fehl: {e}")

        else:
            self.current_config = None
            log("Logs/system.log", "info", f"current_config.ini existiert nicht")
        
        
        self.push_logs()

    def closeEvent(self, event):
        """
        If closing the window
        """

        try:
            # Delete running_config.ini File
            if os.path.isfile("Temp/running_config.ini"):
                os.remove("Temp/running_config.ini")
                log("Logs/system.log", "info", "Temp/running_config.ini-Datei wurde gelöscht")

            # Kill all (monitoring) processes
            for mon, pid in self.processes.items():
                try:
                    psutil.Process(pid).terminate()
                    log("Logs/monitoring.log", "info", f"{mon}-Monitoring wurde beendet. Prozess-ID: {pid}")
                except:
                    log("Logs/monitoring.log", "error", f"{mon}-Monitoring mit der Prozess-ID {pid} war bereits beendet")
            
            # Delete all pickle-Files
            for f in glob.glob("Temp/*.pickle"):
                os.remove(f)
                log("Logs/system.log", "info", f"{f}-Datei wurde gelöscht")
            
        except Exception as e:
            log("Logs/system.log", "debug", f"Programm beenden - Folgender Fehler ist aufgetreten: {e}")
        
        else:
            log("Logs/system.log", "info", f"Programm nach {round(time.time()-self.start_system_time, 2)} Sekunden beendet")
            
    def initWindow(self):
        # Mainwindow Einstellungen
        self.setWindowTitle(self.title)
        self.setWindowIcon(QtGui.QIcon(self.icon))
        self.setFixedSize(self.width, self.height)

        # Tabwidget erstellt
        self.tabWidget = QTabWidget(self)
        self.tabWidget.setGeometry(QRect(0, 0, self.width, self.height))
        
        # Tabs werden initialisiert
        self.initMonitoring()    
        self.initComputerinformation()
        self.initLogs()        
        self.initConfig()        
        #self.initCurrentUtilization()
        self.initGraph()
        
        # Anzeige der GUI
        self.show()

    def initMonitoring(self):
        """
        Setup all the different widget. 
        Name-convention:
        tab_* -> QTabWidget
        lb_* -> QLabel
        btn_* -> QPushButton
        le_* -> QLineEdit
        lw_* -> QListWidget
        """

        self.tab_monitoring = QWidget()
        self.tabWidget.addTab(self.tab_monitoring, "Monitoring")

        self.lb_cpu_start_stop = QLabel(self.tab_monitoring)
        self.lb_cpu_start_stop.setGeometry(QRect(15, 15, self.lb_x_default, self.lb_y_default))
        self.lb_cpu_start_stop.setText("CPU-Monitoring")

        self.btn_cpu_start_stop = QPushButton(self.tab_monitoring)
        self.btn_cpu_start_stop.setGeometry(QRect(200, 15, 130, 25))
        self.btn_cpu_start_stop.setText("Start")
        

        self.lb_ram_start_stop = QLabel(self.tab_monitoring)
        self.lb_ram_start_stop.setGeometry(QRect(15, 50, self.lb_x_default, self.lb_y_default))
        self.lb_ram_start_stop.setText("Arbeitsspeicher-Monitoring")

        self.btn_ram_start_stop = QPushButton(self.tab_monitoring)
        self.btn_ram_start_stop.setGeometry(QRect(200, 50, 130, 25))
        self.btn_ram_start_stop.setText("Start")
        

        self.lb_disk_start_stop = QLabel(self.tab_monitoring)
        self.lb_disk_start_stop.setGeometry(QRect(15, 85, self.lb_x_default-50, self.lb_y_default))
        self.lb_disk_start_stop.setText("Festplatten-Monitoring")

        self.cb_disk_mon = QComboBox(self.tab_monitoring)
        self.cb_disk_mon.setGeometry(QRect(150, 85, 40, 25))

        for drive in self.drives:
            self.cb_disk_mon.addItem(drive)
    
        self.btn_disk_start_stop = QPushButton(self.tab_monitoring)
        self.btn_disk_start_stop.setGeometry(QRect(200, 85, 130, 25))
        self.btn_disk_start_stop.setText("Start")

        self.lb_monitoring_description = QLabel(self.tab_monitoring)
        self.lb_monitoring_description.setGeometry(QRect(15, 130, self.lb_x_default-50, self.lb_y_default))
        self.lb_monitoring_description.setText("Laufende Monitorings:")

        self.lw_processes = QListWidget(self.tab_monitoring)
        self.lw_processes.setGeometry(QRect(15, 155, 100, 200))
        
        self.lb_error = QLabel(self.tab_monitoring)
        self.lb_error.setGeometry(QRect(15, self.height-50, self.width-50, self.lb_y_default))
        self.lb_error.setStyleSheet("color: red")

        self.lb_status = QLabel(self.tab_monitoring)
        self.lb_status.setGeometry(QRect(15, self.height-100, self.width-50, self.lb_y_default))
        self.lb_status.setStyleSheet("color: green")

        # Connect buttons and combobox to methods
        self.btn_cpu_start_stop.clicked.connect(self.start_cpu)
        self.btn_ram_start_stop.clicked.connect(self.start_ram)
        self.btn_disk_start_stop.clicked.connect(lambda: self.start_disk(self.cb_disk_mon.currentText()))
        self.cb_disk_mon.currentTextChanged.connect(lambda: self.cb_disk_mon_change(self.cb_disk_mon.currentText()))

    def start_cpu(self):
        self.start("cpu", "CPU", self.btn_cpu_start_stop, mon_cpu)
       
    def start_ram(self):
        self.start("ram", "Arbeitsspeicher", self.btn_ram_start_stop, mon_memory)

    def start_disk(self, disk):
        """
        :param disk: current chosen disk in the combobox
        """
        # Initialisiere Errorlabel und Statuslabel
        self.lb_error.clear()
        self.lb_status.clear()
        

        # Only if the current_config is initialized you can start monitoring
        if self.current_config is not None:
            try:
                username = self.current_config["username"]
                pwd = base64.b64decode(self.current_config["password"]).decode("utf-8")
                server = self.current_config["server"]
                port = self.current_config["port"]
                logs = self.current_config["logs_path"]

                if not os.path.isdir(logs):
                    raise FileNotFoundError

                attachment = self.current_config["attachment"]
                mail_receiver = self.current_config["mail_receiver"]

                soft = int(self.current_config["limits"][disk]["soft"])
                hard = int(self.current_config["limits"][disk]["hard"])

            except KeyError:
                self.lb_error.setText(f"{disk}-Limits sind nicht konfiguriert.")
                log("Logs/system.log", "error", f"Starten Laufwerk {disk}-Monitorings schlug fehl. Limits sind nicht konfiguriert")
                return
            except FileNotFoundError:
                self.lb_error.setText("Logs-Pfad existiert nicht (mehr)")
                log("Logs/system.log", "error", f"Log-Pfad '{logs}' zur Speicherung der Schwellenwert-Überschreitungen-Logs extistiert nicht")
                return
            except Exception as e:
                self.lb_error.setText(f"Fehler: {e}")
                log("Logs/system.log", "error", f"Aktuelle Konfiguration konnte nicht initiiert werden. Fehler: {e}")
                return

            self.lw_processes.clear()

            """
            Check if the monitoring for the current disk is running
            if True -> Stop monitoring of this disk, the button-text change to "Start",
            status_label-text changed, remove item from the list (for the Listwidget) and
            remove item from the dictionary with the running processes. 
            iterate through the monitoring list and set all the items of monitoring-list 
            to the listwidget
            After this return so the rest of this method will not be executed
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
            
            try:
                # Check if disk is available (in case it's a network disk which is disconnected)
                psutil.disk_usage(disk)
            except Exception as e:
                self.lb_error.setStyleSheet("color: red")
                self.lb_error.setText(e)
                log("Logs/monitoring.log", "info", "Überprüfung, ob alle Laufwerke erreichbar sind --> True")
                return

            """
            If the monitoring for this disk is not running:
            status label changed, button-name set to "Stop", append the description of the monitoring to 
            the monitoring list, starts a seperate monitoring process and creates a new dictionary entry 
            with the name of the process and the PID
            iterate through the monitoring list and set all the items of monitoring-list 
            to the listwidget
            """
            try:
                process = multiprocessing.Process(target=mon_disk, 
                                                args=(disk, logs, mail_receiver, attachment, soft, 
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

        else:
            self.lb_error.setText("Wähle zuerst eine Konfiguration.")
            log("Logs/monitoring.log", "info", f"Laufwerk {disk}-Monitoring konnte nicht gestartet werden - keine Konifguration vorhanden")

    def cb_disk_mon_change(self, disk):
        """
        Changes the button text to "Stopp" or "Start" whether the monitoring for the current chosen disk is started or not
        """
        if self.current_config is not None:

            for d in self.processes.keys():
                if disk == d:
                    self.btn_disk_start_stop.setText("Stopp")
                    return

            self.btn_disk_start_stop.setText("Start")

    def start(self, typ, description, btn, function):
        """
        :param typ: String -> "cpu" or "ram". This is the description for the processes-key
        :param description: String -> Description the the current running processes (for the List-Widget)
        :param btn: QPushButton-Object to change the text of the button
        Start for either cpu-monitoring or ram-monitoring
        """

        # Initialize errorlabel und statuslabel
        self.lb_error.clear()
        self.lb_status.clear()
        
        # Only if the current_config is initialized you are able to start the monitoring
        if self.current_config is not None:

            try:
                username = self.current_config["username"]
                pwd = base64.b64decode(self.current_config["password"]).decode("utf-8")
                server = self.current_config["server"]
                port = self.current_config["port"]
                logs = self.current_config["logs_path"]

                if not os.path.isdir(logs):
                    raise FileNotFoundError

                attachment = self.current_config["attachment"]
                mail_receiver = self.current_config["mail_receiver"]

                soft = int(self.current_config["limits"][typ]["soft"])
                hard = int(self.current_config["limits"][typ]["hard"])

            except KeyError:
                self.lb_error.setText(f"{description}-Limits sind nicht konfiguriert.")
                log("Logs/system.log", "error", f"Starten {typ.upper()}-Monitorings schlug fehl. Limits sind nicht konfiguriert")
                return
            except FileNotFoundError:
                self.lb_error.setText("Logs-Pfad existiert nicht (mehr)")
                log("Logs/system.log", "error", f"Log-Pfad '{logs}' zur Speicherung der Schwellenwert-Überschreitungen-Logs extistiert nicht")
                return
            except Exception as e:
                self.lb_error.setText(f"Fehler: {e}")
                log("Logs/system.log", "error", f"Aktuelle Konfiguration konnte nicht initiiert werden. Fehler: {e}")
                return
            
            self.lw_processes.clear()
            
            """
            Check if the monitoring for is running
            if True -> Stop monitoring , the button-text change to "Start",
            status_label-text changed, remove item from the list (for the Listwidget) and
            remove item from the dictionary with the running processes. 
            iterate through the monitoring list and set all the items of monitoring-list 
            to the listwidget
            After this return so the rest of this method will not be executed
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
            If the monitoring is not running:
            status label changed, button-name set to "Stop", append the description of the monitoring to 
            the monitoring list, starts a seperate monitoring process and creates a new dictionary entry 
            with the name of the process and the PID
            iterate through the monitoring list and set all the items of monitoring-list 
            to the listwidget
            """
            try:
                self.lb_status.setText(f"Starte {description}-Monitoring")
                btn.setText("Stopp")
                self.monitoring.append(description)

                process = multiprocessing.Process(target=function, 
                                                args=(logs, mail_receiver, attachment, soft, hard, 
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
        Initializing the "Computerinformationen"-Tab and sets all the values 
        """
        self.pc_info = get_pc_information()
        self.lb_x_value = 400
        
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
            self.computerinfo["drives"][drive] = {"total_GiB": get_disk_usage(drive)["total"],
                                                  "used_GiB": get_disk_usage(drive)["used"],
                                                  "free_GiB": get_disk_usage(drive)["free"]}

        y = 15
                        
        self.tab_computerinformation = QWidget()
        self.tabWidget.addTab(self.tab_computerinformation, "Computerinformationen")

        self.lb_user_description = QLabel(self.tab_computerinformation)
        self.lb_user_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_user_description.setText("Angemeldeter Benutzer")

        self.lb_user_value = QLabel(self.tab_computerinformation)
        self.lb_user_value.setGeometry(QRect(200, y, self.lb_x_default, self.lb_y_default))
        self.lb_user_value.setText(self.current_user)
        y += 25


        self.lb_hostname_description = QLabel(self.tab_computerinformation)
        self.lb_hostname_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_hostname_description.setText("Hostname")

        self.lb_hostname_value = QLabel(self.tab_computerinformation)
        self.lb_hostname_value.setGeometry(QRect(200, y, self.lb_x_default, self.lb_y_default))
        self.lb_hostname_value.setText(self.hostname)
        y += 25


        self.lb_boot_time_description = QLabel(self.tab_computerinformation)
        self.lb_boot_time_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_boot_time_description.setText("Letzte Boottime")

        self.lb_boot_time_value = QLabel(self.tab_computerinformation)
        self.lb_boot_time_value.setGeometry(QRect(200, y, self.lb_x_default, self.lb_y_default))
        self.lb_boot_time_value.setText(self.boot_time)
        y += 25


        self.lb_ip_description = QLabel(self.tab_computerinformation)
        self.lb_ip_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_ip_description.setText("IP-Adresse")

        self.lb_ip_value = QLabel(self.tab_computerinformation)
        self.lb_ip_value.setGeometry(QRect(200, y, self.lb_x_default, self.lb_y_default))
        self.lb_ip_value.setText(self.ip)
        y += 25


        self.lb_mac_description = QLabel(self.tab_computerinformation)
        self.lb_mac_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_mac_description.setText("MAC-Adresse")

        self.lb_mac_value = QLabel(self.tab_computerinformation)
        self.lb_mac_value.setGeometry(QRect(200, y, self.lb_x_default, self.lb_y_default))
        self.lb_mac_value.setText(self.mac)
        y += 25


        self.lb_os_description = QLabel(self.tab_computerinformation)
        self.lb_os_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_os_description.setText("Betriebssystem")

        self.lb_os_value = QLabel(self.tab_computerinformation)
        self.lb_os_value.setGeometry(QRect(200, y, self.lb_x_default, self.lb_y_default))
        self.lb_os_value.setText(self.os)
        y += 25


        self.lb_os_version_description = QLabel(self.tab_computerinformation)
        self.lb_os_version_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_os_version_description.setText("Betriebssystem Release Version")

        self.lb_os_version_value = QLabel(self.tab_computerinformation)
        self.lb_os_version_value.setGeometry(QRect(200, y, self.lb_x_default, self.lb_y_default))
        self.lb_os_version_value.setText(self.os_version)
        y += 25


        self.lb_processor_description = QLabel(self.tab_computerinformation)
        self.lb_processor_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_processor_description.setText("Verbauter Prozessor")

        self.lb_processor_value = QLabel(self.tab_computerinformation)
        self.lb_processor_value.setGeometry(QRect(200, y, self.lb_x_default+100, self.lb_y_default))
        self.lb_processor_value.setText(self.processor)
        y += 25


        self.lb_count_physical_cores_description = QLabel(self.tab_computerinformation)
        self.lb_count_physical_cores_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_count_physical_cores_description.setText("Anzahl physischer Kerne")

        self.lb_count_physical_cores_value = QLabel(self.tab_computerinformation)
        self.lb_count_physical_cores_value.setGeometry(QRect(200, y, self.lb_x_default, self.lb_y_default))
        self.lb_count_physical_cores_value.setText(str(self.cpu_p))
        y += 25


        self.lb_count_logical_cores_description = QLabel(self.tab_computerinformation)
        self.lb_count_logical_cores_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_count_logical_cores_description.setText("Anzahl logischer Kerne")

        self.lb_count_logical_cores_value = QLabel(self.tab_computerinformation)
        self.lb_count_logical_cores_value.setGeometry(QRect(200, y, self.lb_x_default, self.lb_y_default))
        self.lb_count_logical_cores_value.setText(str(self.cpu_l))
        y += 25


        self.lb_ram_description = QLabel(self.tab_computerinformation)
        self.lb_ram_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_ram_description.setText("Verbauter Arbeitsspeicher")

        self.lb_ram_value = QLabel(self.tab_computerinformation)
        self.lb_ram_value.setGeometry(QRect(200, y, self.lb_x_default, self.lb_y_default))
        self.lb_ram_value.setText(str(self.memory) + " GiB")
        y += 25


        self.lb_drives_description = QLabel(self.tab_computerinformation)
        self.lb_drives_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_drives_description.setText("Laufwerke")

        self.lb_drives_value = QLabel(self.tab_computerinformation)
        self.lb_drives_value.setGeometry(QRect(200, y, self.lb_x_default, self.lb_y_default))
        self.lb_drives_value.setText(", ".join(self.drives))
        y += 25

        
        self.lb_info_saved = QLabel(self.tab_computerinformation)
        self.lb_info_saved.setGeometry(QRect(15, self.height-100, self.width, self.lb_y_default))
        self.lb_info_saved.setStyleSheet("color: green")

        self.btn_save_xml = QPushButton(self.tab_computerinformation)
        self.btn_save_xml.setGeometry(QRect(15, self.height-75, 130, self.lb_y_default))
        self.btn_save_xml.setText("XML-Datei speichern")

        self.btn_save_json = QPushButton(self.tab_computerinformation)
        self.btn_save_json.setGeometry(QRect(150, self.height-75, 130, self.lb_y_default))
        self.btn_save_json.setText("JSON-Datei speichern")


        self.btn_save_xml.clicked.connect(self.save_xml)
        self.btn_save_json.clicked.connect(self.save_json)

    def save_xml(self):
        data = QFileDialog.getSaveFileName(self, "Speichern", "", "XML (*.xml)")

        xml = dicttoxml.dicttoxml(self.computerinfo)
        dom = parseString(xml)

        with open(data[0], "w") as x:
            x.write(dom.toprettyxml())
        
        self.lb_info_saved.setText(f"Gespeichert unter {data[0]}")

    def save_json(self):
        data = QFileDialog.getSaveFileName(self, "Speichern", "", "JSON (*.json)")

        with open(data[0], "w") as j:
            json.dump(self.computerinfo, j, indent=4)

        self.lb_info_saved.setText(f"Gespeichert unter {data[0]}")

    def initLogs(self):
        self.tab_logs = QWidget()
        self.tabWidget.addTab(self.tab_logs, "Logs")
        self.tabWidget.currentChanged.connect(self.push_logs)

        self.tab_logs_all = QTabWidget(self.tab_logs)
        self.tab_logs_all.setGeometry(QRect(0, 0, self.width, self.height))
        
        self.tab_logs_system_logs = QWidget()
        self.tab_logs_all.addTab(self.tab_logs_system_logs, "System-Logs")

        self.tb_logs_system_logs = QTextBrowser(self.tab_logs_system_logs)
        self.tb_logs_system_logs.setGeometry(QRect(15, 15, self.width-40, self.height-80))
        self.tb_logs_system_logs.moveCursor(QtGui.QTextCursor.End)


        self.tab_logs_monitoring_logs = QWidget()
        self.tab_logs_all.addTab(self.tab_logs_monitoring_logs, "Monitoring-Logs")

        self.tb_logs_monitoring_logs = QTextBrowser(self.tab_logs_monitoring_logs)
        self.tb_logs_monitoring_logs.setGeometry(QRect(15, 15, self.width-40, self.height-80))
        self.tb_logs_monitoring_logs.moveCursor(QtGui.QTextCursor.End)

        
        self.tab_logs_threshold_limits = QWidget(self.tab_logs_all)
        self.tab_logs_all.addTab(self.tab_logs_threshold_limits, "Schwelle überschritten-Logs")
        
        self.tb_logs_threshold_limits = QTextBrowser(self.tab_logs_threshold_limits)
        self.tb_logs_threshold_limits.setGeometry(QRect(15, 15, self.width-40, self.height-80))
        self.tb_logs_threshold_limits.moveCursor(QtGui.QTextCursor.End)
        
        self.tab_logs_all.currentChanged.connect(self.push_logs)

    def push_logs(self):
        try:
            
            logs_path = "Logs/system.log"
            if os.path.isfile(logs_path):
                with open(logs_path) as f:
                    logs = f.read()
                    self.tb_logs_system_logs.setText(logs)
                    self.tb_logs_system_logs.moveCursor(QtGui.QTextCursor.End)
            
            logs_path = "Logs/monitoring.log"
            if os.path.isfile(logs_path):
                with open(logs_path) as f:
                    logs = f.read()
                    self.tb_logs_monitoring_logs.setText(logs)
                    self.tb_logs_monitoring_logs.moveCursor(QtGui.QTextCursor.End)

            if self.current_config is not None:
                logs_path = f"{self.current_config['logs_path']}/limits.log"
                if os.path.isfile(logs_path):
                    with open(logs_path) as f:
                        logs = f.read()
                        self.tb_logs_threshold_limits.setText(logs)
                        self.tb_logs_threshold_limits.moveCursor(QtGui.QTextCursor.End)
                                                
        except:
            pass
    
    def initConfig(self):
        self.tab_config = QWidget()
        self.tabWidget.addTab(self.tab_config, "Konfigurieren")

        self.lb_logs_destination_description = QLabel(self.tab_config)
        self.lb_logs_destination_description.setGeometry(QRect(15, 15, 100, 25))
        self.lb_logs_destination_description.setText("Pfad der Logs")

        self.le_logs_destination_value = QLineEdit(self.tab_config)
        self.le_logs_destination_value.setGeometry(QRect(115, 15, 650, 25))
        self.le_logs_destination_value.setDisabled(True)
        
        self.btn_log_path = QPushButton(self.tab_config)
        self.btn_log_path.setGeometry(QRect(765, 15, 25, 25))
        self.btn_log_path.setText("...")

        self.lb_mail_receiver = QLabel(self.tab_config)
        self.lb_mail_receiver.setGeometry(QRect(15, 50, 330, 25))
        self.lb_mail_receiver.setText("Mailadresse(n) eingeben. Mehrfache Eingabe mit Semikolon trennen:")

        self.le_mail_receiver = QLineEdit(self.tab_config)
        self.le_mail_receiver.setGeometry(QRect(350, 50, 415, 25))

        self.lb_attachment_sent = QLabel(self.tab_config)
        self.lb_attachment_sent.setGeometry(QRect(15, 85, 200, 25))
        self.lb_attachment_sent.setText("Logs-Anhang")

        self.cb_attachment_sent = QComboBox(self.tab_config)
        self.cb_attachment_sent.setGeometry(QRect(115, 85, 50, 25))
        self.cb_attachment_sent.addItem("Nein")
        self.cb_attachment_sent.addItem("Ja")


        self.lb_softlimit_description = QLabel(self.tab_config)
        self.lb_softlimit_description.setGeometry(QRect(115, 130, 60, 25))
        self.lb_softlimit_description.setText("Softlimit %")

        self.lb_hardlimit_description = QLabel(self.tab_config)
        self.lb_hardlimit_description.setGeometry(QRect(180, 130, 60, 25))
        self.lb_hardlimit_description.setText("Hardlimit %")

        self.lb_cpu_description = QLabel(self.tab_config)
        self.lb_cpu_description.setGeometry(QRect(15, 155, 200, 25))
        self.lb_cpu_description.setText("CPU")

        self.cb_cpu_softlimit = QComboBox(self.tab_config)
        self.cb_cpu_softlimit.setGeometry(QRect(115, 155, 50, 25))

        self.cb_cpu_hardlimit = QComboBox(self.tab_config)
        self.cb_cpu_hardlimit.setGeometry(QRect(180, 155, 50, 25))

        self.lb_cpu_limit_status = QLabel(self.tab_config)
        self.lb_cpu_limit_status.setGeometry(QRect(250, 155, 200, 25))


        self.lb_ram_description = QLabel(self.tab_config)
        self.lb_ram_description.setGeometry(QRect(15, 190, 200, 25))
        self.lb_ram_description.setText("Arbeitsspeicher")
        
        self.cb_ram_softlimit = QComboBox(self.tab_config)
        self.cb_ram_softlimit.setGeometry(QRect(115, 190, 50, 25))

        self.cb_ram_hardlimit = QComboBox(self.tab_config)
        self.cb_ram_hardlimit.setGeometry(QRect(180, 190, 50, 25))

        self.lb_ram_limit_status = QLabel(self.tab_config)
        self.lb_ram_limit_status.setGeometry(QRect(250, 190, 200, 25))

        
        self.lb_drives_description = QLabel(self.tab_config)
        self.lb_drives_description.setGeometry(QRect(15, 225, 200, 25))
        self.lb_drives_description.setText("Laufwerk")

        self.cb_drives_limits = QComboBox(self.tab_config)
        self.cb_drives_limits.setGeometry(QRect(70, 225, 40, 25))

        for drive in self.drives:
            self.cb_drives_limits.addItem(drive)

        self.cb_drives_softlimit = QComboBox(self.tab_config)
        self.cb_drives_softlimit.setGeometry(QRect(115, 225, 50, 25))
        
        self.cb_drives_hardlimit = QComboBox(self.tab_config)
        self.cb_drives_hardlimit.setGeometry(QRect(180, 225, 50, 25))

        self.lb_drives_limit_status = QLabel(self.tab_config)
        self.lb_drives_limit_status.setGeometry(QRect(250, 225, 200, 25))


        self.cb_cpu_softlimit.addItem("")
        self.cb_ram_softlimit.addItem("")
        self.cb_cpu_hardlimit.addItem("")
        self.cb_ram_hardlimit.addItem("")
        self.cb_drives_softlimit.addItem("")
        self.cb_drives_hardlimit.addItem("")


        for percent in range(100, 0, -1):
            self.cb_cpu_softlimit.addItem(str(percent))
            self.cb_ram_softlimit.addItem(str(percent))
            self.cb_cpu_hardlimit.addItem(str(percent))
            self.cb_ram_hardlimit.addItem(str(percent))
            self.cb_drives_softlimit.addItem(str(percent))
            self.cb_drives_hardlimit.addItem(str(percent))    


        self.lb_mail_sender = QLabel(self.tab_config)
        self.lb_mail_sender.setGeometry(QRect(15, 300, 200, 25))
        self.lb_mail_sender.setText("Sender-Mailadresse")

        self.le_mail_sender = QLineEdit(self.tab_config)
        self.le_mail_sender.setGeometry(QRect(115, 300, 200, 25))


        self.lb_mail_password = QLabel(self.tab_config)
        self.lb_mail_password.setGeometry(QRect(15, 335, 200, 25))
        self.lb_mail_password.setText("Passwort")

        self.le_mail_password = QLineEdit(self.tab_config)
        self.le_mail_password.setGeometry(QRect(115, 335, 200, 25))
        self.le_mail_password.setEchoMode(QLineEdit.Password)


        self.lb_mail_server = QLabel(self.tab_config)
        self.lb_mail_server.setGeometry(QRect(15, 370, 200, 25))
        self.lb_mail_server.setText("Mailserver")
        
        self.le_mail_server = QLineEdit(self.tab_config)
        self.le_mail_server.setGeometry(QRect(115, 370, 200, 25))
        

        self.lb_mail_server_port = QLabel(self.tab_config)
        self.lb_mail_server_port.setGeometry(QRect(15, 405, 200, 25))
        self.lb_mail_server_port.setText("Port")
        
        self.le_mail_server_port = QLineEdit(self.tab_config)
        self.le_mail_server_port.setGeometry(QRect(115, 405, 40, 25))

        
        self.btn_validate_login = QPushButton(self.tab_config)
        self.btn_validate_login.setGeometry(QRect(160, 405, 155, 25))
        self.btn_validate_login.setText("Validiere Zugangsdaten")


        self.lb_validate_login = QLabel(self.tab_config)
        self.lb_validate_login.setGeometry(QRect(15, 440, 400, 25))


        self.lb_config_warnings = QLabel(self.tab_config)
        self.lb_config_warnings.setGeometry(QRect(15, self.height-100, self.width-30, 25))
        self.lb_config_warnings.setStyleSheet("color: red")

        self.btn_running_config = QPushButton(self.tab_config)
        self.btn_running_config.setGeometry(QRect(15, self.height-70, 180, 25))
        self.btn_running_config.setText("Laufende Konfiguration speichern")
        
        self.btn_startup_config = QPushButton(self.tab_config)
        self.btn_startup_config.setGeometry(QRect(200, self.height-70, 180, 25))
        self.btn_startup_config.setText("Startup Konfiguration speichern")

        self.btn_log_path.clicked.connect(self.get_path)
        self.btn_running_config.clicked.connect(self.running_config)
        self.btn_startup_config.clicked.connect(self.startup_config)
        self.cb_drives_limits.currentTextChanged.connect(self.cb_drives_limits_refresh)
        self.cb_drives_softlimit.currentTextChanged.connect(self.cb_drive_soft_commit)
        self.cb_drives_hardlimit.currentTextChanged.connect(self.cb_drive_hard_commit)
        self.btn_validate_login.clicked.connect(self.validate_login)

    def get_path(self):
        # Directory-dialog
        self.le_logs_destination_value.setText(str(QFileDialog.getExistingDirectory(self, "Ordner auswählen")))

    def running_config(self):
        # Check, ob alle Eingaben in Ordnung sind
        self.current_config = self.check_config()

        if self.current_config:

            # If True, write the current_config.ini-File
            parser = ConfigParser()

            parser["DEFAULT"] = {"Pfad_Logs": self.current_config["logs_path"],
                                "Mailadressen": self.current_config["mail_receiver"],
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

            self.lb_validate_login.setStyleSheet("color: green")
            self.lb_validate_login.setText("Laufende Konfiguration gespeichert")
            
            log("Logs/system.log", "info", "Temp/running_config.ini wurde geschrieben")


            # read the config file and set the data to a dictionary 
            try:
                self.current_config = {"username": "",
                                       "password": "",
                                       "server": "",
                                       "port": "",
                                       "logs_path": "",
                                       "mail_receiver": [],
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
                self.current_config["logs_path"] = parser["DEFAULT"]["pfad_logs"]
                mail_addresses = (parser["DEFAULT"]["mailadressen"]).split(";")
                for mail in mail_addresses:
                    self.current_config["mail_receiver"].append(mail)
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
            except Exception as e:
                log("Logs/system.log", "error", f"Temp/running_config.ini-Datei konnte nicht erfolgreich geparsed werden. Fehler: {e}")

    def startup_config(self):
        """
        Save startupconfig
        first save current_config, then copy the current_config.ini file to startup_config.ini file
        """

        self.running_config()
        try:
            shutil.copy("Temp/running_config.ini", "startup_config.ini")            
            self.lb_validate_login.setStyleSheet("color: green")
            self.lb_validate_login.setText("Startup Konfiguration gespeichert")
            log("Logs/system.log", "info", "startup_config.ini erfolgreich erstellt")

        except Exception as e:
            log("Logs/system.log", "info", f"startup_config.ini konnte nicht erstellt werden. Fehler: {e}")
 
    def check_config(self):
        """
        onclick on the one of the save configuration buttons
        It checks if all the necessary inputs are correct
        """
        self.current_config = None
        self.lb_config_warnings.clear()
        self.lb_config_warnings.setStyleSheet("color: red")
        self.lb_validate_login.clear()
        log("Logs/system.log", "info", "Starte Überprüfung Konfigurationsdateien")

        if self.processes:
            self.lb_config_warnings.setText("Beende zunächst alle Monitorings.")
            log("Logs/system.log", "error", "current_config.ini konnte nicht geschrieben werden - monitorings müssen beendet sein")
            return

        if not self.mail_access:
            self.lb_config_warnings.setText("Validiere zunächst den Mailzugang.")
            log("Logs/system.log", "info", "current_config.ini konnte nicht geschrieben werden - Mailzugang muss zunächst validiert werden")
            return

        must_have_inputs = []
        warn_msg_lb = "|"
        drive_chosen = {}

        # temp-config
        config = {"logs_path": "",
                 "mail_receiver": "",
                 "attachment": None,
                 "limits": {"cpu": {},
                            "ram": {},
                            "drives": {}}}

        # All drives appended to the temp config dictionary
        for drive in self.drives:
            config["limits"]["drives"][drive] = {}
            drive_chosen[drive] = {"soft": "", "hard": ""}

        
        # must_have configs
        if os.path.isdir(self.le_logs_destination_value.text()):
            config["logs_path"] = self.le_logs_destination_value.text()
            log("Logs/system.log", "info", f"Ausgewählter Pfad '{self.le_logs_destination_value.text()}' ist gültig")            
        else:
            must_have_inputs.append(False)
            warn_msg_lb += " Ungültiger Pfad zum Speichern der Logs* |"
            log("Logs/system.log", "info", f"Ausgewählter Pfad '{self.le_logs_destination_value.text()}' ist ungültig")

        if self.le_mail_receiver.text():
            # Check if the addresses are reachable

            try:
                server = smtplib.SMTP(self.le_mail_server.text(), int(self.le_mail_server_port.text()))
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.le_mail_sender.text(), self.le_mail_password.text())
                server.sendmail(self.le_mail_sender.text(), self.le_mail_receiver.text().split(";"), "Validiere")
                server.quit()
                config["mail_receiver"] = self.le_mail_receiver.text()
                log("Logs/system.log", "info", f"Validierung der Empfänger-Mailadressen '{self.le_mail_receiver.text()}' erfolgreich")
            except Exception as e:
                must_have_inputs.append(False)
                warn_msg_lb += " Adressen konnten nicht erreicht werden* |"
                log("Logs/system.log", "error", f"Validierung der Empfänger-Mailadressen '{self.le_mail_receiver.text()}' fehlgeschlagen. Fehler: {e}")

        else:
            must_have_inputs.append(False)
            warn_msg_lb += " Keine Mailadresse angegeben* |"
            log("Logs/system.log", "info", "Keine Mailadressen angegeben")
        
        if self.cb_attachment_sent.currentText() == "Nein":
            config["attachment"] = False
        else:
            config["attachment"] = True


        # The Limits are optional. But the user is just able to start the monitoring if the limits are set

        # Some checks for the limits of the cpu
        if self.cb_cpu_softlimit.currentText() == "" or self.cb_cpu_softlimit.currentText()  == "":
            pass
        
        elif (self.cb_cpu_softlimit.currentText()  == "" and not self.cb_cpu_hardlimit.currentText()  == "") or (self.cb_cpu_hardlimit.currentText()  == "" and not self.cb_cpu_softlimit.currentText()  == ""):
            warn_msg_lb += " CPU - Wert wurde nicht eingegeben |"

        elif int(self.cb_cpu_softlimit.currentText() ) >= int(self.cb_cpu_hardlimit.currentText() ):
            warn_msg_lb += " CPU - Hardlimit muss größer als Softlimit sein |"
        
        else:
            config["limits"]["cpu"]["soft"] = int(self.cb_cpu_softlimit.currentText())
            config["limits"]["cpu"]["hard"] = int(self.cb_cpu_hardlimit.currentText())


        # Some checks for the limits of the ram
        if self.cb_ram_softlimit.currentText() == "" or self.cb_ram_softlimit.currentText()  == "":
            pass
        
        elif (self.cb_ram_softlimit.currentText()  == "" and not self.cb_ram_hardlimit.currentText()  == "") or (self.cb_ram_hardlimit.currentText()  == "" and not self.cb_ram_softlimit.currentText()  == ""):
            warn_msg_lb += " Arbeitsspeicher - Ein Wert wurde nicht eingegeben |"

        elif int(self.cb_ram_softlimit.currentText() ) >= int(self.cb_ram_hardlimit.currentText()):
            warn_msg_lb += " Arbeitsspeicher - Hardlimit muss größer als Softlimit sein |"
        
        else:
            config["limits"]["ram"]["soft"] = int(self.cb_ram_softlimit.currentText())
            config["limits"]["ram"]["hard"] = int(self.cb_ram_hardlimit.currentText())


        # Some checks about each drive
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
                

        if len(warn_msg_lb) != 1:
            self.lb_config_warnings.setText(warn_msg_lb)

        if all(must_have_inputs):
            log("Logs/system.log", "info", "Beende Überprüfung Konfigurationsdateien. Alle essentiellen Eingaben sind gültig.")
            return config
        else:
            log("Logs/system.log", "info", "Beende Überprüfung Konfigurationsdateien. Mind. eine ungültige essentielle Eingabe")
            return None

    def cb_drives_limits_refresh(self):
        """
        If someone changes the current text of the drive, it's checks the value of the new chosen 
        drive and sets it to the comboboxes of the limits
        """
        for k in self.drive_chosen.keys():
            if k == self.cb_drives_limits.currentText():
                self.cb_drives_softlimit.setCurrentText(str(self.drive_chosen[k]["soft"]))
                self.cb_drives_hardlimit.setCurrentText(str(self.drive_chosen[k]["hard"]))

    def cb_drive_soft_commit(self):
        """
        On change of the value of the soft limits it's written to the drive_chosen dictionary
        """
        for k in self.drive_chosen.keys():
            if k == self.cb_drives_limits.currentText():
                self.drive_chosen[k]["soft"] = self.cb_drives_softlimit.currentText()

    def cb_drive_hard_commit(self):
        """
        On change of the value of the hard limits it's written to the drive_chosen dictionary
        """
        for k in self.drive_chosen.keys():
            if k == self.cb_drives_limits.currentText():
                self.drive_chosen[k]["hard"] = self.cb_drives_hardlimit.currentText()

    def validate_login(self):
        """
        Validate the login data 
        """

        self.lb_validate_login.clear()
        self.lb_config_warnings.clear()

        try:
            if not self.le_mail_sender.text() or not self.le_mail_password.text() or not self.le_mail_server.text() or not self.le_mail_server_port.text():
                self.lb_validate_login.setStyleSheet("color: red")
                self.lb_validate_login.setText("Es müssen alle Felder ausgefüllt werden")
                log("Logs/system.log", "info", "Mailkonto-Validierung - nicht alle Felder sind ausgefüllt")
                return

            # Try to login. If it works the credentials are correct and the line edits getting disabled 
            mailserver = smtplib.SMTP(self.le_mail_server.text(), int(self.le_mail_server_port.text()))
            mailserver.ehlo()
            mailserver.starttls()
            mailserver.ehlo()
            mailserver.login(self.le_mail_sender.text(), self.le_mail_password.text())
            
            self.le_mail_server.setDisabled(True)
            self.le_mail_server_port.setDisabled(True)
            self.le_mail_sender.setDisabled(True)
            self.le_mail_password.setDisabled(True)
            self.mail_access = True
            self.lb_validate_login.setStyleSheet("color: green")
            self.lb_validate_login.setText("Validierung erfolgreich")
            log("Logs/system.log", "info", f"Mailkonto-Validierung mit Konto '{self.le_mail_sender.text()}' erfolgreich")

        except ValueError:
            self.lb_validate_login.setStyleSheet("color: red")
            self.lb_validate_login.setText("Port muss eine Zahl sein")
            log("Logs/system.log", "info", f"Mailkonto-Validierung - Port '{self.le_mail_server_port.text()}' ist keine Zahl")
        except smtplib.SMTPAuthenticationError:
            self.lb_validate_login.setStyleSheet("color: red")
            self.lb_validate_login.setText("Logindaten nicht korrekt")
            log("Logs/system.log", "info", f"Mailkonto-Validierung - Credentials sind nicht korrekt")
        except Exception as e:
            self.lb_validate_login.setStyleSheet("color: red")
            self.lb_validate_login.setText(f"Folgender Fehler: {e}")
            log("Logs/system.log", "info", f"Mailkonto-Validierung - Folgender Fehler ist aufgetreten: {e} ")
        
    def initGraph(self):
        self.tab_graph = QWidget()
        self.tabWidget.addTab(self.tab_graph, "Graph")


        self.tab_graph_mon = QTabWidget(self.tab_graph)
        self.tab_graph_mon.setGeometry(QRect(0, 0, self.width, self.height))
        

        self.tab_graph_mon_cpu = QWidget()
        self.tab_graph_mon.addTab(self.tab_graph_mon_cpu, "CPU")
        PlotCanvas(self.tab_graph_mon_cpu, width=10, height=4, pickle_file="Temp/cpu.pickle").move(0, 100)


        self.tab_graph_mon_ram = QWidget()
        self.tab_graph_mon.addTab(self.tab_graph_mon_ram, "Arbeitsspeicher")
        PlotCanvas(self.tab_graph_mon_ram, width=10, height=4, pickle_file="Temp/ram.pickle").move(0, 100)


        self.lb_graph_mon_title = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_title.setGeometry(QRect(15, 10, self.lb_x_default, 40))
        self.lb_graph_mon_title.setStyleSheet("font-size: 15px; font-weight: 600")
        self.lb_graph_mon_title.setText("Aktuelle Auslastungen:")


        y = 40
        self.lb_graph_mon_cpu_description = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_cpu_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_graph_mon_cpu_description.setText("CPU:")

        self.lb_graph_mon_cpu_value = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_cpu_value.setGeometry(QRect(115, y, 50, self.lb_y_default))
        
        self.lb_graph_mon_cpu_avg_description = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_cpu_avg_description.setGeometry(QRect(165, y, self.lb_x_default, self.lb_y_default))
        self.lb_graph_mon_cpu_avg_description.setText("CPU-Durchschnitt Systemzeit:")

        self.lb_graph_mon_cpu_avg_value = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_cpu_avg_value.setGeometry(QRect(365, y, 50, self.lb_y_default))
        y += 25


        self.lb_graph_mon_ram_description = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_ram_description.setGeometry(QRect(15, y, self.lb_x_default, self.lb_y_default))
        self.lb_graph_mon_ram_description.setText("Arbeitsspeicher:")

        self.lb_graph_mon_ram_value = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_ram_value.setGeometry(QRect(115, y, 50, self.lb_y_default))

        self.lb_graph_mon_ram_avg_description = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_ram_avg_description.setGeometry(QRect(165, y, self.lb_x_default, self.lb_y_default))
        self.lb_graph_mon_ram_avg_description.setText("Arbeitsspeicher-Durchschnitt Systemzeit:")

        self.lb_graph_mon_ram_avg_value = QLabel(self.tab_graph_mon)
        self.lb_graph_mon_ram_avg_value.setGeometry(QRect(365, y, 50, self.lb_y_default))
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
        y += 25

    def refresh_current_utilization(self):
        cpu = psutil.cpu_percent()
        ram = round(get_virtual_memory()["percent"], 2)
        processes = len(psutil.pids())
        system_time = round(time.time() - self.start_system_time)


        self.cpu_values.append(cpu)
        self.ram_values.append(ram)
        self.systemtime_values.append(system_time)
        
        cpu_avg = round(sum(self.cpu_values)/len(self.cpu_values), 2)
        ram_avg = round(sum(self.ram_values)/len(self.ram_values), 2)

        with open("Temp/cpu.pickle", "wb") as p:
            pickle.dump([self.systemtime_values, self.cpu_values], p)

        with open("Temp/ram.pickle", "wb") as p:
            pickle.dump([self.systemtime_values, self.ram_values], p)

        self.lb_graph_mon_cpu_value.setText(str(cpu) + " %")
        self.lb_graph_mon_ram_value.setText(str(ram) + " %")
        self.lb_graph_mon_processes_value.setText(str(processes))
        self.lb_graph_mon_system_time_value.setText(str(system_time) + " s")
        self.lb_graph_mon_cpu_avg_value.setText(str(cpu_avg) + " %")
        self.lb_graph_mon_ram_avg_value.setText(str(ram_avg) + " %")

        
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
            soft = int(self.current_config["limits"]["cpu"]["soft"])
            hard = int(self.current_config["limits"]["cpu"]["hard"])

            if soft <= ram < hard:
                self.lb_graph_mon_ram_value.setStyleSheet("color: orange")
            elif ram >= hard:
                self.lb_graph_mon_ram_value.setStyleSheet("color: red")
            else:
                self.lb_graph_mon_ram_value.setStyleSheet("color: green")
        else:
            self.lb_graph_mon_ram_value.setStyleSheet("color: black")
        
        

        if self.current_timer % 10 == 0:
            self.lb_error.clear()
            self.lb_status.clear()
            self.lb_validate_login.clear()
            self.lb_config_warnings.clear()        

        self.current_timer += 1



class PlotCanvas(FigureCanvas):

    def __init__(self, parent=None, width=8, height=4, dpi=100, pickle_file=None):
        self.file = pickle_file

        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axis = self.fig.add_subplot(1, 1, 1)
        self.axis.set_ylabel("Auslastung in %")
        self.axis.set_xlabel("Zeit in s")

        self.axis.set_ylim(ymin=0, ymax=105)

        FigureCanvas.__init__(self, self.fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self,
                QSizePolicy.Expanding,
                QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

        self.ani = animation.FuncAnimation(self.fig, self.animate, interval=1000)

    def animate(self, i):
        if os.path.isfile(self.file):
            try:
                with open(self.file, "rb") as p:
                    xs, ys = pickle.load(p)

                y_mean = [sum(ys)/len(ys)] * len(ys)

                while len(xs) > 60:
                    del xs[0]
                    del ys[0]
                    del y_mean[0]

                # Scaling is in int, not float
                self.axis.yaxis.set_major_locator(MaxNLocator(integer=True))
                self.axis.xaxis.set_major_locator(MaxNLocator(integer=True))
                
                self.axis.clear()
                self.axis.set_ylim(ymin=0, ymax=105)

                #self.axis.get_xaxis().set_visible(False)

                self.axis.set_ylabel("Auslastung in %")
                self.axis.set_xlabel("Zeit in s")
                self.axis.plot(xs, ys, label=f"Auslastung letzte 60 s")
                self.axis.plot(xs, y_mean, label="Durchschnitt Auslastung letzte 60 s", linestyle="--")

                self.axis.legend(loc='upper left')
            except Exception as e:
                log("Logs/monitoring.log", "error", f"Graph-Animation nicht möglich. Fehler: {e}")

        else:
            self.axis.clear()

            # Scaling is in int, not float
            self.axis.yaxis.set_major_locator(MaxNLocator(integer=True))
            self.axis.xaxis.set_major_locator(MaxNLocator(integer=True))
            self.axis.set_ylim(ymin=0, ymax=105)
            

if __name__ == "__main__":
    if platform.system() == "Windows":
        app = QApplication(sys.argv)
        window = Monitoring()
        sys.exit(app.exec_())
    else:
        print("Läuft nur auf Windows")
