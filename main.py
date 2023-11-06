#!/usr/bin/python3

import sys
import os
import time
import subprocess
from datetime import datetime
from configparser import ConfigParser

import influxdb_client
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS


def dbWriteTag(measurement, tag, tagvalue, field, value):
    point = (
        Point(measurement)
        .tag(tag, tagvalue)
        .field(field, value)
    )
    write_api.write(bucket=bucket, org=org, record=point)

def dbWrite(measurement, field, value):
    point = (
        Point(measurement)
        .field(field, value)
    )
    write_api.write(bucket=bucket, org=org, record=point)


def df(args):
    try:
        cmd = ['df']
        for item in args:
            cmd.append(item)

        result = subprocess.run(cmd, stdout=subprocess.PIPE, encoding='utf-8')
        row = 0
        k = result.stdout.split('\n')
        for item in k:
            if row > 0:
                item = item.split()
                #print(item)
                if len(item) > 0:
                    dbWriteTag("drive", "mountpoint", item[5], "size", int(item[1]) * 1000)
                    dbWriteTag("drive", "mountpoint", item[5], "free", int(item[3]) * 1000)
                    dbWriteTag("drive", "mountpoint", item[5], "used", int(item[2]) * 1000)
            row = row + 1

    except IOError:
        print("Error: df")

def uptime():
    f = open("/proc/uptime", "r")
    k = f.readline()
    f.close()

    k = k.strip().split()
    dbWrite("uptime", "uptime", int(k[0].split('.')[0]))
    dbWrite("uptime", "idle", int(k[1].split('.')[0]))
    dbWrite("uptime", "days", float(k[0].split('.')[0]) / (24 * 3600))

def loadavg():
    f = open("/proc/loadavg", "r")
    k = f.readline()
    f.close()

    k = k.strip().split()
    dbWrite("loadavg", "min1", float(k[0]))
    dbWrite("loadavg", "min5", float(k[1]))
    dbWrite("loadavg", "min15", float(k[2]))

def entropy():
    f = open("/proc/sys/kernel/random/entropy_avail", "r")
    v = f.readline()
    f.close()
    v = int(v.strip())
    dbWrite("common", "entropy", v)


def smart(drv):
    cmd = ['smartctl', '-a', drv]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, encoding='utf-8')
    k = result.stdout.split('\n')
    rec = False
    for line in k:
        item = line.split()
        if 'Device Model:' in line:
            model = item[-1]
        if 'Serial Number:' in line:
            sn = item[-1]
        if 'ID#' in line:
            rec = True
            continue
        if len(item) == 0:
            rec = False
        if rec:
            #print(item)
            if len(item) > 0:
                c = item[-1]
                if '/' in c:
                    c = item[-3]
                point = (
                    Point("smart")
                    .tag("model", model + " " + sn)
                    .tag("device", drv)
                    .field(item[1], int(c))
                )
                write_api.write(bucket=bucket, org=org, record=point)

                if 'Temperature' in line:
                    c = item[-1]
                    if '/' in c:
                        c = item[-3]
                    point = (
                        Point("hddtemp")
                        .tag("model", model + " " + sn)
                        .tag("device", drv)
                        .field("temp", int(c))
                    )
                    write_api.write(bucket=bucket, org=org, record=point)

                if 'Total_LBAs_Written' in line:
                    c = 512 * int(item[-1])
                    point = (
                        Point("ssd")
                        .tag("model", model + " " + sn)
                        .tag("device", drv)
                        .field("tbw", c)
                    )
                    write_api.write(bucket=bucket, org=org, record=point)


def cputemp():
    result = subprocess.run(['sensors'], stdout=subprocess.PIPE, encoding='utf-8')
    k = result.stdout.split('\n')
    for line in k:
        item = line.split()
        #print(item)
        if 'Package' in line:
            dbWriteTag("temperature", "device", "cpu", "package", int(item[3].split('.')[0]))
        if 'Core' in line:
            dbWriteTag("temperature", "device", "cpu", "cpu"+item[1].split(':')[0], int(item[2].split('.')[0]))

def apc():
    result = subprocess.run(['apcaccess'], stdout=subprocess.PIPE, encoding='utf-8')
    k = result.stdout.split('\n')
    z = {}
    for line in k:
        if ":" in line:
            item = line.split(":")
            item[0] = item[0].strip()
            item[1] = item[1].strip()
            z[item[0]] = item[1]

    if "STATUS" in z:
        dbWrite("ups", "status", z["STATUS"])
    if "LINEV" in z:
        v = float(z["LINEV"].split()[0])
        dbWrite("ups", "linev", v)
    if "OUTPUTV" in z:
        v = float(z["OUTPUTV"].split()[0])
        dbWrite("ups", "outputv", v)
    if "LOADPCT" in z:
        v = float(z["LOADPCT"].split()[0])
        dbWrite("ups", "load", v)
    if "BCHARGE" in z:
        v = float(z["BCHARGE"].split()[0])
        dbWrite("ups", "bcharge", v)
    if "BATTV" in z:
        v = float(z["BATTV"].split()[0])
        dbWrite("ups", "battv", v)
    if "LINEFREQ" in z:
        v = float(z["LINEFREQ"].split()[0])
        dbWrite("ups", "linefreq", v)
    if "ITEMP" in z:
        v = float(z["ITEMP"].split()[0])
        dbWrite("ups", "itemp", v)
    if "TIMELEFT" in z:
        v = float(z["TIMELEFT"].split()[0])
        dbWrite("ups", "timeleft", v)
    if "HITRANS" in z:
        v = float(z["HITRANS"].split()[0])
        dbWrite("ups", "hitrans", v)
    if "LOTRANS" in z:
        v = float(z["LOTRANS"].split()[0])
        dbWrite("ups", "lotrans", v)

    #print(z)

def meminfo():
    f = open("/proc/meminfo", "r")
    z = {}
    for line in f:
        if ":" in line:
            item = line.split(":")
            item[0] = item[0].strip()
            item[1] = item[1].strip()
            if 'kB' in item[1]:
                item[1] = item[1].split()[0]
            z[item[0]] = item[1]
    f.close()


    #print(z)
    values = ["MemTotal", "MemFree", "MemAvailable", "Buffers", "Cached", "SwapTotal", "SwapFree"]
    for item in values:
        if item in z:
            v = int(z[item].split()[0]) * 1024
            dbWrite("mem", item, v)


def cpufreq():
    f = open("/proc/cpuinfo", "r")
    z = []
    for line in f:
        if "cpu MHz" in line:
            line = line.strip()
            v = line.split(":")
            v = float(v[1].strip())
            z.append(v)
    f.close()
    for i in range(len(z)):
        dbWrite("cpufreq", f"core{i}", z[i])





def net(args):
    f = open("/proc/net/dev", "r")
    for line in f:
        line = line.strip()
        while '  ' in line:
            line = line.replace('  ', ' ')
        item = line.split()

        if len(item) > 0:
            if item[0][-1] == ":":
                item[0] = item[0][:-1]
            if item[0] in args:
                dbWriteTag("net", "device", item[0], "rx", int(item[1]))
                dbWriteTag("net", "device", item[0], "tx", int(item[8]))
    f.close()


if __name__ == '__main__':
    # Ищем файл конфигурации
    if os.path.isfile("grafomon.conf"):
        conff = "grafomon.conf"
    elif os.path.isfile("./grafomon.conf"):
        conff = "./grafomon.conf"
    elif os.path.isfile("/etc/grafomon.conf"):
        conff = "/etc/grafomon.conf"
    else:
        print("Файл конфигурации не найден.")
        sys.exit()

    config = ConfigParser()
    config.read(conff)

    url = config.get("DB", "URL")
    token = config.get("DB", "TOKEN")
    org = config.get("DB", "ORG")
    bucket = config.get("DB", "BUCKET")
    interval = config.getint("COMMON", "INTERVAL")

    write_client = influxdb_client.InfluxDBClient(url=url, token=token, org=org)
    write_api = write_client.write_api(write_options=SYNCHRONOUS)

    uptime()
    loadavg()

    drives = config.get("DRIVES", "MOUNTPOINTS")
    drives = drives.split(",")
    for i in range(len(drives)):
        drives[i] = drives[i].strip()
    df(drives)

    entropy()
    cputemp()
    apc()
    meminfo()
    cpufreq()

    ifaces = config.get("NET", "IFACES")
    ifaces = ifaces.split(",")
    for i in range(len(ifaces)):
        ifaces[i] = ifaces[i].strip()
    net(ifaces)

    #if len(sys.argv) > 1:
    now = datetime.now()
    time_m = int(now.strftime("%M"))
    if (time_m >= 59) or (time_m <= 2):
        drv = config.get("SMART", "DEVICES")
        drv = drv.split(",")
        for i in range(len(drv)):
            drv[i] = drv[i].strip()
        for w in drv:
            smart(w)

    # kernelUsage

    cpulist = []
    u0 = []
    n0 = []
    s0 = []
    i0 = []
    u1 = []
    n1 = []
    s1 = []
    i1 = []

    f = open("/proc/stat", "r")
    for line in f:
        if "cpu" in line:
            line = line.strip()
            while "  " in line:
                line = line.replace("  ", " ")
            v = line.split()

            cpulist.append(v[0])
            u0.append(int(v[1]))
            n0.append(int(v[2]))
            s0.append(int(v[3]))
            i0.append(int(v[4]))
    f.close()

    time.sleep(interval)

    f = open("/proc/stat", "r")
    for line in f:
        if "cpu" in line:
            line = line.strip()
            while "  " in line:
                line = line.replace("  ", " ")
            v = line.split()

            u1.append(int(v[1]))
            n1.append(int(v[2]))
            s1.append(int(v[3]))
            i1.append(int(v[4]))
    f.close()

    for i in range(len(cpulist)):
        ud = u1[i] - u0[i]
        nd = n1[i] - n0[i]
        sd = s1[i] - s0[i]
        id = i1[i] - i0[i]

        total = ud + nd + sd + id
        if total != 0:
            avg_load = 100 * (ud + nd + sd) / total
            avg_load = round(avg_load, 3)
        else:
            avg_load = 0

        dbWrite("kernelusage", cpulist[i], avg_load)
