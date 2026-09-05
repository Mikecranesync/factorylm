# FactoryLM / MIRA — Product North Star

**Approved by Mike:** September 5, 2026
**Decision version:** `FLM-APP-NORTH-STAR-2026-09-05-v1`
**Status:** Approved product direction; implementation and release proof remain work to do.

## The product we are building

**FactoryLM is a clean conversational maintenance app. MIRA helps a technician ask a question, add a photo or manual, get useful evidence-backed help, and keep the result with their work.**

The existing FactoryLM mobile app is the starting product. Improve its interface and connect its working capabilities into one coherent experience. Preserve its installed app identity, accounts, data, equipment, notebooks, conversations, documents, integrations, and native behavior. Reuse the existing chat implementation before introducing another framework or service.

Mike's approved direction: keep the existing mobile app, make it feel as clean and familiar as a general-purpose LLM, and unify the project around an app customers can buy and use. A new app identity, wholesale rewrite, or removal of working features requires a separate decision supported by an inventory and migration plan.

## The experience

The app opens directly into MIRA. A technician can start with an ordinary question and add context as it becomes useful. General explanations and help using the app should work before equipment is selected. Asset-specific diagnosis, equipment parameters, and live-machine claims require the applicable identity confirmation and evidence. Missing context becomes a clear follow-up question.

This is the target experience, not permission to bypass today's UNS, retrieval, or safety gates. Implementation must explicitly separate general help from asset-specific troubleshooting and prove that the existing protections remain effective.

On a phone:

- Top bar: menu, MIRA/conversation title, new chat.
- Main area: readable conversation, useful empty state, quiet typography and spacing.
- Bottom composer: one message field, a **+** menu for photo/file/equipment, and send. Voice is offered only where it works and permission states are handled.
- Context appears when needed: attachments, selected equipment, citations, and suggested next actions. Do not make infrastructure, model routing, or agent orchestration part of the normal customer flow.
- Chat history, projects, documents, and work are easy to return to through the menu. The phone does not need five permanent navigation tabs or a dashboard before the first question.

The same information structure can use a sidebar on larger screens:

| Area | Customer purpose | Existing capabilities to preserve |
|---|---|---|
| Chat | Ask, clarify, inspect sources, resume a conversation | MIRA / ChatV2, conversation history, attachments, citations |
| Projects | Group ongoing work around a job, asset, or investigation | Equipment notebooks and existing records; final naming must map to current data |
| Knowledge | Find and manage useful source material | Manuals, uploads, processing state, source provenance |
| Work | Keep findings and approved next actions | Saved findings, work orders, maintenance follow-ups, existing CMMS links |
| Settings | Manage access and preferences | Account, organization, privacy, connections, supported billing controls |

These are navigation groups, not five new subsystems or a demand to rebuild existing records. Advanced equipment, namespace, ingestion, and administrative tools belong behind context or appropriate roles.

## One product, clear responsibilities

| Component | Responsibility |
|---|---|
| FactoryLM | Product/platform and customer relationship |
| MIRA | The assistant customers interact with |
| Existing mobile app in `Mikecranesync/MIRA` | Primary customer experience and first release focus |
| Existing web surfaces | Companion access, onboarding, and administration using shared capabilities |
| `Mikecranesync/factorylm` | Reusable services, integrations, operational context, and evidence that support the app |
| Slack / Foreman | Mike's internal command center for development, status, and reviewed operational work |

Slack can connect to Claude or other approved assistants for internal work. That is a separate integration from customer inference: this direction does not change provider permissions in either repository. Customer adapters already in service remain supported; they do not create competing first-release roadmaps.

Drive Commander, UNS/context building, CMMS, ingestion, and edge integrations remain useful capabilities. Prioritize them when they improve the app's customer journey or meet an existing reliability obligation. Infrastructure, a separate VFD product, a new command-center UI, model training, and fleet expansion are not independent prerequisites for selling the first app release.

## What makes the app worth paying for

The familiar chat interface lowers the effort to start. The value comes from help grounded in the customer's equipment and documents, evidence the technician can inspect, and work they can resume without starting over.

The first proof journey is:

1. A new user signs in and asks a useful question without an operator preparing the account.
2. They add their own manual or photo; the app shows processing, success, or a recoverable failure.
3. For equipment-specific help, MIRA establishes the required context and gives a supported answer with an inspectable source, or explains what is missing.
4. A follow-up retains the right conversation and equipment context.
5. The user saves a finding or approved next action, closes the app, and reopens the same work.

The release candidate must demonstrate this journey on an emulator before phone testing, then on a supported physical device before customer release. Do not present a design mock, a merged feature flag, or a passing unit test as proof that the deployed app works.

## Release and commercial evidence

Record results against a specific build, environment, and date:

- Existing users can still sign in, find their records, and use retained features after upgrade.
- Fresh users complete the proof journey without Mike repairing data or services.
- Source citations resolve to the right material; unsupported equipment claims are refused or clarified; tenant isolation and confirmation gates pass.
- Loading, failure, reconnect, keyboard, attachment permissions, and history behavior are usable. Only show **Stop** where cancellation really works; otherwise show truthful progress.
- Access, privacy, support, recovery, and a working paid-pilot or purchase path are documented and verified before selling access.
- Track activation, repeat use, grounded-answer success, unresolved tasks, support effort, and cost per useful outcome. Set numerical targets from baseline evidence rather than inventing traction or revenue.

The initial commercial test is a bounded maintenance pilot using a real customer's material. Pricing, limits, support commitments, target pilot customer, and any public launch date remain decisions to validate. Historical offer tables are not current price approval.

## How every workstream aligns

Before claiming a task, state the customer outcome, existing capability reused, proof of completion, and which release blocker or revenue learning it addresses. Work that lacks this connection returns to the backlog, unless it is an existing security, safety, incident, or maintenance obligation.

Use the shared [delivery plan](docs/product/2026-09-05-sellable-app-alignment.md). The canonical umbrella is [MIRA #3586](https://github.com/Mikecranesync/MIRA/issues/3586), with [factorylm #227](https://github.com/Mikecranesync/factorylm/issues/227) tracking the supporting repository. Link implementation slices and their evidence there rather than creating another competing master plan.

This decision supersedes older **product priority and positioning** statements that lead with a context platform, Drive Commander, Telegram/WhatsApp/Slack as the customer front door, or Auto-PM as the universal first task. Historical technical work stays available for reuse. It does not ratify pending ADRs or waive repository rules: tenant boundaries, evidence requirements, provider restrictions, OT read-only behavior, paid-training controls, work claims, adversarial review, and merge/deployment approvals continue to apply.

## Keeping both repositories aligned

`NORTH_STAR.md` and `docs/product/2026-09-05-sellable-app-alignment.md` are identical in `Mikecranesync/MIRA` and `Mikecranesync/factorylm`. The issue links above are the shared coordination point. Future changes to this direction must update the mirrored documents in paired PRs and state the decision and evidence that changed.

Approval to save this direction and commit it is not a claim that the app has been redesigned, released, or sold. Merge, deployment, new spend, and consequential external actions retain their existing approval gates.
