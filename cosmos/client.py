"""
Cosmos Reason 2 API client — NVIDIA Cosmos Cookoff 2026.

Loads settings from config/cosmos.yaml and exposes analyze_incident().
Uses real NVIDIA API when NVIDIA_COSMOS_API_KEY is set, otherwise falls back to stub.
"""

import datetime
import json
import logging
import os
from pathlib import Path

import httpx

from cosmos.models import CosmosInsight

logger = logging.getLogger(__name__)


class CosmosClient:
    """HTTP client for NVIDIA Cosmos Reason 2 API with Llama fallback."""

    def __init__(self, config_path: str | None = None) -> None:
        cfg_file = Path(config_path) if config_path else Path("config/cosmos.yaml")
        self.api_key: str = os.getenv("NVIDIA_COSMOS_API_KEY", "")
        self.api_base_url: str = "https://integrate.api.nvidia.com/v1"
        self.model: str = "nvidia/cosmos-reason2-8b"
        self.fallback_model: str = "meta/llama-3.1-70b-instruct"
        self._config: dict = {}
        self._use_fallback: bool = False  # Track if we should use fallback

        if cfg_file.exists():
            try:
                import yaml

                with cfg_file.open("r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
                self._config = raw.get("cosmos", {})
                self.api_base_url = self._config.get("api_base_url", self.api_base_url)
                self.model = self._config.get("model", self.model)
                self.fallback_model = self._config.get("fallback_model", self.fallback_model)
            except ImportError:
                logger.warning("PyYAML not installed — using defaults")
            except Exception:
                logger.exception("Failed to load Cosmos config from %s", cfg_file)

    def analyze_incident(
        self,
        incident_id: str,
        node_id: str,
        tags: dict,
        images: list[str] | None = None,
        video_url: str = "",
        context: str = "",
    ) -> CosmosInsight:
        """Send an incident bundle to Cosmos Reason 2 and return a CosmosInsight.

        Uses real NVIDIA API when api_key is set, otherwise falls back to stub.
        """
        # Use real API if key is available
        if self.api_key:
            return self._analyze_incident_real(
                incident_id, node_id, tags, images, video_url, context
            )

        # Fall back to stub
        logger.info(
            "CosmosClient.analyze_incident called for incident=%s node=%s (STUB - no API key)",
            incident_id,
            node_id,
        )
        return self._analyze_incident_stub(incident_id, node_id, tags, video_url)

    def _analyze_incident_real(
        self,
        incident_id: str,
        node_id: str,
        tags: dict,
        images: list[str] | None,
        video_url: str,
        context: str,
    ) -> CosmosInsight:
        """Make real API call to NVIDIA Cosmos Reason 2 or fallback model."""
        current_model = self.fallback_model if self._use_fallback else self.model
        logger.info(
            "CosmosClient.analyze_incident REAL API call for incident=%s node=%s model=%s",
            incident_id,
            node_id,
            current_model,
        )

        # Build the prompt for fault analysis
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

        # Build message content
        content = [{"type": "text", "text": prompt}]

        # Add video if provided
        if video_url:
            content.append({
                "type": "video_url",
                "video_url": {"url": video_url}
            })

        # Add images if provided
        if images:
            for img_url in images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": img_url}
                })

        try:
            response = httpx.post(
                f"{self.api_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": current_model,
                    "messages": [{"role": "user", "content": content}],
                    "max_tokens": 1024,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            # Parse the response
            raw_text = result["choices"][0]["message"]["content"]
            logger.debug("Cosmos raw response: %s", raw_text)

            # Try to parse as JSON
            try:
                # Handle markdown code blocks
                if "```json" in raw_text:
                    raw_text = raw_text.split("```json")[1].split("```")[0]
                elif "```" in raw_text:
                    raw_text = raw_text.split("```")[1].split("```")[0]
                parsed = json.loads(raw_text.strip())
            except json.JSONDecodeError:
                # Fallback: extract key info from free text
                parsed = {
                    "summary": raw_text[:200],
                    "root_cause": "See full response",
                    "confidence": 0.5,
                    "reasoning": raw_text,
                    "suggested_checks": ["Review full Cosmos response"],
                }

            return CosmosInsight(
                incident_id=incident_id,
                node_id=node_id,
                timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
                summary=parsed.get("summary", "Analysis complete"),
                root_cause=parsed.get("root_cause", "Unknown"),
                confidence=float(parsed.get("confidence", 0.5)),
                reasoning=parsed.get("reasoning", ""),
                suggested_checks=parsed.get("suggested_checks", []),
                video_url=video_url,
                cosmos_model=current_model,
            )

        except httpx.HTTPStatusError as e:
            logger.error("Cosmos API HTTP error: %s - %s", e.response.status_code, e.response.text)
            # If 404 and not already using fallback, try fallback model
            if e.response.status_code == 404 and not self._use_fallback:
                logger.info("Cosmos model not available, switching to fallback: %s", self.fallback_model)
                self._use_fallback = True
                return self._analyze_incident_real(incident_id, node_id, tags, images, video_url, context)
            return self._analyze_incident_stub(incident_id, node_id, tags, video_url)
        except Exception as e:
            logger.exception("Cosmos API error: %s", e)
            return self._analyze_incident_stub(incident_id, node_id, tags, video_url)

    def _analyze_incident_stub(
        self,
        incident_id: str,
        node_id: str,
        tags: dict,
        video_url: str,
    ) -> CosmosInsight:
        """Return stub response for testing without API key."""

        # Build a realistic stub response based on the tags provided
        fault_type = tags.get("error_code", 0)
        if fault_type == 0 and tags.get("e_stop"):
            fault_type = -1
        stub_responses = {
            -1: {
                "summary": "Emergency stop activated. All motion halted.",
                "root_cause": "Operator or safety system triggered e-stop",
                "confidence": 0.95,
                "reasoning": (
                    "E-stop signal is active. All motors de-energized and conveyors stopped. "
                    "This is either a manual operator action or an automated safety interlock response."
                ),
                "suggested_checks": [
                    "Identify who pressed the e-stop and why",
                    "Inspect work area for personnel safety hazards",
                    "Check for jammed material or mechanical failure that triggered the stop",
                    "Reset e-stop, verify safe conditions, then restart in controlled sequence",
                ],
            },
            0: {
                "summary": "No active fault detected. System operating within normal parameters.",
                "root_cause": "N/A — no fault present",
                "confidence": 0.95,
                "reasoning": "All tag values within expected ranges. Motor current, temperature, and pressure readings are nominal.",
                "suggested_checks": ["Continue normal monitoring"],
            },
            1: {
                "summary": "Motor overload detected. Current draw exceeds rated capacity.",
                "root_cause": "Mechanical binding or excessive load on motor shaft",
                "confidence": 0.82,
                "reasoning": (
                    f"Motor current at {tags.get('motor_current', 'N/A')}A exceeds "
                    f"expected range for speed {tags.get('motor_speed', 'N/A')}%. "
                    "This pattern is consistent with mechanical resistance — "
                    "either a jammed workpiece or bearing degradation."
                ),
                "suggested_checks": [
                    "Inspect motor shaft for mechanical binding",
                    "Check conveyor belt alignment and tension",
                    "Verify motor bearings with vibration analysis",
                    "Review motor nameplate amps vs. measured current",
                ],
            },
            2: {
                "summary": "High temperature alarm. Process temperature exceeding safe threshold.",
                "root_cause": "Insufficient cooling or sustained high-load operation",
                "confidence": 0.78,
                "reasoning": (
                    f"Temperature reading at {tags.get('temperature', 'N/A')}°C. "
                    "Thermal runaway pattern suggests cooling system degradation "
                    "or ambient temperature exceeding design limits."
                ),
                "suggested_checks": [
                    "Check cooling fan operation",
                    "Inspect air filters for blockage",
                    "Verify ambient temperature in enclosure",
                    "Check thermal paste on heat sinks",
                ],
            },
            3: {
                "summary": "Conveyor jam detected. Material flow interrupted.",
                "root_cause": "Physical obstruction in conveyor path",
                "confidence": 0.88,
                "reasoning": (
                    "Conveyor motor drawing current but photoeye sensors show "
                    "sustained blockage. Belt speed has dropped to zero while "
                    "motor remains energized — classic jam signature."
                ),
                "suggested_checks": [
                    "Clear jammed material from conveyor path",
                    "Inspect photoeye sensors for alignment",
                    "Check conveyor belt tracking",
                    "Verify guide rail spacing",
                ],
            },
            4: {
                "summary": "Sensor failure detected. One or more sensors not responding.",
                "root_cause": "Sensor wiring fault or component failure",
                "confidence": 0.72,
                "reasoning": (
                    "Sensor readings show flat-line or erratic values inconsistent "
                    "with physical process state. Likely a wiring issue or "
                    "end-of-life sensor."
                ),
                "suggested_checks": [
                    "Check sensor wiring connections",
                    "Verify sensor supply voltage",
                    "Test sensor with known target",
                    "Replace sensor if beyond calibration",
                ],
            },
            5: {
                "summary": "Communication loss with downstream device.",
                "root_cause": "Network or fieldbus interruption",
                "confidence": 0.75,
                "reasoning": (
                    "Communication timeout detected. Could be cable fault, "
                    "switch failure, or device power loss."
                ),
                "suggested_checks": [
                    "Check Ethernet cable connections",
                    "Verify network switch status",
                    "Ping downstream device",
                    "Check device power supply",
                ],
            },
        }

        response = stub_responses.get(fault_type, stub_responses[0])

        return CosmosInsight(
            incident_id=incident_id,
            node_id=node_id,
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
            summary=response["summary"],
            root_cause=response["root_cause"],
            confidence=response["confidence"],
            reasoning=response["reasoning"],
            suggested_checks=response["suggested_checks"],
            video_url=video_url,
            cosmos_model=self.model,
        )

    def analyze_video(
        self,
        video_path: str,
        context: str = "",
    ) -> dict:
        """Analyze a video clip via Cosmos Reason 2.

        Returns a dict with caption, key_events, interesting_score, and cosmos_model.
        Uses real API when api_key is set, otherwise falls back to stub.
        """
        # Use real API if key is available
        if self.api_key:
            return self._analyze_video_real(video_path, context)

        logger.info(
            "CosmosClient.analyze_video called for %s (STUB - no API key)",
            Path(video_path).name if video_path else "unknown",
        )
        return self._analyze_video_stub(video_path)

    def _analyze_video_real(self, video_path: str, context: str) -> dict:
        """Make real API call for video analysis."""
        import base64

        logger.info(
            "CosmosClient.analyze_video REAL API call for %s",
            Path(video_path).name if video_path else "unknown",
        )

        prompt = f"""Analyze this factory floor video. Describe what's happening.

Context: {context or 'Factory floor monitoring'}

Please provide:
1. A caption describing the key events (2-3 sentences)
2. A list of timestamped key events
3. An "interesting score" from 0-100 (higher = more noteworthy events)

Format as JSON with keys: caption, key_events (list of {{timestamp, action}}), interesting_score"""

        # Build content with video
        content = [{"type": "text", "text": prompt}]

        # For video files, we need to encode or use URL
        video_file = Path(video_path)
        if video_file.exists() and video_file.suffix.lower() in [".mp4", ".webm", ".mov"]:
            # Read and base64 encode the video
            try:
                video_data = base64.b64encode(video_file.read_bytes()).decode("utf-8")
                mime_type = "video/mp4" if video_file.suffix.lower() == ".mp4" else "video/webm"
                content.append({
                    "type": "video_url",
                    "video_url": {"url": f"data:{mime_type};base64,{video_data}"}
                })
            except Exception as e:
                logger.warning("Failed to read video file: %s", e)
        elif video_path.startswith("http"):
            content.append({
                "type": "video_url",
                "video_url": {"url": video_path}
            })

        try:
            response = httpx.post(
                f"{self.api_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": content}],
                    "max_tokens": 512,
                },
                timeout=60.0,  # Longer timeout for video
            )
            response.raise_for_status()
            result = response.json()

            raw_text = result["choices"][0]["message"]["content"]

            # Try to parse as JSON
            try:
                if "```json" in raw_text:
                    raw_text = raw_text.split("```json")[1].split("```")[0]
                elif "```" in raw_text:
                    raw_text = raw_text.split("```")[1].split("```")[0]
                parsed = json.loads(raw_text.strip())
                return {
                    "caption": parsed.get("caption", "Analysis complete"),
                    "key_events": parsed.get("key_events", []),
                    "interesting_score": int(parsed.get("interesting_score", 50)),
                    "cosmos_model": self.model,
                }
            except json.JSONDecodeError:
                return {
                    "caption": raw_text[:500],
                    "key_events": [{"timestamp": 0.0, "action": "See full caption"}],
                    "interesting_score": 50,
                    "cosmos_model": self.model,
                }

        except httpx.HTTPStatusError as e:
            logger.error("Cosmos video API error: %s - %s", e.response.status_code, e.response.text)
            return self._analyze_video_stub(video_path)
        except Exception as e:
            logger.exception("Cosmos video API error: %s", e)
            return self._analyze_video_stub(video_path)

    def _analyze_video_stub(self, video_path: str) -> dict:
        """Return stub response for video analysis."""
        # Generate contextual stub responses based on filename
        name = Path(video_path).stem.lower() if video_path else ""
        
        if "jam" in name or "fault" in name or "error" in name:
            return {
                "caption": (
                    "Conveyor jam detected at 0:08. Photoeye sensor blocked by misaligned "
                    "package. Technician arrives at 0:12, clears obstruction manually. "
                    "Belt restarts at 0:18. Total downtime: 10 seconds."
                ),
                "key_events": [
                    {"timestamp": 8.0, "action": "Conveyor jam — photoeye blocked"},
                    {"timestamp": 12.0, "action": "Technician arrives, begins clearing"},
                    {"timestamp": 18.0, "action": "Obstruction cleared, belt restarted"},
                ],
                "interesting_score": 85,
                "cosmos_model": self.model,
            }
        elif "repair" in name or "fix" in name or "maintenance" in name:
            return {
                "caption": (
                    "Scheduled maintenance on conveyor motor. Technician replaces drive "
                    "belt at 0:05, tests motor at 0:20. Belt tracking adjusted at 0:25. "
                    "System returned to service."
                ),
                "key_events": [
                    {"timestamp": 5.0, "action": "Drive belt replacement begins"},
                    {"timestamp": 20.0, "action": "Motor test — running normally"},
                    {"timestamp": 25.0, "action": "Belt tracking adjusted"},
                ],
                "interesting_score": 70,
                "cosmos_model": self.model,
            }
        elif "estop" in name or "emergency" in name or "stop" in name:
            return {
                "caption": (
                    "Emergency stop activated at 0:03. All motion ceased. Operator "
                    "inspects area at 0:06. E-stop released at 0:14. System restart "
                    "sequence initiated."
                ),
                "key_events": [
                    {"timestamp": 3.0, "action": "E-STOP activated"},
                    {"timestamp": 6.0, "action": "Operator inspecting area"},
                    {"timestamp": 14.0, "action": "E-STOP released, restart initiated"},
                ],
                "interesting_score": 90,
                "cosmos_model": self.model,
            }
        else:
            # Normal operation
            import random
            score = random.randint(10, 45)
            return {
                "caption": (
                    "Conveyor running normally. Parts moving through sorting station at "
                    "standard speed. Photoeye sensors cycling as expected. No anomalies "
                    "detected in motor current or temperature."
                ),
                "key_events": [
                    {"timestamp": 0.0, "action": "Normal conveyor operation"},
                ],
                "interesting_score": score,
                "cosmos_model": self.model,
            }

    def is_available(self) -> bool:
        """Return True if the client has credentials configured."""
        return bool(self.api_key)
