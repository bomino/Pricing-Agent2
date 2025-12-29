# Create a one-page reference architecture diagram (PDF) and a phase-by-phase Bill of Materials (CSV)
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.patches as mpatches
import matplotlib

import pandas as pd

# ---- Helper functions for drawing ----
def add_box(ax, x, y, w, h, text, fontsize=9, lw=1.2, fc="#F8F9FB", ec="#2F3B52", alpha=1.0, r=0.03):
    box = FancyBboxPatch((x, y), w, h,
                         boxstyle=mpatches.BoxStyle("Round", rounding_size=r),
                         linewidth=lw, edgecolor=ec, facecolor=fc, alpha=alpha)
    ax.add_patch(box)
    ax.text(x + w/2, y + h/2, text, ha='center', va='center', fontsize=fontsize, wrap=True)
    return box

def arrow(ax, x1, y1, x2, y2, text=None, fontsize=8):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", lw=1, color="#2F3B52"))
    if text:
        ax.text((x1+x2)/2, (y1+y2)/2, text, fontsize=fontsize, ha='center', va='center')

# ---- Build the figure ----
plt.rcParams['pdf.fonttype'] = 42
plt.rcParams['ps.fonttype'] = 42

fig_w, fig_h = 12, 8.5  # landscape letter
fig = plt.figure(figsize=(fig_w, fig_h))
ax = plt.gca()
ax.set_xlim(0, 10)
ax.set_ylim(0, 7)
ax.axis('off')

# Title
ax.text(0.02, 6.75, "AI Pricing Agent — Reference Architecture (MVP→Scale)", fontsize=16, fontweight="bold", ha="left", va="center")
ax.text(0.02, 6.45, "Optimized for <200ms hot-path lookups, <30s reports, GDPR/CCPA/SOC2/ISO-ready", fontsize=10, ha="left", va="center")

# Lanes (visual grouping)
# Clients lane
add_box(ax, 0.2, 5.6, 2.0, 1.0, "Clients\nSourcing • Procurement • Sales • Finance", fontsize=10, fc="#EAF2FF")

# Frontend / API layer
fe = add_box(ax, 0.2, 4.6, 2.0, 0.7, "Frontend\nReact + TanStack Query\nBFF/API Gateway (REST or GraphQL)", fontsize=9, fc="#FFFFFF")
svc = add_box(ax, 2.6, 4.4, 2.4, 1.1, "Stateless Services\nFastAPI on Cloud Run (or ECS Fargate)\nAuthZ/AuthN • Rate limiting • Validation", fontsize=9)

# Caching + DB
cache = add_box(ax, 5.2, 5.0, 1.4, 0.5, "Cache\nRedis (Memorystore/ElastiCache)", fontsize=9, fc="#FDF7E3")
db = add_box(ax, 6.8, 4.6, 2.8, 0.9, "Operational Data Store\nPostgreSQL + TimescaleDB + pgvector\n(Cloud SQL/Aurora)", fontsize=9, fc="#F8FFEE")

# Model Serving and Feature Store
ms = add_box(ax, 2.6, 3.3, 2.4, 0.9, "Model Serving\nVertex AI Endpoints / SageMaker\nBentoML/Ray Serve (OSS option)", fontsize=9, fc="#FFF3F3")
fs = add_box(ax, 5.2, 3.3, 1.4, 0.9, "Feature Store\nVertex FS / Feast", fontsize=9, fc="#FFF3F3")

# Warehouse / Lake and Reporting
wh = add_box(ax, 6.8, 3.1, 2.8, 1.3, "Warehouse/Lake\nBigQuery / Redshift Serverless\nSemantic models (dbt)\nReports (<30s)", fontsize=9, fc="#EEF7FF")

# Ingestion & Orchestration
ing = add_box(ax, 0.2, 2.1, 2.6, 0.9, "Ingestion\nPub/Sub → Dataflow (or Kinesis/Glue)\nAirbyte/Fivetran • Cloud Scheduler", fontsize=9, fc="#FFFFFF")
orc = add_box(ax, 3.0, 2.1, 2.3, 0.9, "Orchestration\nAirflow (Cloud Composer/MWAA)\nPrefect (optional)", fontsize=9, fc="#FFFFFF")
dq = add_box(ax, 5.5, 2.1, 1.6, 0.9, "Data Quality & Observability\nGreat Expectations/Soda\nOpenTelemetry • Evidently/WhyLabs", fontsize=9, fc="#FFFFFF")

# Security lane
sec = add_box(ax, 7.4, 2.1, 2.2, 0.9, "Security & Compliance\nIAM • RBAC • TLS 1.3\nKMS/Secrets • VPC-SC\nAudit logs → BigQuery", fontsize=9, fc="#FFFFFF")

# External systems
ext_sup = add_box(ax, 0.2, 0.8, 2.6, 0.9, "External Data\nSupplier APIs • Market Indices • Wage DBs", fontsize=9, fc="#EAF2FF")
erp = add_box(ax, 3.0, 0.8, 2.3, 0.9, "Internal Systems\nERP/Procurement (POs, RFQs, Contracts)", fontsize=9, fc="#EAF2FF")

# Draw arrows (user request path)
arrow(ax, 1.2, 5.6, 1.2, 5.3)  # Clients -> Frontend
arrow(ax, 2.2, 5.0, 2.6, 5.0)  # Frontend -> Services
arrow(ax, 5.0, 5.25, 5.2, 5.25)  # Services -> Cache
arrow(ax, 6.6, 5.0, 6.8, 5.0)  # Cache -> DB
arrow(ax, 6.8, 4.6, 5.0, 4.95)  # DB -> Services (return)
arrow(ax, 2.6, 4.6, 2.2, 4.95)  # Services -> Frontend (return)

# Services -> Model serving & Feature Store
arrow(ax, 3.8, 4.4, 3.8, 4.2)
arrow(ax, 3.8, 3.3, 3.8, 3.0)
arrow(ax, 4.0, 3.7, 5.2, 3.75)  # Services -> FS
arrow(ax, 6.6, 3.75, 5.2, 3.75)  # Warehouse -> FS (features derived from curated)

# DB <-> Warehouse
arrow(ax, 8.2, 4.3, 8.2, 4.0)   # DB -> Warehouse (ELT)
arrow(ax, 8.2, 3.1, 8.2, 2.6)   # Warehouse -> downstream

# Ingestion to DB/Warehouse
arrow(ax, 1.5, 3.0, 7.0, 4.0, text="Curated loads")  # Ingestion -> DB
arrow(ax, 1.5, 3.0, 7.0, 3.5, text="Raw → Lake")     # Ingestion -> Warehouse
arrow(ax, 4.15, 3.0, 4.15, 3.0)  # no-op (visual)

# External/Internal sources to Ingestion
arrow(ax, 1.5, 1.7, 1.5, 2.1)   # External -> Ingestion
arrow(ax, 4.15, 1.7, 4.15, 2.1) # ERP -> Ingestion

# Orchestration controls ingestion and models
arrow(ax, 4.15, 3.0, 3.8, 3.3, text="Train/refresh")
arrow(ax, 4.15, 3.0, 7.0, 3.8, text="dbt/ELT")

# Observability taps
arrow(ax, 6.3, 2.1, 6.3, 1.5, text="Logs/metrics/drift")  # Downward just to show sinking (abstract)

# Footer note
ax.text(0.02, 0.25, "Notes: Hot path = Redis → Postgres MVs; heavy analytics in Warehouse; background refresh for supplier APIs.\n"
                    "GCP shown; AWS equivalents in parentheses. Portable OSS options: BentoML/Ray, Feast, Airbyte, Prefect.", 
        fontsize=8, ha='left', va='center')

diagram_path = "/mnt/data/AI_Pricing_Agent_Reference_Architecture.pdf"
plt.savefig(diagram_path, bbox_inches='tight')
plt.close(fig)

# ---- Create Phase-by-Phase Bill of Materials (CSV) ----
rows = []

def add_row(phase, component, choice, purpose, notes):
    rows.append({
        "Phase": phase,
        "Component": component,
        "Recommended Choice",
        "Purpose",
        "Notes"
    })
    # Fill data
    rows[-1]["Recommended Choice"] = choice
    rows[-1]["Purpose"] = purpose
    rows[-1]["Notes"] = notes

# Phase 0 — Discovery
add_row("0 - Discovery", "Data Profiling", "dbt + BigQuery/Redshift + SQL profiling", "Understand schemas, units, nulls, duplicates", "Size history; confirm 24–60 months availability")
add_row("0 - Discovery", "Data Quality Baseline", "Great Expectations/Soda", "Define checks for naming/units/accuracy", "Gate data before serving path")
add_row("0 - Discovery", "Security & Compliance", "IAM • KMS/Secrets Manager • Audit sinks", "Map roles, keys, retention, logs", "Prep SOC2/ISO evidence collection")

# Phase 1 — MVP Build
add_row("1 - MVP", "Frontend", "React + BFF (REST/GraphQL)", "Quote validation UI; compare/benchmark views", "Focus on sourcing analysts")
add_row("1 - MVP", "APIs/Services", "FastAPI on Cloud Run/ECS", "Validation, enrichment, routing", "Min instances for warm latency")
add_row("1 - MVP", "Cache", "Redis (Memorystore/ElastiCache)", "Sub-200ms hot lookups", "TTL per category freshness SLA")
add_row("1 - MVP", "Operational DB", "Postgres + Timescale + pgvector", "Store normalized prices, time series, vectors", "Materialized views for common queries")
add_row("1 - MVP", "Warehouse", "BigQuery or Redshift Serverless", "Reports, backtests, heavy analytics", "<30s report SLA via summary tables")
add_row("1 - MVP", "Model Serving", "Managed endpoint (Vertex/SageMaker)", "Should-cost/benchmark scoring", "Versioned deploys, A/B, telemetry")
add_row("1 - MVP", "Ingestion", "Scheduler + Airbyte/Fivetran + Pub/Sub/Kinesis", "Fetch supplier APIs/files; land raw", "Backoff/circuit breakers for flaky feeds")
add_row("1 - MVP", "Orchestration", "Airflow/Composer or MWAA", "DAGs for ingest/normalize/train", "dbt runs; retries; alerts")
add_row("1 - MVP", "Data Quality", "Great Expectations/Soda", "Block bad data at edge", "Automated reports to Slack/Email")
add_row("1 - MVP", "Observability", "OpenTelemetry + Cloud Monitoring", "SLOs, traces, logs", "Model drift with Evidently/WhyLabs")

# Phase 2 — Expansion
add_row("2 - Expansion", "Feature Store", "Vertex FS or Feast", "Train/serve parity, point-in-time correctness", "Shareable features across models")
add_row("2 - Expansion", "Search", "OpenSearch/Elasticsearch (optional)", "Full-text across catalogs/docs", "If product needs rich search facets")
add_row("2 - Expansion", "Streaming", "Pub/Sub/Kinesis", "Near-real-time updates", "For volatile indices/vendors")
add_row("2 - Expansion", "RBAC/ABAC", "Fine-grained IAM/OPA policies", "Least-privilege access & approvals", "Map to procurement roles")
add_row("2 - Expansion", "Cost Optimization", "Cluster slots/compute autoscaling", "Reduce warehouse costs", "Tune partitioning & Z-order/cluster keys")

# Phase 3 — Predictive AI
add_row("3 - Predictive AI", "Forecasting", "XGBoost/LightGBM + Prophet/Neural models", "Category forecasts, price trends", "Backtests in warehouse")
add_row("3 - Predictive AI", "Optimization", "OR-Tools/Pyomo", "Should-cost & supplier mix optimization", "Integrate constraints & SLAs")
add_row("3 - Predictive AI", "Active Learning", "Human-in-the-loop labeling UI", "Continuously improve models", "Confidence thresholds & overrides")

# Phase 4 — Full Rollout
add_row("4 - Full Rollout", "HA/DR", "Multi-zone DB replicas + backups", "99.9% uptime target", "Chaos drills, RTO/RPO defined")
add_row("4 - Full Rollout", "Kubernetes (optional)", "GKE/EKS + GitOps", "Portability, cost control for hot paths", "Migrate select services from serverless")
add_row("4 - Full Rollout", "Governance", "Data catalog + lineage (e.g., Data Catalog/Collibra)", "Traceability for audits", "Link datasets, features, models")
add_row("4 - Full Rollout", "FinOps", "Cost allocation tags/budgets", "Control spend across teams", "Per-category/unit cost visibility")

bom_df = pd.DataFrame(rows, columns=["Phase", "Component", "Recommended Choice", "Purpose", "Notes"])
bom_path = "/mnt/data/AI_Pricing_Agent_BoM.csv"
bom_df.to_csv(bom_path, index=False)

from caas_jupyter_tools import display_dataframe_to_user
display_dataframe_to_user("AI Pricing Agent — Phase-by-Phase BoM", bom_df)

diagram_path, bom_path
