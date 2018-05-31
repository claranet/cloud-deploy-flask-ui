# -*- coding: utf-8 -*-

"""Library to easily manage Host Health"""

from __future__ import division
import psutil
import threading
import time

COLOR_GREEN = '#4caf50'
COLOR_ORANGE = '#ff5722'
COLOR_RED = '#f44336'

CPU_THRESHOLD_WARNING = 70
CPU_THRESHOLD_DANGER = 85

duplex_map = {
    psutil.NIC_DUPLEX_FULL: "full",
    psutil.NIC_DUPLEX_HALF: "half",
    psutil.NIC_DUPLEX_UNKNOWN: "?",
}


def get_host_health(cpu_percent, cpu_percent_details):
    status = {}
    cpu = {}
    cpu['percent'] = cpu_percent
    cpu['percpu'] = cpu_percent_details
    cpu['color'] = COLOR_GREEN
    if cpu_percent > CPU_THRESHOLD_WARNING:
        cpu['color'] = COLOR_ORANGE
    if cpu_percent > CPU_THRESHOLD_DANGER:
        cpu['color'] = COLOR_RED
    cpu['label'] = get_host_cpu_label(cpu_percent)
    status['cpu'] = cpu

    ram = {}
    r_total, r_avail, r_percent, r_used, r_free, r_active, r_inactive, r_buffers, r_cached, r_shared, r_slab = psutil.virtual_memory()
    ram['total'] = r_total / 1024 / 1024 / 1024
    ram['available'] = r_avail / 1024 / 1024 / 1024
    ram['free'] = r_free / 1024 / 1024 / 1024
    ram['used'] = r_used / 1024 / 1024 / 1024
    ram['percent'] = r_percent
    ram['color'] = COLOR_GREEN
    if r_percent > 70:
        ram['color'] = COLOR_ORANGE
    if r_percent > 85:
        ram['color'] = COLOR_RED
    status['ram'] = ram

    disk = {}
    d_total, d_used, d_free, d_percent = psutil.disk_usage('/')
    disk['total'] = d_total / 1024 / 1024 / 1024
    disk['used'] = d_used / 1024 / 1024 / 1024
    disk['free'] = d_free / 1024 / 1024 / 1024
    disk['percent'] = d_percent
    disk['color'] = COLOR_GREEN
    if d_percent > 70:
        disk['color'] = COLOR_ORANGE
    if d_percent > 85:
        disk['color'] = COLOR_RED
    status['disk'] = disk

    status['boot_time'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(psutil.boot_time()))

    status['network_stats'] = psutil.net_if_stats()
    for (key, item) in status['network_stats'].items():
        status['network_stats'][key] = status['network_stats'][key]._replace(duplex=duplex_map[item.duplex])
    status['network_io'] = psutil.net_io_counters(pernic=True)

    return status


def get_host_cpu_label(cpu_percent):
    status = 'success'
    if cpu_percent > CPU_THRESHOLD_WARNING:
        status = 'warning'
    if cpu_percent > CPU_THRESHOLD_DANGER:
        status = 'danger'
    return status


class HostHealth:
    percent = 'N/A'
    percent_details = 'N/A'
    thread = None
    pool_time = 5
    interval = 2

    def __init__(self, pool_time, interval):
        self.pool_time = pool_time
        self.interval = interval

    def start(self):
        self.thread = threading.Timer(self.pool_time, self.update_stats)
        self.thread.start()

    def update_stats(self):
        self.percent = psutil.cpu_percent(interval=self.interval)
        self.percent_details = psutil.cpu_percent(interval=self.interval, percpu=True)
        self.start()

    def get_stats(self):
        return self.percent, self.percent_details
