# media/detector.py
import pyudev, subprocess, os, threading
from media.classifier import classify_usb

MOUNT_BASE = "/media/smarttv"

class USBDetector:
    def __init__(self, on_insert, on_remove):
        self.on_insert = on_insert
        self.on_remove = on_remove
        self.context = pyudev.Context()
        self.monitor = pyudev.Monitor.from_netlink(self.context)
        self.monitor.filter_by(subsystem='block', device_type='partition')

    def start(self):
        observer = pyudev.MonitorObserver(self.monitor, self._handle_event)
        observer.daemon = True
        observer.start()

    def _handle_event(self, action, device):
        if action == "add":
            devnode = device.device_node
            label = device.get('ID_FS_LABEL', 'usb')
            mount_point = f"{MOUNT_BASE}/{label}"
            os.makedirs(mount_point, exist_ok=True)
            subprocess.run(["udisksctl", "mount", "-b", devnode], check=True)
            content_type = classify_usb(mount_point)
            self.on_insert(mount_point, content_type)
        elif action == "remove":
            self.on_remove()