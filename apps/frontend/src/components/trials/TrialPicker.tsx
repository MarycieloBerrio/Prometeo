"use client";

import Link from "next/link";
import { useState } from "react";

import type { Trial } from "@prometeo/contracts";

import { TrialCard } from "@/components/trials/TrialCard";
import { Icon } from "@/components/ui/Icon";

const MAX = 2;

/** Trial grid where the user picks two trials and moves on to the Comparison Lab. */
export function TrialPicker({ trials }: { trials: Trial[] }) {
  const [picked, setPicked] = useState<string[]>([]);

  function toggle(id: string) {
    setPicked((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id].slice(-MAX),
    );
  }

  const ready = picked.length === MAX;
  const compareHref = `/compare?a=${encodeURIComponent(picked[0] ?? "")}&b=${encodeURIComponent(picked[1] ?? "")}`;

  return (
    <>
      <div className="grid">
        {trials.map((t) => {
          const on = picked.includes(t.id);
          return (
            <TrialCard
              key={t.id}
              trial={t}
              selected={on}
              action={
                <button
                  type="button"
                  className={`btn btn-small${on ? " btn-on" : ""}`}
                  aria-pressed={on}
                  onClick={() => toggle(t.id)}
                >
                  <Icon name={on ? "check" : "plus"} size={14} />
                  {on ? "Picked" : "Compare"}
                </button>
              }
            />
          );
        })}
      </div>

      <div className="tray" role="status">
        <div className="tray-slots">
          {[0, 1].map((i) => (
            <span key={i} className={`slot${picked[i] ? " slot-filled" : ""}`}>
              <span className="slot-letter">{i === 0 ? "A" : "B"}</span>
              <span className="mono small">{picked[i] ?? "pick a trial"}</span>
            </span>
          ))}
        </div>
        {ready ? (
          <Link href={compareHref} className="btn btn-primary">
            Compare
            <Icon name="arrowRight" size={16} />
          </Link>
        ) : (
          <span className="btn btn-primary btn-disabled" aria-disabled>
            Pick {MAX - picked.length} more
          </span>
        )}
      </div>
    </>
  );
}
