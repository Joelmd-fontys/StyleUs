import Card from '../components/Card';

const Settings = () => {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-neutral-900">Settings</h1>
      <Card title="Profile preferences" description="All settings are stored locally for now.">
        <ul className="list-disc space-y-2 pl-5 text-sm text-neutral-600">
          <li>Switch themes and notification preferences (coming soon).</li>
          <li>Link external wardrobes to sync with StyleUs.</li>
          <li>Export your catalog for safe keeping.</li>
        </ul>
      </Card>
    </div>
  );
};

export default Settings;
