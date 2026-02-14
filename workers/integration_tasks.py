"""
INTEGRATION TASKS - Celery Tasks
=================================
Unified access to external services: Flowise, n8n, Atlas CMMS, Mautic.
"""

import sys
sys.path.insert(0, '/opt/master_of_puppets')

from celery_app import app
from workers.base_worker import BaseAgent, with_token_tracking, with_celery_tracing
from observability import traced, track_llm_call, track_api_call
from integrations.flowise import get_client as get_flowise
from integrations.n8n import get_client as get_n8n
from integrations.atlas_cmms import get_client as get_cmms
from integrations.mautic import get_client as get_mautic
from typing import Dict, Any, List


class IntegrationHub(BaseAgent):
    """Hub for all external integrations."""
    
    def __init__(self):
        super().__init__("IntegrationHub")


hub = IntegrationHub()


# ==================== FLOWISE ====================

@app.task(bind=True, name='integration.flowise.list_flows')
@with_celery_tracing("flowise_list_flows")
@traced(name="flowise_list_flows", layer="execution")
def flowise_list_flows(self) -> List[Dict]:
    """List all Flowise chatflows."""
    client = get_flowise()
    return client.list_chatflows()


@app.task(bind=True, name='integration.flowise.predict')
@with_token_tracking('integration')
def flowise_predict(self, flow_id: str, question: str, history: list = None) -> Dict:
    """
    Send a prediction to a Flowise chatflow.
    
    Args:
        flow_id: The chatflow ID
        question: User question
        history: Optional chat history
    """
    client = get_flowise()
    return client.predict(flow_id, question, history)


@app.task(bind=True, name='integration.flowise.health')
@with_celery_tracing("flowise_health")
@traced(name="flowise_health", layer="execution")
def flowise_health(self) -> Dict:
    """Check Flowise health."""
    return get_flowise().health_check()


# ==================== N8N ====================

@app.task(bind=True, name='integration.n8n.list_workflows')
@with_celery_tracing("n8n_list_workflows")
@traced(name="n8n_list_workflows", layer="execution")
def n8n_list_workflows(self) -> List[Dict]:
    """List all n8n workflows."""
    return get_n8n().list_workflows()


@app.task(bind=True, name='integration.n8n.execute')
@with_celery_tracing("n8n_execute")
@traced(name="n8n_execute", layer="execution")
def n8n_execute(self, workflow_id: str, data: dict = None) -> Dict:
    """Execute an n8n workflow."""
    return get_n8n().execute_workflow(workflow_id, data)


@app.task(bind=True, name='integration.n8n.trigger_webhook')
@with_celery_tracing("n8n_trigger_webhook")
@traced(name="n8n_trigger_webhook", layer="execution")
def n8n_trigger_webhook(self, webhook_path: str, data: dict = None) -> Dict:
    """Trigger an n8n webhook."""
    return get_n8n().trigger_webhook(webhook_path, data)


@app.task(bind=True, name='integration.n8n.health')
@with_celery_tracing("n8n_health")
@traced(name="n8n_health", layer="execution")
def n8n_health(self) -> Dict:
    """Check n8n health."""
    return get_n8n().health_check()


# ==================== ATLAS CMMS ====================

@app.task(bind=True, name='integration.cmms.list_work_orders')
@with_celery_tracing("cmms_list_work_orders")
@traced(name="cmms_list_work_orders", layer="execution")
def cmms_list_work_orders(self, status: str = None, limit: int = 50) -> List[Dict]:
    """List work orders from Atlas CMMS."""
    return get_cmms().list_work_orders(status, limit)


@app.task(bind=True, name='integration.cmms.create_work_order')
@with_celery_tracing("cmms_create_work_order")
@traced(name="cmms_create_work_order", layer="execution")
def cmms_create_work_order(self, title: str, description: str, priority: str = "MEDIUM",
                           asset_id: int = None, due_date: str = None) -> Dict:
    """
    Create a work order in Atlas CMMS.
    
    Args:
        title: Work order title
        description: Detailed description
        priority: NONE, LOW, MEDIUM, HIGH
        asset_id: Optional asset ID
        due_date: Optional due date (ISO format)
    """
    hub.logger.info(f"Creating work order: {title}")
    return get_cmms().create_work_order(title, description, priority, asset_id, due_date)


@app.task(bind=True, name='integration.cmms.update_status')
@with_celery_tracing("cmms_update_status")
@traced(name="cmms_update_status", layer="execution")
def cmms_update_status(self, wo_id: int, status: str) -> Dict:
    """Update work order status."""
    return get_cmms().update_work_order_status(wo_id, status)


@app.task(bind=True, name='integration.cmms.list_assets')
@with_celery_tracing("cmms_list_assets")
@traced(name="cmms_list_assets", layer="execution")
def cmms_list_assets(self, limit: int = 50) -> List[Dict]:
    """List assets from CMMS."""
    return get_cmms().list_assets(limit)


@app.task(bind=True, name='integration.cmms.health')
@with_celery_tracing("cmms_health")
@traced(name="cmms_health", layer="execution")
def cmms_health(self) -> Dict:
    """Check CMMS health."""
    return get_cmms().health_check()


# ==================== MAUTIC ====================

@app.task(bind=True, name='integration.mautic.list_contacts')
@with_celery_tracing("mautic_list_contacts")
@traced(name="mautic_list_contacts", layer="execution")
def mautic_list_contacts(self, limit: int = 30) -> List[Dict]:
    """List contacts from Mautic."""
    return get_mautic().list_contacts(limit)


@app.task(bind=True, name='integration.mautic.create_contact')
@with_celery_tracing("mautic_create_contact")
@traced(name="mautic_create_contact", layer="execution")
def mautic_create_contact(self, email: str, firstname: str = "", lastname: str = "",
                          phone: str = "", tags: list = None) -> Dict:
    """Create a contact in Mautic."""
    return get_mautic().create_contact(email, firstname, lastname, phone, tags)


@app.task(bind=True, name='integration.mautic.send_email')
@with_celery_tracing("mautic_send_email")
@traced(name="mautic_send_email", layer="execution")
def mautic_send_email(self, email_id: int, contact_id: int) -> Dict:
    """Send an email to a contact."""
    return get_mautic().send_email(email_id, contact_id)


@app.task(bind=True, name='integration.mautic.health')
@with_celery_tracing("mautic_health")
@traced(name="mautic_health", layer="execution")
def mautic_health(self) -> Dict:
    """Check Mautic health."""
    return get_mautic().health_check()


# ==================== UNIFIED HEALTH ====================

@app.task(bind=True, name='integration.health_all')
@with_celery_tracing("health_all")
@traced(name="health_all", layer="execution")
def health_all(self) -> Dict:
    """Check health of all integrations."""
    return {
        "flowise": get_flowise().health_check(),
        "n8n": get_n8n().health_check(),
        "cmms": get_cmms().health_check(),
        "mautic": get_mautic().health_check(),
    }


@app.task(bind=True, name='integration.health')
@with_celery_tracing("health")
@traced(name="health", layer="execution")
def health(self) -> Dict:
    """Simple health check."""
    return {"status": "ok", "agent": "IntegrationHub"}
