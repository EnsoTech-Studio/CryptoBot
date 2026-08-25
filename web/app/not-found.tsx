import Link from "next/link";

export default function NotFound() {
  return (
    <div className="notfound">
      <p className="eyebrow">404</p>
      <h2>That workspace route does not exist</h2>
      <p className="surface-subtitle">
        The page you asked for is not part of the research cockpit. Head back to the dashboard and pick a section from the rail.
      </p>
      <Link className="primary-action notfound-action" href="/">Back to dashboard</Link>
    </div>
  );
}
