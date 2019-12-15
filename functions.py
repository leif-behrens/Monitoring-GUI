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
import pickle


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


def log(file, logtype, msg):
    """
    :param name: Name des Loggers
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
        name = f"Laufwerk {disk}-Auslastung"
        f = f"{logs_destination}/limits.log"

        while True:
            disk_usage = get_disk_usage(disk)         
            
            if soft <= disk_usage["percent"] < hard:

                logtype = "warning"
                log_msg = f"{name} >= {soft} % | Aktuelle Auslastung: {disk_usage['used']} GiB/{disk_usage['total']} GiB = {disk_usage['percent']} %"
                
                log(f, logtype, log_msg)

                start = time.time()
                
                while soft <= disk_usage["percent"] < hard:
                    disk_usage = get_disk_usage(disk)
                    time.sleep(1)
                
                end = time.time()
                
                log(f, "info", f"Dauer der letzen Festplatten-Auslastung Laufwerk {disk}: {str(round((end-start), 2))} s")
                
            elif disk_usage["percent"] >= hard:

                logtype = "critical"
                log_msg = f"{name} >= {hard} % | Aktuelle Auslastung: {disk_usage['used']} GiB/{disk_usage['total']} GiB = {disk_usage['percent']} %"

                log(f, logtype, log_msg)
                
                mail_msg = f"Warnung: Die Festplattennutzung liegt bei {disk_usage['percent']} % | {time.strftime('%d.%m.%y %H:%M:%S')}"

                try:
                    sendmail(mail_addresses, user, mail_msg, name, user, password, server, attachment=[f"{logs_destination}/limits.log"] if attachment else [])
                    log("Logs/system.log", "info", f"Festplattennutzung {disk.replace} - Mail wurde an {mail_addresses} versandt")
                
                except Exception as e:
                    log("Logs/system.log", "error", f"Festplattennutzung {disk.replace} - Mail wurde nicht versandt. Genaue Fehlerbeschreibung: {e}")
                
                start = time.time()
                
                while disk_usage["percent"] >= hard:
                    disk_usage = get_disk_usage(disk)
                    time.sleep(1)

                end = time.time()
                
                log(f, "info", f"Dauer der letzen Festplatten-Auslastung Laufwerk {disk}:{str(round((end-start), 2))} s")
                
            time.sleep(1)

    except Exception as e:
        log("Logs/system.log", "error", f"Laufwerk {disk.replace(':', '')}-Monitoring wurde beendet. Genaue Fehlerbeschreibung: {e}")
        

def mon_cpu(logs_destination, mail_addresses, attachment, soft, hard, user, password, server, serverport):
    try:
        name = f"CPU-Auslastung"
        f = f"{logs_destination}/limits.log"

        while True:
            cpu = psutil.cpu_percent()

            if soft <= cpu < hard:

                logtype = "warning"
                log_msg = f"CPU-Auslastung >= {soft} % | Aktuelle Auslastung: {cpu} %"

                log(f, logtype, log_msg)

                start = time.time()
                
                while soft <= cpu < hard:
                    cpu = psutil.cpu_percent()
                    time.sleep(1)
                
                end = time.time()
                
                log(f, "info", f"Dauer der letzten CPU-Auslastung: {str(round((end-start), 2))} s")
                
            elif cpu >= hard:

                logtype = "critical"
                log_msg = f"CPU-Auslastung >= {hard} % | Aktuelle Auslastung: {cpu} %"

                log(f, logtype, log_msg)

                mail_msg = f"Warnung: Die CPU-Auslastung liegt bei {cpu} % | {time.strftime('%d.%m.%y %H:%M:%S')}"

                try:
                    sendmail(mail_addresses, user, mail_msg, name, user, password, server, port=serverport, attachment=[f"{logs_destination}/limits.log"] if attachment else [])
                    log("Logs/system.log", "info", f"CPU - Mail wurde an {mail_addresses} versandt")

                except Exception as e:
                    log("Logs/system.log", "error", f"CPU - Mail wurde nicht versandt. Genaue Fehlerbeschreibung: {e}")   
                
                start = time.time()
                
                while cpu >= hard:
                    cpu = psutil.cpu_percent()
                    time.sleep(1)
                
                end = time.time()
                
                log(f, "info", f"Dauer der letzten CPU-Auslastung: {str(round((end-start), 2))} s")
                
            time.sleep(1)

    except Exception as e:
        log("Logs/system.log", "error", f"CPU-Monitoring wurde unerwartet beendet. Genaue Fehlerbeschreibung: {e}")


def mon_memory(logs_destination, mail_addresses, attachment, soft, hard, user, password, server, serverport):
    try:
        name = f"Arbeitsspeichernutzung"
        f = f"{logs_destination}/limits.log"

        while True:
            virtual_memory = get_virtual_memory()

            if soft <= virtual_memory["percent"] < hard:

                logtype = "warning"
                log_msg = f"{name} >= {soft} % | Aktuelle Auslastung: {virtual_memory['used']} GiB/{virtual_memory['total']} GiB = {virtual_memory['percent']} %"

                log(name, f, logtype, log_msg)

                start = time.time()
                
                while soft <= virtual_memory["percent"] < hard:
                    virtual_memory = get_virtual_memory()
                    time.sleep(1)
                
                end = time.time()
                
                log(f, "info", f"Dauer der letzten Arbeitsspeicher-Auslastung: {str(round((end-start), 2))} s")
                
            elif virtual_memory["percent"] >= hard:

                logtype = "critical"
                log_msg = f"{name} >= {hard} % | Aktuelle Auslastung: {virtual_memory['used']} GiB/{virtual_memory['total']} GiB = {virtual_memory['percent']} %"

                log(f, logtype, log_msg)

                mail_msg = f"Warnung: Die {name} liegt bei {virtual_memory['percent']} % | {time.strftime('%d.%m.%y %H:%M:%S')}"

                try:
                    sendmail(mail_addresses, user, mail_msg, name, user, password, server, port=serverport, attachment=[f"{logs_destination}/limits.log"] if attachment else [])
                    log("Logs/system.log", "info", f"Arbeitsspeicher - Mail wurde an {mail_addresses} versandt")

                except Exception as e:
                    log("Logs/system.log", "error", f"Arbeitsspeicher - Mail wurde nicht versandt. Genaue Fehlerbeschreibung: {e}")
                   
                start = time.time()
                
                while virtual_memory["percent"] >= hard:
                    virtual_memory = get_virtual_memory()
                    time.sleep(1)
                
                end = time.time()
                
                log(f, "info", f"Dauer der letzten Arbeitsspeicher-Auslastung: {str(round((end-start), 2))} s")
                
            time.sleep(1)

    except Exception as e:
        log("Logs/system.log", "error", f"Arbeitsspeicher-Monitoring wurde unerwartet beendet. Genaue Fehlerbeschreibung: {e}")



if __name__ == '__main__':
    pass