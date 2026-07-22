import os
import sys
os.environ['PATH'] = r'C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem;C:\Windows\System32\WindowsPowerShell\v1.0'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iOS Mirror Capture (CustomTkinter Version)
"""

import json
import subprocess
import threading
import queue
import time
import tempfile
import shutil
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

try:
    import win32gui
    import win32process
    import win32clipboard
    HAVE_PYWIN32 = True
except ImportError:
    HAVE_PYWIN32 = False

# Hides the console window for spawned subprocesses
CREATE_NO_WINDOW = 0x08000000

def copy_bmp_to_clipboard(filepath):
    if not HAVE_PYWIN32:
        return
    try:
        with open(filepath, 'rb') as f:
            data = f.read()[14:]
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()
    except Exception as e:
        print('Clipboard error:', e)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mirror_capture_config.json")

DEFAULT_CONFIG = {
    "uxplay_path": "",
    "ffmpeg_path": "",
    "device_name": "iOSMirror",
    "resolution": "1920x1080",
    "window_title": "iOSMirror",
    "output_dir": os.path.join(os.path.expanduser("~"), "Videos", "iOSMirrorCaptures"),
}

def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
            
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    bin_dir = os.path.join(base_dir, "bin")
    
    if not cfg.get("uxplay_path") or not os.path.exists(cfg["uxplay_path"]):
        bundled_ux = os.path.join(bin_dir, "uxplay.exe")
        if os.path.exists(bundled_ux):
            cfg["uxplay_path"] = bundled_ux
            
    if not cfg.get("ffmpeg_path") or not os.path.exists(cfg["ffmpeg_path"]):
        bundled_ff = os.path.join(bin_dir, "ffmpeg.exe")
        if os.path.exists(bundled_ff):
            cfg["ffmpeg_path"] = bundled_ff
            
    return cfg

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def list_window_titles():
    titles = []
    def _enum(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title.strip():
                titles.append(title)
    win32gui.EnumWindows(_enum, None)
    seen = set()
    result = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result

class FloatingToolbar(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        
        self.configure(fg_color="#2b2b2b")
        self.geometry("100x90")
        
        # We must keep a reference to stop tracking
        self._tracking = True
        
        self.btn_cap = ctk.CTkButton(self, text='📷 캡처', command=self.app.take_screenshot, 
                                     width=80, height=35, fg_color="#3a7ebf", hover_color="#2a5e8f")
        self.btn_cap.pack(pady=(10, 5), padx=10)
        
        self.btn_rec = ctk.CTkButton(self, text='⏺ 녹화', command=self.app.toggle_recording, 
                                     width=80, height=35, fg_color="#bf3a3a", hover_color="#8f2a2a")
        self.btn_rec.pack(pady=(0, 10), padx=10)
        
        self._poll_position()
        
    def _poll_position(self):
        if not self._tracking: return
        try:
            target_title = self.app.name_var.get().strip() or 'iOSMirror'
            candidates = [target_title, 'Direct3D12 renderer', 'Direct3D11 renderer', 'Direct3D12 Renderer', 'Direct3D11 Renderer', 'Direct3D renderer', 'Direct3D Renderer']
            hwnd = 0
            for title in candidates:
                hwnd = win32gui.FindWindow(None, title)
                if hwnd: break
            
            if hwnd:
                rect = win32gui.GetWindowRect(hwnd)
                x = rect[2]
                y = rect[1] + 30
                self.geometry(f'+{x}+{y}')
                
                actual_title = win32gui.GetWindowText(hwnd)
                if self.app.title_var.get() != actual_title:
                    self.app.title_var.set(actual_title)
        except Exception:
            pass
        self.after(200, self._poll_position)
        
    def close(self):
        self._tracking = False
        self.destroy()

class MirrorCaptureApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        
        self.title("iOS Mirror Capture")
        self.geometry("760x650")

        self.cfg = load_config()

        self.uxplay_proc = None
        self.record_proc = None
        self.log_queue = queue.Queue()

        self.recording = False
        self.record_start_time = None
        self.toolbar = None

        self._build_ui()
        self._poll_log_queue()
        self._tick_timer()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        pad = {"padx": 10, "pady": 10}

        # ------------------------------------------------------------- Settings
        settings = ctk.CTkFrame(self)
        settings.pack(fill="x", **pad)
        
        ctk.CTkLabel(settings, text="기본 설정", font=ctk.CTkFont(size=14, weight="normal")).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 5))

        self.uxplay_var = tk.StringVar(value=self.cfg["uxplay_path"])
        self.ffmpeg_var = tk.StringVar(value=self.cfg["ffmpeg_path"])
        self.name_var = tk.StringVar(value=self.cfg["device_name"])
        self.res_var = tk.StringVar(value=self.cfg["resolution"])
        self.outdir_var = tk.StringVar(value=self.cfg["output_dir"])
        self.title_var = tk.StringVar(value=self.cfg["window_title"])

        self._row_path(settings, 1, "uxplay.exe 경로", self.uxplay_var, self._browse_uxplay)
        self._row_path(settings, 2, "ffmpeg.exe 경로", self.ffmpeg_var, self._browse_ffmpeg)

        row = ctk.CTkFrame(settings, fg_color="transparent")
        row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=10, pady=5)
        
        ctk.CTkLabel(row, text="기기 이름").pack(side="left", padx=(0, 5))
        ctk.CTkEntry(row, textvariable=self.name_var, width=150).pack(side="left", padx=5)
        
        ctk.CTkLabel(row, text="해상도").pack(side="left", padx=(20, 5))
        ctk.CTkEntry(row, textvariable=self.res_var, width=100).pack(side="left", padx=5)

        self._row_path(settings, 4, "저장 폴더", self.outdir_var, self._browse_outdir, is_dir=True)

        settings.columnconfigure(1, weight=1)

        # ------------------------------------------------- mirroring controls
        mirror = ctk.CTkFrame(self)
        mirror.pack(fill="x", **pad)
        
        ctk.CTkLabel(mirror, text="미러링 (AirPlay 수신)", font=ctk.CTkFont(size=14, weight="normal")).pack(anchor="w", padx=10, pady=(10, 5))

        btn_row = ctk.CTkFrame(mirror, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 10))
        
        self.btn_start_mirror = ctk.CTkButton(btn_row, text="▶ 미러링 시작", command=self.start_mirroring, fg_color="#28a745", hover_color="#218838")
        self.btn_start_mirror.pack(side="left", padx=(0, 5))
        
        self.btn_stop_mirror = ctk.CTkButton(btn_row, text="■ 미러링 중지", command=self.stop_mirroring, state="disabled", fg_color="#dc3545", hover_color="#c82333")
        self.btn_stop_mirror.pack(side="left", padx=5)
        
        self.mirror_status = ctk.CTkLabel(btn_row, text="상태: 꺼짐", text_color="#aaaaaa")
        self.mirror_status.pack(side="left", padx=15)

        ctk.CTkLabel(mirror, text="iPhone/iPad에서 제어센터 > 화면 미러링에서 위 기기 이름을 선택하세요.",
                     text_color="#888888", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=10, pady=(0, 10))

        # ------------------------------------------------- capture controls
        capture = ctk.CTkFrame(self)
        capture.pack(fill="x", **pad)
        
        ctk.CTkLabel(capture, text="캡처 (스크린샷 / 녹화)", font=ctk.CTkFont(size=14, weight="normal")).pack(anchor="w", padx=10, pady=(10, 5))

        win_row = ctk.CTkFrame(capture, fg_color="transparent")
        win_row.pack(fill="x", padx=10, pady=(0, 5))
        
        ctk.CTkLabel(win_row, text="대상 창 제목").pack(side="left", padx=(0, 10))
        
        # Combobox replacement in CustomTkinter
        self.window_combo = ctk.CTkComboBox(win_row, variable=self.title_var, width=250)
        self.window_combo.pack(side="left", padx=5)
        
        ctk.CTkButton(win_row, text="창 목록 새로고침", command=self.refresh_windows, width=120).pack(side="left", padx=5)
        
        if not HAVE_PYWIN32:
            ctk.CTkLabel(win_row, text="(pywin32 미설치: 제목을 직접 입력하세요)", text_color="#ff5555").pack(side="left", padx=10)

        cap_btn_row = ctk.CTkFrame(capture, fg_color="transparent")
        cap_btn_row.pack(fill="x", padx=10, pady=(5, 10))
        
        ctk.CTkButton(cap_btn_row, text="📷 스크린샷", command=self.take_screenshot, fg_color="#17a2b8", hover_color="#138496").pack(side="left", padx=(0, 5))
        self.btn_record = ctk.CTkButton(cap_btn_row, text="⏺ 녹화 시작", command=self.toggle_recording, fg_color="#dc3545", hover_color="#c82333")
        self.btn_record.pack(side="left", padx=5)
        
        self.record_status = ctk.CTkLabel(cap_btn_row, text="", text_color="#ffaaaa")
        self.record_status.pack(side="left", padx=15)
        
        ctk.CTkButton(cap_btn_row, text="저장 폴더 열기", command=self.open_output_dir, fg_color="#6c757d", hover_color="#5a6268").pack(side="right")

        # ------------------------------------------------------------- log
        log_frame = ctk.CTkFrame(self)
        log_frame.pack(fill="both", expand=True, **pad)
        
        self.log_text = ctk.CTkTextbox(log_frame, wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text.configure(state="disabled")

        self.refresh_windows()

    def _row_path(self, parent, r, label, var, browse_cmd, is_dir=False):
        ctk.CTkLabel(parent, text=label).grid(row=r, column=0, sticky="w", padx=10, pady=5)
        ctk.CTkEntry(parent, textvariable=var).grid(row=r, column=1, sticky="ew", padx=5, pady=5)
        ctk.CTkButton(parent, text="찾아보기", command=browse_cmd, width=80).grid(row=r, column=2, padx=10, pady=5)

    def _browse_uxplay(self):
        path = filedialog.askopenfilename(title="uxplay.exe 선택", filetypes=[("Executable", "*.exe")])
        if path:
            self.uxplay_var.set(path)

    def _browse_ffmpeg(self):
        path = filedialog.askopenfilename(title="ffmpeg.exe 선택", filetypes=[("Executable", "*.exe")])
        if path:
            self.ffmpeg_var.set(path)

    def _browse_outdir(self):
        path = filedialog.askdirectory(title="저장 폴더 선택")
        if path:
            self.outdir_var.set(path)

    def open_output_dir(self):
        d = self.outdir_var.get().strip()
        os.makedirs(d, exist_ok=True)
        os.startfile(d)

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{ts}] {msg}")

    def _poll_log_queue(self):
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.after(200, self._poll_log_queue)

    def refresh_windows(self):
        if not HAVE_PYWIN32:
            return
        try:
            titles = list_window_titles()
            self.window_combo.configure(values=titles)
        except Exception as e:
            self.log(f"창 목록을 가져오지 못했습니다: {e}")

    def start_mirroring(self):
        uxplay = self.uxplay_var.get().strip()
        if not uxplay or not os.path.exists(uxplay):
            messagebox.showerror("오류", "uxplay.exe 경로를 먼저 지정하세요.")
            return
        if self.uxplay_proc is not None:
            messagebox.showinfo("안내", "이미 미러링이 실행 중입니다.")
            return

        name = self.name_var.get().strip() or "iOSMirror"
        res = self.res_var.get().strip() or "1920x1080"
        cmd = [uxplay, "-n", name, "-nh", "-s", res]

        self.log(f"미러링 시작: {' '.join(cmd)}")
        
        env = os.environ.copy()
        gst_plugins_dir = os.path.join(os.path.dirname(uxplay), "gstreamer-plugins")
        if os.path.exists(gst_plugins_dir):
            env["GST_PLUGIN_SYSTEM_PATH"] = gst_plugins_dir
            env["GST_PLUGIN_PATH"] = gst_plugins_dir

        try:
            self.uxplay_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW,
                text=True,
                bufsize=1,
                env=env,
            )
        except Exception as e:
            messagebox.showerror("오류", f"uxplay 실행 실패: {e}")
            self.uxplay_proc = None
            return

        threading.Thread(target=self._read_proc_output, args=(self.uxplay_proc, "uxplay"), daemon=True).start()

        self.btn_start_mirror.configure(state="disabled")
        self.btn_stop_mirror.configure(state="normal")
        self.mirror_status.configure(text="상태: 켜짐 (iPhone에서 기기를 선택하세요)", text_color="#28a745")

        if not self.title_var.get().strip():
            self.title_var.set(name)
            
        if HAVE_PYWIN32:
            self.toolbar = FloatingToolbar(self)

    def stop_mirroring(self):
        if self.uxplay_proc is None:
            return
        self.log("미러링 중지 중...")
        self._kill_process_tree(self.uxplay_proc)
        self.uxplay_proc = None
        if self.toolbar:
            self.toolbar.close()
            self.toolbar = None
        self.btn_start_mirror.configure(state="normal")
        self.btn_stop_mirror.configure(state="disabled")
        self.mirror_status.configure(text="상태: 꺼짐", text_color="#aaaaaa")

    def _read_proc_output(self, proc, tag):
        try:
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self.log(f"[{tag}] {line}")
        except Exception:
            pass

    def _kill_process_tree(self, proc):
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=CREATE_NO_WINDOW
                )
            else:
                proc.terminate()
        except Exception:
            pass

    def _ensure_output_dir(self):
        d = self.outdir_var.get().strip() or DEFAULT_CONFIG["output_dir"]
        os.makedirs(d, exist_ok=True)
        return d

    def take_screenshot(self):
        ffmpeg = self.ffmpeg_var.get().strip()
        title = self.title_var.get().strip()
        if not ffmpeg or not os.path.exists(ffmpeg):
            messagebox.showerror("오류", "ffmpeg.exe 경로를 먼저 지정하세요.")
            return
        if not title:
            messagebox.showerror("오류", "캡처할 창 제목을 지정하세요.")
            return

        outdir = self._ensure_output_dir()
        fname = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        outpath = os.path.join(outdir, fname)

        hwnd = win32gui.FindWindow(None, title)
        if not hwnd:
            messagebox.showerror("오류", "해당 제목의 창을 찾을 수 없습니다.")
            return
        rect = win32gui.GetClientRect(hwnd)
        pt = win32gui.ClientToScreen(hwnd, (0, 0))
        x, y = pt[0], pt[1]
        w, h = rect[2], rect[3]
        if w <= 0 or h <= 0: return

        temp_bmp = os.path.join(tempfile.gettempdir(), 'mirror_capture_temp.bmp')
        cmd = [ffmpeg, "-y", "-f", "gdigrab", "-offset_x", str(x), "-offset_y", str(y), "-video_size", f"{w}x{h}", "-i", "desktop", "-frames:v", "1", outpath, "-frames:v", "1", temp_bmp]
        self.log(f"스크린샷 캡처 중... (창: {title} 내부영역)")

        def _run():
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=CREATE_NO_WINDOW)
            if result.returncode == 0 and os.path.exists(outpath):
                self.log(f"스크린샷 저장됨: {outpath}")
                if os.path.exists(temp_bmp):
                    copy_bmp_to_clipboard(temp_bmp)
                    self.log("클립보드에 복사되었습니다.")
            else:
                self.log("스크린샷 실패. 창 제목이 정확한지 '창 목록 새로고침'으로 확인하세요.")
                self.log(result.stdout[-800:] if result.stdout else "(출력 없음)")

        threading.Thread(target=_run, daemon=True).start()

    def toggle_recording(self):
        if self.recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        ffmpeg = self.ffmpeg_var.get().strip()
        title = self.title_var.get().strip()
        if not ffmpeg or not os.path.exists(ffmpeg):
            messagebox.showerror("오류", "ffmpeg.exe 경로를 먼저 지정하세요.")
            return
        if not title:
            messagebox.showerror("오류", "캡처할 창 제목을 지정하세요.")
            return

        outdir = self._ensure_output_dir()
        fname = f"record_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        outpath = os.path.join(outdir, fname)
        self._last_record_path = outpath

        hwnd = win32gui.FindWindow(None, title)
        if not hwnd:
            messagebox.showerror("오류", "해당 제목의 창을 찾을 수 없습니다.")
            return
        rect = win32gui.GetClientRect(hwnd)
        pt = win32gui.ClientToScreen(hwnd, (0, 0))
        x, y = pt[0], pt[1]
        w, h = rect[2], rect[3]
        if w <= 0 or h <= 0: return
        
        w = w if w % 2 == 0 else w - 1
        h = h if h % 2 == 0 else h - 1

        cmd = [
            ffmpeg, "-y",
            "-f", "gdigrab", "-framerate", "30",
            "-offset_x", str(x), "-offset_y", str(y), "-video_size", f"{w}x{h}", "-i", "desktop",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            outpath,
        ]
        self.log(f"녹화 시작 (내부영역): {outpath}")
        try:
            self.record_proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, creationflags=CREATE_NO_WINDOW
            )
        except Exception as e:
            messagebox.showerror("오류", f"녹화 시작 실패: {e}")
            return

        threading.Thread(target=self._read_proc_output, args=(self.record_proc, "ffmpeg"), daemon=True).start()

        self.recording = True
        self.record_start_time = time.time()
        self.btn_record.configure(text="⏹ 녹화 중지")
        if self.toolbar:
            self.toolbar.btn_rec.configure(text="⏹ 녹화 중지", fg_color="#993333")

    def _stop_recording(self):
        if self.record_proc is None:
            self.recording = False
            return
        self.log("녹화 중지 중... (파일 마무리 처리)")
        try:
            self.record_proc.stdin.write("q")
            self.record_proc.stdin.flush()
        except Exception:
            pass

        def _wait_and_finish():
            try:
                self.record_proc.wait(timeout=10)
            except Exception:
                self._kill_process_tree(self.record_proc)
            
            saved_path = getattr(self, '_last_record_path', None)
            if saved_path and os.path.exists(saved_path):
                dest = filedialog.asksaveasfilename(
                    title="녹화 영상 저장",
                    defaultextension=".mp4",
                    filetypes=[("MP4 Video", "*.mp4"), ("All files", "*.*")],
                    initialfile=os.path.basename(saved_path),
                    initialdir=os.path.dirname(saved_path)
                )
                if dest:
                    try:
                        shutil.move(saved_path, dest)
                        self.log(f"녹화 저장됨: {dest}")
                    except Exception as e:
                        self.log(f"파일 이동 실패: {e}")
                else:
                    self.log(f"저장 취소됨. 임시 폴더에 유지: {saved_path}")

        threading.Thread(target=_wait_and_finish, daemon=True).start()

        self.record_proc = None
        self.recording = False
        self.record_start_time = None
        self.btn_record.configure(text="⏺ 녹화 시작")
        if self.toolbar:
            self.toolbar.btn_rec.configure(text="⏺ 녹화", fg_color="#bf3a3a")
        self.record_status.configure(text="")

    def _tick_timer(self):
        if self.recording and self.record_start_time:
            elapsed = int(time.time() - self.record_start_time)
            m, s = divmod(elapsed, 60)
            self.record_status.configure(text=f"녹화 중: {m:02d}:{s:02d}")
        self.after(500, self._tick_timer)

    def _on_close(self):
        self.cfg.update({
            "uxplay_path": self.uxplay_var.get().strip(),
            "ffmpeg_path": self.ffmpeg_var.get().strip(),
            "device_name": self.name_var.get().strip(),
            "resolution": self.res_var.get().strip(),
            "window_title": self.title_var.get().strip(),
            "output_dir": self.outdir_var.get().strip(),
        })
        save_config(self.cfg)

        if self.recording:
            self._stop_recording()
        if self.uxplay_proc is not None:
            self.stop_mirroring()

        self.destroy()

if __name__ == "__main__":
    app = MirrorCaptureApp()
    app.mainloop()
