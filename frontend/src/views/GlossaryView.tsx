import { HELP_ENTRIES, type HelpGroup } from '../content/helpCopy';
import { InfoTip } from '../components/InfoTip';

const GROUP_LABELS: Record<HelpGroup, string> = {
  trade: 'Trade terms',
  app: 'App terms',
  ask: 'Ask & research',
};

export function GlossaryView() {
  const groups: HelpGroup[] = ['trade', 'app', 'ask'];

  return (
    <section className="panel-view">
      <p className="hint">
        Plain-English definitions for every ⓘ tip in the app. Same text as the hover help.
      </p>
      {groups.map((group) => (
        <div key={group} className="glossary-group">
          <h3>{GROUP_LABELS[group]}</h3>
          {HELP_ENTRIES.filter((e) => e.group === group).map((entry) => (
            <div key={entry.key} className="glossary-item">
              <strong>
                {entry.title} <InfoTip id={entry.key} />
              </strong>
              <p className="muted">{entry.body}</p>
            </div>
          ))}
        </div>
      ))}
    </section>
  );
}
