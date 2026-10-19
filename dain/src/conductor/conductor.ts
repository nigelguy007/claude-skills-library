// Layer 4 · the conductor (C0). One entry point over every department. Unlike the map's
// "Jarvis", it does not read text to decide who handles a job: each command has one fixed
// route, so the most safety-critical part of the system stays deterministic and auditable (F9).
import { Brain, type Approval } from "../brain/store.js";
import type { Blueprint, TranscriptSegment } from "../contracts.js";
import { EventLog } from "../events.js";
import { ActionGate, type ActionAdapter, type ApprovalToken } from "../gate.js";
import { BudgetExceeded, ContractError, type LLM, type NodeContext } from "../llm.js";
import { ReviewService } from "../review.js";
import { StateMachines } from "../state.js";
import { applyConfirmation, checkAgainstTranscript, coverageGaps, followUpQuestions, MAX_FOLLOW_UP_ROUNDS, writeBlueprint } from "../agents/a1.js";
import { planWeek, type PastPost } from "../agents/a2.js";
import { RUBRIC_V0, type Rubric } from "../agents/b2.js";
import { runContentLoop } from "../agents/content-loop.js";
import { captureEnquiry, isQualified } from "../agents/p1.js";
import { runRadar, type Fetcher } from "../agents/b1.js";
import { changesSince, coverNote, packFor, renderPack, type BureauProfile } from "../agents/p2.js";
import { nightlySweep } from "../agents/groundskeeper.js";
import { renderBlueprintDocument } from "../agents/blueprint-doc.js";
import { parseForm, parseReply, type ReplyDecision } from "../review-reply.js";
import { COMMANDS, screen, type Command, type Payload, type SpeakerProfile } from "./commands.js";
import { deliver, runWorkflow, type Run } from "./runner.js";

export interface Deps {
  brain: Brain;
  log: EventLog;
  llm: LLM;
  adapters: { linkedin: ActionAdapter; email: ActionAdapter };
  fetcher?: Fetcher;
}

export class Conductor {
  readonly sm: StateMachines;
  readonly gate: ActionGate;
  readonly review: ReviewService;
  private brain: Brain;
  private log: EventLog;

  constructor(private deps: Deps) {
    this.brain = deps.brain;
    this.log = deps.log;
    this.sm = new StateMachines(this.brain, this.log);
    this.gate = new ActionGate(this.brain, this.log);
    this.review = new ReviewService(this.brain, this.log, this.gate, this.sm);
  }

  /** The single front door. Unknown commands are refused; there is no free-text routing. */
  async dispatch<C extends Command>(command: C, payload: unknown): Promise<unknown> {
    const schema = COMMANDS[command];
    if (!schema) throw new Error(`unknown command "${String(command)}"; known: ${Object.keys(COMMANDS).join(", ")}`);
    const p = schema.parse(payload) as Payload<C>;
    const route = this.routes[command] as (p: Payload<C>) => Promise<unknown>;
    return route(p);
  }

  private routes: { [C in Command]: (p: Payload<C>) => Promise<unknown> } = {
    "speaker.onboard": (p) => this.onboarding(p.speaker_id, p),
    "interview.transcript": (p) => this.resume(`onboard:${p.speaker_id}`, "interview.transcript", p),
    "interview.followup": (p) => this.resume(`onboard:${p.speaker_id}`, `interview.followup.${p.round}`, p),
    "blueprint.confirm": async (p) => {
      const out = await this.resume(`onboard:${p.speaker_id}`, "blueprint.confirmation", p);
      if (this.profile(p.speaker_id)?.bureau_ids.length) await this.dispatch("pack.render", { speaker_id: p.speaker_id });
      return out;
    },
    "content.weekly": (p) => runWorkflow(this.brain, `weekly:${p.speaker_id}:${p.week}`, (run) => this.weeklyContent(run, p.speaker_id, p.week)),
    "review.open": async (p) => this.review.open(p.item_id, p.role, p.at_ms),
    "review.edit": async (p) => this.review.edit(p.item_id, p.content, p.at_ms),
    "review.approve": async (p) => {
      const token = this.review.approve(p.item_id, p.approval, p.at_ms);
      if (!token) return { status: "moved_to_next_reviewer" };
      const item = this.review.item(p.item_id);
      if (item.entity === "ContentItem") return this.publish(p.item_id, token);
      if (item.entity === "Enquiry") return this.sendReply(p.item_id, token);
      return { status: "approved", token_id: token.id };
    },
    "review.reply": async (p) => {
      const item = this.review.item(p.item_id);
      const profile = this.profile(item.speaker_id);
      // Only the speaker's own address may answer for their own item. The inbound mail
      // provider must also verify SPF/DKIM before this command is called; a From header alone can be forged.
      if (!profile?.email || profile.email.toLowerCase() !== p.from.toLowerCase())
        throw new Error("reply refused: sender is not the speaker this item belongs to");
      if (item.entity !== "ContentItem" || this.sm.get("ContentItem", p.item_id).state !== "SPEAKER_REVIEW")
        throw new Error(`reply refused: ${p.item_id} is not waiting for the speaker`);
      const channel = p.form ? "form" : "email";
      const d: ReplyDecision | null = p.form ? parseForm(p.form) : parseReply(p.body!);
      if (!d) return { status: "unclear", ask: "Reply with APPROVE, EDIT followed by your new text, or REJECT and a reason." };
      const approval = { approver: profile.name, role: "speaker" as const };
      this.review.open(p.item_id, "speaker", p.at_ms, channel);
      if (d.decision === "reject") {
        this.review.reject(p.item_id, "speaker", d.reason, p.at_ms);
        return { status: "rejected", reason: d.reason };
      }
      if (d.decision === "edit") this.review.edit(p.item_id, d.text, p.at_ms);
      const token = this.review.approve(p.item_id, approval, p.at_ms)!;
      return this.publish(p.item_id, token);
    },
    "enquiry.capture": (p) => runWorkflow(this.brain, `enquiry:${p.enquiry_id}`, (run) => this.enquiry(run, p)),
    "radar.weekly": (p) => runWorkflow(this.brain, `radar:${p.week}`, (run) => this.radar(run, p)),
    "radar.promote": async (p) => {
      const newest = [...p.evidence].sort((a, b) => b.date.localeCompare(a.date))[0]!;
      return this.brain.promote("angle_evidence", `${p.speaker_id}:${p.angle_id}`, { date: newest.date, evidence: p.evidence }, p.approval);
    },
    "pack.render": async (p) => this.assetPack(p.speaker_id),
    "pack.sent": async (p) => {
      this.sm.transition("AssetPack", `${p.speaker_id}:${p.pack_version}`, "SENT");
      return this.brain.append("p2.sent", p.speaker_id, { bureau: p.bureau_id, pack_version: p.pack_version, by: p.approval.approver });
    },
    "sweep.answer": async (p) => this.log.emit({ type: "sweep.answered", speaker_id: p.speaker_id, week: p.week, missed_count: p.missed_count }),
    nightly: async () => nightlySweep(this.brain, this.sm, this.log),
  };

  // ---------- helpers ----------

  ctx(speakerId: string | null): NodeContext {
    return { llm: this.deps.llm, log: this.log, speaker_id: speakerId, canon_version: speakerId ? this.brain.canonVersion(speakerId) : "global" };
  }

  profile(id: string): SpeakerProfile | undefined {
    return this.brain.get<SpeakerProfile>("speaker", id)?.value;
  }

  rubric(): Rubric {
    return this.brain.get<Rubric>("rubric", "current")?.value ?? RUBRIC_V0;
  }

  private resume(runId: string, event: string, payload: unknown) {
    deliver(this.brain, runId, event, payload);
    const speakerId = runId.split(":")[1]!;
    return runWorkflow(this.brain, runId, (run) => this.onboardingFlow(run, speakerId));
  }

  // ---------- Content department: onboarding (A1) ----------

  private onboarding(speakerId: string, p: Payload<"speaker.onboard">) {
    this.brain.kv.set(`onboard.input:${speakerId}`, p);
    return runWorkflow(this.brain, `onboard:${speakerId}`, (run) => this.onboardingFlow(run, speakerId));
  }

  private async onboardingFlow(run: Run, speakerId: string) {
    const input = this.brain.kv.get(`onboard.input:${speakerId}`) as Payload<"speaker.onboard">;
    const screened = await run.step("screen", () => screen(input.screener));
    if (!screened.pass) return { status: "screened_out", reasons: screened.reasons };

    await run.step("profile", () => {
      this.brain.promote("speaker", speakerId, input.profile, { approver: input.profile.name, role: "speaker" });
      this.sm.create("Speaker", speakerId, speakerId);
      this.sm.transition("Speaker", speakerId, "INTERVIEW_BOOKED");
      this.log.emit({ type: "speaker.onboarded", speaker_id: speakerId, tier: input.profile.tier, baseline_enquiries_6m: input.profile.baseline_enquiries_6m });
      return true;
    });

    const t = run.waitFor<Payload<"interview.transcript">>("interview.transcript");
    await run.step("interviewed", () => {
      this.brain.append("interview.transcript", speakerId, t.transcript);
      this.sm.transition("Speaker", speakerId, "INTERVIEWED");
      return true;
    });

    let transcript: TranscriptSegment[] = t.transcript;
    let draft: { bp: Blueprint; gaps: string[]; questions: string[] } | undefined;
    for (let round = 0; round <= MAX_FOLLOW_UP_ROUNDS; round++) {
      if (round > 0) transcript = [...transcript, ...run.waitFor<Payload<"interview.followup">>(`interview.followup.${round}`).segments];
      draft = await run.step(`blueprint.${round}`, async () => {
        if (round > 0) this.sm.transition("Speaker", speakerId, "INTERVIEWED");
        const ctx = this.ctx(speakerId);
        const bp = await writeBlueprint(ctx, { transcript, existing_assets: t.existing_assets, writing_samples: t.writing_samples, fee_band: input.profile.fee_band, formats: t.formats, blueprint_version: `draft-${round}` });
        const check = await checkAgainstTranscript(ctx, transcript, bp);
        const gaps = coverageGaps(bp);
        const questions = gaps.length || check.unsupported.length ? followUpQuestions(gaps, check, bp) : [];
        this.brain.append("blueprint.draft", speakerId, { round, bp, check, gaps, questions });
        this.sm.transition("Speaker", speakerId, "BLUEPRINT_DRAFT");
        return { bp, gaps, questions };
      });
      if (!draft.questions.length) break;
      // After two follow-up rounds the specialist takes the remaining gaps by hand.
      if (round === MAX_FOLLOW_UP_ROUNDS)
        await run.step("specialist.gaps", () => this.brain.append("specialist.task", speakerId, { what: "Blueprint gaps after 2 follow-up rounds", gaps: draft!.gaps, questions: draft!.questions }));
    }

    const c = run.waitFor<Payload<"blueprint.confirm">>("blueprint.confirmation");
    return run.step("approve", () => {
      if (c.approval.role !== "speaker") throw new Error("the speaker, not the team, confirms their own Blueprint");
      const confirmed = applyConfirmation(draft!.bp, c.decisions);
      // The speaker's own edits to their boundaries replace whatever the interview recorded.
      const bp = c.boundaries ? { ...confirmed, boundaries: c.boundaries } : confirmed;
      const rec = this.brain.promote("blueprint", speakerId, { ...bp, blueprint_version: `v${(this.brain.get("blueprint", speakerId)?.version ?? 0) + 1}` }, c.approval);
      this.sm.transition("Speaker", speakerId, "BLUEPRINT_APPROVED", c.approval);
      this.sm.transition("Speaker", speakerId, "ACTIVE");
      const html = renderBlueprintDocument(this.profile(speakerId)!.name, rec.value, rec.version, rec.approved_at);
      this.brain.append("blueprint.document", speakerId, { version: rec.version, html });
      return { status: "active", blueprint_version: rec.version };
    });
  }

  // ---------- Content department: weekly cycle (A2 + B2) ----------

  private async weeklyContent(run: Run, speakerId: string, week: string) {
    const bpRec = this.brain.get<Blueprint>("blueprint", speakerId);
    if (!bpRec || this.sm.get("Speaker", speakerId).state !== "ACTIVE") return { status: "skipped", reason: "speaker not ACTIVE with an approved Blueprint" };
    const bp = bpRec.value;
    const profile = this.profile(speakerId)!;
    const published = this.brain.read<PastPost & { text: string }>("content.published", speakerId).map((e) => e.payload);
    const voiceSamples = [...profile.voice_samples, ...this.brain.canonOf<string>("voice_sample").filter((r) => r.key.startsWith(`${speakerId}:`)).map((r) => r.value)];
    const slots = await run.step("plan", () => planWeek(bp, published));
    const rubric = this.rubric();

    // Fan out: the three drafts don't depend on each other. Each has its own fresh-context scorer.
    const results = await Promise.all(
      slots.map((slot, i) =>
        run.step(`loop.${i}`, async () => {
          const itemId = `${speakerId}:${week}:${i + 1}`;
          this.sm.create("ContentItem", itemId, speakerId);
          try {
            const res = await runContentLoop(this.ctx(speakerId), this.log, { item_id: itemId, speaker_id: speakerId, blueprint: bp, slot, rubric, recent_posts: published.map((p) => p.text), voice_samples: voiceSamples });
            res.passes.forEach((p, n) => {
              this.sm.transition("ContentItem", itemId, "DRAFTED");
              this.sm.transition("ContentItem", itemId, "SCORED");
              if (n < res.passes.length - 1) this.sm.transition("ContentItem", itemId, "REVISE");
            });
            this.brain.append("content.drafts", speakerId, res);
            const last = res.passes[res.passes.length - 1]!;
            this.sm.transition("ContentItem", itemId, res.status === "pass" ? "SPECIALIST_REVIEW" : "ESCALATED");
            this.review.enqueue({
              id: itemId,
              entity: "ContentItem",
              speaker_id: speakerId,
              content: res.final.text,
              label: rubric.label,
              context: { slot, claim_ids: res.final.claim_ids, reasons: last.score?.reasons, blocked_reason: last.blocked_reason, versions: res.passes.length },
            });
            return { item_id: itemId, status: res.status, passes: res.passes.length };
          } catch (e) {
            if (!(e instanceof BudgetExceeded || e instanceof ContractError)) throw e;
            this.sm.transition("ContentItem", itemId, "ESCALATED");
            this.log.emit({ type: "item.escalated", item_id: itemId, reason: e.message });
            return { item_id: itemId, status: "escalated" as const, passes: 0, reason: e.message };
          }
        }),
      ),
    );
    return { status: "queued", items: results };
  }

  private async publish(itemId: string, token: ApprovalToken) {
    return runWorkflow(this.brain, `publish:${itemId}`, async (run) => {
      const item = this.review.item(itemId);
      const postId = await run.step("publish", () =>
        this.gate.execute(this.deps.adapters.linkedin, { item_id: itemId, content: item.content, token_id: token.id, idempotency_key: `publish:${itemId}` }),
      );
      return run.step("record", () => {
        this.sm.transition("ContentItem", itemId, "PUBLISHED");
        const slot = item.context.slot as PastPost;
        this.brain.append("content.published", item.speaker_id, { angle_id: slot.angle_id, format: slot.format, text: item.content, post_id: postId });
        // The speaker's final text becomes a voice sample: the voice guide learns from real edits.
        this.brain.promote("voice_sample", `${item.speaker_id}:${itemId}`, item.content, { approver: token.approver, role: token.role });
        return { status: "published", post_id: postId };
      });
    });
  }

  // ---------- Pipeline department: enquiries (P1) ----------

  private async enquiry(run: Run, p: Payload<"enquiry.capture">) {
    const profile = this.profile(p.speaker_id);
    const bp = this.brain.get<Blueprint>("blueprint", p.speaker_id)?.value;
    if (!profile || !bp) throw new Error(`speaker ${p.speaker_id} has no approved Blueprint`);
    const id = p.enquiry_id;
    const res = await run.step("capture", async () => {
      this.brain.append("enquiry.raw", p.speaker_id, p.raw);
      this.sm.create("Enquiry", id, p.speaker_id);
      this.log.emit({ type: "enquiry.created", enquiry_id: id, speaker_id: p.speaker_id, channel: p.raw.channel, completeness: p.raw.completeness, latency_ms: this.brain.clock().getTime() - new Date(p.raw.received_at).getTime() });
      const consent = this.brain.get<string>("policy", "referral_consent")?.value;
      return captureEnquiry(this.ctx(p.speaker_id), p.raw, { name: profile.name, blueprint: bp, consent_line: consent?.replace("[Speaker]", profile.name) });
    });
    if (res.stage === "NEW") return res;
    await run.step("stage", () => {
      const qualified = isQualified(res.extraction!, false);
      for (const to of ["EXTRACTED", "QUALIFIED", "REPLY_DRAFTED"]) {
        const from = this.sm.get("Enquiry", id).state;
        this.sm.transition("Enquiry", id, to);
        this.log.emit({ type: "enquiry.stage_changed", enquiry_id: id, from, to, qualified, source_answer: null });
      }
      this.brain.append("enquiry.extracted", p.speaker_id, { enquiry_id: id, ...res });
      this.review.enqueue({ id, entity: "Enquiry", speaker_id: p.speaker_id, content: res.reply_draft!, blocked: res.blocked, context: { extraction: res.extraction, warnings: res.warnings, next_action: res.next_action } });
      return true;
    });
    return res;
  }

  private async sendReply(enquiryId: string, token: ApprovalToken) {
    return runWorkflow(this.brain, `send:${enquiryId}`, async (run) => {
      const item = this.review.item(enquiryId);
      await run.step("send", () => this.gate.execute(this.deps.adapters.email, { item_id: enquiryId, content: item.content, token_id: token.id, idempotency_key: `send:${enquiryId}` }));
      return run.step("record", () => {
        this.sm.transition("Enquiry", enquiryId, "SENT");
        this.log.emit({ type: "enquiry.stage_changed", enquiry_id: enquiryId, from: "APPROVED", to: "SENT", qualified: false, source_answer: null });
        return { status: "sent" };
      });
    });
  }

  // ---------- Bookability department: radar (B1) ----------

  private async radar(run: Run, p: Payload<"radar.weekly">) {
    if (!this.deps.fetcher) throw new Error("radar needs a fetcher (Firecrawl, Apify…)");
    const speakers = this.sm
      .all()
      .filter((s) => s.entity === "Speaker" && s.state === "ACTIVE")
      .map((s) => ({ speaker_id: s.id, blueprint: this.brain.get<Blueprint>("blueprint", s.id)!.value }));
    const out = await run.step("radar", () => runRadar(this.ctx(null), this.brain, { sources: p.sources, fetcher: this.deps.fetcher!, speakers, week: p.week }));
    return Object.fromEntries([...out.entries()].map(([k, v]) => [k, v.length]));
  }

  // ---------- Pipeline department: asset packs (P2) ----------

  private assetPack(speakerId: string) {
    const history = this.brain.history<Blueprint>("blueprint", speakerId);
    const cur = history.at(-1);
    const profile = this.profile(speakerId);
    if (!cur || !profile) throw new Error(`no approved Blueprint for ${speakerId}`);
    const version = `bp${cur.version}`;
    const files = renderPack(profile.name, cur.value, version, profile.clips);
    const changes = changesSince(history.at(-2)?.value, cur.value);
    const perBureau = profile.bureau_ids
      .map((id) => this.brain.get<BureauProfile>("bureau", id)?.value)
      .filter((b): b is BureauProfile => Boolean(b))
      .map((b) => ({ bureau: b.id, contact: b.contact, cover_draft: coverNote(b, profile.name, changes, version), files: packFor(b, files).map((f) => f.name) }));
    const packId = `${speakerId}:${version}`;
    this.sm.create("AssetPack", packId, speakerId);
    this.brain.append("p2.pack", speakerId, { pack_version: version, files, changes_since_last: changes, per_bureau: perBureau });
    this.review.enqueue({ id: packId, entity: "AssetPack", speaker_id: speakerId, content: perBureau.map((b) => b.cover_draft).join("\n\n---\n\n"), context: { changes, per_bureau: perBureau } });
    return { pack_version: version, files: files.map((f) => f.name), changes_since_last: changes, per_bureau: perBureau };
  }
}

export type { Approval };
