"""
PEPPER Integration Example

Shows how to integrate the Digital Twin system with PEPPER's
diagnosis service and Telegram bot for end-to-end factory questions.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add pepper directory to path
pepper_dir = Path(__file__).parent.parent
sys.path.insert(0, str(pepper_dir))

from twins.registry import TwinRegistry
from twins.plc_twin import PLCTwin
from twins.vps_twin import VPSTwin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FactoryDiagnosisService:
    """
    Factory diagnosis service using Digital Twin routing.

    This service:
    1. Receives factory questions via Telegram
    2. Routes to the appropriate twin (PLC laptop)
    3. Gets AI diagnosis using real PLC data
    4. Returns response via Telegram
    """

    def __init__(self):
        """Initialize the diagnosis service with twin registry"""
        self.registry = TwinRegistry.create_default()
        self.chat_history: Dict[str, list] = {}  # chat_id -> messages

    async def initialize(self):
        """Initialize the service and check twin health"""
        logger.info("🚀 Initializing Factory Diagnosis Service...")

        # Check health of all twins
        health_results = await self.registry.health_check_all()

        online_count = sum(1 for healthy in health_results.values() if healthy)
        total_count = len(health_results)

        logger.info(f"💓 Health check: {online_count}/{total_count} twins online")

        # Log status of critical twins
        plc = self.registry.resolve_twin("plc")
        vps = self.registry.resolve_twin("vps")

        if plc:
            logger.info(f"  - PLC Laptop: {plc.status.value}")
        if vps:
            logger.info(f"  - VPS Server: {vps.status.value}")

        # Start periodic health monitoring
        await self.registry.start_health_monitoring(interval=60)
        logger.info("🏥 Started health monitoring (60s interval)")

    async def handle_telegram_question(
        self,
        chat_id: str,
        question: str,
        user_name: str = "User"
    ) -> str:
        """
        Handle a factory question from Telegram.

        Args:
            chat_id: Telegram chat ID
            question: Factory question from user
            user_name: Name of the user asking

        Returns:
            str: Response to send back to user
        """
        logger.info(f"📩 Received question from {user_name} (chat {chat_id}): {question}")

        # Store in chat history
        if chat_id not in self.chat_history:
            self.chat_history[chat_id] = []
        self.chat_history[chat_id].append({
            "role": "user",
            "question": question
        })

        # Check if PLC twin is available
        plc = self.registry.get_best_twin_for_capability("diagnose")

        if not plc:
            logger.error("❌ No PLC twin available for diagnosis")
            return "🔴 Factory diagnostics unavailable - PLC offline. Please try again later."

        if not plc.is_online():
            logger.warning(f"⚠️ PLC twin status: {plc.status.value}")
            return "🟡 Factory diagnostics temporarily unavailable. Attempting to reconnect..."

        try:
            # Get AI diagnosis from PLC twin
            logger.info(f"🔍 Routing question to {plc.name}...")
            diagnosis = await plc.diagnose(question, context={
                "chat_id": chat_id,
                "user_name": user_name,
                "history_length": len(self.chat_history[chat_id])
            })

            # Store response in history
            self.chat_history[chat_id].append({
                "role": "assistant",
                "response": diagnosis
            })

            logger.info(f"✅ Diagnosis complete, response: {len(diagnosis)} chars")
            return diagnosis

        except Exception as e:
            logger.error(f"❌ Error during diagnosis: {e}", exc_info=True)
            return f"🔴 Error processing factory question: {str(e)}"

    async def send_telegram_response(
        self,
        chat_id: str,
        message: str
    ) -> bool:
        """
        Send response back to Telegram via VPS twin.

        Args:
            chat_id: Telegram chat ID
            message: Message to send

        Returns:
            bool: True if sent successfully
        """
        vps = self.registry.resolve_twin("vps")

        if not vps or not vps.is_online():
            logger.error("❌ VPS twin unavailable for Telegram response")
            return False

        try:
            success = await vps.send_telegram(chat_id, message)
            if success:
                logger.info(f"📤 Sent Telegram response to chat {chat_id}")
            else:
                logger.error(f"❌ Failed to send Telegram response to chat {chat_id}")
            return success

        except Exception as e:
            logger.error(f"❌ Error sending Telegram: {e}", exc_info=True)
            return False

    async def process_telegram_message(
        self,
        chat_id: str,
        message: str,
        user_name: str = "User"
    ) -> None:
        """
        Complete workflow: receive question, get diagnosis, send response.

        Args:
            chat_id: Telegram chat ID
            message: User's message
            user_name: User's name
        """
        logger.info(f"🔄 Processing Telegram workflow for {user_name}")

        # Get diagnosis
        response = await self.handle_telegram_question(chat_id, message, user_name)

        # Send response back
        await self.send_telegram_response(chat_id, response)

        logger.info(f"✅ Workflow complete for chat {chat_id}")

    async def get_factory_status(self) -> Dict[str, Any]:
        """
        Get comprehensive factory status from all twins.

        Returns:
            dict: Factory status including PLC data, system health, etc.
        """
        logger.info("📊 Getting factory status...")

        status = {
            "timestamp": None,
            "twins": self.registry.get_status_summary(),
            "plc": None,
            "io_status": None
        }

        # Get PLC-specific status
        plc = self.registry.resolve_twin("plc")
        if plc and plc.is_online():
            try:
                # Get I/O status
                io_status = await plc.get_io_status()
                status["io_status"] = io_status

                # Get system info
                system_info = await plc.get_system_info()
                status["plc"] = system_info

            except Exception as e:
                logger.error(f"❌ Error getting PLC status: {e}")
                status["plc"] = {"error": str(e)}

        return status

    async def inject_test_fault(self, fault_type: str = "conveyor_jam") -> Dict[str, Any]:
        """
        Inject a test fault for demo purposes.

        Args:
            fault_type: Type of fault to inject

        Returns:
            dict: Fault injection result
        """
        logger.info(f"⚠️ Injecting test fault: {fault_type}")

        plc = self.registry.resolve_twin("plc")
        if not plc or not plc.is_online():
            return {"success": False, "error": "PLC offline"}

        try:
            result = await plc.inject_fault(fault_type, duration=60)
            logger.info(f"✅ Fault injection result: {result}")
            return result

        except Exception as e:
            logger.error(f"❌ Fault injection error: {e}")
            return {"success": False, "error": str(e)}

    async def shutdown(self):
        """Shutdown the service and clean up resources"""
        logger.info("🛑 Shutting down Factory Diagnosis Service...")
        await self.registry.shutdown()
        logger.info("✅ Shutdown complete")


async def demo_workflow():
    """Demonstrate the complete workflow"""
    print("\n" + "="*70)
    print("FACTORY DIAGNOSIS SERVICE - INTEGRATION DEMO")
    print("="*70)

    # Create and initialize service
    service = FactoryDiagnosisService()
    await service.initialize()

    print("\n📋 Demo Scenario:")
    print("  User: Mike")
    print("  Chat ID: 123456789")
    print("  Question: 'Is the factory running normally?'")

    # Simulate Telegram message
    print("\n1️⃣ Simulating Telegram message from Mike...")
    question = "Is the factory running normally?"
    chat_id = "123456789"

    # Get diagnosis (but don't send via Telegram)
    print("\n2️⃣ Getting AI diagnosis from PLC twin...")
    response = await service.handle_telegram_question(
        chat_id=chat_id,
        question=question,
        user_name="Mike"
    )

    print(f"\n3️⃣ Diagnosis response:")
    print(f"  {response[:200]}..." if len(response) > 200 else f"  {response}")

    # Get factory status
    print("\n4️⃣ Getting comprehensive factory status...")
    status = await service.get_factory_status()
    print(f"  Twins online: {status['twins']['online']}/{status['twins']['total_twins']}")

    if status['io_status']:
        print(f"  I/O Status: ✅ Retrieved")
    else:
        print(f"  I/O Status: ❌ Unavailable")

    # Try another question
    print("\n5️⃣ Trying another question...")
    question2 = "What is the conveyor speed?"
    response2 = await service.handle_telegram_question(
        chat_id=chat_id,
        question=question2,
        user_name="Mike"
    )
    print(f"  Response: {response2[:150]}..." if len(response2) > 150 else f"  Response: {response2}")

    # Shutdown
    print("\n6️⃣ Shutting down service...")
    await service.shutdown()

    print("\n" + "="*70)
    print("DEMO COMPLETE")
    print("="*70 + "\n")


async def demo_fault_injection():
    """Demonstrate fault injection for testing"""
    print("\n" + "="*70)
    print("FAULT INJECTION DEMO")
    print("="*70)

    service = FactoryDiagnosisService()
    await service.initialize()

    print("\n⚠️ Injecting test fault: conveyor_jam")
    result = await service.inject_test_fault("conveyor_jam")

    if result.get("success"):
        print(f"  ✅ Fault injected successfully")
        print(f"  Duration: 60 seconds")

        # Now ask about the fault
        print("\n❓ Asking AI to diagnose the fault...")
        diagnosis = await service.handle_telegram_question(
            chat_id="test",
            question="What's wrong with the conveyor?",
            user_name="Technician"
        )
        print(f"\n🤖 AI Diagnosis:")
        print(f"  {diagnosis}")

    else:
        print(f"  ❌ Fault injection failed: {result.get('error')}")

    await service.shutdown()
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    print("\n🏭 FactoryLM Digital Twin Integration\n")

    try:
        # Run the main workflow demo
        asyncio.run(demo_workflow())

        # Uncomment to run fault injection demo
        # asyncio.run(demo_fault_injection())

    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
