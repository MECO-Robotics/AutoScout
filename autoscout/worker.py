"""GPU worker queue, started by the app; runs one analysis per configured GPU."""
import fcntl
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from .automatic import VERSION
from .store import now


class Worker:
    def __init__(self,store):
        self.store=store;self.stop=threading.Event();self.children={}
        devices=os.environ.get('AUTOSCOUT_GPU_DEVICES','0').split(',')
        # The detector and video decoder each hold large CPU/GPU buffers.  A
        # second process on this host exhausts RAM (and the P600 has only 2GB),
        # so queue work serially even if multiple devices are configured.
        self.devices=[d.strip() for d in devices if d.strip()][:1]
        self.max_attempts=max(1,int(os.environ.get('AUTOSCOUT_MAX_ATTEMPTS','3')))
    def start(self):
        self.thread=threading.Thread(target=self.loop,daemon=True,name='automatic-scouting');self.thread.start()
    def close(self):
        self.stop.set()
        for child in self.children.values():
            if child.poll() is None: child.terminate()
        self.thread.join(timeout=5)
    def loop(self):
        if os.environ.get('AUTOSCOUT_AUTOMATIC','1')=='0':
            self.store.put_config('automatic_queue',{'status':'paused','reason':'Automatic processing temporarily paused','updated_at':now()});return
        if not (self.store.root/'models/frc9550/model.pt').is_file():return
        logdir=self.store.root/'automatic';logdir.mkdir(exist_ok=True)
        with (logdir/'worker.lock').open('w') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return
            # A previous server may have terminated during a run; retry once per startup.
            for m in self.store.matches():
                if m.get('automatic',{}).get('status')=='running':
                    m['automatic']['status']='interrupted';self.store.put_match(m)
            while not self.stop.is_set():
                # This queue is intentionally serialized.  Do not launch a
                # replacement until the current child has exited and has
                # been reaped below.
                if self.children:
                    self.stop.wait(1)
                    for key, child in list(self.children.items()):
                        if child.poll() is not None:
                            self.children.pop(key, None)
                    continue
                candidates=[m for m in self.store.matches() if self.store.video_path(m) and m['key'] not in self.children and not (m.get('automatic',{}).get('version')==VERSION and m.get('automatic',{}).get('status')=='complete') and (m.get('automatic',{}).get('attempts',0) < self.max_attempts)]
                if not candidates and not self.children:
                    self.store.put_config('automatic_queue',{'status':'idle','reason':'All available matches processed','updated_at':now()});self.stop.wait(5);continue
                free=shutil.disk_usage(self.store.root).free
                if free<750*1024**2:
                    self.store.put_config('automatic_queue',{'status':'paused','reason':'Low disk space: free at least 750 MiB to resume automatically','free_bytes':free,'updated_at':now()});self.stop.wait(30);continue
                self.store.put_config('automatic_queue',{'status':'running','reason':'Processing matches automatically','free_bytes':free,'updated_at':now()})
                for device,m in zip(self.devices[:1],candidates[:1]):
                    key=m['key']; previous=m.get('automatic',{});m['automatic']={'report':previous.get('report'),'version':VERSION,'status':'running','progress':0,'started_at':now(),'gpu_device':device,'attempts':previous.get('attempts',0)+1};self.store.put_match(m)
                    env={**os.environ,'AUTOSCOUT_DATA_DIR':str(self.store.root),'AUTOSCOUT_GPU_DEVICE':device}
                    log=(logdir/f'{key}.log').open('a')
                    self.children[key]=subprocess.Popen([sys.executable,'-m','autoscout.automatic',key],stdout=log,stderr=subprocess.STDOUT,env=env)
                    log.close()
                for key,child in list(self.children.items()):
                    if child.poll() is None: continue
                    code=child.wait();self.children.pop(key,None)
                    if code!=0:
                        current=self.store.match(key)
                        automatic=current.setdefault('automatic',{})
                        automatic.update(version=VERSION,status='interrupted' if self.stop.is_set() else ('queued' if automatic.get('attempts',0) < self.max_attempts else 'failed'),error=automatic.get('error') or 'Worker stopped. Partial evidence retained.')
                        self.store.put_match(current)
                self.stop.wait(1)
