import { useState } from "react";
import { Button, Dialog } from "../components/ui";
import { useStudio } from "./store";

export function NewThreadDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const { createThread } = useStudio();
  const [form, setForm] = useState({ company: "", role: "", recipient: "" });

  const submit = () => {
    const company = form.company.trim();
    if (!company) return;
    onCreated(createThread({ company, role: form.role.trim() || undefined, recipient: form.recipient.trim() || undefined }));
  };

  const field = (label: string, key: keyof typeof form, placeholder: string, required = false) => (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-xs font-medium text-ink-2">
        {label}
        {!required && " (optional)"}
      </span>
      <input
        required={required}
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        placeholder={placeholder}
        className="h-9 px-3"
      />
    </label>
  );

  return (
    <Dialog title="New writing thread" onClose={onClose}>
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        {field("Company", "company", "e.g. Northstar Bio", true)}
        {field("Role", "role", "e.g. Product Design Lead")}
        {field("Who are you writing to?", "recipient", "e.g. Jordan Lee, hiring manager")}
        <p className="text-xs text-ink-2">One thread per company keeps every draft and what you sent together, so later drafts can build on it.</p>
        <div className="mt-1 flex justify-end gap-2">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" disabled={!form.company.trim()}>
            Create thread
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
