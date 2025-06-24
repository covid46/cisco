import pymysql
import re
import glob
from datetime import datetime

# Koneksi ke MySQL
try:
    db = pymysql.connect(host="localhost", user="root", password="", database="cisco_monitor")
    cursor = db.cursor()
except pymysql.MySQLError as e:
    print(f"Error connecting to MySQL: {e}")
    exit(1)

# Pola regex untuk MAC flapping
mac_flap_pattern = re.compile(r"%SW_MATM-4-MACFLAP_NOTIF: Host ([\dA-F:]+) in vlan (\d+) is flapping between port (\S+) and port (\S+)")

# Ambil semua file syslog.log dari direktori /var/log/cisco/*/syslog.log
log_files = glob.glob("/var/log/cisco/*/syslog.log")

if not log_files:
    print("No syslog files found in /var/log/cisco/*/syslog.log")
    db.close()
    exit(1)

# Hostname yang tidak diizinkan (misalnya log sistem Ubuntu)
excluded_hostnames = ["ubuntu20"]

# Loop melalui setiap file syslog
for file_path in log_files:
    hostname = file_path.split("/")[-2]  # contoh: main1.hwi.it

    if hostname in excluded_hostnames:
        print(f"Skipping file for hostname {hostname} (in excluded list)")
        continue

    print(f"Processing file: {file_path} (Hostname: {hostname})")

    try:
        with open(file_path, "r") as file:
            for line in file:
                timestamp = None

                # Cek apakah ISO 8601
                iso_match = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2})?)", line)
                if iso_match:
                    try:
                        timestamp = datetime.fromisoformat(iso_match.group(1).replace("Z", "+00:00"))
                    except ValueError as e:
                        print(f"Error parsing ISO timestamp: {e} | line: {line.strip()}")
                        continue
                else:
                    # Cek apakah format syslog lama
                    legacy_match = re.match(r"(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})", line)
                    if legacy_match:
                        timestamp_str = f"{legacy_match.group(1)} {datetime.now().year}"
                        try:
                            timestamp = datetime.strptime(timestamp_str, "%b %d %H:%M:%S %Y")
                        except ValueError as e:
                            print(f"Error parsing legacy timestamp: {e} | line: {line.strip()}")
                            continue

                if not timestamp:
                    print(f"Could not parse timestamp in line: {line.strip()}")
                    continue

                # Cek apakah log adalah MAC flapping
                mac_flap_match = mac_flap_pattern.search(line)
                if mac_flap_match:
                    mac_address, vlan, port1, port2 = mac_flap_match.groups()
                    print(f"Found MAC flap: {mac_address} VLAN: {vlan} Ports: {port1}, {port2}")
                    try:
                        sql_mac_flap = "INSERT INTO mac_flap_logs (hostname, mac_address, vlan, port1, port2, timestamp) VALUES (%s, %s, %s, %s, %s, %s)"
                        cursor.execute(sql_mac_flap, (hostname, mac_address, vlan, port1, port2, timestamp))
                    except pymysql.MySQLError as e:
                        if e.args[0] == 1062:
                            print(f"Duplicate MAC flap log skipped: {line.strip()}")
                        else:
                            print(f"Error inserting into mac_flap_logs: {e} | line: {line.strip()}")
                    continue

                # Jika bukan MAC flap, masukkan sebagai syslog biasa
                message = line.strip()
                try:
                    sql_syslog = "INSERT INTO syslogs (hostname, timestamp, message, message_hash) VALUES (%s, %s, %s, SHA2(%s, 256))"
                    cursor.execute(sql_syslog, (hostname, timestamp, message, message))
                except pymysql.MySQLError as e:
                    if e.args[0] == 1062:
                        print(f"Duplicate syslog skipped: {line.strip()}")
                    else:
                        print(f"Error inserting into syslogs: {e} | line: {line.strip()}")

    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")

# Commit ke database
try:
    db.commit()
    print("Data successfully inserted into database")
except pymysql.MySQLError as e:
    print(f"Error committing changes: {e}")
    db.rollback()

cursor.close()
db.close()
