import pandas as pd
import numpy as np
import json
import os
from services.hash import make_compact_uid_b32
import re


def coerce_bool_option(value):
    if value == 0:
        return None
    else:
        return 0


def format_config(experiment_folder, config):
    # Return empty dict if no config file is selected
    config_name = config.get("name", "None") if isinstance(config, dict) else "None"
    if not config_name or config_name == "None":
        return {}
    
    file_path = os.path.join(experiment_folder, config_name)
    config_type = config_name.split(".")[-1]
    
    if config_type == "json":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if config.get("options", {}).get("flatten"):
            data = pd.json_normalize(data, sep="_").to_dict(orient="records")[0]
    elif config_type == "xlsx" or config_type == "xlsm":
        data = pd.read_excel(file_path, sheet_name=config.get("sheet")).to_dict(orient="records")
    elif config_type == "csv":
        sep = (config.get("options", {}) or {}).get("sep", ",")
        sep = "\t" if sep == "\\t" else sep
        data = pd.read_csv(file_path, sep=sep).to_dict(orient="records")
    else:
        raise ValueError(f"Unsupported config type: {config_type}")
    
    return data


def format_metrics(experiment_folder, metrics):
    metrics_data = {}
    metrics_name = metrics.get("name", "None") if isinstance(metrics, dict) else "None"
    if metrics_name and metrics_name != "None":
        file_path = os.path.join(experiment_folder, metrics_name)
        metrics_type = metrics_name.split(".")[-1]
        # determine header handling once
        header_arg = coerce_bool_option(metrics.get("options", {}).get("header", 0))
        if metrics_type == "xlsx" or metrics_type == "xlsm":
            df = pd.read_excel(
                file_path,
                sheet_name=metrics.get("sheet"),
                header=header_arg,
            )
        elif metrics_type == "csv":
            # respect configured separator for metrics CSV
            sep = (metrics.get("options", {}) or {}).get("sep", ",")
            # handle both escaped and real tab characters
            sep = "\t" if sep in ("\\t", "\t") else sep
            df = pd.read_csv(file_path, header=header_arg, sep=sep)
        else:
            raise ValueError(f"Unsupported metrics type: {metrics_type}")

        metrics_columns = {}

        options = metrics.get("options", {}) or {}
        selected_cols = options.get("selected_cols", []) or []
        has_time = 1 if options.get("has_time", 0) == 1 else 0
        time_col_name = options.get("time_col", "")

        # when no header, pandas will use integer column indices; UI sends strings
        def _normalize_col_key(name):
            if header_arg is None:  # no header
                try:
                    return int(name)
                except Exception:
                    return name
            return name

        # set x_axis if requested (do this regardless of it being in selected columns)
        if has_time and time_col_name != "":
            time_key = _normalize_col_key(time_col_name)
            if time_key in df.columns:
                metrics_data["x_axis"] = df[time_key].to_list()

        for col in selected_cols:
            col_key = _normalize_col_key(col)
            if col_key in df.columns:
                metrics_columns[col] = df[col_key].to_list()

        metrics_data["columns"] = metrics_columns

    return metrics_data


def format_results(experiment_folder, results):
    results_data = {}
    results_name = results.get("name", "None") if isinstance(results, dict) else "None"
    if results_name and results_name != "None":
        file_path = os.path.join(experiment_folder, results_name)
        results_type = results_name.split(".")[-1]
        if results_type == "xlsx" or results_type == "xlsm":
            data_ = pd.read_excel(file_path, sheet_name=results.get("sheet"), header=None).to_dict(orient="records")
            data = {e[0]: e[1] for e in data_}

        elif results_type == "csv":
            sep = (results.get("options", {}) or {}).get("sep", ",")
            sep = "\t" if sep == "\\t" else sep
            data_ = pd.read_csv(file_path, sep=sep, header=None).to_dict(orient="records")
            data = {e[0]: e[1] for e in data_}

        elif results_type == "json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            raise ValueError(f"Unsupported results type: {results_type}")
        
        results_data = {}

        for k, v in data.items():
            results_data[k] = v

    return results_data


def format_raw_data(experiment_folder, raw_data):
    files = {}
    raw_data_name = raw_data.get("name", "None") if isinstance(raw_data, dict) else "None"
    if raw_data_name and raw_data_name != "None":
        experiment_name = experiment_folder.split("/")[-1]
        file_path = os.path.join(experiment_folder, raw_data_name)
        if os.path.isfile(file_path):
            file = {
                'source_path': file_path,
                'new_name': make_compact_uid_b32(experiment_name) + "-" + raw_data_name,
                'minio_folder':  raw_data_name.split(".")[0],
            }
            files[raw_data_name] = file

        elif os.path.isdir(file_path):
            for f in raw_data.get("files", []):
                file = {
                    'source_path': os.path.join(file_path, f),
                    'new_name': make_compact_uid_b32(experiment_name) + "-" + f,
                    'minio_folder':  f.split(".")[0],
                }
                files[f] = file
        else:
            raise ValueError(f"Raw data file or folder not found: {file_path}")

    return files