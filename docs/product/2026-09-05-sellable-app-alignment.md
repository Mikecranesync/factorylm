# FactoryLM / MIRA — Unified Delivery Plan

**Date:** September 5, 2026
**Decision:** `FLM-APP-NORTH-STAR-2026-09-05-v1`
**Governing direction:** [NORTH_STAR.md](../../NORTH_STAR.md)
**Umbrella:** [MIRA #3586](https://github.com/Mikecranesync/MIRA/issues/3586)
**Supporting repo:** [factorylm #227](https://github.com/Mikecranesync/factorylm/issues/227)

## Outcome and scope

Make the existing FactoryLM mobile app a clean, reliable place to talk to MIRA and complete maintenance work. Reuse existing services and data. This plan turns the approved interface direction into a sequence of reviewable slices; it does not claim those slices are already implemented or authorize release.

## Repository ownership

| Repository | Owns | How work connects |
|---|---|---|
| `Mikecranesync/MIRA` | Existing mobile UI, assistant experience, customer knowledge/evidence flow, web companion, release proof | One customer journey and canonical delivery tracker |
| `Mikecranesync/factorylm` | Reusable diagnostic/context services, integrations, read-only edge capabilities, supporting operations | A named app use case, consumer, interface contract, and failure behavior |

This assigns product responsibility, not an instruction to move directories or duplicate services. Confirm runtime ownership before changing an integration. Preserve existing deployments and contracts until a reviewed migration is ready.

## Punch list in delivery order

| Order | Slice | Acceptance evidence | Dependency |
|---|---|---|---|
| 0 | Persist the north star and reconcile agent/README entry points in both repos | Paired commits, identical shared docs, linked review PRs, old priority statements clearly historical | This documentation slice |
| 1 | Inventory the current installed app and reachable backend paths | Build/package IDs, routes, auth, feature flags, existing data types, navigation/feature map, working/broken/mocked/deferred labels with evidence | No production mutation required |
| 2 | Make chat the app-level front door inside the existing mobile app | New chat and history work outside an equipment notebook; existing notebook chat still works; simple top bar and composer; responsive menu | Slice 1 and an explicit general-help vs asset-diagnosis contract |
| 3 | Bring existing features into the new navigation | Accounts, equipment, notebooks, manuals, work and citations remain reachable; no silent data migration; clear attachment/permission/error states | Slice 2, preserve current record IDs |
| 4 | Prove the complete maintenance journey | Fresh-user manual/photo → required context → cited help → follow-up → saved finding → reopen; repeat with missing evidence, another tenant, and network failure | Slices 2–3 and applicable beta/security gates |
| 5 | Prepare and run a bounded paid pilot | Verified access/purchase path, approved offer and limits, support/recovery instructions, device proof, customer material and success criteria, unit-cost evidence | Slice 4 and explicit release approval |
| 6 | Improve from actual usage | Prioritized defects and next features tied to activation, repeat use, resolution, support burden, and willingness to pay | Pilot evidence |

Critical fixes and existing service obligations continue throughout. Do not make a complete infrastructure rebuild, new model, or new fleet a hidden prerequisite for slices 1–5.

## Inventory template for the next implementation slice

Create a focused inventory attached to the umbrella issue before refactoring the UI:

| Existing feature/route | Current build and evidence | Destination in new UI | Shared service/data owner | Preserve or migrate? | Verification and rollback |
|---|---|---|---|---|---|
| Fill from current app, not assumptions | Working / broken / mocked / deferred, with reference | Chat / Projects / Knowledge / Work / Settings / contextual | Actual path and contract | Default: preserve | Specific user check and recovery |

Capture app identifier and native platform, login/session handling, general vs equipment threads, attachment ingestion, notebook/history storage, citation rendering, existing work-order actions, connectivity behavior, and flags. Label source inspection separately from deployed-device verification.

## Interface implementation contract

- Keep the existing mobile app identity and build pipeline. Reuse the existing ChatV2 and shared conversation components where their actual behavior fits.
- Default to chat. Put grouping and navigation in a side menu on phones and a sidebar where screen space allows. Do not turn the five information groups into five compulsory phone tabs.
- Reuse existing notebook/asset/conversation identifiers. A customer-facing label such as Projects is not a new persistence schema by itself.
- Support general explanation without presenting unverified equipment advice. Preserve required identity confirmation, approved retrieval, tenant checks, and refusal paths for asset-specific turns. Resolve any contract conflict in a scoped design/review task before implementation.
- Preserve typed citations, attachment provenance, evidence state, and refusal behavior. A cleaner bubble renderer must not discard the underlying evidence packet.
- Keep loading and cancellation honest: a native buffered request can show Working; a Stop control requires tested cancellation. Handle keyboard, safe areas, permissions, timeout, retry, reconnection, and duplicate sends.
- Introduce changes behind the existing rollout mechanism after confirming its current behavior. Include a reversible route/flag fallback and prove old records still open.

## Reuse the work already in motion

These are coordination references checked during the September 5 documentation session, not merge or release approvals. Refresh PR status, exact head, filenames, claims, and deployment evidence before implementation.

| Existing effort | Relationship to this release | Treatment |
|---|---|---|
| MIRA mobile ChatV2 integration; design at `docs/superpowers/specs/2026-08-31-mira-mobile-chatv2-integration-design.md` | Existing conversation surface to extend; app-level home/history was deferred | Start here, verify current flags and native behavior; do not start a replacement app |
| [MIRA #3514](https://github.com/Mikecranesync/MIRA/pull/3514), [#3515](https://github.com/Mikecranesync/MIRA/pull/3515) — chat design/spike | Potential reuse for interaction and chat implementation | Compare with actual mobile contract; preserve existing held/review gates |
| [MIRA #3477](https://github.com/Mikecranesync/MIRA/pull/3477) and current beta/evidence work | Notebook ownership and credible cited answers | Refresh ownership and state; preserve approved retrieval and tenant tests |
| [MIRA #3448](https://github.com/Mikecranesync/MIRA/pull/3448) — parity/convergence proposal | Helps identify duplicate paths and which service is authoritative | Use as input; this north star does not ratify its architecture automatically |
| [MIRA #3548](https://github.com/Mikecranesync/MIRA/pull/3548), [#3559](https://github.com/Mikecranesync/MIRA/pull/3559), [#3573](https://github.com/Mikecranesync/MIRA/pull/3573) — Foreman/fleet work | Internal coordination and reliable delivery | Tie remaining tasks to app delivery or operational reliability; no automatic worker launch or expanded authority |
| Drive Commander / drive intelligence | Useful evidence-backed maintenance capability within the app | Reuse when a pilot needs it; independent launch priority is superseded |
| UNS, ingest, knowledge graph, CMMS, edge and provider infrastructure | Supplies trusted context and durable work | Prioritize a verified customer blocker; preserve current controls and interfaces |
| Slack command center / Claude integration | Mike's internal control surface | Reuse the existing adapter after inventory; read/status first, private alerts and writes only under explicit authorization |

Do not mass-close issues, merge held PRs, delete services, repoint live integrations, or start scheduled automation to make the board look unified. Record the disposition of existing work on the umbrella: **release blocker**, **reuse in this slice**, **maintenance obligation**, or **later/customer evidence required**.

## Slack setup stays attached to the delivery plan

Inventory MIRA's existing Slack adapter and Foreman before creating an additional Slack app. Confirm installed workspace/app, supported Socket Mode or webhook path, available commands, identity mapping, and provider configuration from actual code and settings. Keep credentials in the approved secret manager.

Track workspace installation, bot/app tokens, private-message/event configuration, member allowlisting, and read-only command verification as a bounded integration task. General Claude conversations and FactoryLM operational commands are separate capabilities; availability and vendor prerequisites must be rechecked when that setup is performed. No Slack message, subscription, recurring alert, provider change, or system mutation is enabled by these documentation commits.

## Shared definition of ready and done

Each implementation issue should include:

1. **User outcome:** which step of the customer journey improves, and for whom.
2. **Reuse and ownership:** actual files/services/records, durable work claim, overlap review.
3. **Scope:** one bounded behavior, retained capabilities, exclusions, dependencies.
4. **Evidence:** acceptance checks, build/commit, environment, results, and limitations.
5. **Release effect:** blocker removed or pilot assumption tested; rollout and rollback.

Done means the claimed behavior is proved at the appropriate layer, review is current to the exact commit, and the handoff states what is still unmerged or unverified. A mock, document, or merged feature flag is only its own deliverable. It is not evidence of deployed app behavior or customer revenue.

## Commercial decisions to settle from evidence

- Select the first maintenance pilot and one repeatable job using its actual equipment/material.
- Confirm who buys, who uses it, what successful completion means, and what support is included.
- Inspect and reuse existing authentication, entitlement, payment, and support paths; verify what actually works before adding another stack.
- Approve price, limits, trial/pilot terms, and launch claims based on cost and customer evidence. Historical pricing remains a hypothesis.
- Record onboarding completion, useful cited outcomes, repeat use, unresolved tasks, support effort, and cost per outcome. Choose targets after the baseline.

## Immediate next slice and release boundary

After these paired documentation PRs receive the required review, the next slice is **inventory the current mobile app and produce the feature-to-navigation map**, then implement app-level chat/home/history using the existing components. Keep current production stable while proof happens locally and in approved staging. Emulator proof precedes phone testing; supported-device proof precedes release.

The current documentation authorization covers saving, committing, and presenting the aligned direction. It does not authorize merging, deploying, new spending, equipment control, changing inference-provider restrictions, or waiving existing human/review gates. Preserve the stricter applicable runtime policies while product implementation is designed and reviewed.
