"""PySide6 Native Desktop Workbench for Multi-Agent Stock & Financial News Analysis."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict, Optional

import markdown
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.agents.orchestrator import AnalysisCancelledError, AnalysisOrchestrator
from src.core.config_manager import (
    DEFAULT_BASE_URLS,
    SUGGESTED_MODELS,
    SUPPORTED_PROVIDERS,
    AgentModelConfig,
    ConfigManager,
    ResolvedRuntimeSettings,
)
from src.core.llm_gateway import LLMCallConfig, LLMGateway
from src.core.schemas import FullAnalysisReport
from src.core.storage import LocalStorage


APP_QSS = """
QMainWindow, QWidget {
    background-color: #0B1120;
    color: #E2E8F0;
    font-family: "Segoe UI", "PingFang TC", "Microsoft JhengHei", sans-serif;
    font-size: 13px;
}
QFrame#Sidebar {
    background-color: #111827;
    border-right: 1px solid #1E293B;
}
QFrame#Card, QGroupBox {
    background-color: #111827;
    border: 1px solid #1F2937;
    border-radius: 8px;
}
QGroupBox {
    margin-top: 12px;
    padding-top: 16px;
    font-weight: 600;
    color: #93C5FD;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QLabel#BrandTitle {
    font-size: 17px;
    font-weight: 700;
    color: #F8FAFC;
}
QLabel#BrandSub {
    font-size: 11px;
    color: #94A3B8;
}
QLabel#SectionTitle {
    font-size: 16px;
    font-weight: 700;
    color: #F8FAFC;
}
QLabel#KpiLabel {
    font-size: 11px;
    color: #94A3B8;
}
QLabel#KpiValue {
    font-size: 16px;
    font-weight: 700;
    color: #F8FAFC;
}
QPushButton {
    background-color: #1E293B;
    color: #E2E8F0;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #334155;
}
QPushButton:disabled {
    background-color: #111827;
    color: #475569;
    border-color: #1E293B;
}
QPushButton#PrimaryBtn {
    background-color: #2563EB;
    border-color: #3B82F6;
    color: #FFFFFF;
}
QPushButton#PrimaryBtn:hover {
    background-color: #1D4ED8;
}
QPushButton#DangerBtn {
    background-color: #991B1B;
    border-color: #DC2626;
    color: #FFFFFF;
}
QPushButton#DangerBtn:hover {
    background-color: #7F1D1D;
}
QPushButton#NavBtn {
    text-align: left;
    padding: 10px 12px;
    border: none;
    background-color: transparent;
    color: #CBD5E1;
}
QPushButton#NavBtn:hover {
    background-color: #1E293B;
}
QPushButton#NavBtn[active="true"] {
    background-color: #1D4ED8;
    color: #FFFFFF;
}
QPushButton#ChipBtn {
    padding: 4px 10px;
    font-size: 12px;
    background-color: #172554;
    border-color: #1E40AF;
    color: #BFDBFE;
}
QPushButton#ChipBtn:hover {
    background-color: #1E3A8A;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #0F172A;
    color: #F8FAFC;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #3B82F6;
}
QListWidget {
    background-color: #0F172A;
    border: 1px solid #1E293B;
    border-radius: 6px;
    padding: 4px;
}
QListWidget::item {
    padding: 8px;
    border-radius: 5px;
    margin-bottom: 2px;
}
QListWidget::item:selected {
    background-color: #1E3A8A;
    color: #FFFFFF;
}
QProgressBar {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 6px;
    text-align: center;
    height: 18px;
    color: #F8FAFC;
    font-weight: 600;
}
QProgressBar::chunk {
    background-color: #2563EB;
    border-radius: 5px;
}
QTextBrowser, QPlainTextEdit {
    background-color: #0F172A;
    color: #E2E8F0;
    border: 1px solid #1E293B;
    border-radius: 6px;
    padding: 10px;
}
QTabWidget::pane {
    border: 1px solid #1E293B;
    border-radius: 6px;
    background-color: #0F172A;
}
QTabBar::tab {
    background-color: #111827;
    color: #94A3B8;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
}
QTabBar::tab:selected {
    background-color: #1E293B;
    color: #F8FAFC;
    font-weight: 600;
}
"""

REPORT_HTML_CSS = """
<style>
body {
    font-family: "Segoe UI", "PingFang TC", "Microsoft JhengHei", sans-serif;
    color: #E2E8F0;
    background-color: #0F172A;
    line-height: 1.65;
    padding: 12px;
}
h1 { color: #F8FAFC; font-size: 22px; border-bottom: 1px solid #334155; padding-bottom: 8px; }
h2 { color: #93C5FD; font-size: 17px; margin-top: 22px; border-bottom: 1px solid #1E293B; padding-bottom: 4px; }
h3 { color: #CBD5E1; font-size: 14px; margin-top: 14px; }
blockquote {
    background-color: #172554;
    border-left: 4px solid #3B82F6;
    margin: 10px 0;
    padding: 8px 12px;
    color: #DBEAFE;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 10px 0 16px 0;
    font-size: 12.5px;
}
th {
    background-color: #1E293B;
    color: #93C5FD;
    text-align: left;
    padding: 8px;
    border: 1px solid #334155;
}
td {
    padding: 7px 8px;
    border: 1px solid #1E293B;
    vertical-align: top;
}
code {
    background-color: #1E293B;
    color: #FDE68A;
    padding: 1px 5px;
    border-radius: 4px;
    font-family: Consolas, Monaco, monospace;
}
a { color: #60A5FA; text-decoration: none; }
hr { border: none; border-top: 1px solid #1E293B; margin: 18px 0; }
li { margin-bottom: 4px; }
</style>
"""

PROVIDER_LABELS: Dict[str, str] = {
    "openai": "OpenAI API",
    "anthropic": "Anthropic Claude API",
    "gemini": "Google Gemini API",
    "deepseek": "DeepSeek API",
    "ollama": "Ollama (本機模型端點)",
    "openai_compatible": "自訂 OpenAI-Compatible API",
    "tavily": "Tavily 財經新聞搜尋 API (選填)",
}

AGENT_ROLE_LABELS: Dict[str, str] = {
    "orchestrator": "Orchestrator 總管協調官",
    "past_agent": "Past Agent 過去基本面分析師",
    "present_agent": "Present Agent 現在新聞情緒分析師",
    "future_agent": "Future Agent 未來趨勢策略師",
    "risk_agent": "Risk Agent 風控與反方審查員",
}

STAGE_NAMES = {
    1: "1. 代碼驗證",
    2: "2. 過去＆現在平行蒐集",
    3: "3. 未來情境推演",
    4: "4. 風控反方審查",
    5: "5. 報告彙整",
}


class AnalysisWorker(QObject):
    """Runs the Multi-Agent pipeline in a dedicated QThread without blocking UI."""

    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal(str)

    def __init__(
        self,
        orchestrator: AnalysisOrchestrator,
        raw_ticker: str,
        runtime: ResolvedRuntimeSettings,
        history_years: int,
        news_lookback_days: int,
        force_refresh: bool,
    ) -> None:
        super().__init__()
        self.orchestrator = orchestrator
        self.raw_ticker = raw_ticker
        self.runtime = runtime
        self.history_years = history_years
        self.news_lookback_days = news_lookback_days
        self.force_refresh = force_refresh
        self.cancel_event = threading.Event()

    def request_cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            report = self.orchestrator.run_pipeline(
                raw_ticker=self.raw_ticker,
                runtime=self.runtime,
                history_years=self.history_years,
                news_lookback_days=self.news_lookback_days,
                force_refresh=self.force_refresh,
                progress_cb=lambda stage, pct, msg: self.progress.emit(stage, pct, msg),
                cancel_event=self.cancel_event,
            )
            self.finished.emit(report)
        except AnalysisCancelledError as exc:
            self.cancelled.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))


class ConnectionTestWorker(QObject):
    """Tests a single LLM provider connection off the main UI thread."""

    completed = Signal(str, bool, str)

    def __init__(self, gateway: LLMGateway, provider: str, call_config: LLMCallConfig) -> None:
        super().__init__()
        self.gateway = gateway
        self.provider = provider
        self.call_config = call_config

    def run(self) -> None:
        ok, msg = self.gateway.test_connection(self.call_config)
        self.completed.emit(self.provider, ok, msg)


class MainWindow(QMainWindow):
    """Main desktop window containing Analysis Workbench and Local API/Model Settings."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Stock Multi-Agent Desktop — 跨維度財經趨勢分析工作台")
        self.resize(1380, 880)
        self.setMinimumSize(1100, 720)

        self.config_manager = ConfigManager()
        self.storage = LocalStorage()
        self.gateway = LLMGateway()
        self.orchestrator = AnalysisOrchestrator(gateway=self.gateway, storage=self.storage)

        self.runtime_settings: ResolvedRuntimeSettings = self.config_manager.load()
        self.current_report: Optional[FullAnalysisReport] = None

        self._analysis_thread: Optional[QThread] = None
        self._analysis_worker: Optional[AnalysisWorker] = None
        self._test_thread: Optional[QThread] = None
        self._test_worker: Optional[ConnectionTestWorker] = None

        # References to dynamic settings widgets
        self._key_inputs: Dict[str, QLineEdit] = {}
        self._url_inputs: Dict[str, QLineEdit] = {}
        self._test_buttons: Dict[str, QPushButton] = {}
        self._agent_widgets: Dict[str, Dict[str, object]] = {}

        self._build_ui()
        self._populate_settings_widgets()
        self._refresh_history_list()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter)

        # ---------------- Left Sidebar ----------------
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setMinimumWidth(260)
        sidebar.setMaximumWidth(320)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(14, 16, 14, 14)
        sb_layout.setSpacing(10)

        brand_title = QLabel("Stock Multi-Agent")
        brand_title.setObjectName("BrandTitle")
        brand_sub = QLabel("過去 · 現在 · 未來 · 風控 獨立桌面端")
        brand_sub.setObjectName("BrandSub")
        sb_layout.addWidget(brand_title)
        sb_layout.addWidget(brand_sub)

        self.nav_analysis_btn = QPushButton("  趨勢分析工作台")
        self.nav_analysis_btn.setObjectName("NavBtn")
        self.nav_analysis_btn.setProperty("active", True)
        self.nav_analysis_btn.clicked.connect(lambda: self._switch_page(0))

        self.nav_settings_btn = QPushButton("  API 金鑰與模型設定")
        self.nav_settings_btn.setObjectName("NavBtn")
        self.nav_settings_btn.setProperty("active", False)
        self.nav_settings_btn.clicked.connect(lambda: self._switch_page(1))

        sb_layout.addWidget(self.nav_analysis_btn)
        sb_layout.addWidget(self.nav_settings_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #1E293B;")
        sb_layout.addWidget(sep)

        hist_header = QHBoxLayout()
        hist_label = QLabel("本機歷史報告")
        hist_label.setStyleSheet("font-weight: 600; color: #94A3B8;")
        hist_header.addWidget(hist_label)
        hist_header.addStretch()
        self.delete_hist_btn = QPushButton("刪除")
        self.delete_hist_btn.setFixedHeight(26)
        self.delete_hist_btn.clicked.connect(self._delete_selected_history)
        hist_header.addWidget(self.delete_hist_btn)
        sb_layout.addLayout(hist_header)

        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self._on_history_clicked)
        sb_layout.addWidget(self.history_list, 1)

        path_hint = QLabel(f"設定檔：{self.config_manager.settings_path.name}\n資料庫：{self.storage.db_path.name}")
        path_hint.setStyleSheet("font-size: 11px; color: #64748B;")
        sb_layout.addWidget(path_hint)

        splitter.addWidget(sidebar)

        # ---------------- Right Stacked Pages ----------------
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_analysis_page())
        self.pages.addWidget(self._build_settings_page())
        splitter.addWidget(self.pages)
        splitter.setStretchFactor(1, 1)

    def _build_analysis_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Top Control Card
        ctrl_card = QFrame()
        ctrl_card.setObjectName("Card")
        ctrl_layout = QVBoxLayout(ctrl_card)
        ctrl_layout.setContentsMargins(14, 12, 14, 12)
        ctrl_layout.setSpacing(10)

        row1 = QHBoxLayout()
        ticker_lbl = QLabel("股票代碼：")
        ticker_lbl.setStyleSheet("font-weight: 600;")
        self.ticker_input = QLineEdit()
        self.ticker_input.setPlaceholderText("輸入美股或台股代碼，例如 NVDA、AAPL、2330.TW、2317")
        self.ticker_input.setMinimumWidth(280)
        self.ticker_input.returnPressed.connect(self._start_analysis)

        row1.addWidget(ticker_lbl)
        row1.addWidget(self.ticker_input, 1)

        for sample in ("NVDA", "2330.TW", "AAPL", "2317.TW"):
            chip = QPushButton(sample)
            chip.setObjectName("ChipBtn")
            chip.clicked.connect(lambda checked=False, s=sample: self.ticker_input.setText(s))
            row1.addWidget(chip)

        ctrl_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("歷史年數："))
        self.years_spin = QSpinBox()
        self.years_spin.setRange(1, 5)
        self.years_spin.setSuffix(" 年")
        row2.addWidget(self.years_spin)

        row2.addSpacing(10)
        row2.addWidget(QLabel("新聞回溯："))
        self.lookback_spin = QSpinBox()
        self.lookback_spin.setRange(3, 30)
        self.lookback_spin.setSuffix(" 天")
        row2.addWidget(self.lookback_spin)

        row2.addSpacing(10)
        self.force_refresh_cb = QCheckBox("略過快取強制重新抓取")
        row2.addWidget(self.force_refresh_cb)

        row2.addStretch()

        self.run_btn = QPushButton("開始 Multi-Agent 分析")
        self.run_btn.setObjectName("PrimaryBtn")
        self.run_btn.clicked.connect(self._start_analysis)
        row2.addWidget(self.run_btn)

        self.cancel_btn = QPushButton("中止")
        self.cancel_btn.setObjectName("DangerBtn")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_analysis)
        row2.addWidget(self.cancel_btn)

        ctrl_layout.addLayout(row2)
        layout.addWidget(ctrl_card)

        # Pipeline Progress Card
        prog_card = QFrame()
        prog_card.setObjectName("Card")
        prog_layout = QVBoxLayout(prog_card)
        prog_layout.setContentsMargins(14, 10, 14, 10)
        prog_layout.setSpacing(8)

        stage_row = QHBoxLayout()
        self._stage_labels: Dict[int, QLabel] = {}
        for idx, title in STAGE_NAMES.items():
            lbl = QLabel(title)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                "background-color: #0F172A; border: 1px solid #1E293B; "
                "border-radius: 5px; padding: 4px 8px; color: #64748B; font-size: 12px;"
            )
            self._stage_labels[idx] = lbl
            stage_row.addWidget(lbl, 1)
        prog_layout.addLayout(stage_row)

        bar_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.status_label = QLabel("就緒：請確認 API Key 已設定，輸入股票代碼後開始分析。")
        self.status_label.setStyleSheet("color: #94A3B8;")
        bar_row.addWidget(self.progress_bar, 1)
        bar_row.addSpacing(12)
        bar_row.addWidget(self.status_label, 2)
        prog_layout.addLayout(bar_row)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(90)
        self.log_box.setFont(QFont("Consolas", 10))
        self.log_box.setPlaceholderText("Multi-Agent 即時執行日誌將顯示於此...")
        prog_layout.addWidget(self.log_box)
        layout.addWidget(prog_card)

        # KPI Strip
        kpi_row = QHBoxLayout()
        self.kpi_price = self._create_kpi_card("最新收盤價", "--")
        self.kpi_past = self._create_kpi_card("過去估值評價", "--")
        self.kpi_present = self._create_kpi_card("現在新聞情緒", "--")
        self.kpi_risk = self._create_kpi_card("風控等級 / 信心", "--")
        kpi_row.addWidget(self.kpi_price["card"], 1)
        kpi_row.addWidget(self.kpi_past["card"], 1)
        kpi_row.addWidget(self.kpi_present["card"], 1)
        kpi_row.addWidget(self.kpi_risk["card"], 1)
        layout.addLayout(kpi_row)

        # Report Tabs + Actions
        tab_header = QHBoxLayout()
        tab_title = QLabel("研究報告檢視器")
        tab_title.setObjectName("SectionTitle")
        tab_header.addWidget(tab_title)
        tab_header.addStretch()

        self.copy_md_btn = QPushButton("複製 Markdown")
        self.copy_md_btn.setEnabled(False)
        self.copy_md_btn.clicked.connect(self._copy_markdown)
        tab_header.addWidget(self.copy_md_btn)

        self.export_md_btn = QPushButton("匯出 .md 報告")
        self.export_md_btn.setEnabled(False)
        self.export_md_btn.clicked.connect(self._export_markdown)
        tab_header.addWidget(self.export_md_btn)
        layout.addLayout(tab_header)

        self.report_tabs = QTabWidget()
        self.report_browser = QTextBrowser()
        self.report_browser.setOpenExternalLinks(True)
        self.report_browser.setHtml(
            f"{REPORT_HTML_CSS}<p style='color:#94A3B8;'>尚未載入報告。請在上方輸入股票代碼啟動 Multi-Agent 分析，或從左側點選本機歷史報告。</p>"
        )
        self.report_tabs.addTab(self.report_browser, "完整研究報告 (Markdown)")

        # JSON Inspector Tab
        json_tab = QWidget()
        json_layout = QVBoxLayout(json_tab)
        json_top = QHBoxLayout()
        json_top.addWidget(QLabel("檢視 Agent 標準 JSON 資料契約："))
        self.json_section_combo = QComboBox()
        self.json_section_combo.addItems(
            [
                "past_analysis (PastAgent 輸出)",
                "present_analysis (PresentAgent 輸出)",
                "future_analysis (FutureAgent 輸出)",
                "risk_review (RiskAgent 輸出)",
                "stock_data (yfinance 原始數據束)",
            ]
        )
        self.json_section_combo.currentIndexChanged.connect(self._refresh_json_inspector)
        json_top.addWidget(self.json_section_combo, 1)
        json_layout.addLayout(json_top)

        self.json_viewer = QPlainTextEdit()
        self.json_viewer.setReadOnly(True)
        self.json_viewer.setFont(QFont("Consolas", 11))
        json_layout.addWidget(self.json_viewer, 1)
        self.report_tabs.addTab(json_tab, "Agent JSON 結構檢查器")

        layout.addWidget(self.report_tabs, 1)
        return page

    def _create_kpi_card(self, title: str, default_val: str) -> Dict[str, object]:
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)
        t_lbl = QLabel(title)
        t_lbl.setObjectName("KpiLabel")
        v_lbl = QLabel(default_val)
        v_lbl.setObjectName("KpiValue")
        lay.addWidget(t_lbl)
        lay.addWidget(v_lbl)
        return {"card": card, "value": v_lbl}

    def _build_settings_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)

        header = QLabel("本機 API 金鑰與 Multi-Agent 模型分配設定")
        header.setObjectName("SectionTitle")
        layout.addWidget(header)

        sec_note = QLabel(
            f"所有 API Key 皆以本機 Fernet 金鑰加密後儲存於 {self.config_manager.settings_path}，"
            "絕不會寫死於程式碼或上傳至任何第三方伺服器。\n"
            "💡 免費方案指引：若目前沒有付費 API Key，可至 Google AI Studio (https://aistudio.google.com/apikey) "
            "免費申請 Gemini API Key 並填入下方「Google Gemini API」欄位（系統預設全部 5 個 Agent 皆採用 gemini-2.5-flash）。"
        )
        sec_note.setStyleSheet("color: #93C5FD; background-color: #172554; border: 1px solid #1E40AF; border-radius: 6px; padding: 10px;")
        sec_note.setWordWrap(True)
        layout.addWidget(sec_note)

        # Provider Keys Group
        keys_group = QGroupBox("1. 供應商 API Key 與端點設定（支援自由切換與本機 Ollama）")
        keys_form = QGridLayout(keys_group)
        keys_form.setSpacing(10)

        keys_form.addWidget(QLabel("供應商"), 0, 0)
        keys_form.addWidget(QLabel("API Key（本地加密儲存）"), 0, 1)
        keys_form.addWidget(QLabel("Base URL（可選自訂代理或 Ollama 位址）"), 0, 2)
        keys_form.addWidget(QLabel("操作"), 0, 3)

        row_idx = 1
        for key_name, label_text in PROVIDER_LABELS.items():
            lbl = QLabel(label_text)
            lbl.setMinimumWidth(190)
            keys_form.addWidget(lbl, row_idx, 0)

            key_edit = QLineEdit()
            key_edit.setEchoMode(QLineEdit.Password)
            key_edit.setPlaceholderText("Ollama 本地端可留空" if key_name == "ollama" else "請貼上 API Key")
            self._key_inputs[key_name] = key_edit
            keys_form.addWidget(key_edit, row_idx, 1)

            if key_name in DEFAULT_BASE_URLS:
                url_edit = QLineEdit()
                url_edit.setPlaceholderText(DEFAULT_BASE_URLS[key_name])
                self._url_inputs[key_name] = url_edit
                keys_form.addWidget(url_edit, row_idx, 2)
            else:
                na_lbl = QLabel("https://api.tavily.com/search")
                na_lbl.setStyleSheet("color: #64748B;")
                keys_form.addWidget(na_lbl, row_idx, 2)

            action_box = QHBoxLayout()
            toggle_btn = QPushButton("顯示")
            toggle_btn.setCheckable(True)
            toggle_btn.setFixedWidth(60)
            toggle_btn.toggled.connect(
                lambda checked, edit=key_edit, btn=toggle_btn: (
                    edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password),
                    btn.setText("隱藏" if checked else "顯示"),
                )
            )
            action_box.addWidget(toggle_btn)

            if key_name in SUPPORTED_PROVIDERS:
                test_btn = QPushButton("測試連線")
                test_btn.setFixedWidth(84)
                test_btn.clicked.connect(lambda checked=False, p=key_name: self._test_provider_connection(p))
                self._test_buttons[key_name] = test_btn
                action_box.addWidget(test_btn)

            keys_form.addLayout(action_box, row_idx, 3)
            row_idx += 1

        layout.addWidget(keys_group)

        # Per-Agent Model Routing Group
        agent_group = QGroupBox("2. Multi-Agent 個別模型指派（支援一鍵統一套用或混搭不同模型）")
        agent_group_lay = QVBoxLayout(agent_group)
        agent_group_lay.setSpacing(10)

        bulk_row = QHBoxLayout()
        bulk_row.addWidget(QLabel("快速一鍵套用至全部 Agent："))
        self.bulk_prov_combo = QComboBox()
        self.bulk_prov_combo.addItems(list(SUPPORTED_PROVIDERS))
        self.bulk_prov_combo.setCurrentText("gemini")
        self.bulk_model_combo = QComboBox()
        self.bulk_model_combo.setEditable(True)
        self.bulk_model_combo.setMinimumWidth(220)
        self.bulk_model_combo.addItems(SUGGESTED_MODELS.get("gemini", []))
        self.bulk_prov_combo.currentTextChanged.connect(
            lambda prov, mc=self.bulk_model_combo: self._on_agent_provider_changed(prov, mc)
        )
        apply_all_btn = QPushButton("套用至全部 5 個 Agent")
        apply_all_btn.clicked.connect(self._apply_bulk_agent_model)
        bulk_row.addWidget(self.bulk_prov_combo)
        bulk_row.addWidget(self.bulk_model_combo)
        bulk_row.addWidget(apply_all_btn)
        bulk_row.addStretch()
        agent_group_lay.addLayout(bulk_row)

        agent_grid = QGridLayout()
        agent_grid.setSpacing(10)
        agent_group_lay.addLayout(agent_grid)

        agent_grid.addWidget(QLabel("Agent 角色"), 0, 0)
        agent_grid.addWidget(QLabel("AI 供應商"), 0, 1)
        agent_grid.addWidget(QLabel("模型名稱（可選預設或自行輸入）"), 0, 2)
        agent_grid.addWidget(QLabel("Temperature"), 0, 3)
        agent_grid.addWidget(QLabel("Max Tokens"), 0, 4)

        for idx, (role, role_label) in enumerate(AGENT_ROLE_LABELS.items(), start=1):
            agent_grid.addWidget(QLabel(role_label), idx, 0)

            prov_combo = QComboBox()
            prov_combo.addItems(list(SUPPORTED_PROVIDERS))

            model_combo = QComboBox()
            model_combo.setEditable(True)
            model_combo.setMinimumWidth(240)

            temp_spin = QDoubleSpinBox()
            temp_spin.setRange(0.0, 1.5)
            temp_spin.setSingleStep(0.05)

            tokens_spin = QSpinBox()
            tokens_spin.setRange(256, 32768)
            tokens_spin.setSingleStep(500)

            prov_combo.currentTextChanged.connect(
                lambda prov, mc=model_combo: self._on_agent_provider_changed(prov, mc)
            )

            agent_grid.addWidget(prov_combo, idx, 1)
            agent_grid.addWidget(model_combo, idx, 2)
            agent_grid.addWidget(temp_spin, idx, 3)
            agent_grid.addWidget(tokens_spin, idx, 4)

            self._agent_widgets[role] = {
                "provider": prov_combo,
                "model": model_combo,
                "temperature": temp_spin,
                "max_tokens": tokens_spin,
            }

        layout.addWidget(agent_group)

        # Cache & Default Preferences Group
        pref_group = QGroupBox("3. 快取與分析預設參數")
        pref_form = QFormLayout(pref_group)
        self.cache_ttl_spin = QSpinBox()
        self.cache_ttl_spin.setRange(0, 1440)
        self.cache_ttl_spin.setSuffix(" 分鐘（設為 0 表示停用快取）")
        pref_form.addRow("股價與新聞快取有效時間：", self.cache_ttl_spin)
        layout.addWidget(pref_group)

        # Action Buttons
        btn_row = QHBoxLayout()
        self.save_settings_btn = QPushButton("儲存並加密所有設定")
        self.save_settings_btn.setObjectName("PrimaryBtn")
        self.save_settings_btn.clicked.connect(self._save_settings_from_ui)
        btn_row.addWidget(self.save_settings_btn)

        clear_cache_btn = QPushButton("清除股價與新聞快取")
        clear_cache_btn.clicked.connect(self._clear_cache)
        btn_row.addWidget(clear_cache_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def _switch_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self.nav_analysis_btn.setProperty("active", index == 0)
        self.nav_settings_btn.setProperty("active", index == 1)
        self.nav_analysis_btn.style().unpolish(self.nav_analysis_btn)
        self.nav_analysis_btn.style().polish(self.nav_analysis_btn)
        self.nav_settings_btn.style().unpolish(self.nav_settings_btn)
        self.nav_settings_btn.style().polish(self.nav_settings_btn)

    def _on_agent_provider_changed(self, provider: str, model_combo: QComboBox) -> None:
        current_text = model_combo.currentText().strip()
        suggestions = SUGGESTED_MODELS.get(provider, [])
        model_combo.blockSignals(True)
        model_combo.clear()
        model_combo.addItems(suggestions)
        if suggestions:
            model_combo.setCurrentText(suggestions[0])
        elif current_text:
            model_combo.setCurrentText(current_text)
        model_combo.blockSignals(False)

    def _apply_bulk_agent_model(self) -> None:
        provider = self.bulk_prov_combo.currentText().strip()
        model_name = self.bulk_model_combo.currentText().strip()
        for widgets in self._agent_widgets.values():
            prov_combo: QComboBox = widgets["provider"]  # type: ignore[assignment]
            model_combo: QComboBox = widgets["model"]  # type: ignore[assignment]
            prov_combo.blockSignals(True)
            prov_combo.setCurrentText(provider)
            prov_combo.blockSignals(False)

            model_combo.blockSignals(True)
            model_combo.clear()
            model_combo.addItems(SUGGESTED_MODELS.get(provider, []))
            model_combo.setCurrentText(model_name)
            model_combo.blockSignals(False)

    def _populate_settings_widgets(self) -> None:
        rt = self.runtime_settings
        for key_name, edit in self._key_inputs.items():
            edit.setText(rt.api_keys.get(key_name, ""))

        for prov, edit in self._url_inputs.items():
            edit.setText(rt.settings.base_urls.get(prov, DEFAULT_BASE_URLS.get(prov, "")))

        for role, widgets in self._agent_widgets.items():
            cfg = rt.settings.agent_models.get(role, AgentModelConfig())
            prov_combo: QComboBox = widgets["provider"]  # type: ignore[assignment]
            model_combo: QComboBox = widgets["model"]  # type: ignore[assignment]
            temp_spin: QDoubleSpinBox = widgets["temperature"]  # type: ignore[assignment]
            tokens_spin: QSpinBox = widgets["max_tokens"]  # type: ignore[assignment]

            prov_combo.blockSignals(True)
            prov_combo.setCurrentText(cfg.provider)
            prov_combo.blockSignals(False)

            model_combo.blockSignals(True)
            model_combo.clear()
            model_combo.addItems(SUGGESTED_MODELS.get(cfg.provider, []))
            model_combo.setCurrentText(cfg.model)
            model_combo.blockSignals(False)

            temp_spin.setValue(cfg.temperature)
            tokens_spin.setValue(cfg.max_tokens)

        self.years_spin.setValue(rt.settings.preferences.history_years)
        self.lookback_spin.setValue(rt.settings.preferences.news_lookback_days)
        self.cache_ttl_spin.setValue(rt.settings.preferences.cache_ttl_minutes)

    def _collect_settings_from_ui(self) -> ResolvedRuntimeSettings:
        settings = self.runtime_settings.settings.model_copy(deep=True)
        api_keys: Dict[str, str] = {}

        for key_name, edit in self._key_inputs.items():
            api_keys[key_name] = edit.text().strip()

        for prov, edit in self._url_inputs.items():
            val = edit.text().strip()
            settings.base_urls[prov] = val or DEFAULT_BASE_URLS.get(prov, "")

        for role, widgets in self._agent_widgets.items():
            prov_combo: QComboBox = widgets["provider"]  # type: ignore[assignment]
            model_combo: QComboBox = widgets["model"]  # type: ignore[assignment]
            temp_spin: QDoubleSpinBox = widgets["temperature"]  # type: ignore[assignment]
            tokens_spin: QSpinBox = widgets["max_tokens"]  # type: ignore[assignment]

            settings.agent_models[role] = AgentModelConfig(
                provider=prov_combo.currentText().strip(),
                model=model_combo.currentText().strip(),
                temperature=round(temp_spin.value(), 2),
                max_tokens=tokens_spin.value(),
            )

        settings.preferences.history_years = self.years_spin.value()
        settings.preferences.news_lookback_days = self.lookback_spin.value()
        settings.preferences.cache_ttl_minutes = self.cache_ttl_spin.value()
        return ResolvedRuntimeSettings(settings=settings, api_keys=api_keys)

    def _save_settings_from_ui(self) -> None:
        resolved = self._collect_settings_from_ui()
        self.config_manager.save(resolved.settings, resolved.api_keys)
        self.runtime_settings = resolved
        QMessageBox.information(
            self,
            "設定已儲存",
            f"API Key 與 Agent 模型分派已加密儲存至：\n{self.config_manager.settings_path}",
        )

    def _clear_cache(self) -> None:
        self.storage.clear_api_caches()
        QMessageBox.information(self, "快取已清除", "已清空本機股價與財經新聞快取。")

    def _test_provider_connection(self, provider: str) -> None:
        if self._test_thread is not None and self._test_thread.isRunning():
            return

        resolved = self._collect_settings_from_ui()
        suggestions = SUGGESTED_MODELS.get(provider, [])
        test_model = suggestions[0] if suggestions else "gpt-4o-mini"

        # Prefer a model currently assigned to an agent using this provider if available
        for cfg in resolved.settings.agent_models.values():
            if cfg.provider == provider and cfg.model.strip():
                test_model = cfg.model.strip()
                break

        call_cfg = LLMCallConfig(
            provider=provider,
            model=test_model,
            api_key=resolved.api_keys.get(provider, ""),
            base_url=resolved.settings.base_urls.get(provider, DEFAULT_BASE_URLS.get(provider, "")),
        )

        for p_name, btn in self._test_buttons.items():
            btn.setEnabled(False)
            if p_name == provider:
                btn.setText("測試中...")

        self._test_thread = QThread()
        self._test_worker = ConnectionTestWorker(self.gateway, provider, call_cfg)
        self._test_worker.moveToThread(self._test_thread)
        self._test_thread.started.connect(self._test_worker.run)
        self._test_worker.completed.connect(self._test_thread.quit)
        self._test_worker.completed.connect(self._on_test_completed)
        self._test_thread.finished.connect(self._cleanup_test_thread)
        self._test_thread.start()

    def _on_test_completed(self, provider: str, ok: bool, msg: str) -> None:
        if ok:
            QMessageBox.information(self, f"{provider} 連線成功", msg)
        else:
            QMessageBox.warning(self, f"{provider} 連線失敗", msg)

    def _cleanup_test_thread(self) -> None:
        for btn in self._test_buttons.values():
            btn.setEnabled(True)
            btn.setText("測試連線")
        if self._test_worker is not None:
            self._test_worker.deleteLater()
            self._test_worker = None
        if self._test_thread is not None:
            self._test_thread.deleteLater()
            self._test_thread = None

    def _set_stage_highlight(self, active_stage: int) -> None:
        for idx, lbl in self._stage_labels.items():
            if idx < active_stage:
                lbl.setStyleSheet(
                    "background-color: #064E3B; border: 1px solid #10B981; "
                    "border-radius: 5px; padding: 4px 8px; color: #A7F3D0; font-size: 12px; font-weight: 600;"
                )
            elif idx == active_stage:
                lbl.setStyleSheet(
                    "background-color: #1E3A8A; border: 1px solid #3B82F6; "
                    "border-radius: 5px; padding: 4px 8px; color: #FFFFFF; font-size: 12px; font-weight: 700;"
                )
            else:
                lbl.setStyleSheet(
                    "background-color: #0F172A; border: 1px solid #1E293B; "
                    "border-radius: 5px; padding: 4px 8px; color: #64748B; font-size: 12px;"
                )

    def _start_analysis(self) -> None:
        raw_ticker = self.ticker_input.text().strip()
        if not raw_ticker:
            QMessageBox.warning(self, "缺少股票代碼", "請先輸入股票代碼（例如 NVDA 或 2330.TW）。")
            return

        # Persist latest UI preferences & check if required provider keys exist
        self.runtime_settings = self._collect_settings_from_ui()
        self.config_manager.save(self.runtime_settings.settings, self.runtime_settings.api_keys)

        missing_roles = []
        for role, cfg in self.runtime_settings.settings.agent_models.items():
            if cfg.provider != "ollama" and not self.runtime_settings.api_keys.get(cfg.provider, "").strip():
                missing_roles.append(f"{role} ({cfg.provider})")
        if missing_roles:
            QMessageBox.warning(
                self,
                "尚未設定 API Key",
                "以下 Agent 所指派的供應商尚未設定 API Key：\n\n"
                + "\n".join(f"• {r}" for r in missing_roles)
                + "\n\n請先切換至左側「API 金鑰與模型設定」填入 Key，或將該 Agent 改指派給已設定 Key 的供應商（或本機 Ollama）。",
            )
            self._switch_page(1)
            return

        if self._analysis_thread is not None and self._analysis_thread.isRunning():
            QMessageBox.information(self, "分析進行中", "目前已有分析任務正在執行，請稍候或先點擊「中止」。")
            return

        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_box.clear()
        self._set_stage_highlight(1)

        self._analysis_thread = QThread()
        self._analysis_worker = AnalysisWorker(
            orchestrator=self.orchestrator,
            raw_ticker=raw_ticker,
            runtime=self.runtime_settings,
            history_years=self.years_spin.value(),
            news_lookback_days=self.lookback_spin.value(),
            force_refresh=self.force_refresh_cb.isChecked(),
        )
        self._analysis_worker.moveToThread(self._analysis_thread)

        self._analysis_thread.started.connect(self._analysis_worker.run)
        self._analysis_worker.progress.connect(self._on_analysis_progress)
        self._analysis_worker.finished.connect(self._on_analysis_finished)
        self._analysis_worker.failed.connect(self._on_analysis_failed)
        self._analysis_worker.cancelled.connect(self._on_analysis_cancelled)

        self._analysis_worker.finished.connect(self._analysis_thread.quit)
        self._analysis_worker.failed.connect(self._analysis_thread.quit)
        self._analysis_worker.cancelled.connect(self._analysis_thread.quit)
        self._analysis_thread.finished.connect(self._cleanup_analysis_thread)

        self._analysis_thread.start()

    def _cleanup_analysis_thread(self) -> None:
        if self._analysis_worker is not None:
            self._analysis_worker.deleteLater()
            self._analysis_worker = None
        if self._analysis_thread is not None:
            self._analysis_thread.deleteLater()
            self._analysis_thread = None

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._analysis_worker is not None:
            self._analysis_worker.request_cancel()
        if self._analysis_thread is not None and self._analysis_thread.isRunning():
            self._analysis_thread.quit()
            if not self._analysis_thread.wait(3000):
                self._analysis_thread.terminate()
                self._analysis_thread.wait(500)
        if self._test_thread is not None and self._test_thread.isRunning():
            self._test_thread.quit()
            if not self._test_thread.wait(3000):
                self._test_thread.terminate()
                self._test_thread.wait(500)
        super().closeEvent(event)

    def _cancel_analysis(self) -> None:
        if self._analysis_worker is not None:
            self._analysis_worker.request_cancel()
            self.status_label.setText("正在中止任務...")
            self.cancel_btn.setEnabled(False)

    def _on_analysis_progress(self, stage: int, pct: int, message: str) -> None:
        self._set_stage_highlight(stage)
        self.progress_bar.setValue(pct)
        self.status_label.setText(message)
        self.log_box.appendPlainText(f"[Stage {stage}] {message}")

    def _on_analysis_finished(self, report: FullAnalysisReport) -> None:
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._set_stage_highlight(6)
        self.progress_bar.setValue(100)
        self._display_report(report)
        self._refresh_history_list()

    def _on_analysis_failed(self, err_msg: str) -> None:
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("分析失敗")
        self.log_box.appendPlainText(f"[ERROR] {err_msg}")
        QMessageBox.critical(self, "分析執行失敗", err_msg)

    def _on_analysis_cancelled(self, msg: str) -> None:
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status_label.setText(msg)
        self.log_box.appendPlainText(f"[CANCELLED] {msg}")

    def _display_report(self, report: FullAnalysisReport) -> None:
        self.current_report = report
        self.copy_md_btn.setEnabled(True)
        self.export_md_btn.setEnabled(True)

        # Update KPI Strip
        close_val = report.stock_data.technicals.latest_close
        chg_1d = report.stock_data.technicals.change_1d_pct
        close_txt = f"{close_val:,.2f} {report.currency}" if close_val is not None else "N/A"
        if chg_1d is not None:
            close_txt += f" ({chg_1d:+.2f}%)"
        self.kpi_price["value"].setText(close_txt)  # type: ignore[attr-defined]

        self.kpi_past["value"].setText(  # type: ignore[attr-defined]
            f"{report.past_analysis.valuation_assessment} ({report.past_analysis.confidence_score:.2f})"
        )
        self.kpi_present["value"].setText(  # type: ignore[attr-defined]
            f"{report.present_analysis.overall_sentiment_score:+.2f} · {report.present_analysis.sentiment_regime}"
        )
        self.kpi_risk["value"].setText(  # type: ignore[attr-defined]
            f"{report.risk_review.overall_risk_level} · 信心 {report.risk_review.adjusted_confidence_score:.2f}"
        )

        # Render Markdown to styled HTML
        html_body = markdown.markdown(
            report.markdown_report,
            extensions=["tables", "fenced_code", "nl2br"],
        )
        self.report_browser.setHtml(REPORT_HTML_CSS + html_body)
        self._refresh_json_inspector()

    def _refresh_json_inspector(self) -> None:
        if not self.current_report:
            self.json_viewer.setPlainText("")
            return
        idx = self.json_section_combo.currentIndex()
        mapping = {
            0: self.current_report.past_analysis,
            1: self.current_report.present_analysis,
            2: self.current_report.future_analysis,
            3: self.current_report.risk_review,
            4: self.current_report.stock_data,
        }
        model_obj = mapping.get(idx, self.current_report.past_analysis)
        self.json_viewer.setPlainText(
            json.dumps(model_obj.model_dump(mode="json"), ensure_ascii=False, indent=2)
        )

    def _refresh_history_list(self) -> None:
        self.history_list.clear()
        records = self.storage.list_reports(limit=50)
        for rec in records:
            ticker = str(rec["ticker"])
            created = str(rec["created_at"])[:16]
            risk = str(rec["overall_risk_level"])
            sent = float(rec["overall_sentiment_score"])
            item = QListWidgetItem(f"{ticker}  |  情緒 {sent:+.2f}  |  風險 {risk}\n{created}")
            item.setData(Qt.UserRole, str(rec["report_id"]))
            self.history_list.addItem(item)

    def _on_history_clicked(self, item: QListWidgetItem) -> None:
        report_id = item.data(Qt.UserRole)
        if not report_id:
            return
        loaded = self.storage.load_report(str(report_id))
        if loaded:
            self._switch_page(0)
            self._display_report(loaded)
            self.status_label.setText(f"已從本機資料庫載入歷史報告：{loaded.ticker}（{loaded.created_at}）")

    def _delete_selected_history(self) -> None:
        item = self.history_list.currentItem()
        if not item:
            return
        report_id = item.data(Qt.UserRole)
        if report_id:
            self.storage.delete_report(str(report_id))
            self._refresh_history_list()

    def _copy_markdown(self) -> None:
        if not self.current_report:
            return
        QApplication.clipboard().setText(self.current_report.markdown_report)
        self.status_label.setText("已將 Markdown 報告複製到系統剪貼簿。")

    def _export_markdown(self) -> None:
        if not self.current_report:
            return
        default_name = f"{self.current_report.report_id}.md"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "匯出研究報告",
            str(Path.home() / default_name),
            "Markdown Files (*.md);;All Files (*)",
        )
        if file_path:
            Path(file_path).write_text(self.current_report.markdown_report, encoding="utf-8")
            QMessageBox.information(self, "匯出成功", f"報告已儲存至：\n{file_path}")
