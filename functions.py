import os
import smtplib
import platform
import psutil
import socket
import logging
import time
import json
import base64
from configparser import ConfigParser
import pickle
import getpass
import argparse
import sys
import glob

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE
import win32api


def log(file, logtype, msg):
    """
    :param file: Das File, wo der Log-Eintrag hingeschrieben wird
    :param logtype: e.g. Warning, Error, Critical etc
    :param msg: Zusätzliche Message/Informationen
    :return:
    """
    name = socket.gethostname()

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)    

    formatter = logging.Formatter("%(asctime)s\t%(levelname)s\t%(name)s\t%(message)s")

    filehandler = logging.FileHandler(file)
    filehandler.setLevel(logging.DEBUG)
    filehandler.setFormatter(formatter)

    streamhandler = logging.StreamHandler()
    streamhandler.setFormatter(formatter)

    logger.addHandler(filehandler)
    logger.addHandler(streamhandler)
    

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
    
    del logger.handlers[:]
    return

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
                log("Logs/system.log", "error", f"Mailversand - Datei {attach} konnte nicht angehängt werden. Fehler: {e}")

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
    except smtplib.SMTPAuthenticationError as e:
        log("Logs/system.log", "error", f"Mail - ungültige Zugangsdaten. Fehler: {e}")
        return False
    except smtplib.SMTPConnectError as e:
        log("Logs/system.log", "error", f"Mail - Connectionerror. Fehler: {e}")
        return False
    except smtplib.SMTPDataError as e:
        log("Logs/system.log", "error", f"Mail - Dataerror. Fehler: {e}")
        return False
    except smtplib.SMTPHeloError as e:
        log("Logs/system.log", "error", f"Mail - Heloerror. Fehler: {e}")
        return False
    except smtplib.SMTPNotSupportedError as e:
        log("Logs/system.log", "error", f"Mail - Not supported-error. Fehler: {e}")
        return False
    except smtplib.SMTPRecipientsRefused as e:
        log("Logs/system.log", "error", f"Mail - Empfänger refused. Fehler: {e}")
        return False
    except Exception as e:
        log("Logs/system.log", "error", f"Mailversand. Fehler: {e}")
        return False

def mon_disk(disk, mail_addresses, attachment, soft, hard, user, password, server, serverport):
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
    if len(sys.argv) > 1:
        if os.path.isfile("Temp/processes.pickle"):
            with open("Temp/processes.pickle", "rb") as p:
                processes = pickle.load(p)
        else:
            processes = {}
        
        processes[disk.replace(":", "").lower()] = os.getpid()
        with open("Temp/processes.pickle", "wb") as p:
            pickle.dump(processes, p)

    try:
        name = f"Laufwerk {disk}-Auslastung"
        f = "Logs/limits.log"

        while True:
            disk_usage = get_disk_usage(disk)         
            
            if soft <= disk_usage["percent"] < hard:

                logtype = "warning"
                log_msg = f"{name} >= {soft} % | Aktuelle Auslastung: {disk_usage['used']} GiB/{disk_usage['total']} GiB = {disk_usage['percent']} %"
                
                log(f, logtype, log_msg)
                
                while soft <= disk_usage["percent"] < hard:
                    disk_usage = get_disk_usage(disk)
                    time.sleep(1)
                
            elif disk_usage["percent"] >= hard:

                logtype = "critical"
                log_msg = f"{name} >= {hard} % | Aktuelle Auslastung: {disk_usage['used']} GiB/{disk_usage['total']} GiB = {disk_usage['percent']} %"

                log(f, logtype, log_msg)
                
                mail_msg = f"Warnung: Die Festplattennutzung liegt bei {disk_usage['percent']} % | {time.strftime('%d.%m.%y %H:%M:%S')}"

                try:
                    sendmail(mail_addresses, user, mail_msg, name, user, password, server, attachment=glob.glob("Logs/*.log") if attachment else [])
                    log("Logs/system.log", "info", f"Festplattennutzung {disk} - Mail wurde an {mail_addresses} versandt")
                
                except Exception as e:
                    log("Logs/system.log", "error", f"Festplattennutzung {disk} - Mail wurde nicht versandt. Genaue Fehlerbeschreibung: {e}")
                                
                while disk_usage["percent"] >= hard:
                    disk_usage = get_disk_usage(disk)
                    time.sleep(1)

            time.sleep(1)

    except Exception as e:
        log("Logs/system.log", "error", f"Laufwerk {disk}-Monitoring wurde beendet. Genaue Fehlerbeschreibung: {e}")

def mon_cpu(mail_addresses, attachment, soft, hard, user, password, server, serverport):
    if len(sys.argv) > 1:

        if os.path.isfile("Temp/processes.pickle"):
            with open("Temp/processes.pickle", "rb") as p:
                processes = pickle.load(p)
        else:
            processes = {}
        
        processes["cpu"] = os.getpid()
        with open("Temp/processes.pickle", "wb") as p:
            pickle.dump(processes, p)

    try:
        name = f"CPU-Auslastung"
        f = "Logs/limits.log"

        while True:
            cpu = psutil.cpu_percent()

            if soft <= cpu < hard:

                logtype = "warning"
                log_msg = f"CPU-Auslastung >= {soft} % | Aktuelle Auslastung: {cpu} %"

                log(f, logtype, log_msg)

                while soft <= cpu < hard:
                    cpu = psutil.cpu_percent()
                    time.sleep(1)
                
            elif cpu >= hard:

                logtype = "critical"
                log_msg = f"CPU-Auslastung >= {hard} % | Aktuelle Auslastung: {cpu} %"

                log(f, logtype, log_msg)

                mail_msg = f"Warnung: Die CPU-Auslastung liegt bei {cpu} % | {time.strftime('%d.%m.%y %H:%M:%S')}"

                try:
                    sendmail(mail_addresses, user, mail_msg, name, user, password, server, port=serverport, attachment=glob.glob("Logs/*.log") if attachment else [])
                    log("Logs/system.log", "info", f"CPU - Mail wurde an {mail_addresses} versandt")

                except Exception as e:
                    log("Logs/system.log", "error", f"CPU - Mail wurde nicht versandt. Genaue Fehlerbeschreibung: {e}")   
                
                while cpu >= hard:
                    cpu = psutil.cpu_percent()
                    time.sleep(1)
                
            time.sleep(1)

    except Exception as e:
        log("Logs/system.log", "error", f"CPU-Monitoring wurde unerwartet beendet. Genaue Fehlerbeschreibung: {e}")

def mon_memory(mail_addresses, attachment, soft, hard, user, password, server, serverport):
    if len(sys.argv) > 1:

        if os.path.isfile("Temp/processes.pickle"):
            with open("Temp/processes.pickle", "rb") as p:
                processes = pickle.load(p)
        else:
            processes = {}
        
        processes["ram"] = os.getpid()
        with open("Temp/processes.pickle", "wb") as p:
            pickle.dump(processes, p)

    try:
        name = f"Arbeitsspeichernutzung"
        f = "Logs/limits.log"

        while True:
            virtual_memory = get_virtual_memory()

            if soft <= virtual_memory["percent"] < hard:

                logtype = "warning"
                log_msg = f"{name} >= {soft} % | Aktuelle Auslastung: {virtual_memory['used']} GiB/{virtual_memory['total']} GiB = {virtual_memory['percent']} %"

                log(f, logtype, log_msg)
                
                while soft <= virtual_memory["percent"] < hard:
                    virtual_memory = get_virtual_memory()
                    time.sleep(1)
                
            elif virtual_memory["percent"] >= hard:

                logtype = "critical"
                log_msg = f"{name} >= {hard} % | Aktuelle Auslastung: {virtual_memory['used']} GiB/{virtual_memory['total']} GiB = {virtual_memory['percent']} %"

                log(f, logtype, log_msg)

                mail_msg = f"Warnung: Die {name} liegt bei {virtual_memory['percent']} % | {time.strftime('%d.%m.%y %H:%M:%S')}"

                try:
                    sendmail(mail_addresses, user, mail_msg, name, user, password, server, port=serverport, attachment=glob.glob("Logs/*.log") if attachment else [])
                    log("Logs/system.log", "info", f"Arbeitsspeicher - Mail wurde an {mail_addresses} versandt")

                except Exception as e:
                    log("Logs/system.log", "error", f"Arbeitsspeicher - Mail wurde nicht versandt. Genaue Fehlerbeschreibung: {e}")
                   
                while virtual_memory["percent"] >= hard:
                    virtual_memory = get_virtual_memory()
                    time.sleep(1)
                
            time.sleep(1)

    except Exception as e:
        log("Logs/system.log", "error", f"Arbeitsspeicher-Monitoring wurde unerwartet beendet. Genaue Fehlerbeschreibung: {e}")


if __name__ == '__main__':

    parser = argparse.ArgumentParser()

    mon = ["cpu", "ram"]
    for drive in get_pc_information()["drives"]:
        mon.append(drive.replace(":", "").lower())

    parser.add_argument("startstop", metavar="start, stop", help="Starten (start) oder stoppen (stop) eines Monitorings", choices=["start", "stop"])
    parser.add_argument("monitoring", metavar=", ".join(mon), help="Typ des Monitoring", choices=mon)

    parser.add_argument("-a", action="store_true", dest="attachment", help="Attachment als Anhang senden")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-m", "--manual", metavar="", action="store", dest="commands", nargs=7,
                        help="int: <Softlimit>, int: <Hardlimit>, str: <Mailempfänger>, str: <Mailuser>, str: <Mailpassword>, str: <SMTP-Server>, int: <Port>")


    args = parser.parse_args()


    if args.startstop == "start":
        if args.monitoring == "cpu":
            log("Logs/monitoring.log", "info", f"{args.monitoring}-Monitoring wurde gestarted. Prozess-ID: {os.getpid()}")
            mon_cpu(args.commands[2], args.attachment, int(args.commands[0]), int(args.commands[1]), args.commands[3], args.commands[4], args.commands[5], int(args.commands[6]))

        elif args.monitoring == "ram":
            log("Logs/monitoring.log", "info", f"{args.monitoring}-Monitoring wurde gestarted. Prozess-ID: {os.getpid()}") 
            mon_memory(args.commands[2], args.attachment, int(args.commands[0]), int(args.commands[1]), args.commands[3], args.commands[4], args.commands[5], int(args.commands[6]))

        elif args.monitoring in mon:
            log("Logs/monitoring.log", "info", f"{args.monitoring.upper()}-Monitoring wurde gestarted. Prozess-ID: {os.getpid()}") 
            mon_disk(f"{args.monitoring.upper()}:", args.commands[2], args.attachment, int(args.commands[0]), int(args.commands[1]), args.commands[3], args.commands[4], args.commands[5], int(args.commands[6]))
