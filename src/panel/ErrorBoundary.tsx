import { Component, type ReactNode } from "react";

/** Keeps a render error from leaving an invisible (fully transparent) panel. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="card crash">
        <h3>Something went wrong</h3>
        <p className="crash-message">{this.state.error.message}</p>
        <pre>{String(this.state.error.stack ?? this.state.error)}</pre>
        <button onClick={() => this.setState({ error: null })}>Try again</button>
      </div>
    );
  }
}
