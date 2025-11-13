import Card from '../components/Card';
import { useStatsPreference } from '../hooks/useStatsPreference';
import { cn } from '../lib/utils';

const Settings = () => {
  const [statsForNerds, setStatsForNerds] = useStatsPreference();

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-neutral-900">Settings</h1>
      <div className="space-y-4">
        <Card>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-neutral-900">Stats for nerds</span>
            <button
              type="button"
              role="switch"
              aria-checked={statsForNerds}
              onClick={() => setStatsForNerds((prev) => !prev)}
              className={cn(
                'relative inline-flex h-6 w-11 items-center rounded-full transition',
                statsForNerds ? 'bg-accent-600' : 'bg-neutral-300'
              )}
            >
              <span
                className={cn(
                  'inline-block h-4 w-4 rounded-full bg-white transition',
                  statsForNerds ? 'translate-x-5' : 'translate-x-1'
                )}
              />
            </button>
          </div>
        </Card>

        <Card title="Profile preferences" description="All settings are stored locally for now.">
          <ul className="list-disc space-y-2 pl-5 text-sm text-neutral-600">
            <li>Switch themes and notification preferences (coming soon).</li>
            <li>Link external wardrobes to sync with StyleUs.</li>
            <li>Export your catalog for safe keeping.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
};

export default Settings;
