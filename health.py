#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Library to easily manage Host Health"""

from __future__ import division
import psutil
import time

COLOR_GREEN = '#4caf50'
COLOR_ORANGE = '#ff5722'
COLOR_RED = '#f44336'

def get_host_health(cpu_percent, cpu_percent_details):
    status = {}
    cpu = {}
    cpu['percent'] = cpu_percent
    cpu['percpu'] = cpu_percent_details
    cpu['color'] = COLOR_GREEN
    if cpu_percent > 60:
        cpu['color'] = COLOR_ORANGE
    if cpu_percent > 80:
        cpu['color'] = COLOR_RED
    status['cpu'] = cpu

    ram = {}
    r_total, r_avail, r_percent, r_used, r_free, r_active, r_inactive, r_buffers, r_cached, r_shared = psutil.virtual_memory()
    ram['total'] = r_total / 1024 / 1024 / 1024
    ram['available'] = r_avail / 1024 / 1024 / 1024
    ram['free'] = r_free / 1024 / 1024 / 1024
    ram['used'] = r_used / 1024 / 1024 / 1024
    ram['percent'] = r_percent
    ram['color'] = COLOR_GREEN
    if r_percent < 30:
        ram['color'] = COLOR_ORANGE
    if r_percent < 15:
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

    status ['network'] = psutil.net_io_counters(pernic=True)

    return status;

def get_host_cpu_label(cpu_percent):
    status = 'success'
    if cpu_percent > 70:
        status = 'warning'
    if cpu_percent > 85:
        status = 'danger'
    return status;
