import psutil
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE
import platform
import getpass
import socket
import logging
import time
import win32api
import ctypes
import winsound
import json
import base64
from configparser import ConfigParser


class ValueTooHighOrTooLowException(Exception):
    pass


class ValueGreaterThanOtherValueException(Exception):
    pass


def get_disk_usage(path):
    """
    :param path: Path of the disk
    :return: Dictionary -> rounded elements in GiB except percentage
    """

    disk_usage = psutil.disk_usage(path)
    total = round((disk_usage.total / 2 ** 30), 2)
    used = round((disk_usage.used / 2 ** 30), 2)
    free = round((disk_usage.free / 2 ** 30), 2)
    percent = disk_usage.percent

    return {"total": total, "used": used, "free": free, "percent": percent}


def get_virtual_memory():
    """
    :return: Dictionary -> rounded elements in GiB except percentage
    """

    total = round((psutil.virtual_memory().total / 2 ** 30), 2)
    available = round((psutil.virtual_memory().available / 2 ** 30), 2)
    percent = psutil.virtual_memory().percent
    used = round((psutil.virtual_memory().used / 2 ** 30), 2)
    free = round((psutil.virtual_memory().free / 2 ** 30), 2)

    return {"total": total, "available": available, "percent": percent, "used": used, "free": free}


def get_pc_information():
    """
    :return: Dictionary with pc-information
    """

    current_user = getpass.getuser()  # Aktuell angemeldeter User
    hostname = socket.gethostname()  # Hostname dieses Rechners
    ip_address = socket.gethostbyname(hostname)  # IP-Adresse des Rechners
    cpu_cores_physical = psutil.cpu_count(logical=False)  # Anzahl physischer CPU-Kerne
    cpu_cores_logical = psutil.cpu_count()  # Anzahl logischer CPU-Kerne
    processor = platform.processor()  # Verbauter Prozessor
    operating_system = platform.system() + " " + platform.release()  # Betriebssystem mit Version --> Windows 10
    drives = [drive.replace("\\", "") for drive in
              win32api.GetLogicalDriveStrings().split("\000")[:-1]]  # Alle Laufwerke
    memory = get_virtual_memory()["total"]  # Verbauter Arbeitsspeicher

    return {"current_user": current_user, "hostname": hostname, "ip_address": ip_address, "cpu_p": cpu_cores_physical,
            "cpu_l": cpu_cores_logical, "processor": processor, "os": operating_system, "drives": drives,
            "memory": memory}


def sendmail(receiver, sender, message, subject, username, password, smtp_server, attachment=None, port=587):
    """
    :param sender: String
    :param receiver: List with all receivers of the mail
    :param message: (Doc)string
    :param attachment: list with the locations (paths) of the files
    :param smtp_server: String
    :param username: String
    :param password: String
    :param port: Integer -> Port of server -> Default 587
    :param subject: String
    :return: None
    """

    # Mime-Objekt wird erstellt
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = COMMASPACE.join(receiver)
    msg["Subject"] = subject
    msg.attach(MIMEText(message))

    # Falls dem Parameter ein Argument übergeben wurde, wird versucht den Anhang an das Mime-Objekt anzuhängen
    if attachment:
        for attach in attachment:
            try:
                with open(attach, "rb") as file:
                    part = MIMEApplication(file.read(), Name=os.path.basename(attach))
                part["Content-Disposition"] = "attachment; filename='%s'" % os.path.basename(attach)
                msg.attach(part)
            except Exception as e:
                if len(attachment) > 1:
                    print("Konnte die Dateien nicht anhängen. Fehler: {}".format(e))
                else:
                    print("Konnte die Datei nicht anhängen. Fehler: {}".format(e))

    try:
        # Objekt der Klasse smtplib.SMTP wird erstellt
        mailserver = smtplib.SMTP(smtp_server, port)

        # Am Mailserver identifizieren
        mailserver.ehlo()

        # Verschlüsselung starten
        mailserver.starttls()

        # Erneut am Mailserver identifizieren
        mailserver.ehlo()

        # Anmelden mit Kontodaten
        mailserver.login(username, password)

        # Mail wird versendet
        mailserver.sendmail(sender, receiver, msg.as_string())

        # Verbindung wird getrennt
        mailserver.close()

        return True

    # Unterschiedliche smtplib-Errors werden abgefangen
    except smtplib.SMTPAuthenticationError:
        print("Credentials sind nicht korrekt")
        return False
    except smtplib.SMTPConnectError:
        print("SMTP-Server konnte nicht erreicht werden. Überprüfen Sie Ihre Internetverbindung oder den angegebenen "
              "Server.")
        return False
    except smtplib.SMTPDataError:
        print("DataError.")
        return False
    except smtplib.SMTPHeloError:
        print("Helo Error.")
        return False
    except smtplib.SMTPNotSupportedError:
        print("Not Supported.")
        return False
    except smtplib.SMTPRecipientsRefused:
        print(f"Mailadresse '{receiver[0]}' konnte nicht erreicht werden.")
        return False
    except Exception as e:
        print(e)
        return False


def log(name, file, logtype, msg):
    """
    :param name: Name des Loggers
    :param file: Das File, wo der Log-Eintrag hingeschrieben wird
    :param logtype: e.g. Warning, Error, Critical etc
    :param msg: Zusätzliche Message/Informationen
    :return:
    """

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(name)s\t%(levelname)s\t%(asctime)s\t%(message)s")

    filehandler = logging.FileHandler(file)
    filehandler.setLevel(logging.DEBUG)
    filehandler.setFormatter(formatter)

    logger.addHandler(filehandler)

    logtypes = ["debug", "info", "warning", "error", "critical"]

    if logtype not in logtypes:
        logtype = "debug"
    if logtype == "debug":
        logger.debug(msg)
    elif logtype == "info":
        logger.info(msg)
    elif logtype == "warning":
        logger.warning(msg)
    elif logtype == "error":
        logger.error(msg)
    elif logtype == "critical":
        logger.critical(msg)

    del logger


def warn_message(limit, levelname, typ, func):
    """
    :param limit: Soft- oder Hardlimit
    :param levelname: e.g. Warning, Critical etc.
    :param typ: Typ der Überwachung (CPU, Memory etc.)
    :param func: Die Funktion (get_cpu_usage, get_disk_usage etc.)
    :return: None
    """

    # Wenn ein Limit überschritten ist, wird zunächst ein Warnsound ausgegeben.
    winsound.Beep(1000, 500)

    # Wenn ein Limit überschritten wird, popt eine Warnbox auf
    if typ == "disk":
        ctypes.windll.user32.MessageBoxW(0, f"{levelname}: Speichernutzung höher als {limit} % - {func['used']} GiB von"
                                            f" {func['total']} GiB --> {func['percent']} %", "Festplattennutzung - "
                                                                                             "Warnung", 0)

    elif typ == "memory":
        ctypes.windll.user32.MessageBoxW(0, f"{levelname}: Arbeitsspeichernutzung höher als {limit} % - {func['used']} "
                                            f"GiB von {func['total']} GiB --> {func['percent']} %",
                                            "Arbeitsspeichernutzung - Warnung", 0)

    elif typ == "cpu":
        ctypes.windll.user32.MessageBoxW(0, f"{levelname}: CPU-Auslastung höher als {limit} % --> {func} %",
                                            "CPU-Auslastung - Warnung", 0)


def mon_disk(disk, logs_destination, mail_addresses, attachment, soft, hard, user, password, server, serverport):
    """
    :param disk: String -> Festplatte
    :param logs_destination: String -> Speicherort der Logs
    :param mail_addresses: List -> Alle Empfänger
    :param attachment: Bool -> Logs als Anhang senden Ja/Nein
    :param soft: int -> Softlimit
    :param hard: int -> Hardlimit
    :param user: String -> User Maillogin
    :param password: String -> Passwort Maillogin
    :param server: String -> smtp-Server
    :param serverport: int -> smtp-Port
    :param errorlabel: PyQt5.QLabel-Object -> Errorlabel
    :return:
    """

    # While-Schleife, die permanent überprüft, ob ein Limit überschritten ist. Nach jedem Schleifendurchlauf "schläft"
    # der Prozess in der Mainfunction für eine Sekunde.
    try:
        while True:
            disk_usage = get_disk_usage(disk)
            name = f"Festplattennutzung Laufwerk {disk}"
            file = f"{logs_destination}/limits.log"
            
            if soft <= disk_usage["percent"] < hard:
                logtype = "warning"
                log_msg = f"| Hostname: {socket.gethostname()} | {name} >= {soft} % | Aktuelle Auslastung: {disk_usage['used']} GiB/{disk_usage['total']} GiB = {disk_usage['percent']} %"
                
                log(name, file, logtype, log_msg)

                start = time.time()
                
                while soft <= disk_usage < hard:
                    disk_usage = get_disk_usage(disk)["percent"]
                    time.sleep(.1)
                
                end = time.time()
                
                log(f"Dauer der letzen Festplatten-Auslastung Laufwerk {disk}", file, "info", f"{str(round((end-start), 2))} s")
                
                
            if disk_usage["percent"] >= hard:
                name = f"Festplattennutzung Laufwerk {disk}"
                file = f"{logs_destination}/limits.log"
                logtype = "critical"
                log_msg = f"| Hostname: {socket.gethostname()} | {name} >= {hard} % | Aktuelle Auslastung: {disk_usage['used']} GiB/{disk_usage['total']} GiB = {disk_usage['percent']} %"

                log(name, file, logtype, log_msg)
                
                mail_msg = f"Warnung: Die Festplattennutzung liegt bei {disk_usage['percent']} % | {time.strftime('%d.%m.%y %H:%M:%S')}"

                sendmail(mail_addresses, user, mail_msg, name, user, password, server, attachment=[f"{logs_destination}/limits.log"] if attachment else [])
                
                start = time.time()
                
                while disk_usage["percent"] >= hard:
                    disk_usage = get_disk_usage(disk)["percent"]
                    time.sleep(.1)
                
                end = time.time()
                
                log(f"Dauer der letzen Festplatten-Auslastung Laufwerk {disk}", file, "info", f"{str(round((end-start), 2))} s")
                
            time.sleep(1)

    except Exception as e:
        print(f"Festplattennutzungs-Monitoring wurde beendet. Genaue Fehlerbeschreibung: {e}")
        

def mon_cpu(logs_destination, mail_addresses, attachment, soft, hard, user, password, server, serverport):
    try:
        while True:
            cpu = psutil.cpu_percent()
            name = f"CPU-Auslastung"
            file = f"{logs_destination}/limits.log"

            if soft <= cpu < hard:
                logtype = "warning"
                log_msg = f"| Hostname: {socket.gethostname()} | CPU-Auslastung >= {soft} % | Aktuelle Auslastung: {cpu} %"

                log(name, file, logtype, log_msg)

                start = time.time()
                
                while soft <= cpu < hard:
                    cpu = psutil.cpu_percent()
                    time.sleep(.1)
                
                end = time.time()
                
                log("Dauer der letzten CPU-Auslastung", file, "info", f"{str(round((end-start), 2))} s")
                
            if cpu >= hard:
                logtype = "critical"
                log_msg = f"| Hostname: {socket.gethostname()} | CPU-Auslastung >= {hard} % | Aktuelle Auslastung: {cpu} %"

                log(name, file, logtype, log_msg)

                mail_msg = f"Warnung: Die CPU-Auslastung liegt bei {cpu} % | {time.strftime('%d.%m.%y %H:%M:%S')}"
                sendmail(mail_addresses, user, mail_msg, name, user, password, server, port=serverport, attachment=[f"{logs_destination}/limits.log"] if attachment else [])
                   
                start = time.time()
                
                while cpu >= hard:
                    cpu = psutil.cpu_percent()
                    time.sleep(.1)
                
                end = time.time()
                
                log("Dauer der letzten CPU-Auslastung", file, "info", f"{str(round((end-start), 2))} s")
                
            time.sleep(1)

    except Exception as e:
        print(f"Festplattennutzungs-Monitoring wurde beendet. Genaue Fehlerbeschreibung: {e}")


def mon_memory(logs_destination, mail_addresses, attachment, soft, hard, user, password, server, serverport):
    try:
        while True:
            virtual_memory = get_virtual_memory()
            name = f"Arbeitsspeichernutzung"
            file = f"{logs_destination}/limits.log"

            if soft <= virtual_memory["percent"] < hard:
                logtype = "warning"
                log_msg = f"Hostname: {socket.gethostname()} | Festplattennutzung > {soft} % | Aktuelle Auslastung: {virtual_memory['used']} GiB/{virtual_memory['total']} GiB = {virtual_memory['percent']} %"

                log(name, file, logtype, log_msg)

                start = time.time()
                
                while soft <= virtual_memory["percent"] < hard:
                    virtual_memory = get_virtual_memory()["percent"]
                    time.sleep(.1)
                
                end = time.time()
                
                log("Dauer der letzten Arbeitsspeicher-Auslastung", file, "info", str(round((end-start), 2)))
                
            if virtual_memory["percent"] >= hard:
                logtype = "critical"
                log_msg = f"Hostname: {socket.gethostname()} | Festplattennutzung höher als {hard} % | Aktuelle Auslastung: {virtual_memory['used']} GiB/{virtual_memory['total']} GiB = {virtual_memory['percent']} %"

                log(name, file, logtype, log_msg)

                mail_msg = f"Warnung: Die Festplattennutzung liegt bei {virtual_memory['percent']} % | {time.strftime('%d.%m.%y %H:%M:%S')}"

                sendmail(mail_addresses, user, mail_msg, name, user, password, server, port=serverport, attachment=[f"{logs_destination}/limits.log"] if attachment else [])
                   
                start = time.time()
                
                while virtual_memory["percent"] >= hard:
                    virtual_memory = get_virtual_memory()["percent"]
                    time.sleep(.1)
                
                end = time.time()
                
                log("Dauer", file, "info", str(round((end-start), 2)))
                
            time.sleep(1)

    except Exception as e:
        print("Festplattennutzungs-Monitoring wurde beendet. Genaue Fehlerbeschreibung:", e)



def show_hardware_information():
    """
    Printed Hardwareinformationen
    :return: Dictionary
    """

    sys_info = get_pc_information()
    cpu = psutil.cpu_percent(interval=1)
    memory = get_virtual_memory()
    timestamp = time.strftime("%d.%m.%y %H:%M:%S")

    data = {"timestamp": timestamp,
            "cpu": 0,
            "memory": {"total": 0.0,
                       "available": 0.0,
                       "percent": 0.0,
                       "used": 0.0,
                       "free": 0.0},
            "disk": [],
            "processes": len(psutil.pids())
            }
    cls()

    print("Aktuelle Auslastungen:")
    print("Timestamp:", timestamp)
    print()
    print()

    print("CPU-Auslastung:", cpu, "%")
    data["cpu"] = cpu
    print()

    print("Anzahl laufender Prozesse:", len(psutil.pids()))
    print()

    print("Arbeitsspeichernutzung:")
    print("\tGesamt:                ", memory["total"], "GiB")
    print("\tVerfügbar:             ", memory["free"], "GiB")
    print("\tAbsolut genutzt:       ", memory["used"], "GiB")
    print("\tProzentual genutzt:    ", memory["percent"], "%")
    print()

    data["memory"]["total"] = memory["total"]
    data["memory"]["free"] = memory["free"]
    data["memory"]["used"] = memory["used"]
    data["memory"]["percent"] = memory["percent"]

    print("Festplattennutzung:")
    for drive in sys_info["drives"]:
        # Falls ein Netzlaufwerk eingebunden ist und das nicht erreichbar ist
        try:
            print("\tLaufwerk:              ", drive[0])
            print("\tGesamt:                ", get_disk_usage(drive)["total"], "GiB")
            print("\tVerfügbar:             ", get_disk_usage(drive)["free"], "GiB")
            print("\tAbsolut genutzt:       ", get_disk_usage(drive)["used"], "GiB")
            print("\tProzentual genutzt:    ", get_disk_usage(drive)["percent"], "%")
            print()

            data["disk"].append({"drive": drive[0],
                                 "total": get_disk_usage(drive)["total"],
                                 "free": get_disk_usage(drive)["free"],
                                 "used": get_disk_usage(drive)["used"],
                                 "percent": get_disk_usage(drive)["percent"]
                                 })
        except Exception as e:
            print(e)
            input("Drücke Enter um fortzufahren.")

        print()

    return data


if __name__ == '__main__':
    pass
