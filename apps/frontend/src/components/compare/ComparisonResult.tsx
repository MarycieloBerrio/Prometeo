import type { CompareResponse, Trial } from "@prometeo/contracts";

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
    note: "Read the warnings before using the difference.",
  },
  not_comparable: {
    tone: "danger",
    title: "Not comparable",
    note: "A controlled variable differs, so the numbers are withheld.",
  },
};

export function ComparisonResult({ result }: { result: CompareResponse }) {
  const [a, b] = result.trials;
  const verdict = VERDICTS[result.level] ?? { tone: "warn" as const, title: humanize(result.level), note: "" };

  return (
    <>
      <Callout tone={verdict.tone} title={verdict.title}>
        {verdict.note}
      </Callout>

      <Section title="Conditions side by side" hint="Verdict per variable comes from the Physics Validator">
        <ConditionDiff a={a} b={b} result={result} />
      </Section>

      <Section title="Measured difference" hint="B − A">
        {result.withheld_reason ? (
          <Callout tone="neutral" icon="ban" title="Numbers withheld">
            {result.withheld_reason}
          </Callout>
        ) : result.deltas.length === 0 ? (
          <Callout tone="neutral" title="No shared measurement">
            These trials have no recorded result in common. No difference can be shown.
          </Callout>
        ) : (
          <div className="grid">
            {result.deltas.map((d) => (
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
              </div>
            ))}
          </div>
        )}
      </Section>
    </>
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
