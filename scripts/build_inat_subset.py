from __future__ import annotations

import argparse
import csv
import ctypes
import os
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.common import (
    ALLOWED_LICENSES,
    ensure_parent,
    load_species_manifest,
    manifest_lookup_rows,
    point_in_poland,
)

EUROPE_BOUNDS = {
    "min_lat": 34.0,
    "max_lat": 73.0,
    "min_lon": -32.0,
    "max_lon": 45.0,
}

POLAND_BOUNDS = {
    "min_lon": 14.05,
    "max_lon": 24.25,
    "min_lat": 49.0,
    "max_lat": 55.05,
}


@dataclass(frozen=True)
class Candidate:
    label_id: str
    kingdom: str
    scientific_name: str
    polish_name: str
    english_name: str
    photo_id: str
    observation_id: str
    observer_id: str
    license_code: str
    photographer: str
    image_url: str
    source_url: str
    latitude: float
    longitude: float
    country_code: str
    is_poland: bool


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def detect_total_ram_gb() -> float | None:
    try:
        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
            return None
        return status.ullTotalPhys / (1024**3)
    except Exception:
        return None


def default_threads() -> int:
    logical_cpus = os.cpu_count() or 8
    if logical_cpus >= 20:
        return min(logical_cpus - 4, 20)
    if logical_cpus >= 12:
        return logical_cpus - 2
    return max(4, logical_cpus)


def default_memory_limit_gb() -> int:
    total_ram_gb = detect_total_ram_gb()
    if total_ram_gb is None:
        return 16
    return max(12, min(int(total_ram_gb * 0.45), 32))


def default_download_workers() -> int:
    logical_cpus = os.cpu_count() or 8
    return max(8, min(logical_cpus, 24))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a NaturaVision training subset from iNaturalist metadata.")
    parser.add_argument("--metadata-dir", type=Path, required=True, help="Directory with iNaturalist metadata files.")
    parser.add_argument("--species-manifest", type=Path, required=True, help="Taxonomy manifest CSV.")
    parser.add_argument("--output-dir", type=Path, default=Path("data"), help="Output directory root.")
    parser.add_argument("--cache-dir", type=Path, default=None, help="Directory for the DuckDB cache and temp files.")
    parser.add_argument(
        "--image-root",
        type=Path,
        default=None,
        help="Directory for downloaded images. Defaults to a fast local folder next to the metadata.",
    )
    parser.add_argument("--target-pool-per-label", type=int, default=450, help="Raw pool size per known label.")
    parser.add_argument("--unknown-pool-size", type=int, default=3200, help="Raw pool size for unknown examples.")
    parser.add_argument("--seed", type=int, default=23, help="Random seed for deterministic sampling.")
    parser.add_argument("--max-retries", type=int, default=3, help="HTTP retries per image.")
    parser.add_argument("--timeout-seconds", type=int, default=60, help="HTTP timeout per image.")
    parser.add_argument("--threads", type=int, default=default_threads(), help="DuckDB worker threads.")
    parser.add_argument(
        "--memory-limit-gb",
        type=int,
        default=default_memory_limit_gb(),
        help="DuckDB memory limit in gigabytes.",
    )
    parser.add_argument(
        "--download-workers",
        type=int,
        default=default_download_workers(),
        help="Parallel image downloads.",
    )
    parser.add_argument(
        "--known-poland-cap",
        type=int,
        default=1500,
        help="Maximum pre-photo Polish observation candidates per target label.",
    )
    parser.add_argument(
        "--known-europe-cap",
        type=int,
        default=2500,
        help="Maximum pre-photo non-Polish European observation candidates per target label.",
    )
    parser.add_argument(
        "--unknown-poland-cap",
        type=int,
        default=12000,
        help="Maximum pre-photo Polish unknown candidates.",
    )
    parser.add_argument(
        "--unknown-europe-cap",
        type=int,
        default=30000,
        help="Maximum pre-photo non-Polish European unknown candidates.",
    )
    return parser.parse_args()


def print_stage(message: str) -> None:
    print(message, flush=True)


def require_duckdb():
    try:
        import duckdb  # type: ignore
    except ImportError as exc:
        raise SystemExit("duckdb is required. Install it with: pip install -r requirements-data.txt") from exc
    return duckdb


def escape_sql(value: str) -> str:
    return value.replace("'", "''")


def metadata_relation(path: Path) -> str:
    escaped = escape_sql(str(path))
    return f"read_csv_auto('{escaped}', header=true, all_varchar=true, sample_size=4096, ignore_errors=true)"


def find_metadata_file(metadata_dir: Path, stem: str) -> Path:
    patterns = (
        f"{stem}.csv",
        f"{stem}.csv.gz",
        f"{stem}.tsv",
        f"{stem}.tsv.gz",
        f"{stem}.parquet",
        f"{stem}-*.csv",
        f"{stem}-*.csv.gz",
        f"{stem}-*.parquet",
    )
    for pattern in patterns:
        matches = sorted(metadata_dir.glob(pattern))
        if matches:
            return matches[0]
    for pattern in patterns:
        matches = sorted(metadata_dir.rglob(pattern))
        if matches:
            return matches[0]
    raise FileNotFoundError(f"Could not find a metadata file for '{stem}' in {metadata_dir}")


def choose_cache_dir(args: argparse.Namespace) -> Path:
    if args.cache_dir is not None:
        return args.cache_dir
    return args.metadata_dir / "_natura_cache"


def choose_image_root(args: argparse.Namespace) -> Path:
    if args.image_root is not None:
        return args.image_root
    return args.metadata_dir / "raw_cache"


def reset_duckdb_files(db_path: Path) -> None:
    for candidate in (db_path, db_path.with_suffix(db_path.suffix + ".wal"), db_path.with_suffix(".tmp")):
        if candidate.exists():
            candidate.unlink()


def configure_duckdb(connection, args: argparse.Namespace, temp_dir: Path) -> None:
    temp_dir.mkdir(parents=True, exist_ok=True)
    connection.execute(f"PRAGMA threads={args.threads}")
    connection.execute(f"SET memory_limit='{args.memory_limit_gb}GB'")
    connection.execute(f"SET temp_directory='{escape_sql(str(temp_dir))}'")
    connection.execute("SET preserve_insertion_order=false")


def create_manifest_table(connection, manifest_path: Path) -> list:
    entries = load_species_manifest(manifest_path)
    connection.execute(
        """
        CREATE OR REPLACE TEMP TABLE manifest (
            label_id VARCHAR,
            kingdom VARCHAR,
            scientific_name VARCHAR,
            polish_name VARCHAR,
            english_name VARCHAR
        )
        """
    )
    connection.executemany(
        "INSERT INTO manifest VALUES (?, ?, ?, ?, ?)",
        [
            (
                entry.label_id,
                entry.kingdom,
                entry.scientific_name,
                entry.polish_name,
                entry.english_name,
            )
            for entry in entries
        ],
    )
    connection.execute(
        """
        CREATE OR REPLACE TEMP TABLE manifest_lookup (
            label_id VARCHAR,
            kingdom VARCHAR,
            scientific_name VARCHAR,
            polish_name VARCHAR,
            english_name VARCHAR
        )
        """
    )
    connection.executemany(
        "INSERT INTO manifest_lookup VALUES (?, ?, ?, ?, ?)",
        manifest_lookup_rows(entries),
    )
    return entries


def normalized_license_sql(raw_expr: str) -> str:
    normalized = (
        "LOWER(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE("
        + raw_expr
        + ", ''), 'creative commons', 'cc'), 'creativecommons', 'cc'), '_', '-'), ' ', ''))"
    )
    return f"""
    CASE
      WHEN {normalized} = '' THEN NULL
      WHEN {normalized} LIKE 'cc0%' OR {normalized} = 'publicdomain' THEN 'CC0'
      WHEN {normalized} LIKE 'cc-by-nc%' OR {normalized} IN ('cc-bync', 'ccbync') THEN 'CC-BY-NC'
      WHEN {normalized} LIKE 'cc-by%' OR {normalized} IN ('by', 'ccby') THEN 'CC-BY'
      ELSE NULL
    END
    """


def build_taxa_lookup(connection, taxa_path: Path) -> None:
    taxa_relation = metadata_relation(taxa_path)
    print_stage("Stage 1/5: building taxon lookup...")
    connection.execute(
        f"""
        CREATE OR REPLACE TABLE taxa_lookup AS
        WITH raw AS (
          SELECT
            CAST(taxon_id AS VARCHAR) AS taxon_id,
            COALESCE(name, '') AS scientific_name,
            CASE
              WHEN ('/' || COALESCE(ancestry, '') || '/') LIKE '%/47170/%' OR CAST(taxon_id AS VARCHAR) = '47170' THEN 'fungi'
              WHEN ('/' || COALESCE(ancestry, '') || '/') LIKE '%/47126/%' OR CAST(taxon_id AS VARCHAR) = '47126' THEN 'plants'
              ELSE NULL
            END AS kingdom
          FROM {taxa_relation}
        )
        SELECT
          raw.taxon_id,
          raw.scientific_name,
          raw.kingdom,
          manifest_lookup.label_id,
          manifest_lookup.polish_name,
          manifest_lookup.english_name
        FROM raw
        LEFT JOIN manifest_lookup
          ON LOWER(raw.scientific_name) = LOWER(manifest_lookup.scientific_name)
        WHERE raw.kingdom IS NOT NULL
        """
    )
    stats = connection.execute(
        """
        SELECT
          SUM(CASE WHEN label_id IS NOT NULL THEN 1 ELSE 0 END) AS target_taxa,
          COUNT(*) AS all_taxa
        FROM taxa_lookup
        """
    ).fetchone()
    print_stage(f"  Taxa lookup ready: {stats[0]} target taxa, {stats[1]} plant/fungi taxa")


def build_observation_candidates(connection, observation_path: Path) -> None:
    observation_relation = metadata_relation(observation_path)
    print_stage("Stage 2/5: filtering candidate observations across Europe...")
    connection.execute(
        f"""
        CREATE OR REPLACE TABLE observation_candidates AS
        WITH raw AS (
          SELECT
            CAST(observation_uuid AS VARCHAR) AS observation_id,
            COALESCE(CAST(observer_id AS VARCHAR), 'unknown_observer') AS observer_id,
            CAST(taxon_id AS VARCHAR) AS taxon_id,
            LOWER(COALESCE(quality_grade, '')) AS quality_grade,
            TRY_CAST(latitude AS DOUBLE) AS latitude,
            TRY_CAST(longitude AS DOUBLE) AS longitude
          FROM {observation_relation}
        )
        SELECT
          raw.observation_id,
          raw.observer_id,
          lookup.taxon_id,
          lookup.scientific_name,
          lookup.kingdom,
          lookup.label_id,
          COALESCE(lookup.polish_name, 'nieznane') AS polish_name,
          COALESCE(lookup.english_name, 'unknown') AS english_name,
          raw.latitude,
          raw.longitude,
          CASE
            WHEN raw.longitude BETWEEN {POLAND_BOUNDS['min_lon']} AND {POLAND_BOUNDS['max_lon']}
             AND raw.latitude BETWEEN {POLAND_BOUNDS['min_lat']} AND {POLAND_BOUNDS['max_lat']}
            THEN TRUE
            ELSE FALSE
          END AS is_poland
        FROM raw
        JOIN taxa_lookup lookup
          ON raw.taxon_id = lookup.taxon_id
        WHERE raw.latitude IS NOT NULL
          AND raw.longitude IS NOT NULL
          AND raw.latitude BETWEEN {EUROPE_BOUNDS['min_lat']} AND {EUROPE_BOUNDS['max_lat']}
          AND raw.longitude BETWEEN {EUROPE_BOUNDS['min_lon']} AND {EUROPE_BOUNDS['max_lon']}
          AND raw.quality_grade IN ('research', 'research grade', 'needs_id', 'needs id', 'verifiable')
        """
    )
    stats = connection.execute(
        """
        SELECT
          SUM(CASE WHEN label_id IS NOT NULL THEN 1 ELSE 0 END) AS known_rows,
          SUM(CASE WHEN label_id IS NULL THEN 1 ELSE 0 END) AS unknown_rows
        FROM observation_candidates
        """
    ).fetchone()
    print_stage(f"  Observation candidates ready: {int(stats[0] or 0)} known, {int(stats[1] or 0)} unknown")


def build_observation_pool(connection, args: argparse.Namespace) -> None:
    print_stage("Stage 3/5: sampling a manageable observation pool for this machine...")
    connection.execute(
        f"""
        CREATE OR REPLACE TABLE observation_pool AS
        WITH known_ranked AS (
          SELECT
            observation_id,
            observer_id,
            taxon_id,
            scientific_name,
            kingdom,
            label_id,
            polish_name,
            english_name,
            latitude,
            longitude,
            is_poland,
            ROW_NUMBER() OVER (PARTITION BY label_id, is_poland ORDER BY hash(observation_id)) AS rn
          FROM observation_candidates
          WHERE label_id IS NOT NULL
        ),
        unknown_ranked AS (
          SELECT
            observation_id,
            observer_id,
            taxon_id,
            scientific_name,
            kingdom,
            latitude,
            longitude,
            is_poland,
            ROW_NUMBER() OVER (PARTITION BY is_poland ORDER BY hash(observation_id)) AS rn
          FROM observation_candidates
          WHERE label_id IS NULL
        )
        SELECT
          observation_id,
          observer_id,
          taxon_id,
          scientific_name,
          kingdom,
          label_id,
          polish_name,
          english_name,
          latitude,
          longitude,
          is_poland
        FROM known_ranked
        WHERE (is_poland AND rn <= {args.known_poland_cap})
           OR ((NOT is_poland) AND rn <= {args.known_europe_cap})
        UNION ALL
        SELECT
          observation_id,
          observer_id,
          taxon_id,
          scientific_name,
          kingdom,
          'unknown' AS label_id,
          'nieznane' AS polish_name,
          'unknown' AS english_name,
          latitude,
          longitude,
          is_poland
        FROM unknown_ranked
        WHERE (is_poland AND rn <= {args.unknown_poland_cap})
           OR ((NOT is_poland) AND rn <= {args.unknown_europe_cap})
        """
    )
    connection.execute("DROP TABLE observation_candidates")
    pool_count = connection.execute("SELECT COUNT(*) FROM observation_pool").fetchone()[0]
    print_stage(f"  Observation pool ready: {pool_count} rows")


def build_photos_best(connection, photo_path: Path) -> None:
    photo_relation = metadata_relation(photo_path)
    license_sql = normalized_license_sql("raw.license_raw")
    print_stage("Stage 4/5: scanning photos only for the sampled observation pool...")
    connection.execute(
        f"""
        CREATE OR REPLACE TABLE photos_best AS
        WITH raw AS (
          SELECT
            CAST(observation_uuid AS VARCHAR) AS observation_id,
            CAST(photo_id AS VARCHAR) AS photo_id,
            LOWER(COALESCE(extension, '')) AS extension,
            COALESCE(license, '') AS license_raw,
            COALESCE(CAST(observer_id AS VARCHAR), '') AS photographer,
            TRY_CAST(position AS INTEGER) AS position
          FROM {photo_relation}
        ),
        ranked AS (
          SELECT
            raw.observation_id,
            raw.photo_id,
            raw.extension,
            {license_sql} AS license_code,
            raw.photographer,
            ROW_NUMBER() OVER (
              PARTITION BY raw.observation_id
              ORDER BY COALESCE(raw.position, 2147483647), TRY_CAST(raw.photo_id AS BIGINT) NULLS LAST, raw.photo_id
            ) AS rn
          FROM raw
          JOIN observation_pool pool
            ON raw.observation_id = pool.observation_id
          WHERE raw.extension <> ''
        )
        SELECT
          observation_id,
          photo_id,
          license_code,
          photographer,
          'https://inaturalist-open-data.s3.amazonaws.com/photos/' || photo_id || '/large.' || extension AS image_url,
          'https://www.inaturalist.org/photos/' || photo_id AS source_url
        FROM ranked
        WHERE rn = 1
          AND license_code IN ('CC0', 'CC-BY', 'CC-BY-NC')
        """
    )
    photo_count = connection.execute("SELECT COUNT(*) FROM photos_best").fetchone()[0]
    print_stage(f"  Photo pool ready: {photo_count} observation-photo pairs")


def fetch_candidates(connection) -> list[Candidate]:
    rows = connection.execute(
        """
        SELECT
          pool.label_id,
          pool.kingdom,
          pool.scientific_name,
          pool.polish_name,
          pool.english_name,
          photos.photo_id,
          pool.observation_id,
          pool.observer_id,
          photos.license_code,
          COALESCE(NULLIF(photos.photographer, ''), pool.observer_id) AS photographer,
          photos.image_url,
          photos.source_url,
          pool.latitude,
          pool.longitude,
          '' AS country_code,
          pool.is_poland
        FROM observation_pool pool
        JOIN photos_best photos USING (observation_id)
        """
    ).fetchall()
    return [
        Candidate(
            label_id=row[0],
            kingdom=row[1],
            scientific_name=row[2],
            polish_name=row[3],
            english_name=row[4],
            photo_id=row[5],
            observation_id=row[6],
            observer_id=row[7],
            license_code=row[8],
            photographer=row[9],
            image_url=row[10],
            source_url=row[11],
            latitude=float(row[12]),
            longitude=float(row[13]),
            country_code=row[14],
            is_poland=bool(row[15]),
        )
        for row in rows
    ]


def load_candidates(args: argparse.Namespace) -> list[Candidate]:
    duckdb = require_duckdb()
    cache_dir = choose_cache_dir(args)
    temp_dir = cache_dir / "tmp"
    db_path = cache_dir / "inat_subset.duckdb"

    cache_dir.mkdir(parents=True, exist_ok=True)
    reset_duckdb_files(db_path)

    observation_path = find_metadata_file(args.metadata_dir, "observations")
    photo_path = find_metadata_file(args.metadata_dir, "photos")
    taxa_path = find_metadata_file(args.metadata_dir, "taxa")

    connection = duckdb.connect(database=str(db_path))
    try:
        configure_duckdb(connection, args, temp_dir)
        create_manifest_table(connection, args.species_manifest)
        build_taxa_lookup(connection, taxa_path)
        build_observation_candidates(connection, observation_path)
        build_observation_pool(connection, args)
        build_photos_best(connection, photo_path)
        print_stage("Stage 5/5: materializing candidate rows for final per-class selection...")
        candidates = fetch_candidates(connection)
        print_stage(f"  Final candidate rows with downloadable images: {len(candidates)}")
        return candidates
    finally:
        connection.close()


def select_candidates(
    candidates: list[Candidate],
    target_label_ids: list[str],
    target_pool_per_label: int,
    unknown_pool_size: int,
    seed: int,
) -> tuple[list[Candidate], dict[str, int]]:
    import random

    rng = random.Random(seed)
    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.label_id].append(candidate)

    shortages: dict[str, int] = {}
    selected: list[Candidate] = []
    for label_id in target_label_ids + ["unknown"]:
        quota = target_pool_per_label if label_id != "unknown" else unknown_pool_size
        bucket = grouped.get(label_id, [])
        poland = [row for row in bucket if row.is_poland]
        europe = [row for row in bucket if not row.is_poland]
        rng.shuffle(poland)
        rng.shuffle(europe)

        observer_counts: dict[str, int] = defaultdict(int)
        used_observations: set[str] = set()
        chosen: list[Candidate] = []
        for record in poland + europe:
            if record.observation_id in used_observations:
                continue
            if observer_counts[record.observer_id] >= 2:
                continue
            chosen.append(record)
            used_observations.add(record.observation_id)
            observer_counts[record.observer_id] += 1
            if len(chosen) == quota:
                break
        if len(chosen) < quota:
            shortages[label_id] = quota - len(chosen)
        selected.extend(chosen)
    return selected, shortages


def download_file(url: str, destination: Path, timeout_seconds: int, max_retries: int) -> None:
    if destination.exists():
        return
    ensure_parent(destination)
    tmp_path = destination.with_suffix(destination.suffix + ".part")
    candidate_urls = [url]
    if "/large." in url:
        candidate_urls.extend(
            [
                url.replace("/large.", "/original."),
                url.replace("/large.", "/medium."),
                url.replace("/large.", "/small."),
                url.replace("/large.", "/square."),
            ]
        )

    seen_urls: set[str] = set()
    last_error: Exception | None = None
    for candidate_url in candidate_urls:
        if candidate_url in seen_urls:
            continue
        seen_urls.add(candidate_url)
        request = urllib.request.Request(
            candidate_url,
            headers={"User-Agent": "Project NaturaVision / academic dataset builder"},
        )
        for attempt in range(1, max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                    tmp_path.write_bytes(response.read())
                    tmp_path.replace(destination)
                    return
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
                if attempt == max_retries:
                    break
                time.sleep(attempt)
    raise RuntimeError(f"Failed to download {url}: {last_error}") from last_error


def planned_image_path(image_root: Path, record: Candidate) -> Path:
    return (image_root / record.label_id / f"{record.photo_id}.jpg").resolve()


def download_selected_images(
    selected: list[Candidate],
    image_root: Path,
    timeout_seconds: int,
    max_retries: int,
    workers: int,
) -> tuple[dict[str, Path], dict[str, int]]:
    jobs: dict[Path, str] = {}
    path_by_photo_id: dict[str, Path] = {}
    record_by_photo_id: dict[str, Candidate] = {}
    for record in selected:
        image_path = planned_image_path(image_root, record)
        jobs[image_path] = record.image_url
        path_by_photo_id[record.photo_id] = image_path
        record_by_photo_id[record.photo_id] = record

    pending = [(path, url) for path, url in jobs.items() if not path.exists()]
    total = len(pending)
    if total == 0:
        return path_by_photo_id, {}

    print_stage(f"Downloading {total} images with {workers} workers into {image_root} ...")
    failed_by_label: dict[str, int] = defaultdict(int)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(download_file, url, path, timeout_seconds, max_retries): path
            for path, url in pending
        }
        for index, future in enumerate(as_completed(future_map), start=1):
            path = future_map[future]
            try:
                future.result()
            except Exception as exc:
                failed_record = next(record for record in selected if planned_image_path(image_root, record) == path)
                failed_by_label[failed_record.label_id] += 1
                print_stage(f"  Failed {index}/{total}: {path.name} ({exc})")
                continue
            if index % 100 == 0 or index == total:
                print_stage(f"  Downloaded {index}/{total}: {path.name}")
    return path_by_photo_id, failed_by_label


def write_outputs(
    output_dir: Path,
    image_root: Path,
    selected: list[Candidate],
    timeout_seconds: int,
    max_retries: int,
    download_workers: int,
) -> dict[str, int]:
    records_path = output_dir / "records.csv"
    attribution_path = output_dir / "attribution.csv"
    image_paths, failed_by_label = download_selected_images(
        selected=selected,
        image_root=image_root,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        workers=download_workers,
    )

    with records_path.open("w", encoding="utf-8", newline="") as records_handle, attribution_path.open(
        "w", encoding="utf-8", newline=""
    ) as attribution_handle:
        records_writer = csv.DictWriter(
            records_handle,
            fieldnames=[
                "label_id",
                "kingdom",
                "scientific_name",
                "polish_name",
                "english_name",
                "photo_id",
                "observation_id",
                "observer_id",
                "license_code",
                "photographer",
                "image_path",
                "source_url",
                "download_url",
                "latitude",
                "longitude",
                "country_code",
                "is_poland",
            ],
        )
        attribution_writer = csv.DictWriter(
            attribution_handle,
            fieldnames=[
                "photo_id",
                "observation_id",
                "label_id",
                "scientific_name",
                "photographer",
                "license_code",
                "source_url",
                "download_url",
            ],
        )
        records_writer.writeheader()
        attribution_writer.writeheader()

        for record in selected:
            if failed_by_label.get(record.label_id) and not image_paths[record.photo_id].exists():
                continue
            image_path = image_paths[record.photo_id]
            records_writer.writerow(
                {
                    "label_id": record.label_id,
                    "kingdom": record.kingdom,
                    "scientific_name": record.scientific_name,
                    "polish_name": record.polish_name,
                    "english_name": record.english_name,
                    "photo_id": record.photo_id,
                    "observation_id": record.observation_id,
                    "observer_id": record.observer_id,
                    "license_code": record.license_code,
                    "photographer": record.photographer,
                    "image_path": str(image_path),
                    "source_url": record.source_url,
                    "download_url": record.image_url,
                    "latitude": f"{record.latitude:.6f}",
                    "longitude": f"{record.longitude:.6f}",
                    "country_code": record.country_code,
                    "is_poland": str(record.is_poland).lower(),
                }
            )
            attribution_writer.writerow(
                {
                    "photo_id": record.photo_id,
                    "observation_id": record.observation_id,
                    "label_id": record.label_id,
                    "scientific_name": record.scientific_name,
                    "photographer": record.photographer,
                    "license_code": record.license_code,
                    "source_url": record.source_url,
                    "download_url": record.image_url,
                }
            )
    return failed_by_label


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    image_root = choose_image_root(args)
    image_root.mkdir(parents=True, exist_ok=True)

    print_stage(
        "Fast pipeline config: "
        f"{args.threads} DuckDB threads, {args.memory_limit_gb} GB memory limit, "
        f"{args.download_workers} download workers, image cache at {image_root}"
    )

    entries = load_species_manifest(args.species_manifest)
    candidates = load_candidates(args)
    selected, shortages = select_candidates(
        candidates=candidates,
        target_label_ids=[entry.label_id for entry in entries],
        target_pool_per_label=args.target_pool_per_label,
        unknown_pool_size=args.unknown_pool_size,
        seed=args.seed,
    )

    print_stage(f"Selected {len(selected)} records for download and export.")
    download_shortages = write_outputs(
        output_dir=args.output_dir,
        image_root=image_root,
        selected=selected,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
        download_workers=args.download_workers,
    )

    for label_id, missing in download_shortages.items():
        shortages[label_id] = shortages.get(label_id, 0) + missing

    if shortages:
        shortage_summary = ", ".join(f"{label}: {missing}" for label, missing in sorted(shortages.items()))
        print(f"Dataset build completed with shortages: {shortage_summary}")
        return 1

    print(f"Wrote {len(selected)} downloaded examples into {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
