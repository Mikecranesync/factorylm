"""
Master of Puppets - Celery Application
=======================================
Central Celery app configuration for the Industrial AI Swarm.
"""

from celery import Celery
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv('/opt/master_of_puppets/.env')

# Redis connection (from environment or default)
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create the Celery app
app = Celery(
    'master_of_puppets',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        'workers.conductor_tasks',
        'workers.manual_hunter_tasks',
        'workers.alarm_triage_tasks',
        'workers.workflow_tracker_tasks',
        'workers.weaver_tasks',
        'workers.watchman_tasks',
        'workers.cartographer_tasks',
        'workers.monkey_tasks',
        'workers.monkey_dispatcher',
        'workers.polish_tasks',
        'workers.evolution_tasks',
        'workers.photo_analyzer_tasks',
        'workers.edge_log_watcher',
        'workers.trace_tasks',
        # Phase 2: Collectors
        'collectors.s7_collector_tasks',
        'collectors.ab_collector_tasks',
        'collectors.modbus_collector_tasks',
        'collectors.collector_manager',
        # Integrations
        'workers.integration_tasks',
        'workers.maintenance_llm_tasks',
        'workers.edge_gateway_tasks',
        # Analytics (Phase 3-4)
        'analytics.baseline_builder',
        'analytics.drift_detector',
        'analytics.pattern_embedder',
        # Execution & Monitoring (Phase 5)
        'execution.action_executor',
        'monitoring.system_health',
        # Synthetic Users - 24/7 KB Builder
        'workers.synthetic_user_tasks',
        # Keymaster - API Key Guardian
        'workers.keymaster_tasks',
        # Content Capture - YouTube Automation
        'workers.content_capture_tasks',
        # GitHub Scrubber - Continuous repo scanning
        'workers.github_scrubber_tasks',
        # Article Publisher - Scientific article generation
        'workers.article_publisher_tasks',
        # 👁️ Foreman - The Enforcer (Pharaoh's Observatory)
        'workers.foreman_tasks',
        # 🎬 Demo Director - YC Demo Automation
        'workers.demo_director_tasks',
        'workers.obs_controller_tasks',
        'workers.plc_sync_tasks',
        # 📝 Commit Enricher - AI-powered commit note summaries
        'workers.commit_enricher_tasks',
    ]
)

# Celery configuration
app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Fair task distribution
    worker_concurrency=4,  # 4 concurrent tasks per worker
    
    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,  # Requeue if worker dies
    
    # Rate limiting (token budget enforcement)
    task_annotations={
        '*': {'rate_limit': '10/m'}  # Default: 10 tasks per minute
    },
    
    # Beat schedule for periodic tasks
    beat_schedule={
        # 🐒 Monkey Dispatcher - polls Trello every 5 minutes
        'monkey-dispatch-every-5-min': {
            'task': 'monkey.run_cycle',
            'schedule': 300.0,  # 5 minutes
            'args': ['trello'],
        },
        # 🧬 Evolution Cycle - analyze, plan, create tasks every 30 minutes
        'evolution-cycle-every-30-min': {
            'task': 'evolution.run_cycle',
            'schedule': 1800.0,  # 30 minutes
            'args': [True],  # auto_dispatch=True
        },
        'health-check-every-5-minutes': {
            'task': 'monkey.health_check',
            'schedule': 300.0,  # 5 minutes
        },
        # Phase 2: Collector schedules (disabled by default - uncomment when PLCs connected)
        # 'collect-all-every-second': {
        #     'task': 'collector_manager.collect_all',
        #     'schedule': 1.0,  # 1 second for high-frequency collection
        # },
        'collector-health-every-minute': {
            'task': 'collector_manager.health_check',
            'schedule': 60.0,  # 1 minute
        },
        # Phase 3: Drift detection (runs after collector health check)
        # Uncomment when collectors are producing data
        # 'drift-check-every-minute': {
        #     'task': 'drift.check_all_metrics',
        #     'schedule': 60.0,
        # },
        # Phase 5: System health monitoring
        'system-health-every-5-min': {
            'task': 'health_monitor.check_all',
            'schedule': 300.0,  # 5 minutes
        },
        # Photo Analyzer - scan synced photos every 10 minutes
        'photo-analyzer-every-10-min': {
            'task': 'photo_analyzer.scan_new',
            'schedule': 600.0,  # 10 minutes
        },
        # Edge Log Watcher - ingest BeagleBone logs every minute
        'edge-log-ingest-every-minute': {
            'task': 'edge_watcher.scan_logs',
            'schedule': 60.0,  # 1 minute
        },
        # Business Docs Indexer - daily at 2 AM
        'business-docs-daily-index': {
            'task': 'manual_hunter.index_business_docs',
            'schedule': 86400.0,  # 24 hours (adjust with crontab for 2 AM)
        },
        # Daily Summary Report - generate at end of day
        'daily-summary-report': {
            'task': 'weaver.generate_daily_summary',
            'schedule': 86400.0,  # 24 hours
        },
        # Maintenance LLM health check - every 5 minutes
        'maintenance-llm-health-every-5-min': {
            'task': 'maintenance_llm.health_check',
            'schedule': 300.0,  # 5 minutes
        },
        # Edge Gateway health check - every 1 minute
        'edge-gateway-health-every-minute': {
            'task': 'edge_gateway.health_check',
            'schedule': 60.0,  # 1 minute
        },
        # Edge Gateway PLC polling - every 5 seconds (when enabled)
        'edge-gateway-poll-every-5-sec': {
            'task': 'edge_gateway.poll_registers',
            'schedule': 5.0,  # 5 seconds
        },
        # 🧪 Synthetic Users - 24/7 KB Builder (10 min intervals)
        'synth-kb-builder-every-10-min': {
            'task': 'synth.continuous',
            'schedule': 600.0,  # 10 minutes
            'args': [3, 5],  # 3 sessions of 5 questions each
        },
        # 🔑 Keymaster - API Key Guardian (30 min intervals)
        'keymaster-scan-every-30-min': {
            'task': 'keymaster.scan',
            'schedule': 1800.0,  # 30 minutes
            'args': [False],  # Incremental scan (rotates sections)
        },
        # 🔍 GitHub Scrubber - scan repos every hour
        'github-scrub-every-hour': {
            'task': 'github.scrub_all',
            'schedule': 3600.0,  # 1 hour
        },
        # 📝 Article Publisher - process queue every 2 hours
        'article-publish-every-2-hours': {
            'task': 'articles.process_queue',
            'schedule': 7200.0,  # 2 hours
            'args': [3],  # Process 3 items at a time
        },
        # 👁️ FOREMAN - Pharaoh's Observatory (THE ENFORCER)
        # Health check every 5 minutes - ensure workers haven't stopped
        'foreman-health-check-every-5-min': {
            'task': 'foreman.health_check',
            'schedule': 300.0,  # 5 minutes
        },
        # Queue review every 15 minutes - route artifacts to Hammurabi
        'foreman-queue-review-every-15-min': {
            'task': 'foreman.review_queue',
            'schedule': 900.0,  # 15 minutes
        },
        # Shift start - daily at 6 AM UTC
        'foreman-morning-shift': {
            'task': 'foreman.start_shift',
            'schedule': 86400.0,  # 24 hours
            'args': ['morning'],
        },
        # 📝 Commit Enricher - enrich new commit notes every 12 hours
        'commit-enricher-post-sync': {
            'task': 'commit_enricher.enrich_latest',
            'schedule': 43200.0,  # 12 hours
        },
    },
)

if __name__ == '__main__':
    app.start()
