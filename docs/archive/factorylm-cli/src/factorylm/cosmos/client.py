"""Cosmos Reason 2 API client.

Uses real NVIDIA API when NVIDIA_COSMOS_API_KEY is set, otherwise falls back to stub.
"""

from __future__ import annotations

import datetime
import json
import logging
import os

import httpx

from factorylm.cosmos.models import CosmosInsight

logger = logging.getLogger(__name__)


class CosmosClient:
    """HTTP client for NVIDIA Cosmos Reason 2 API with stub fallback."""

    def __init__(self, api_key: str = "", model: str = "") -> None:
        self.api_key: str = api_key or os.getenv("NVIDIA_COSMOS_API_KEY", "")
        self.api_base_url: str = "https://integrate.api.nvidia.com/v1"
        self.model: str = model or "nvidia/cosmos-reason2-8b"
        self.fallback_model: str = "meta/llama-3.1-70b-instruct"
        self._use_fallback: bool = False

    def analyze_incident(
        self,
        incident_id: str,
        node_id: str,
        tags: dict,
        images: list[str] | None = None,
        video_url: str = "",
        context: str = "",
    ) -> CosmosInsight:
        """Analyze an incident with Cosmos or stub."""
        if self.api_key:
            return self._analyze_real(incident_id, node_id, tags, images, video_url, context)
        return self._analyze_stub(incident_id, node_id, tags, video_url)

    def _analyze_real(
        self, incident_id, node_id, tags, images, video_url, context,
    ) -> CosmosInsight:
        current_model = self.fallback_model if self._use_fallback else self.model

        tag_summary = json.dumps(tags, indent=2)
        prompt = f"""Analyze this industrial equipment fault. Provide a diagnosis.

Equipment Node: {node_id}
Incident ID: {incident_id}
Current Tag Values:
{tag_summary}
Additional Context: {context or 'None provided'}

Please provide:
1. A brief summary of the fault
2. The most likely root cause
3. Your confidence level (0-1)
4. Reasoning for your diagnosis
5. Suggested checks/fixes (as a list)

Format your response as JSON with keys: summary, root_cause, confidence, reasoning, suggested_checks"""

        content = [{"type": "text", "text": prompt}]
        if video_url:
            content.append({"type": "video_url", "video_url": {"url": video_url}})
        if images:
            for img in images:
                content.append({"type": "image_url", "image_url": {"url": img}})

        try:
            resp = httpx.post(
                f"{self.api_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": current_model, "messages": [{"role": "user", "content": content}], "max_tokens": 1024},
                timeout=30.0,
            )
            resp.raise_for_status()
            raw_text = resp.json()["choices"][0]["message"]["content"]

            try:
                if "```json" in raw_text:
                    raw_text = raw_text.split("```json")[1].split("```")[0]
                elif "```" in raw_text:
                    raw_text = raw_text.split("```")[1].split("```")[0]
                parsed = json.loads(raw_text.strip())
            except json.JSONDecodeError:
                parsed = {"summary": raw_text[:200], "root_cause": "See full response",
                          "confidence": 0.5, "reasoning": raw_text, "suggested_checks": []}

            return CosmosInsight(
                incident_id=incident_id, node_id=node_id,
                timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
                summary=parsed.get("summary", ""), root_cause=parsed.get("root_cause", ""),
                confidence=float(parsed.get("confidence", 0.5)),
                reasoning=parsed.get("reasoning", ""),
                suggested_checks=parsed.get("suggested_checks", []),
                video_url=video_url, cosmos_model=current_model,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404 and not self._use_fallback:
                self._use_fallback = True
                return self._analyze_real(incident_id, node_id, tags, images, video_url, context)
            return self._analyze_stub(incident_id, node_id, tags, video_url)
        except Exception:
            logger.exception("Cosmos API error")
            return self._analyze_stub(incident_id, node_id, tags, video_url)

    def _analyze_stub(self, incident_id, node_id, tags, video_url="") -> CosmosInsight:
        fault_type = tags.get("error_code", 0)
        if fault_type == 0 and tags.get("e_stop"):
            fault_type = -1

        stubs = {
            -1: ("Emergency stop activated.", "Operator or safety system triggered e-stop", 0.95,
                 "E-stop signal is active.", ["Check who pressed e-stop", "Inspect area", "Reset and restart"]),
            0: ("No fault detected.", "N/A", 0.95, "All values nominal.", ["Continue monitoring"]),
            1: ("Motor overload detected.", "Mechanical binding or excessive load", 0.82,
                "Motor current exceeds rated capacity.", ["Inspect motor shaft", "Check belt", "Verify bearings"]),
            2: ("High temperature alarm.", "Insufficient cooling", 0.78,
                "Temperature exceeding threshold.", ["Check cooling fan", "Inspect filters", "Check ambient temp"]),
            3: ("Conveyor jam detected.", "Physical obstruction", 0.88,
                "Belt speed zero while motor energized.", ["Clear jam", "Check sensors", "Check belt tracking"]),
            4: ("Sensor failure.", "Wiring fault or component failure", 0.72,
                "Erratic sensor values.", ["Check wiring", "Verify supply voltage", "Replace sensor"]),
            5: ("Communication loss.", "Network interruption", 0.75,
                "Timeout detected.", ["Check cables", "Verify switch", "Ping device"]),
        }

        s = stubs.get(fault_type, stubs[0])
        return CosmosInsight(
            incident_id=incident_id, node_id=node_id,
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
            summary=s[0], root_cause=s[1], confidence=s[2],
            reasoning=s[3], suggested_checks=s[4],
            video_url=video_url, cosmos_model=self.model,
        )

    def is_available(self) -> bool:
        return bool(self.api_key)
