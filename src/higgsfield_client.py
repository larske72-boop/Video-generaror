"""Higgsfield AI REST API client voor video en afbeelding generatie."""

import os
import time
import requests
from pathlib import Path
from typing import Optional
from rich.console import Console

console = Console()


class HiggsFieldClient:
    BASE_URL = "https://api.higgsfield.ai"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("HIGGSFIELD_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "Higgsfield API key ontbreekt. Stel HIGGSFIELD_API_KEY in als omgevingsvariabele "
                "of geef hem mee via --api-key."
            )
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    # ------------------------------------------------------------------
    # Video generatie
    # ------------------------------------------------------------------

    def generate_video(
        self,
        prompt: str,
        model: str = "kling3_0",
        duration: int = 5,
        aspect_ratio: str = "9:16",
    ) -> str:
        """Start een video generatie job, geeft job_id terug."""
        payload = {
            "model": model,
            "prompt": prompt,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
        }
        resp = self.session.post(f"{self.BASE_URL}/v1/videos", json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["job_id"]

    def generate_image(
        self,
        prompt: str,
        model: str = "nano_banana_pro",
        aspect_ratio: str = "9:16",
    ) -> str:
        """Start een afbeelding generatie job, geeft job_id terug."""
        payload = {
            "model": model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
        }
        resp = self.session.post(f"{self.BASE_URL}/v1/images", json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["job_id"]

    # ------------------------------------------------------------------
    # Job polling
    # ------------------------------------------------------------------

    def wait_for_job(
        self,
        job_id: str,
        poll_interval: int = 5,
        max_wait: int = 300,
        label: str = "Genereren",
    ) -> dict:
        """Poll totdat de job klaar is, geeft resultaat terug."""
        elapsed = 0
        while elapsed < max_wait:
            status = self.get_job_status(job_id)
            state = status.get("status", "pending")
            if state == "completed":
                return status
            if state == "failed":
                raise RuntimeError(f"Job {job_id} mislukt: {status.get('error', 'onbekende fout')}")
            console.print(f"  [dim]{label}... ({elapsed}s)[/dim]")
            time.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(f"Job {job_id} time-out na {max_wait}s")

    def get_job_status(self, job_id: str) -> dict:
        resp = self.session.get(f"{self.BASE_URL}/v1/jobs/{job_id}", timeout=15)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Download helpers
    # ------------------------------------------------------------------

    def download_result(self, job_result: dict, dest_path: Path) -> Path:
        """Download het eerste resultaat van een voltooide job naar dest_path."""
        results = job_result.get("results", [])
        if not results:
            raise ValueError("Geen resultaten gevonden in job response")
        url = results[0].get("url")
        if not url:
            raise ValueError("Geen download URL gevonden in job resultaat")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with self.session.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return dest_path

    # ------------------------------------------------------------------
    # Gecombineerde hulpfuncties
    # ------------------------------------------------------------------

    def generate_and_download_video(
        self,
        prompt: str,
        dest_path: Path,
        model: str = "kling3_0",
        duration: int = 5,
        aspect_ratio: str = "9:16",
    ) -> Path:
        """Genereer video en download naar dest_path, geeft pad terug."""
        console.print(f"  [cyan]Video genereren:[/cyan] {prompt[:60]}...")
        job_id = self.generate_video(prompt, model=model, duration=duration, aspect_ratio=aspect_ratio)
        result = self.wait_for_job(job_id, label="Video genereren")
        return self.download_result(result, dest_path)

    def generate_and_download_image(
        self,
        prompt: str,
        dest_path: Path,
        model: str = "nano_banana_pro",
        aspect_ratio: str = "9:16",
    ) -> Path:
        """Genereer afbeelding en download naar dest_path, geeft pad terug."""
        console.print(f"  [cyan]Afbeelding genereren:[/cyan] {prompt[:60]}...")
        job_id = self.generate_image(prompt, model=model, aspect_ratio=aspect_ratio)
        result = self.wait_for_job(job_id, label="Afbeelding genereren")
        return self.download_result(result, dest_path)
