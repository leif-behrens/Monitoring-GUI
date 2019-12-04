from PyQt5 import QtGui
from PyQt5.QtWidgets import QApplication, QLineEdit, QFileDialog, QListWidget, QMainWindow, QFrame, QTabWidget, QWidget, QPushButton, QLabel, QComboBox
from PyQt5.QtCore import Qt, QRect
import sys
from functions import *
import psutil
import multiprocessing


class Monitoring(QMainWindow):
    def __init__(self):
        super().__init__()
        self.title = "Monitoring"
        self.icon = "Icon.png"
        self.top = 100
        self.left = 100
        self.width = 800
        self.height = 550
        self.current_config = ""#None
        self.processes = {}
        self.monitoring = []

        self.initWindow()

    def initWindow(self):
        # Mainwindow Einstellungen
        self.setWindowTitle(self.title)
        self.setWindowIcon(QtGui.QIcon(self.icon))
        self.setFixedSize(self.width, self.height)

        # Tabwidget erstellt
        self.tabWidget = QTabWidget(self)
        self.tabWidget.setGeometry(QRect(0, 0, 800, 550))
        
        # Tabs werden initialisiert
        self.initMonitoring()    
        self.initComputerinformation()
        self.initLogs()        
        self.initConfig()        
        self.initLoadFile()
        self.initGraph()
        
        # Anzeige der GUI
        self.show()

    def initMonitoring(self):
        self.tab_monitoring = QWidget()
        self.tabWidget.addTab(self.tab_monitoring, "Monitoring")

        self.lb_cpu_start_stop = QLabel(self.tab_monitoring)
        self.lb_cpu_start_stop.setGeometry(QRect(15, 15, 150, 25))
        self.lb_cpu_start_stop.setText("CPU-Monitoring")

        self.btn_cpu_start_stop = QPushButton(self.tab_monitoring)
        self.btn_cpu_start_stop.setGeometry(QRect(150, 15, 130, 25))
        self.btn_cpu_start_stop.setText("Start")
        


        self.lb_ram_start_stop = QLabel(self.tab_monitoring)
        self.lb_ram_start_stop.setGeometry(QRect(15, 50, 150, 25))
        self.lb_ram_start_stop.setText("RAM-Monitoring")

        self.btn_ram_start_stop = QPushButton(self.tab_monitoring)
        self.btn_ram_start_stop.setGeometry(QRect(150, 50, 130, 25))
        self.btn_ram_start_stop.setText("Start")
        

        self.lb_disk_start_stop = QLabel(self.tab_monitoring)
        self.lb_disk_start_stop.setGeometry(QRect(15, 85, 150, 25))
        self.lb_disk_start_stop.setText("Festplatten-Monitoring")

        self.cb_disk_mon = QComboBox(self.tab_monitoring)
        self.cb_disk_mon.setGeometry(QRect(150, 85, 40, 25))

        self.drives = get_pc_information()["drives"]

        for drive in self.drives:
            self.cb_disk_mon.addItem(drive)
    
        self.btn_disk_start_stop = QPushButton(self.tab_monitoring)
        self.btn_disk_start_stop.setGeometry(QRect(200, 85, 130, 25))
        self.btn_disk_start_stop.setText("Start")

        self.lb_disk_mon_status = QLabel(self.tab_monitoring)
        self.lb_disk_mon_status.setGeometry(QRect(335, 85, 250, 25))
        self.lb_disk_mon_status.setText(f"{self.cb_disk_mon.currentText()}-Laufwerk Monitoring: Gestoppt")
        self.lb_disk_mon_status.setStyleSheet("color: red")
        

        self.lb_monitoring_description = QLabel(self.tab_monitoring)
        self.lb_monitoring_description.setGeometry(QRect(15, 130, 200, 25))
        self.lb_monitoring_description.setText("Laufende Monitorings:")

        self.lw_processes = QListWidget(self.tab_monitoring)
        self.lw_processes.setGeometry(QRect(15, 155, 100, 200))
        
        self.lb_error = QLabel(self.tab_monitoring)
        self.lb_error.setGeometry(QRect(15, self.height-50, self.width-50, 25))
        self.lb_error.setStyleSheet("color: red")

        self.lb_status = QLabel(self.tab_monitoring)
        self.lb_status.setGeometry(QRect(15, self.height-100, self.width-50, 25))
        self.lb_status.setStyleSheet("color: green")

        self.btn_cpu_start_stop.clicked.connect(self.start_cpu)
        self.btn_ram_start_stop.clicked.connect(self.start_ram)
        self.btn_disk_start_stop.clicked.connect(lambda: self.start_disk(self.cb_disk_mon.currentText()))
        self.cb_disk_mon.currentTextChanged.connect(lambda: self.cb_disk_mon_change(self.cb_disk_mon.currentText()))

    def start_cpu(self):
        self.start("cpu", "CPU", self.btn_cpu_start_stop)
       
    def start_ram(self):
        self.start("ram", "Arbeitsspeicher", self.btn_ram_start_stop)

    def start_disk(self, disk):
        # Initialisiere Errorlabel und Statuslabel
        self.lb_error.setText("")
        self.lb_status.setText("")
        self.lw_processes.clear()

        if self.current_config is not None:
            for d, p in self.processes.items():
                if disk == d:
                    self.lb_status.setText(f"Beende Festplatten-Monitoring für Laufwerk: {disk}")
                    self.lb_disk_mon_status.setStyleSheet("color: red")
                    self.lb_disk_mon_status.setText(f"{d}-Laufwerk Monitoring: Gestoppt")
                    self.btn_disk_start_stop.setText("Start")
                    psutil.Process(pid=p).terminate()
                    del self.processes[d]
                    self.monitoring.remove(f"{disk}-Laufwerk")
                    for mon in self.monitoring:
                        self.lw_processes.addItem(mon)
                    return
                else:
                    continue
            
            self.lb_status.setText(f"Starte Festplatten-Monitoring für Laufwerk: {disk}")
            self.lb_disk_mon_status.setStyleSheet("color: green")
            self.lb_disk_mon_status.setText(f"{disk}-Laufwerk Monitoring: Gestartet")
            self.btn_disk_start_stop.setText("Stopp")
            self.monitoring.append(f"{disk}-Laufwerk")

            process = multiprocessing.Process(target=mon_disk, args=(1, "logs", "info@leifbehrens.de", True, 70, 80))
            process.start()
            self.processes[disk] = process.pid

            for mon in self.monitoring:
                self.lw_processes.addItem(mon)
        else:
            self.lb_error.setText("Wähle zuerst eine Konfiguration.")

    def cb_disk_mon_change(self, disk):
        if self.current_config is not None:

            for d in self.processes.keys():
                if disk == d:
                    self.btn_disk_start_stop.setText("Stopp")
                    self.lb_disk_mon_status.setStyleSheet("color: green")
                    self.lb_disk_mon_status.setText(f"{d}-Laufwerk Monitoring: Gestartet")
                    return

            self.btn_disk_start_stop.setText("Start")
            self.lb_disk_mon_status.setStyleSheet("color: red")
            self.lb_disk_mon_status.setText(f"{disk}-Laufwerk Monitoring: Gestoppt")

    def start(self, typ, description, btn):
        # Initialisiere Errorlabel und Statuslabel
        self.lb_error.setText("")
        self.lb_status.setText("")
        self.lw_processes.clear()
        
        if self.current_config is not None:
            for d, p in self.processes.items():
                if typ == d:
                    self.lb_status.setText(f"Beende {description}-Monitoring")
                    btn.setText("Start")
                    psutil.Process(pid=p).terminate()
                    del self.processes[d]
                    self.monitoring.remove(description)
                    for mon in self.monitoring:
                        self.lw_processes.addItem(mon)
                    return
                else:
                    continue
            

            self.lb_status.setText(f"Starte {description}-Monitoring")
            self.btn_ram_start_stop.setText("Stopp")
            self.monitoring.append(description)

            process = multiprocessing.Process(target=mon_memory, args=(1, "logs", "info@leifbehrens.de", True, 70, 80))
            process.start()
            self.processes[typ] = process.pid

            for mon in self.monitoring:
                self.lw_processes.addItem(mon)
        else:
            self.lb_error.setText("Wähle zuerst eine Konfiguration.")


    def initComputerinformation(self):
        self.pc_info = get_pc_information()
        self.lb_x_value = 400
        
        self.current_user = self.pc_info["current_user"]
        self.hostname = self.pc_info["hostname"]
        self.ip = self.pc_info["ip_address"]
        self.cpu_p = self.pc_info["cpu_p"]
        self.cpu_l = self.pc_info["cpu_l"]
        self.processor = self.pc_info["processor"]
        self.os = self.pc_info["os"]
        self.drives = self.pc_info["drives"]
        self.memory = self.pc_info["memory"]

        self.tab_computerinformation = QWidget()
        self.tabWidget.addTab(self.tab_computerinformation, "Computerinformationen")

        self.btn_refresh = QPushButton(self.tab_computerinformation)
        self.btn_refresh.setGeometry(QRect(15, self.height-50, 20, 20))
        self.btn_refresh.setIcon(QtGui.QIcon("refresh.jpg"))


        self.lb_user_description = QLabel(self.tab_computerinformation)
        self.lb_user_description.setGeometry(QRect(15, 15, 200, 25))
        self.lb_user_description.setText("Angemeldeter Benutzer")

        self.lb_user_value = QLabel(self.tab_computerinformation)
        self.lb_user_value.setGeometry(QRect(200, 15, self.lb_x_value, 25))
        self.lb_user_value.setText(self.current_user)


        self.lb_processes_description = QLabel(self.tab_computerinformation)
        self.lb_processes_description.setGeometry(QRect(15, 40, 200, 25))
        self.lb_processes_description.setText("Anzahl laufender Prozesse")

        self.lb_processes_value = QLabel(self.tab_computerinformation)
        self.lb_processes_value.setGeometry(QRect(200, 40, self.lb_x_value, 25))
        self.lb_processes_value.setText(str(len(psutil.pids())))


        self.lb_hostname_description = QLabel(self.tab_computerinformation)
        self.lb_hostname_description.setGeometry(QRect(15, 65, 200, 25))
        self.lb_hostname_description.setText("Hostname")

        self.lb_hostname_value = QLabel(self.tab_computerinformation)
        self.lb_hostname_value.setGeometry(QRect(200, 65, self.lb_x_value, 25))
        self.lb_hostname_value.setText(self.hostname)


        self.lb_user_description = QLabel(self.tab_computerinformation)
        self.lb_user_description.setGeometry(QRect(15, 90, 200, 25))
        self.lb_user_description.setText("IP-Adresse")

        self.lb_user_value = QLabel(self.tab_computerinformation)
        self.lb_user_value.setGeometry(QRect(200, 90, self.lb_x_value, 25))
        self.lb_user_value.setText(self.ip)


        self.lb_count_physical_cores_description = QLabel(self.tab_computerinformation)
        self.lb_count_physical_cores_description.setGeometry(QRect(15, 115, 200, 25))
        self.lb_count_physical_cores_description.setText("Anzahl physischer Kerne")

        self.lb_count_physical_cores_value = QLabel(self.tab_computerinformation)
        self.lb_count_physical_cores_value.setGeometry(QRect(200, 115, self.lb_x_value, 25))
        self.lb_count_physical_cores_value.setText(str(self.cpu_p))


        self.lb_count_logical_cores_description = QLabel(self.tab_computerinformation)
        self.lb_count_logical_cores_description.setGeometry(QRect(15, 140, 200, 25))
        self.lb_count_logical_cores_description.setText("Anzahl logischer Kerne")

        self.lb_count_logical_cores_value = QLabel(self.tab_computerinformation)
        self.lb_count_logical_cores_value.setGeometry(QRect(200, 140, self.lb_x_value, 25))
        self.lb_count_logical_cores_value.setText(str(self.cpu_l))
        

        self.lb_processor_description = QLabel(self.tab_computerinformation)
        self.lb_processor_description.setGeometry(QRect(15, 165, 200, 25))
        self.lb_processor_description.setText("Verbauter Prozessor")

        self.lb_processor_value = QLabel(self.tab_computerinformation)
        self.lb_processor_value.setGeometry(QRect(200, 165, self.lb_x_value, 25))
        self.lb_processor_value.setText(self.processor)


        self.lb_os_description = QLabel(self.tab_computerinformation)
        self.lb_os_description.setGeometry(QRect(15, 190, 200, 25))
        self.lb_os_description.setText("Betriebssystem")

        self.lb_os_value = QLabel(self.tab_computerinformation)
        self.lb_os_value.setGeometry(QRect(200, 190, self.lb_x_value, 25))
        self.lb_os_value.setText(self.os)


        self.lb_drives_description = QLabel(self.tab_computerinformation)
        self.lb_drives_description.setGeometry(QRect(15, 215, 200, 25))
        self.lb_drives_description.setText("Laufwerke")

        self.lb_drives_value = QLabel(self.tab_computerinformation)
        self.lb_drives_value.setGeometry(QRect(200, 215, self.lb_x_value, 25))
        self.lb_drives_value.setText(", ".join(self.drives))


        self.lb_ram_description = QLabel(self.tab_computerinformation)
        self.lb_ram_description.setGeometry(QRect(15, 240, 200, 25))
        self.lb_ram_description.setText("Verbauter Arbeitsspeicher")

        self.lb_ram_value = QLabel(self.tab_computerinformation)
        self.lb_ram_value.setGeometry(QRect(200, 240, self.lb_x_value, 25))
        self.lb_ram_value.setText(str(self.memory) + " GiB")


        self.btn_save_xml = QPushButton(self.tab_computerinformation)
        self.btn_save_xml.setGeometry(QRect(15, 450, 130, 25))
        self.btn_save_xml.setText("XML-Datei speichern")

        self.btn_save_json = QPushButton(self.tab_computerinformation)
        self.btn_save_json.setGeometry(QRect(150, 450, 130, 25))
        self.btn_save_json.setText("JSON-Datei speichern")

    def initLogs(self):
        self.tab_logs = QWidget()
        self.tabWidget.addTab(self.tab_logs, "Logs")
    
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

        self.lb_softlimits = QLabel(self.tab_config)
        self.lb_softlimits.setGeometry(QRect(15, 120, 200, 25))
        self.lb_softlimits.setText("Soflimits")

        self.lb_hardlimits = QLabel(self.tab_config)
        self.lb_hardlimits.setGeometry(QRect(15, 155, 200, 25))
        self.lb_hardlimits.setText("Hardlimits")

        self.btn_log_path.clicked.connect(self.get_path)

    def get_path(self):
        self.le_logs_destination_value.setText(str(QFileDialog.getExistingDirectory(self, "Ordner auswählen")))

    def initLoadFile(self):
        self.tab_loadFile = QWidget()
        self.tabWidget.addTab(self.tab_loadFile, "Lade Datei")

    def initGraph(self):
        self.tab_graph = QWidget()
        self.tabWidget.addTab(self.tab_graph, "Graph")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Monitoring()
    sys.exit(app.exec_())
