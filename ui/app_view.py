import customtkinter as ctk
from services.prefs import Preferences
from services.experiment_sender import send_experiment
from pathlib import Path
from ui.mongo_view import MongoSection
from ui.minio_view import MinioSection
from ui.experiment_view import ExperimentSection
import threading


class AppView(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AltarSender")
        # Window size will adapt to content via fit_to_content()
        # Start wider by default
        try:
            self.geometry("1200x800")
        except Exception:
            pass

        # Prefs (sauvegarde/restauration)
        self.prefs = Preferences()

        # --- ROOT GRID ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- SCROLLABLE FRAME ---
        frm = ctk.CTkScrollableFrame(self, corner_radius=12, height=700, fg_color="transparent")
        frm.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        # keep a reference to adjust height dynamically on resize
        self.content_frame = frm
        frm.grid_columnconfigure(0, weight=1)
        frm.grid_columnconfigure(1, weight=2)

        # Left stack: Mongo (top) then MinIO (bottom)
        self.mongo_section = MongoSection(frm, on_save=self.save_prefs, on_change=lambda: self.after(10, self.fit_to_content))
        self.mongo_section.grid(row=0, column=0, sticky="nsew", padx=12, pady=(8, 8))

        # --- EXPERIMENT FILES SECTION ---
        self.exp_section = ExperimentSection(
            frm,
            on_change=lambda: self.after(0, self.fit_to_content),
            on_send=self._on_send_experiment,
        )
        self.exp_section.grid(row=0, column=1, rowspan=20, sticky="nsew", padx=12, pady=(8, 8))

        # --- MINIO SECTION (below Mongo on the left) ---
        self.minio_section = MinioSection(frm, on_save=self.save_prefs, on_change=lambda: self.after(10, self.fit_to_content))
        self.minio_section.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 8))

        # (button and status are now inside ExperimentSection)

        # Charger préférences + hook fermeture
        self.load_prefs()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        # Fit window to the current content
        self.after(50, self.fit_to_content)

    # --- HELPERS ---
    def toggle_uri(self):
        # Deprecated: handled inside MongoSection
        pass

    # --- Prefs ---
    def prefs_dict(self):
        data = {}
        data.update(self.mongo_section.get_prefs())
        data.update(self.exp_section.get_prefs())
        data.update(self.minio_section.get_prefs())
        return data

    def save_prefs(self):
        data = self.prefs_dict()
        self.prefs.save_without_password(data)
        # mot de passe via keyring si demandé (Mongo)
        self.prefs.save_password_if_allowed(
            remember=bool(data.get("remember_pwd")),
            user=data.get("user") or "default",
            password=self.mongo_section.get_password()
        )
        # minio secret via keyring
        minio_user_key = f"minio:{(data.get('minio_access_key') or 'default')}@{(data.get('minio_endpoint') or 'localhost')}"
        self.prefs.save_password_if_allowed(
            remember=bool(data.get("remember_minio", 0)),
            user=minio_user_key,
            password=self.minio_section.get_secret()
        )

    def load_prefs(self):
        data = self.prefs.load()
        # delegate to sections
        self.mongo_section.set_prefs(data, password_loader=lambda user: self.prefs.load_password_if_any(user=user))
        self.exp_section.set_prefs(data)
        # ensure experiment cards render on launch
        try:
            self.exp_section.render_details_sections()
        except Exception:
            pass
        self.minio_section.set_prefs(data, password_loader=lambda user: self.prefs.load_password_if_any(user=user))
        self.after(10, self.fit_to_content)

    # --- Send experiment handler ---
    def _on_send_experiment(self):
        try:
            # persist current values first
            self.save_prefs()
        except Exception:
            pass
        # aggregate data
        data = self.prefs_dict()
        # Build structured payload with selectors grouped under experiment
        payload = {
            "mongo": {
                "use_uri": data.get("use_uri", 0),
                "uri": data.get("uri", ""),
                "host": data.get("host", ""),
                "port": data.get("port", ""),
                "user": data.get("user", ""),
                "db": data.get("db", ""),
                "tls": data.get("tls", 0),
                "password": self.mongo_section.get_password(),
            },
            "minio": {
                "endpoint": data.get("minio_endpoint", ""),
                "access_key": data.get("minio_access_key", ""),
                "tls": data.get("minio_tls", 0),
                "secret_key": self.minio_section.get_secret(),
                "bucket": data.get("minio_bucket", ""),
            },
            "experiment": {
                "folder": data.get("experiment_folder", ""),
                "name": data.get("experiment_name", ""),
                "folders": data.get("experiment_folders", []),
                "selectors": {
                    "config": {
                        "name": data.get("config_name", ""),
                        "sheet": data.get("config_sheet", ""),
                        "options": {
                            "flatten": data.get("config_flatten", 0),
                            "sep": data.get("config_sep", ","),
                        },
                    },
                    "metrics": {
                        "name": data.get("metrics_name", ""),
                        "sheet": data.get("metrics_sheet", ""),
                        "options": {
                            "header": data.get("metrics_header", 0),
                            "has_time": data.get("metrics_has_time", 0),
                            "time_col": data.get("metrics_time_col", ""),
                            "selected_cols": data.get("metrics_selected_cols", []),
                            "sep": data.get("metrics_sep", ","),
                        },
                    },
                    "results": {
                        "name": data.get("results_name", ""),
                        "sheet": data.get("results_sheet", ""),
                        "options": {
                            "sep": data.get("results_sep", ","),
                        },
                    },
                    "raw_data": {
                        "name": data.get("raw_data_name", ""),
                        "files": data.get("raw_data_files", []),
                        "options": {
                            "send_minio": data.get("raw_data_send_minio", 1),
                            "save_locally": data.get("raw_data_save_locally", 0),
                            "local_path": data.get("raw_data_local_path", ""),
                        },
                    },
                    "artifacts": {
                        "name": data.get("artifacts_name", ""),
                        "files": data.get("artifacts_files", []),
                    },
                },
            },
        }

        # produce payload and call service (non-blocking)
        try:
            try:
                self.exp_section.send_status.configure(text="Sending experiment…")
            except Exception:
                pass
            try:
                # disable button to avoid double-clicks
                self.exp_section.send_btn.configure(state="disabled")
            except Exception:
                pass

            def _worker():
                res = None
                err = None
                try:
                    res = send_experiment(payload)
                except Exception as e:
                    err = e

                def _update_ui():
                    try:
                        if err is not None:
                            self.exp_section.send_status.configure(text=f"❌ Error: {err.__class__.__name__}: {err}")
                        else:
                            if isinstance(res, dict) and res.get("ok"):
                                self.exp_section.send_status.configure(text=f"✅ {res.get('message', 'OK')}")
                            else:
                                msg = (res.get("message") if isinstance(res, dict) else str(res)) or "Failed"
                                self.exp_section.send_status.configure(text=f"❌ {msg}")
                    except Exception:
                        pass
                    finally:
                        try:
                            self.exp_section.send_btn.configure(state="normal")
                        except Exception:
                            pass
                        self.after(10, self.fit_to_content)

                self.after(0, _update_ui)

            threading.Thread(target=_worker, daemon=True).start()
        except Exception as e:
            try:
                self.exp_section.send_status.configure(text=f"❌ Error: {e.__class__.__name__}: {e}")
            except Exception:
                pass
            try:
                self.exp_section.send_btn.configure(state="normal")
            except Exception:
                pass
        self.after(10, self.fit_to_content)

    def on_close(self):
        # Sauvegarde avant sortie
        self.save_prefs()
        self.destroy()

    # --- Window sizing helper ---
    def fit_to_content(self):
        try:
            self.update_idletasks()
            req_w = self.winfo_reqwidth()
            req_h = self.winfo_reqheight()
            # widen default clamps
            min_w, max_w = 1200, 1800
            min_h, max_h = 800, 1000
            new_w = max(min(req_w, max_w), min_w)
            new_h = max(min(req_h, max_h), min_h)
            self.minsize(min_w, min_h)
            self.geometry(f"{new_w}x{new_h}")
            # adjust scrollable frame height so it doesn't reserve extra space
            try:
                self.content_frame.configure(height=max(min_h - 40, 400))
            except Exception:
                pass
        except Exception:
            pass

