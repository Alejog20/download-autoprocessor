# -*- coding: utf-8 -*-
"""
File Processor with Data Integrity Validation

Automatically monitors Downloads directory and processes files:
- CSV to XLSX conversion with encoding detection and type preservation
- ZIP and 7z archive extraction

"""
from __future__ import annotations

import logging
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import chardet
import pandas as pd
import py7zr
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import ui


@dataclass(frozen=True)
class ValidationResult:
    dimensions_match: bool
    columns_match: bool
    data_types_preserved: bool
    sample_data_match: bool

    @property
    def is_valid(self) -> bool:
        return all([
            self.dimensions_match,
            self.columns_match,
            self.data_types_preserved,
            self.sample_data_match
        ])


def setup_logging() -> None:
    log_file_path = Path.cwd() / 'file_processing.log'
    ui.setup_rich_logging(log_file_path)


def detect_file_encoding(file_path: Path, sample_size: int = 100000) -> str:
    with open(file_path, 'rb') as f:
        raw_data = f.read(sample_size)

    result = chardet.detect(raw_data)
    detected_encoding = result['encoding']
    confidence = result['confidence']

    if detected_encoding and confidence > 0.7:
        ui.logger.dim(f"Detected encoding: {detected_encoding} (confidence: {confidence:.2f})")
        return detected_encoding

    ui.logger.warning("Low confidence encoding detection. Using UTF-8 fallback.")
    return 'utf-8'


def try_parse_csv_with_strategy(
    file_path: Path,
    encoding: str,
    engine: str = 'c',
    on_bad_lines: str = 'error',
    quoting: int = 0,
    delimiter: str = ','
) -> Optional[pd.DataFrame]:
    try:
        df = pd.read_csv(
            file_path,
            encoding=encoding,
            low_memory=False,
            engine=engine,
            on_bad_lines=on_bad_lines,
            quoting=quoting,
            delimiter=delimiter
        )
        return df
    except Exception:
        return None


def read_csv_with_encoding(file_path: Path) -> Optional[pd.DataFrame]:
    import csv

    encoding = detect_file_encoding(file_path)
    encodings_to_try = [encoding, 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    encodings_to_try = list(dict.fromkeys(encodings_to_try))

    for enc in encodings_to_try:
        try:
            df = pd.read_csv(file_path, encoding=enc, low_memory=False)
            ui.logger.dim(f"Successfully read CSV with encoding: {enc}")
            return df
        except (UnicodeDecodeError, UnicodeError):
            continue
        except pd.errors.ParserError as e:
            error_msg = str(e)
            if "expected" in error_msg.lower() and "fields" in error_msg.lower():
                ui.logger.warning(f"Malformed CSV detected with {enc}: {e}")
                ui.logger.info("Attempting fallback parsing strategies...")

                strategies = [
                    ("Python engine with error skip", enc, 'python', 'skip', csv.QUOTE_MINIMAL, ','),
                    ("Python engine with error warn", enc, 'python', 'warn', csv.QUOTE_MINIMAL, ','),
                    ("C engine with QUOTE_ALL", enc, 'c', 'error', csv.QUOTE_ALL, ','),
                    ("C engine with QUOTE_NONE", enc, 'c', 'error', csv.QUOTE_NONE, ','),
                    ("Python engine with QUOTE_ALL", enc, 'python', 'warn', csv.QUOTE_ALL, ','),
                ]

                for strategy_name, *args in strategies:
                    ui.logger.dim(f"Trying: {strategy_name}")
                    df = try_parse_csv_with_strategy(file_path, *args)
                    if df is not None:
                        ui.logger.success(f"CSV parsed successfully using: {strategy_name}")
                        ui.logger.dim(f"Successfully read CSV with encoding: {enc}")
                        return df

                ui.logger.error(f"All parsing strategies failed for encoding {enc}")
                continue
            else:
                ui.logger.error(f"Error reading CSV with {enc}: {e}")
                continue
        except Exception as e:
            ui.logger.error(f"Error reading CSV with {enc}: {e}")
            continue

    ui.logger.error("Failed to read CSV with any encoding")
    return None


def preserve_numeric_precision(df: pd.DataFrame) -> pd.DataFrame:
    df_copy = df.copy()

    for col in df_copy.columns:
        if df_copy[col].dtype == 'object':
            try:
                numeric_col = pd.to_numeric(df_copy[col], errors='coerce')
                if not numeric_col.isna().all():
                    non_null_original = df_copy[col].dropna()
                    non_null_numeric = numeric_col.dropna()

                    if len(non_null_numeric) == len(non_null_original):
                        if (numeric_col.notna() & (numeric_col == numeric_col.astype(int))).all():
                            continue
                        df_copy[col] = numeric_col
            except (ValueError, TypeError):
                continue

    return df_copy


def validate_conversion(csv_path: Path, xlsx_path: Path) -> ValidationResult:
    try:
        df_csv = read_csv_with_encoding(csv_path)
        if df_csv is None:
            return ValidationResult(False, False, False, False)

        df_xlsx = pd.read_excel(xlsx_path)

        dimensions_match = df_csv.shape == df_xlsx.shape
        columns_match = list(df_csv.columns) == list(df_xlsx.columns)

        data_types_preserved = True
        for col in df_csv.columns:
            csv_dtype = df_csv[col].dtype
            xlsx_dtype = df_xlsx[col].dtype

            if csv_dtype != xlsx_dtype:
                if not (pd.api.types.is_numeric_dtype(csv_dtype) and
                       pd.api.types.is_numeric_dtype(xlsx_dtype)):
                    data_types_preserved = False
                    ui.logger.warning(f"Type change in column '{col}': {csv_dtype} -> {xlsx_dtype}")

        sample_data_match = True
        if len(df_csv) > 0:
            sample_size = min(5, len(df_csv))
            for i in range(sample_size):
                for col in df_csv.columns:
                    csv_val = df_csv.iloc[i][col]
                    xlsx_val = df_xlsx.iloc[i][col]

                    if pd.isna(csv_val) and pd.isna(xlsx_val):
                        continue

                    if pd.api.types.is_numeric_dtype(type(csv_val)) and pd.api.types.is_numeric_dtype(type(xlsx_val)):
                        if abs(float(csv_val) - float(xlsx_val)) > 1e-6:
                            sample_data_match = False
                            ui.logger.warning(f"Data mismatch at row {i}, col '{col}': {csv_val} != {xlsx_val}")
                    elif str(csv_val) != str(xlsx_val):
                        sample_data_match = False
                        ui.logger.warning(f"Data mismatch at row {i}, col '{col}': {csv_val} != {xlsx_val}")

        return ValidationResult(
            dimensions_match=dimensions_match,
            columns_match=columns_match,
            data_types_preserved=data_types_preserved,
            sample_data_match=sample_data_match
        )

    except Exception as e:
        ui.logger.error(f"Validation error: {e}")
        return ValidationResult(False, False, False, False)


def process_csv_file(file_path: Path) -> bool:
    try:
        ui.display_processing_start(file_path.name, "CSV")
        xlsx_path = file_path.with_suffix(".xlsx")

        df = read_csv_with_encoding(file_path)
        if df is None:
            return False

        if df.empty:
            ui.logger.warning(f"CSV file {file_path.name} is empty. Skipping conversion.")
            return False

        ui.logger.info(f"CSV dimensions: {df.shape[0]} rows x {df.shape[1]} columns")

        df_processed = preserve_numeric_precision(df)

        with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
            df_processed.to_excel(writer, index=False, float_format='%.15g')

        ui.logger.success(f"Converted to: {xlsx_path.name}")

        validation = validate_conversion(file_path, xlsx_path)

        ui.display_validation_result(
            validation.is_valid,
            validation.dimensions_match,
            validation.columns_match,
            validation.data_types_preserved,
            validation.sample_data_match
        )

        if validation.is_valid:
            file_path.unlink()
            ui.logger.dim(f"Removed original CSV file: {file_path.name}")
            return True
        else:
            ui.logger.error("Keeping original CSV file due to validation failure")
            return False

    except Exception as e:
        ui.logger.error(f"Failed to process {file_path.name}. Error: {e}")
        return False


def process_zip_file(file_path: Path, extract_to_path: Path) -> bool:
    try:
        ui.display_processing_start(file_path.name, "ZIP")
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            extracted_files = zip_ref.namelist()
            zip_ref.extractall(extract_to_path)
        ui.logger.success(f"Decompressed {file_path.name} to {extract_to_path}")
        return True
    except zipfile.BadZipFile:
        ui.logger.error(f"Failed to decompress {file_path.name}. Not a valid ZIP archive.")
        return False
    except Exception as e:
        ui.logger.error(f"Failed to decompress {file_path.name}. Error: {e}")
        return False


def process_7z_file(file_path: Path, extract_to_path: Path) -> bool:
    try:
        ui.display_processing_start(file_path.name, "7z")
        with py7zr.SevenZipFile(file_path, mode='r') as z:
            z.extractall(path=extract_to_path)
        ui.logger.success(f"Decompressed {file_path.name} to {extract_to_path}")
        return True
    except py7zr.exceptions.Bad7zFile:
        ui.logger.error(f"Failed to decompress {file_path.name}. Not a valid 7z archive.")
        return False
    except Exception as e:
        ui.logger.error(f"Failed to decompress {file_path.name}. Error: {e}")
        return False


class DownloadHandler(FileSystemEventHandler):

    def process_file(self, file_path: Path) -> None:
        ui.logger.dim(f"Waiting 3 seconds before processing {file_path.name}...")
        time.sleep(3)

        if not file_path.exists():
            ui.logger.dim(f"{file_path.name} no longer exists. Skipping.")
            return

        if file_path.suffix.lower() in ['.tmp', '.crdownload', '.part']:
            ui.logger.dim(f"Ignoring temporary file: {file_path.name}")
            return

        suffix = file_path.suffix.lower()
        downloads_path = file_path.parent

        match suffix:
            case '.csv':
                process_csv_file(file_path)
            case '.zip':
                process_zip_file(file_path, downloads_path)
            case '.7z':
                process_7z_file(file_path, downloads_path)
            case _:
                ui.logger.dim(f"File type '{suffix}' not supported. Skipping {file_path.name}.")

    def on_created(self, event) -> None:
        if not event.is_directory:
            ui.logger.highlight(f"File detected: {Path(event.src_path).name}")
            self.process_file(Path(event.src_path))

    def on_moved(self, event) -> None:
        if not event.is_directory:
            ui.logger.highlight(f"File detected: {Path(event.dest_path).name}")
            self.process_file(Path(event.dest_path))


def main() -> None:
    ui.display_banner()
    setup_logging()

    downloads_path = Path.home() / "Downloads"
    if not downloads_path.is_dir():
        ui.logger.error(f"Downloads directory not found at: {downloads_path}. Exiting.")
        sys.exit(1)

    ui.display_startup_info(downloads_path)

    event_handler = DownloadHandler()
    observer = Observer()
    observer.schedule(event_handler, str(downloads_path), recursive=False)

    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        ui.display_shutdown()
    observer.join()


if __name__ == "__main__":
    main()