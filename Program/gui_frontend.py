# gui_frontend_v2.py — E-NOSE ZIZU ULTIMATE EDITION
# Fitur: Tab View (Cards, Combined Graph, Split Graphs), Auto Edge Impulse, Gnuplot Export

import sys, socket, csv, os, requests, json, subprocess
from datetime import datetime
from collections import deque
import pyqtgraph as pg
from PyQt6.QtWidgets import *
from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal as Signal, pyqtSlot as Slot, QTimer
from PyQt6.QtGui import QDesktopServices, QFont, QColor
from PyQt6.QtCore import QUrl

# ==================== CONFIG ====================
EI_API_KEY    = "ei_f57e7e7dc5f9cd0ac88d30bf5159acace5af25b67dbbd9ff" # Ganti dengan API Key Anda
EI_PROJECT_ID = "835258"

HOST_DATA, PORT_DATA = "0.0.0.0", 8080
HOST_CMD,  PORT_CMD  = "127.0.0.1", 8082
HISTORY = "sampling_history"
os.makedirs(HISTORY, exist_ok=True)

NAMES  = ["NO2_GM","C2H5OH_GM","VOC_GM","CO_GM","CO_MiCS","C2H5OH_MiCS","VOC_MiCS"]
COLORS = ['#ff0000', '#00ff00', '#0000ff', '#ffff00', '#ff00ff', '#00ffff', '#ffa500']

# ==================== CUSTOM WIDGETS ====================
class SensorCard(QFrame):
    """Widget Kartu untuk Tab Dashboard"""
    def __init__(self, title, color):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #2c3e50;
                border: 2px solid {color};
                border-radius: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 14pt;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_value = QLabel("0.00")
        self.lbl_value.setStyleSheet("color: white; font-weight: bold; font-size: 32pt;")
        self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)

    def update_val(self, val):
        self.lbl_value.setText(f"{val:.2f}")

# ==================== WORKER THREAD ====================
class Receiver(QObject):
    data = Signal(str)
    status = Signal(str)
    
    def run(self):
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((HOST_DATA, PORT_DATA))
            s.listen(5)
            self.status.emit("Menunggu Backend Rust...")
            while True:
                c, a = s.accept()
                self.status.emit(f"Connected: {a[0]}")
                with c.makefile('r') as f:
                    while True:
                        l = f.readline().strip()
                        if not l: break
                        if l.startswith("SENSOR:"):
                            self.data.emit(l)
        except Exception as e:
            self.status.emit(f"Error Socket: {e}")

# ==================== MAIN WINDOW ====================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("E-NOSE ZIZU 2025 — ULTIMATE MONITOR")
        self.setGeometry(50, 50, 1600, 900)
        pg.setConfigOptions(background='#1e1e1e', foreground='#f0f0f0', antialias=True)
        self.setStyleSheet("background:#1e1e1e;color:#f0f0f0;")

        # Data Logic
        self.sampling = False
        self.log = []
        self.time = deque(maxlen=2000)
        self.data_store = {n:deque(maxlen=2000) for n in NAMES}

        self.init_ui()
        self.start_worker()

    def init_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # === LEFT PANEL (CONTROLS) ===
        left_panel = QVBoxLayout()
        left_panel.setSpacing(15)
        
        # 1. Info Group
        gb1 = QGroupBox("Info Sampel")
        v1 = QVBoxLayout(gb1)
        v1.addWidget(QLabel("Nama Sampel:")); self.txt_name = QLineEdit("Kopi_Robusta")
        v1.addWidget(self.txt_name)
        v1.addWidget(QLabel("Label EI:")); self.txt_label = QLineEdit("kopi")
        v1.addWidget(self.txt_label)
        left_panel.addWidget(gb1)

        # 2. Status Group
        gb2 = QGroupBox("Status & FSM")
        v2 = QVBoxLayout(gb2)
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color:#f39c12; font-weight:bold;")
        v2.addWidget(self.lbl_status)
        self.lbl_fsm = QLabel("IDLE")
        self.lbl_fsm.setStyleSheet("color:#7f8c8d; font-size:20pt; font-weight:bold; border:1px solid #7f8c8d; padding:5px;")
        self.lbl_fsm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v2.addWidget(self.lbl_fsm)
        left_panel.addWidget(gb2)

        # 3. Control Buttons
        self.btn_start = QPushButton("START SAMPLING")
        self.btn_start.setStyleSheet("background:#c0392b; color:white; font-size:16pt; padding:15px; font-weight:bold; border-radius:5px;")
        self.btn_start.clicked.connect(self.go_start)

        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("background:#27ae60; color:white; font-size:16pt; padding:15px; font-weight:bold; border-radius:5px;")
        self.btn_stop.clicked.connect(self.go_stop)

        left_panel.addWidget(self.btn_start)
        left_panel.addWidget(self.btn_stop)

        # 4. Action Buttons
        gb3 = QGroupBox("Actions")
        v3 = QVBoxLayout(gb3)
        self.chk_auto = QCheckBox("Auto Upload Edge Impulse"); self.chk_auto.setChecked(True)
        v3.addWidget(self.chk_auto)
        
        self.btn_upload = QPushButton("Upload Manual EI")
        self.btn_upload.clicked.connect(lambda: self.upload_to_ei(False))
        v3.addWidget(self.btn_upload)

        self.btn_gnuplot = QPushButton("Export GNUPLOT")
        self.btn_gnuplot.setStyleSheet("background:#8e44ad; color:white; padding:8px;")
        self.btn_gnuplot.clicked.connect(self.export_gnuplot)
        v3.addWidget(self.btn_gnuplot)

        hbox_save = QHBoxLayout()
        btn_csv = QPushButton("CSV"); btn_csv.clicked.connect(self.save_csv)
        btn_json = QPushButton("JSON"); btn_json.clicked.connect(self.save_json)
        hbox_save.addWidget(btn_csv); hbox_save.addWidget(btn_json)
        v3.addLayout(hbox_save)
        
        left_panel.addWidget(gb3)
        left_panel.addStretch()
        
        # Wrapper Left Panel
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setFixedWidth(300)
        main_layout.addWidget(left_widget)

        # === RIGHT PANEL (TABS) ===
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #444; }
            QTabBar::tab { background: #333; color: #aaa; padding: 10px; min-width: 100px; }
            QTabBar::tab:selected { background: #555; color: white; border-bottom: 2px solid #3498db; }
        """)
        main_layout.addWidget(self.tabs)

        # --- TAB 1: DASHBOARD (CARDS) ---
        self.tab_dashboard = QWidget()
        dash_layout = QGridLayout(self.tab_dashboard)
        self.cards = {}
        for i, name in enumerate(NAMES):
            card = SensorCard(name, COLORS[i])
            self.cards[name] = card
            row, col = divmod(i, 3) # 3 Kolom
            dash_layout.addWidget(card, row, col)
        self.tabs.addTab(self.tab_dashboard, "DASHBOARD (CARDS)")

        # --- TAB 2: COMBINED GRAPH ---
        self.plot_combined = pg.PlotWidget(title="All Sensors Combined")
        self.plot_combined.addLegend()
        self.lines_combined = {}
        for i, name in enumerate(NAMES):
            pen = pg.mkPen(color=COLORS[i], width=2)
            self.lines_combined[name] = self.plot_combined.plot([], [], pen=pen, name=name)
        self.tabs.addTab(self.plot_combined, "COMBINED GRAPH")

        # --- TAB 3: SPLIT GRAPHS ---
        self.tab_split = QWidget()
        split_layout = QVBoxLayout(self.tab_split)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.vbox_split = QVBoxLayout(scroll_content)

        self.split_plots = {}
        self.split_lines = {}

        for i, name in enumerate(NAMES):
            pw = pg.PlotWidget(title=f"Sensor: {name}")
            pw.setFixedHeight(200) # Tinggi fix per grafik
            pw.showGrid(x=True, y=True, alpha=0.3)
            pen = pg.mkPen(color=COLORS[i], width=2)
            line = pw.plot([], [], pen=pen)
            
            self.split_plots[name] = pw
            self.split_lines[name] = line
            self.vbox_split.addWidget(pw)

        self.vbox_split.addStretch()
        scroll.setWidget(scroll_content)
        split_layout.addWidget(scroll)
        self.tabs.addTab(self.tab_split, "SPLIT GRAPHS")

    def start_worker(self):
        self.rcv = Receiver()
        self.th = QThread()
        self.rcv.moveToThread(self.th)
        self.th.started.connect(self.rcv.run)
        self.rcv.data.connect(self.process_data)
        self.rcv.status.connect(self.lbl_status.setText)
        self.th.start()

    def send_cmd(self, cmd):
        try:
            with socket.socket() as s:
                s.connect((HOST_CMD, PORT_CMD))
                s.sendall(f"{cmd}\n".encode())
            return True
        except: return False

    def go_start(self):
        if self.send_cmd("START_SAMPLING"):
            self.sampling = True
            self.log.clear()
            self.time.clear()
            for q in self.data_store.values(): q.clear()
            self.btn_start.setEnabled(False); self.btn_stop.setEnabled(True)
            self.lbl_status.setText("SAMPLING RUNNING...")

    def go_stop(self):
        if self.send_cmd("STOP_SAMPLING"):
            self.finalize_sampling()

    def finalize_sampling(self):
        self.sampling = False
        self.btn_start.setEnabled(True); self.btn_stop.setEnabled(False)
        self.lbl_status.setText("SAMPLING FINISHED.")
        if self.chk_auto.isChecked(): QTimer.singleShot(1000, lambda: self.upload_to_ei(True))

    @Slot(str)
    def process_data(self, raw):
        if not self.sampling: return
        try:
            # Parse: SENSOR:v1,v2...v7,state,level
            parts = raw.split(":",1)[1].split(",")
            vals = [float(x) for x in parts[:7]]
            state = int(parts[7])
            level = int(parts[8]) + 1
        except: return

        # Update FSM Label
        states_txt = ["IDLE","PRE-COND","RAMP","HOLD","PURGE","RECOVERY","DONE"]
        colors_fsm = ["#7f8c8d","#e67e22","#3498db","#27ae60","#c0392b","#9b59b6","#2ecc71"]
        self.lbl_fsm.setText(f"L{level} : {states_txt[state]}")
        self.lbl_fsm.setStyleSheet(f"color:{colors_fsm[state]}; font-size:20pt; font-weight:bold; border:2px solid {colors_fsm[state]};")

        if state == 6 and self.sampling: self.finalize_sampling()

        # Update Data structures
        t = len(self.log) * 0.25 # Asumsi 4Hz
        self.time.append(t)
        
        row_data = {"timestamp": t}
        for i, name in enumerate(NAMES):
            val = vals[i]
            self.data_store[name].append(val)
            row_data[name] = val
            
            # Update Dashboard Cards (Realtime)
            self.cards[name].update_val(val)

        self.log.append(row_data)

        # Update Graphs (Efficiency Check: Only update visible tabs if needed, but here we update all for smooth switching)
        current_idx = self.tabs.currentIndex()
        
        # 1. Update Combined Graph
        if current_idx == 1:
            for name in NAMES:
                self.lines_combined[name].setData(list(self.time), list(self.data_store[name]))
        
        # 2. Update Split Graphs
        elif current_idx == 2:
            for name in NAMES:
                self.split_lines[name].setData(list(self.time), list(self.data_store[name]))

    # ==================== EXPORT & GNUPLOT ====================
    def get_fname(self, ext):
        n = self.txt_name.text().strip() or "sample"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(HISTORY, f"{n}_{ts}.{ext}")

    def save_csv(self):
        if not self.log: return
        fn = self.get_fname("csv")
        with open(fn,"w",newline="") as f:
            w = csv.DictWriter(f, ["timestamp"]+NAMES)
            w.writeheader(); w.writerows(self.log)
        QMessageBox.information(self, "Saved", f"CSV Saved:\n{fn}")
        return fn

    def save_json(self):
        if not self.log: return
        fn = self.get_fname("json")
        with open(fn,"w") as f: json.dump(self.log, f, indent=2)
        QMessageBox.information(self, "Saved", f"JSON Saved:\n{fn}")

    def export_gnuplot(self):
        if not self.log: return QMessageBox.warning(self, "Empty", "No data to export!")
        
        base_name = self.txt_name.text().strip() or "data"
        dat_file = f"{base_name}.dat"
        gp_file  = f"{base_name}.gp"
        
        # 1. Write Data (.dat) - Space separated for Gnuplot
        try:
            with open(dat_file, "w") as f:
                f.write("# Time " + " ".join(NAMES) + "\n")
                for row in self.log:
                    line = [f"{row['timestamp']:.2f}"] + [f"{row[n]:.2f}" for n in NAMES]
                    f.write(" ".join(line) + "\n")
        except Exception as e:
            return QMessageBox.critical(self, "Error", str(e))

        # 2. Write Script (.gp)
        plot_cmds = []
        for i, name in enumerate(NAMES):
            # Column 1 is Time, so Data starts at Column 2
            col_idx = i + 2 
            plot_cmds.append(f"'{dat_file}' using 1:{col_idx} with lines lw 2 title '{name}'")
        
        plot_str = ", ".join(plot_cmds)
        
        script_content = f"""
# Gnuplot Script for E-Nose Zizu
set terminal pngcairo size 1200,800 enhanced font 'Arial,12'
set output '{base_name}.png'
set title "E-NOSE Sensor Response: {base_name}"
set xlabel "Time (seconds)"
set ylabel "Sensor Value (Raw/PPM)"
set grid
set key outside right top
plot {plot_str}

# Uncomment below to open window interactive
# set terminal wxt size 1200,800
# replot
# pause -1
"""
        with open(gp_file, "w") as f:
            f.write(script_content)

        msg = f"Gnuplot files created!\n1. Data: {dat_file}\n2. Script: {gp_file}\n\n"
        msg += "Run command: gnuplot " + gp_file
        QMessageBox.information(self, "Gnuplot Export", msg)

    # ==================== EDGE IMPULSE ====================
    def upload_to_ei(self, auto=False):
        if not self.log: return
        tmp = "temp_ei.csv"
        try:
            with open(tmp,"w",newline="") as f:
                w = csv.DictWriter(f, ["timestamp"]+NAMES); w.writeheader(); w.writerows(self.log)
            
            url = "https://ingestion.edgeimpulse.com/api/training/files"
            headers = {"x-api-key": EI_API_KEY, "x-label": self.txt_label.text(), "x-protected": "false"}
            files = {"data": (f"{self.txt_name.text()}.csv", open(tmp,"rb"), "text/csv")}
            
            r = requests.post(url, headers=headers, files=files, timeout=60)
            if r.status_code == 200:
                self.lbl_status.setText("UPLOAD OK!")
                if not auto: QMessageBox.information(self,"Success","Uploaded to Edge Impulse!")
            else:
                self.lbl_status.setText("UPLOAD FAIL")
        except Exception as e:
            self.lbl_status.setText(f"Err: {str(e)[:10]}")
        finally:
            if os.path.exists(tmp): os.remove(tmp)

    def closeEvent(self, e):
        self.th.quit()
        super().closeEvent(e)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())