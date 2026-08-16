import shutil
import subprocess
import time

import psutil


def get_uptime_seconds() -> float:
    return time.time() - psutil.boot_time()


def get_cpu_stats() -> dict:
    per_core = psutil.cpu_percent(interval=None, percpu=True)
    overall = sum(per_core) / len(per_core) if per_core else 0.0
    return {
        "percent": round(overall, 1),
        "per_core": per_core,
        "core_count": psutil.cpu_count(logical=True),
    }


def get_memory_stats() -> dict:
    memory = psutil.virtual_memory()
    return {
        "total": memory.total,
        "used": memory.used,
        "percent": memory.percent,
    }


def get_disk_stats() -> list:
    disks = []
    seen_mountpoints = set()
    for partition in psutil.disk_partitions(all=False):
        if partition.mountpoint in seen_mountpoints:
            continue
        seen_mountpoints.add(partition.mountpoint)
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except (PermissionError, OSError):
            continue
        disks.append({
            "mountpoint": partition.mountpoint,
            "total": usage.total,
            "used": usage.used,
            "percent": usage.percent,
        })
    return disks


def get_gpu_stats() -> list:
    if not shutil.which("nvidia-smi"):
        return []

    query = "name,utilization.gpu,memory.used,memory.total,temperature.gpu"
    try:
        result = subprocess.run(
            ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (subprocess.SubprocessError, OSError):
        return []

    if result.returncode != 0:
        return []

    gpu_stats = []
    for line in result.stdout.strip().splitlines():
        parsed_gpu = _parse_gpu_line(line)
        if parsed_gpu:
            gpu_stats.append(parsed_gpu)
    return gpu_stats


def _parse_gpu_line(line: str) -> dict | None:
    values = [value.strip() for value in line.split(",")]
    if len(values) != 5:
        return None
    name, utilization, memory_used, memory_total, temperature = values
    try:
        return {
            "name": name,
            "utilization_percent": float(utilization),
            "memory_used_mb": float(memory_used),
            "memory_total_mb": float(memory_total),
            "temperature_c": float(temperature),
        }
    except ValueError:
        return None


def get_all_stats() -> dict:
    return {
        "uptime_seconds": get_uptime_seconds(),
        "cpu": get_cpu_stats(),
        "memory": get_memory_stats(),
        "disks": get_disk_stats(),
        "gpus": get_gpu_stats(),
        "timestamp": time.time(),
    }
