import type { CompareResponse, Trial } from "@prometeo/contracts";

import { SourceLine } from "@/components/trials/SourceLine";
import { DataQualityBadge } from "@/components/ui/Badges";
import { Callout } from "@/components/ui/Callout";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Section } from "@/components/ui/PageHeader";
import { formatQuantity, humanize, VARIABLES } from "@/domain/format";

const VERDICTS: Record<string, { tone: "ok" | "warn" | "danger"; title: string; note: string }> = {
  directly_comparable: {
    tone: "ok",
    title: "Directly comparable",
    note: "Everything except the varied variable matches.",
  },
  partially_comparable: {
    tone: "warn",
    title: "Partially comparable",
    note: "Controlled conditions differ or remain uncertain. Read the recorded values separately.",
  },
  not_comparable: {
    tone: "danger",
    title: "Not comparable",
    note: "A controlled condition conflicts. Read the records separately; no comparative delta is displayed.",
  },
};

export function ComparisonResult({ result, metric }: { result: CompareResponse; metric: string }) {
  const [a, b] = result.trials;
  const verdict = VERDICTS[result.level] ?? { tone: "warn" as const, title: humanize(result.level), note: "" };
  const direct = result.level === "directly_comparable" && !result.withheld_reason;
  const deltas = direct ? result.deltas.filter((delta) => delta.metric === metric) : [];

  return (
    <>
      <div className={`verdict-panel verdict-${verdict.tone}`} role="status">
        <span className="verdict-symbol"><Icon name={verdict.tone === "ok" ? "check" : verdict.tone === "danger" ? "ban" : "alert"} size={30} /></span>
        <div className="verdict-message"><p className="eyebrow">PHYSICS VALIDATOR / COMPARABILITY</p><h2>{verdict.title}</h2><p>{verdict.note}</p></div>
        <div className="verdict-meta"><span>{result.issues.length} {result.issues.length === 1 ? "issue" : "issues"}</span><strong>{direct ? "DIRECT" : result.level === "not_comparable" ? "BLOCKED" : "CONDITIONAL"}</strong></div>
      </div>

      <div className="control-intent">
        <div><span className="eyebrow">DECLARED AS VARIED</span><strong>{result.varied.length ? result.varied.map(humanize).join(" · ") : "None declared"}</strong></div>
        <div><span className="eyebrow">CHECKED AS CONTROLLED</span><span>{VARIABLES.filter((variable) => !result.varied.includes(variable.key)).map((variable) => variable.label).join(" · ") || "None"}</span></div>
      </div>

      <Section title="Trial records" hint="Identity and provenance of both experimental setups">
        <div className="grid">
          {[a, b].map((trial, index) => (
            <article className="card trial-summary comparison-record" key={trial.id}>
              <div className="comparison-record-heading"><span className="slot-letter">{index === 0 ? "A" : "B"}</span><span className="eyebrow">EXPERIMENT RECORD</span><strong className="mono">{trial.id}</strong></div>
              <h3>{trial.material}</h3>
              <span className="small muted">{trial.investigation}{trial.composition ? ` · ${trial.composition}` : ""} · {trial.geometry}</span>
              <span className="small muted">Sample {trial.sample_id ?? "not recorded"} · {trial.phenomena.length ? trial.phenomena.map(humanize).join(", ") : "phenomena not recorded"}</span>
              <SourceLine provenance={trial.provenance} />
            </article>
          ))}
        </div>
      </Section>

      {result.issues.length > 0 && (
        <Section title="Physics checks" hint="Messages returned by the Evidence Engine">
          <ul className="list">
            {result.issues.map((issue, index) => (
              <li key={`${issue.variable}-${index}`} className={`issue-row issue-${issue.severity}`}>
                <span className="issue-severity"><Icon name={issue.severity === "blocking" ? "ban" : issue.severity === "warning" ? "alert" : "info"} size={16} />{issue.severity}</span>
                <strong>{humanize(issue.variable)}</strong>
                <span className="small">{issue.message}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Conditions side by side" hint="Verdict per variable comes from the Physics Validator">
        <ConditionDiff a={a} b={b} result={result} />
      </Section>

      <Section title={direct ? "Recorded result and difference" : "Recorded results, separately"} hint={humanize(metric)}>
        {!direct && result.withheld_reason && (
          <Callout tone="neutral" icon="ban" title="Delta withheld">
            {result.withheld_reason}
          </Callout>
        )}
        {!direct ? (
          <div className="grid">
            {[a, b].map((trial, index) => {
              const measurement = trial.results.find((item) => item.name === metric);
              return (
                <div key={trial.id} className="card separate-result">
                  <span className="slot-letter">{index === 0 ? "A" : "B"} · {trial.id}</span>
                  {measurement ? (
                    <>
                      <strong className="big">{formatQuantity(measurement.value)}</strong>
                      <DataQualityBadge quality={measurement.quality} />
                      <SourceLine provenance={measurement.provenance} />
                    </>
                  ) : <span className="muted">Not recorded</span>}
                </div>
              );
            })}
          </div>
        ) : deltas.length === 0 ? (
          <Callout tone="neutral" title="No shared measurement">
            These trials have no recorded result in common. No difference can be shown.
          </Callout>
        ) : (
          <div className="grid">
            {deltas.map((d) => (
              <div key={d.metric} className="card delta">
                <span className="small muted">{humanize(d.metric)}</span>
                <div className="delta-values">
                  <span>
                    <span className="slot-letter">A</span>
                    <strong>{formatQuantity(d.a.value)}</strong>
                    <DataQualityBadge quality={d.a.quality} />
                  </span>
                  <Icon name="arrowRight" size={16} />
                  <span>
                    <span className="slot-letter">B</span>
                    <strong>{formatQuantity(d.b.value)}</strong>
                    <DataQualityBadge quality={d.b.quality} />
                  </span>
                </div>
                <p className="delta-diff">
                  {d.difference.value > 0 ? "+" : ""}
                  {formatQuantity(d.difference)}
                </p>
                <RecordedBars a={d.a.value.value} b={d.b.value.value} unit={d.a.value.unit} sameUnit={d.a.value.unit === d.b.value.unit} />
                <SourceLine provenance={d.a.provenance} />
                <SourceLine provenance={d.b.provenance} />
              </div>
            ))}
          </div>
        )}
      </Section>
    </>
  );
}

function RecordedBars({ a, b, unit, sameUnit }: { a: number; b: number; unit: string; sameUnit: boolean }) {
  if (!sameUnit || !Number.isFinite(a) || !Number.isFinite(b) || a < 0 || b < 0) return null;
  const maximum = Math.max(a, b);
  return (
    <figure className="recorded-bars" aria-label={`Recorded values: A ${a} ${unit}; B ${b} ${unit}`}>
      <div className="bar-row"><span>A</span><i style={{ width: `${maximum ? a / maximum * 100 : 0}%` }} /><span>{a} {unit}</span></div>
      <div className="bar-row"><span>B</span><i style={{ width: `${maximum ? b / maximum * 100 : 0}%` }} /><span>{b} {unit}</span></div>
      <figcaption className="small muted">Recorded measurements only. Bars share a scale; no values are interpolated.</figcaption>
    </figure>
  );
}

const STATUS: Record<string, { icon: IconName; tone: string; label: string }> = {
  blocking: { icon: "ban", tone: "danger", label: "Blocks comparison" },
  warning: { icon: "alert", tone: "warn", label: "Warning" },
  info: { icon: "info", tone: "neutral", label: "Note" },
  varied: { icon: "compare", tone: "info", label: "Varied on purpose" },
  ok: { icon: "check", tone: "ok", label: "No issue reported" },
};

function valueOf(trial: Trial, key: string): string | null {
  switch (key) {
    case "fuel":
      return trial.material;
    case "geometry":
      return humanize(trial.geometry);
    case "thickness":
      return formatQuantity(trial.thickness);
    case "thermal_regime":
      return trial.thermal_regime === "unknown" ? null : humanize(trial.thermal_regime);
    case "oxygen":
      return formatQuantity(trial.oxygen);
    case "flow_speed":
      return formatQuantity(trial.flow_speed);
    case "flow_direction":
      return trial.flow_direction === "unknown" ? null : humanize(trial.flow_direction);
    case "pressure":
      return formatQuantity(trial.pressure);
    default:
      return null;
  }
}

function ConditionDiff({ a, b, result }: { a: Trial; b: Trial; result: CompareResponse }) {
  return (
    <div className="diff" role="table">
      <div className="diff-row diff-head" role="row">
        <span role="columnheader">Variable</span>
        <span role="columnheader" className="mono">
          A · {a.id}
        </span>
        <span role="columnheader" className="mono">
          B · {b.id}
        </span>
        <span role="columnheader">Check</span>
      </div>
      {VARIABLES.map((v) => {
        const issues = result.issues.filter((i) => i.variable === v.key);
        const worst =
          issues.find((i) => i.severity === "blocking") ?? issues.find((i) => i.severity === "warning") ?? issues[0];
        const status = STATUS[worst?.severity ?? (result.varied.includes(v.key) ? "varied" : "ok")] ?? STATUS.ok;
        return (
          <div key={v.key} className="diff-row" role="row">
            <span role="cell" className="diff-var">
              <Icon name={v.icon} size={16} />
              {v.label}
            </span>
            <Cell value={valueOf(a, v.key)} />
            <Cell value={valueOf(b, v.key)} />
            <span role="cell" className={`diff-status tone-${status.tone}`}>
              <Icon name={status.icon} size={16} />
              <span className="small">{worst?.message ?? status.label}</span>
            </span>
          </div>
        );
      })}
    </div>
  );
}

function Cell({ value }: { value: string | null }) {
  return (
    <span role="cell" className={value ? undefined : "muted"}>
      {value ?? "Not recorded"}
    </span>
  );
}
