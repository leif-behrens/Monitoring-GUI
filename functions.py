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


def get_disk_usage(path="C:/"):
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
    except OSError as e:
        print(e)
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


def mon_disk(idle, logs_destination, mail_addresses, attachment, soft, hard):
    """
    :param idle: Int -> Sleep, bis die nächste Mail versand werden darf
    :param logs_destination: String -> Speicherort der Logs
    :param mail_addresses: List -> Alle Empfänger
    :param attachment: Bool -> Logs als Anhang senden Ja/Nein
    :param soft: int -> Softlimit
    :param hard: int -> Hardlimit
    :return:
    """

    config = ConfigParser()

    config.read("Config.ini")
    mail = config["Email"]

    user = mail["user"]
    password = base64.b64decode(mail["password"]).decode("utf-8")
    server = mail["server"]

    if attachment:
        attach = [f"{logs_destination}/hardlimit.log"]
    else:
        attach = []

    # While-Schleife, die permanent überprüft, ob ein Limit überschritten ist. Nach jedem Schleifendurchlauf "schläft"
    # der Prozess in der Mainfunction für eine Sekunde.
    try:
        while True:
            disk_usage = get_disk_usage()
            if soft < disk_usage["percent"] < hard:
                # Sollte die Festplattennutzung größer als das Soft- und kleiner als das Hardlimit sein, wird ein
                # Logeintrag geschrieben. Anschließend wird in der Mainfunction (in Main.py) eine Warn-Message geprinted
                log("Festplattennutzung", f"{logs_destination}/softlimit.log", "warning",
                    f"Hostname: {socket.gethostname()} - Festplattennutzung höher als {soft} % - Aktuelle Auslastung: "
                    f"{disk_usage['used']} GiB/{disk_usage['total']} GiB = {disk_usage['percent']} %")
                warn_message(soft, "Warnung", "disk", disk_usage)
                time.sleep(idle / 2)

            if disk_usage["percent"] >= hard:
                log("Festplattennutzung", f"{logs_destination}/hardlimit.log", "critical",
                    f"Hostname: {socket.gethostname()} - Festplattennutzung höher als {hard} % - Aktuelle Auslastung: "
                    f"{disk_usage['used']} GiB/{disk_usage['total']} GiB = {disk_usage['percent']} %")
                warn_message(hard, "Kritisch", "disk", disk_usage)
                msg = f"Warnung: Die Festplattennutzung liegt bei {disk_usage['percent']} % - " \
                      f"{time.strftime('%d.%m.%y %H:%M:%S')}"
                sendmail(mail_addresses, user, msg, "CPU-Auslastung", user, password, server, attachment=attach)
                time.sleep(idle)
            time.sleep(1)

    except KeyboardInterrupt:
        print("Festplattennutzungs-Monitoring wurde manuell beendet.")

    except Exception as e:
        print("Festplattennutzungs-Monitoring wurde beendet. Genaue Fehlerbeschreibung:", e)


def mon_memory(idle, logs_destination, mail_addresses, attachment, soft, hard):
    """
    :param idle: Int -> Sleep, bis die nächste Mail versendet werden darf
    :param logs_destination: String -> Speicherort der Logs
    :param mail_addresses: List -> Alle Empfänger
    :param attachment: Bool -> Logs als Anhang senden Ja/Nein
    :param soft: int -> Softlimit
    :param hard: int -> Hardlimit
    :return:
    """

    config = ConfigParser()

    config.read("Config.ini")
    mail = config["Email"]

    user = mail["user"]
    password = base64.b64decode(mail["password"]).decode("utf-8")
    server = mail["server"]

    if attachment:
        attach = [f"{logs_destination}/hardlimit.log"]
    else:
        attach = []

    try:
        while True:
            virtual_memory = get_virtual_memory()
            if soft < virtual_memory["percent"] < hard:
                log("Arbeitsspeichernutzung", f"{logs_destination}/softlimit.log", "warning",
                    f"Hostname: {socket.gethostname()} - Arbeitsspeichernutzung höher als {soft} % - "
                    f"Aktuelle Auslastung: {virtual_memory['used']} GiB/{virtual_memory['total']} GiB = "
                    f"{virtual_memory['percent']} %")
                warn_message(soft, "Warnung", "memory", virtual_memory)
                time.sleep(idle / 2)

            if virtual_memory["percent"] >= hard:
                log("Arbeitsspeichernutzung", f"{logs_destination}/hardlimit.log", "critical",
                    f"Hostname: {socket.gethostname()} - Arbeitsspeichernutzung höher als {hard} % - "
                    f"Aktuelle Auslastung: {virtual_memory['used']} GiB/{virtual_memory['total']} GiB = "
                    f"{virtual_memory['percent']} %")
                warn_message(hard, "Kritisch", "memory", virtual_memory)
                msg = f"Warnung: Die Arbeitsspeichernutzung liegt bei {virtual_memory['percent']} % - " \
                      f"{time.strftime('%d.%m.%y %H:%M:%S')}"
                sendmail(mail_addresses, user, msg, "Arbeitsspeichernutzung", user, password, server, attachment=attach)
                time.sleep(idle)
            time.sleep(1)

    except KeyboardInterrupt:
        print("Arbeitsspeichernutzungs-Monitoring wurde manuell beendet.")

    except Exception as e:
        print("Arbeitsspeichernutzungs-Monitoring wurde beendet. Genaue Fehlerbeschreibung:", e)


def mon_cpu(idle, logs_destination, mail_addresses, attachment, soft, hard):
    """
    :param idle: Int -> Sleep, bis die nächste Mail versand werden darf
    :param logs_destination: String -> Speicherort der Logs
    :param mail_addresses: List -> Alle Empfänger
    :param attachment: Bool -> Logs als Anhang senden Ja/Nein
    :param soft: int -> Softlimit
    :param hard: int -> Hardlimit
    :return:
    """

    config = ConfigParser()

    config.read("Config.ini")
    mail = config["Email"]

    user = mail["user"]
    password = base64.b64decode(mail["password"]).decode("utf-8")
    server = mail["server"]

    if attachment:
        attach = [f"{logs_destination}/hardlimit.log"]
    else:
        attach = []

    try:
        while True:

            cpu = psutil.cpu_percent()
            if soft < cpu < hard:
                log("CPU-Auslastung", f"{logs_destination}/softlimit.log", "warning",
                    f"Hostname: {socket.gethostname()} - CPU-Auslastung höher als {soft} % - Aktuelle Auslastung: "
                    f"{cpu} %")
                warn_message(soft, "Warnung", "cpu", cpu)
                time.sleep(idle / 2)

            if cpu >= hard:
                log("CPU-Auslastung", f"{logs_destination}/hardlimit.log", "critical",
                    f"Hostname: {socket.gethostname()} - CPU-Auslastung höher als {hard} % - Aktuelle Auslastung: "
                    f"{cpu} %")
                warn_message(hard, "Kritisch", "cpu", cpu)

                msg = f"Warnung: Die CPU-Auslastung liegt bei {cpu} % - {time.strftime('%d.%m.%y %H:%M:%S')}"
                sendmail(mail_addresses, user, msg, "CPU-Auslastung", user, password, server, attachment=attach)
                time.sleep(idle)
            time.sleep(1)
    except KeyboardInterrupt:
        print("CPU-Monitoring wurde manuell beendet.")
    except Exception as e:
        print("CPU-Monitoring wurde beendet. Genaue Fehlerbeschreibung:", e)


def get_config_filename():
    """
    :return: String - Name der Datei
    """

    while True:
        filename = input("Konfigurationsdateiname eingeben:\n")
        path = "Config"

        if os.path.isfile(f"{path}/{filename}.json"):
            print("Dieser Name ist bereits vergeben.")
            time.sleep(.5)
            cls()
        else:
            cls()
            return filename


def get_logs_path():
    """
    :return: String - Pfad, wo die Logs abgespeichert werden sollen
    """

    while True:
        logs_destination = input("Wo sollen die Logs abgespeichert werden? Bitte Pfad eingeben (relativer oder "
                                 "absoluter Pfad).\n")
        logs_destination = logs_destination.replace('"', '')

        if os.path.isdir(logs_destination):
            cls()
            return logs_destination
        else:
            print("Speicherort nicht vorhanden.")
            time.sleep(.5)
            cls()


def get_mail_addresses():
    """
    :return: None
    """

    # Zugangsdaten werden eingelesen
    config = ConfigParser()

    config.read("Config.ini")
    mail = config["Email"]

    user = mail["user"]
    password = base64.b64decode(mail["password"]).decode("utf-8")
    server = mail["server"]

    while True:
        mail_address = input("Mailadresse(n) eingeben. Mehrere Mailadressen mit Komma (ohne Leerzeichen) "
                             "trennen.\n")
        if len(mail_address) == 0:
            print("Mindestens eine Mailadresse eingeben.")
            time.sleep(.5)
            cls()
            continue
        else:
            cls()
            mail_state = []
            if len(mail_state) > 1:
                print("Es wird nun eine Mail an die eingegebene Adresse geschickt, um zu überprüfen, ob die "
                      "Mailadresse gültig ist.")
            else:
                print("Es wird nun eine Mail an die eingegebenen Adressen geschickt, um zu überprüfen, ob die "
                      "Mailadressen gültig sind.")

            # Mailversand an alle eingegegebenen Adressen. Wenn ein Absender nicht erreicht werden kann, muss der User
            # erneut Mailadressen iengeben
            for mail in mail_address.split(","):
                mail_status = sendmail([mail], user, "-----", "Verifizierung", user, password, server)
                mail_state.append(mail_status)

            if all(mail_state):
                cls()
                return mail_address.split(",")
            else:
                continue


def get_attachment_send():
    """
    :return: Bool
    """

    while True:
        attachment_send = input("Soll die Hardlimitlog-Datei immer per Mail mitgeschickt werden, wenn ein Hardlimit "
                                "überschritten wird? y/n\n").lower()
        if attachment_send == "n":
            cls()
            return False
        elif attachment_send == "y":
            cls()
            return True
        else:
            print("Ungültige Eingabe.")
            time.sleep(.5)
            cls()


def get_idle_time():
    """
    IDLE-Zeit nach Sendung einer Mail
    :return: Tuple
    """

    print("Im Fall der Überschreitung eines Hardlimits wird automatisch eine Mail generiert. Wie viele Sekunden "
          "soll gewartet werden, bis die nächste Mail gesendet werden kann?")

    while True:
        try:
            idle_cpu = int(input("Fürs CPU-Monitoring:\n"))
            break
        except ValueError:
            print("Ungültige Eingabe.")

    while True:
        try:
            idle_disk = int(input("Fürs Festplattennutzungs-Monitoring:\n"))
            break
        except ValueError:
            print("Ungültige Eingabe.")

    while True:
        try:
            idle_memory = int(input("Fürs Arbeitsspeicher-Monitoring:\n"))
            break
        except ValueError:
            print("Ungültige Eingabe.")

    cls()
    return idle_cpu, idle_disk, idle_memory


def get_limits():
    """
    :return: Tuple
    """

    while True:
        try:
            soft_limit = int(input("Softlimit in Prozent:\n"))
            hard_limit = int(input("Hardlimit in Prozent:\n"))

            if (soft_limit >= 100 or soft_limit <= 0) or (hard_limit >= 100 or hard_limit <= 0):
                raise ValueTooHighOrTooLowException

            elif soft_limit >= hard_limit:
                raise ValueGreaterThanOtherValueException

            else:
                cls()
                return soft_limit, hard_limit
        except ValueError:
            print("Ungültige Eingabe.")

        except ValueTooHighOrTooLowException:
            print("Soft- und Hardlimit müssen zwischen 0 und 100 liegen.")

        except ValueGreaterThanOtherValueException:
            print("Softlimit muss kleiner als das Hardlimit sein.")


def edit_configfile(file, options):
    """
    :param file: Dictionary - die zu konfigurierende Datei
    :param options: Set mit Integers - zu bearbeitende Informationen
    [1] - Name der Konfigurationsdatei
    [2] - Speicherort der Logs
    [3] - Email-Adressen
    [4] - Log als Anhang
    [5] - Limits
    [6] - IDLE-Zeit nach Mailversand
    :return:
    """

    config_file = file

    for option in options:
        if option == 1:
            current_file = f"Config/{config_file['filename']}"
            name = get_config_filename()
            config_file["filename"] = name
            os.remove(current_file)
        elif option == 2:
            logs_path = get_logs_path()
            config_file["logs_destination"] = logs_path
        elif option == 3:
            mail_addresses = get_mail_addresses()
            config_file["mail_address"] = mail_addresses
        elif option == 4:
            attachment_send = get_attachment_send()
            config_file["attachment_send"] = attachment_send
        elif option == 5:
            soft_limit, hard_limit = get_limits()
            config_file["limits"]["soft"] = soft_limit
            config_file["limits"]["hard"] = hard_limit
        elif option == 6:
            idle_cpu, idle_disk, idle_memory = get_idle_time()
            config_file["IDLE_time"]["cpu"] = idle_cpu
            config_file["IDLE_time"]["disk"] = idle_disk
            config_file["IDLE_time"]["memory"] = idle_memory

    with open(f"Config/{config_file['filename']}.json", "w") as j:
        json.dump(config_file, j, indent=4)


def setup():
    """
    :return: Dictionary
    """

    setup_dic = {"filename": None,
                 "logs_destination": None,
                 "mail_address": None,
                 "attachment_send": None,
                 "limits": {"soft": 0,
                            "hard": 0},
                 "IDLE_time": {"cpu": 0,
                               "disk": 0,
                               "memory": 0}}

    print("Setup wird gestartet...")
    time.sleep(.5)
    print()

    filename = get_config_filename()

    logs_destination = get_logs_path()

    mail_addresses = get_mail_addresses()

    attachment_send = get_attachment_send()

    idle_cpu, idle_disk, idle_memory = get_idle_time()
    print("Im Fall der Überschreitung eines Hardlimits wird automatisch eine Mail generiert. Wie viele Sekunden "
          "soll gewartet werden, bis die nächste Mail gesendet werden kann?")

    soft_limit, hard_limit = get_limits()

    setup_dic["filename"] = f"{filename}.json"
    setup_dic["logs_destination"] = logs_destination
    setup_dic["mail_address"] = mail_addresses
    setup_dic["attachment_send"] = attachment_send
    setup_dic["limits"]["soft"] = soft_limit
    setup_dic["limits"]["hard"] = hard_limit
    setup_dic["IDLE_time"]["cpu"] = idle_cpu
    setup_dic["IDLE_time"]["disk"] = idle_disk
    setup_dic["IDLE_time"]["memory"] = idle_memory

    return setup_dic


def save_json_send_mail(msg, receiver, user, password, server, data):
    """
    :param msg: String - Nachricht der Mail
    :param receiver: List
    :param user: String
    :param password: String
    :param server: String
    :param data: Dictionary
    :return: None
    """

    while True:
        path = input("Speicherort (Ordner) angeben:\n")

        if not os.path.isdir(path):
            print("Ordner nicht vorhanden.")
            continue

        while True:
            name = input("Name der Datei:\n")

            if os.path.isfile(f"{path}/{name}.json"):
                print("Datei existiert bereits.")
                continue
            break

        with open(f"{path}/{name}.json", "w") as j:
            json.dump(data, j, indent=4)
        print(f"Erfolgreich unter {path}/{name} gespeichert.")
        time.sleep(.5)

        sendmail(receiver, user, "Siehe Anhang", msg, user, password, server,
                 attachment=[f"{path}/{name}.json"])
        print("Mail wurde versandt.")
        time.sleep(.5)
        cls()
        break


def save_json(data):
    """
    :param data: Daten, die gespeichert werden sollen
    :return: None
    """

    while True:
        path = input("Speicherort (Ordner) angeben:\n")

        if not os.path.isdir(path):
            print("Ordner nicht vorhanden.")
            continue

        while True:
            name = input("Name der Datei:\n")

            if os.path.isfile(f"{path}/{name}.json"):
                print("Datei existiert bereits.")
                continue
            break

        with open(f"{path}/{name}.json", "w") as j:
            json.dump(data, j, indent=4)
        print(f"Erfolgreich unter {path}/{name} gespeichert.")
        time.sleep(.5)
        break


def show_system_information():
    """
    Printed Systeminformationen
    :return: Dictionary - Systeminfo
    """

    cls()

    sys_info = get_pc_information()

    print("Angemeldeter User:               ", sys_info["current_user"])
    print("Anzahl laufender Prozesse:       ", len(psutil.pids()))
    print("Hostname:                        ", sys_info["hostname"])
    print("IP-Adresse:                      ", sys_info["ip_address"])
    print("Anzahl physischer Kerne:         ", sys_info["cpu_p"])
    print("Anzahl logischer Kerne:          ", sys_info["cpu_l"])
    print("Verbauter Prozessor:             ", sys_info["processor"])
    print("Installiertes Betriebssystem:    ", sys_info["os"])
    print("Laufwerke:                       ", ", ".join(sys_info["drives"]))
    print("Verbauter Arbeitsspeicher:       ", sys_info["memory"], "GiB")
    print()

    return sys_info


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


def cls():
    os.system("cls")


if __name__ == '__main__':
    get_mail_addresses()
