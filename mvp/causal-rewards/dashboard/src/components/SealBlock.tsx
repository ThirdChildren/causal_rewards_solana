/**
 * The seal block — the dashboard's signature element and its whole argument in one picture.
 *
 * Freeze-before-reveal (invariant 1) is the protocol's central claim, and it is normally
 * invisible: two hex strings in a JSON file. Here each 32-byte commitment is contact-printed
 * as 32 cells whose height is the byte value, so a commitment has a *shape* you can compare
 * at a glance. The manifest strip is printed in ink because the manifest is public. The
 * assignment-seed strip stays LATENT — washed out and slightly blurred — for exactly as long
 * as the seed is unrevealed on-chain, then develops into ink when the reveal lands.
 *
 * The strip is decoration only in the sense that it renders committed bytes and nothing else.
 * It invents no value: if a commitment is absent, no strip is drawn.
 */
import type { SealState } from "../protocol/stateMachine";
import { Hash } from "./primitives";

function bytesOf(hex: string): number[] {
  const clean = hex.replace(/^0x/, "");
  const out: number[] = [];
  for (let i = 0; i + 1 < clean.length; i += 2) {
    const v = Number.parseInt(clean.slice(i, i + 2), 16);
    out.push(Number.isNaN(v) ? 0 : v);
  }
  return out;
}

export function CommitmentStrip({ hex, latent }: { hex: string; latent: boolean }) {
  const bytes = bytesOf(hex);
  if (bytes.length === 0) return null;
  return (
    <div className="strip" data-latent={latent ? "true" : "false"} aria-hidden="true">
      {bytes.map((b, i) => (
        <span
          key={i}
          className="strip__cell"
          style={{ height: `${Math.max(8, Math.round((b / 255) * 100))}%` }}
        />
      ))}
    </div>
  );
}

export interface SealBlockProps {
  manifestHashHex: string;
  seedCommitmentHex: string | null;
  revealedSeedHex: string | null;
  seal: SealState;
}

export function SealBlock({
  manifestHashHex,
  seedCommitmentHex,
  revealedSeedHex,
  seal,
}: SealBlockProps) {
  const seedRevealed = seal.seedRevealed;
  return (
    <div className="seal">
      <div className="seal__row">
        <div className="seal__label">
          <span className="name">frozen manifest</span>
          <span className="seal__state" data-tone={seal.manifestSealed ? "wax" : "latent"}>
            {seal.manifestSealed ? "Sealed" : "Not frozen"}
          </span>
        </div>
        <div>
          <CommitmentStrip hex={manifestHashHex} latent={!seal.manifestSealed} />
          <p className="seal__hash">
            <Hash value={manifestHashHex} chars={64} />
          </p>
        </div>
      </div>

      <div className="seal__row">
        <div className="seal__label">
          <span className="name">assignment seed</span>
          <span className="seal__state" data-tone={seedRevealed ? "develop" : "latent"}>
            {seedRevealed ? "Revealed" : "Still sealed"}
          </span>
        </div>
        <div>
          {seedCommitmentHex ? (
            <>
              <CommitmentStrip
                hex={revealedSeedHex ?? seedCommitmentHex}
                latent={!seedRevealed}
              />
              <p className="seal__hash">
                commitment <Hash value={seedCommitmentHex} chars={64} />
                {revealedSeedHex ? (
                  <>
                    <br />
                    revealed seed <Hash value={revealedSeedHex} chars={64} />
                  </>
                ) : null}
              </p>
            </>
          ) : (
            <p className="seal__hash">
              This source publishes no seed commitment for the experiment.
            </p>
          )}
        </div>
      </div>

      <p className="seal__note">
        {seal.summary} The manifest hash was written on-chain before the seed was revealed, so
        anyone can check that the design, outcome and analysis plan could not be chosen after
        seeing the assignment. <strong>Check it yourself</strong> — the verifier re-derives every
        cohort arm from the revealed seed with <code>crp-verify --seed</code>.
      </p>
    </div>
  );
}
